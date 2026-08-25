from __future__ import annotations

import json
import os
import re
import math
import time
import urllib.request
import logging
from dataclasses import dataclass, field
from typing import Any

import requests

from biome_rag.config import get_runtime_settings
from biome_rag.retrieval.models import RankedChunk

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    chunk_index: int
    text: str
    verified: bool = False


@dataclass
class ConfidenceScores:
    retrieval_confidence: float
    citation_coverage: float
    completeness: float
    composite: float


@dataclass
class AnswerResponse:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    confidence: ConfidenceScores | None = None
    retrieved_chunks: list[RankedChunk] = field(default_factory=list)


def _build_context_prompt(chunks: list[RankedChunk]) -> str:
    """Format retrieved chunks as numbered context blocks for the LLM prompt."""
    lines: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        source_label = chunk.source or "unknown"
        heading = f" — {chunk.section_heading}" if chunk.section_heading else ""
        lines.append(f"[{idx}] (Source: {source_label}{heading})\n{chunk.text.strip()}")
    return "\n\n".join(lines)


def _parse_citations(answer_text: str, context_chunks: list[RankedChunk]) -> list[Citation]:
    """Extract [n] citation markers from answer text and map to context chunks."""
    cited_indices: list[int] = []
    seen: set[int] = set()
    for match in re.finditer(r"\[(\d+)\]", answer_text):
        n = int(match.group(1))
        if n not in seen and 1 <= n <= len(context_chunks):
            cited_indices.append(n)
            seen.add(n)

    citations: list[Citation] = []
    for n in cited_indices:
        chunk = context_chunks[n - 1]
        citations.append(Citation(chunk_index=n - 1, text=chunk.text, verified=False))

    # If the LLM produced no citations but context exists, attach the top chunk as implicit
    if not citations and context_chunks:
        citations.append(Citation(chunk_index=0, text=context_chunks[0].text, verified=False))

    return citations


class AnswerBuilder:
    def __init__(self, confidence_threshold: float | None = None):
        self.settings = get_runtime_settings()
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else self.settings.insufficient_confidence_threshold
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def answer(self, question: str, chunks: list[RankedChunk]) -> AnswerResponse:
        logger.info(
            "Answering question: '%s' with %d retrieved chunks. Provider: %s",
            question,
            len(chunks),
            self.settings.llm_provider,
        )

        if not chunks:
            logger.warning("No retrieval chunks for question: '%s'", question)
            return AnswerResponse(
                answer="I don't know. No supporting context was found in the indexed documents.",
                citations=[],
                confidence=ConfidenceScores(0.0, 0.0, 0.0, 0.0),
                retrieved_chunks=[],
            )

        # --- Retrieval confidence from best rerank score ---
        max_rerank = max(chunk.rerank_score for chunk in chunks)
        try:
            retrieval_confidence = 1.0 / (1.0 + math.exp(-max_rerank))
        except OverflowError:
            retrieval_confidence = 1.0 if max_rerank > 0 else 0.0

        # --- Early exit if below threshold ---
        if retrieval_confidence < self.confidence_threshold:
            logger.warning(
                "Retrieval confidence %.4f below threshold %.4f — returning insufficient-context response.",
                retrieval_confidence,
                self.confidence_threshold,
            )
            doc_suggestions = list(
                {chunk.source for chunk in chunks if chunk.source}
            )[:3]
            suggestion_text = ""
            if doc_suggestions:
                suggestion_text = (
                    " You might find relevant information in: "
                    + ", ".join(doc_suggestions)
                    + "."
                )
            low_citations = [
                Citation(chunk_index=idx, text=chunk.text, verified=False)
                for idx, chunk in enumerate(chunks)
            ]
            return AnswerResponse(
                answer=(
                    "I don't know. The retrieved context was insufficient to answer this confidently."
                    + suggestion_text
                ),
                citations=low_citations,
                confidence=ConfidenceScores(retrieval_confidence, 0.0, 0.0, retrieval_confidence * 0.5),
                retrieved_chunks=chunks,
            )

        # --- Build context window (token-budget aware) ---
        context_chunks = self._build_context_window(chunks)

        # --- Generate answer ---
        answer_text = self._generate(question, context_chunks)

        # --- Parse [n] citations from answer text ---
        raw_citations = _parse_citations(answer_text, context_chunks)

        # --- Verify citations ---
        verified_citations = [
            Citation(
                chunk_index=c.chunk_index,
                text=c.text,
                verified=self._verify_citation(question, c.text),
            )
            for c in raw_citations
        ]

        # --- Compute confidence ---
        verified_count = sum(1 for c in verified_citations if c.verified)
        citation_coverage = verified_count / len(verified_citations) if verified_citations else 0.0
        completeness = self._score_completeness(question, answer_text)
        composite = (retrieval_confidence * 0.5) + (citation_coverage * 0.3) + (completeness * 0.2)

        logger.info(
            "Confidence: composite=%.4f (retrieval=%.4f, citations=%.4f, completeness=%.4f)",
            composite, retrieval_confidence, citation_coverage, completeness,
        )

        return AnswerResponse(
            answer=answer_text,
            citations=verified_citations,
            confidence=ConfidenceScores(retrieval_confidence, citation_coverage, completeness, composite),
            retrieved_chunks=chunks,
        )

    # ------------------------------------------------------------------
    # Context window construction
    # ------------------------------------------------------------------

    def _count_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.3)

    def _build_context_window(self, chunks: list[RankedChunk]) -> list[RankedChunk]:
        """Select top chunks respecting MAX_CONTEXT_CHUNKS and MAX_CONTEXT_TOKENS."""
        context_chunks: list[RankedChunk] = []
        accumulated_tokens = 0
        for chunk in chunks[: self.settings.max_context_chunks]:
            chunk_tokens = self._count_tokens(chunk.text)
            if accumulated_tokens + chunk_tokens <= self.settings.max_context_tokens:
                context_chunks.append(chunk)
                accumulated_tokens += chunk_tokens
            else:
                remaining = self.settings.max_context_tokens - accumulated_tokens
                if remaining > 20:
                    allowed = int(remaining / 1.3)
                    truncated = " ".join(chunk.text.split()[:allowed]) + "..."
                    context_chunks.append(
                        RankedChunk(
                            text=truncated,
                            source=chunk.source,
                            section_heading=chunk.section_heading,
                            page_number=chunk.page_number,
                            dense_score=chunk.dense_score,
                            sparse_score=chunk.sparse_score,
                            fused_score=chunk.fused_score,
                            rerank_score=chunk.rerank_score,
                        )
                    )
                break
        return context_chunks

    # ------------------------------------------------------------------
    # Generation dispatch
    # ------------------------------------------------------------------

    def _generate(self, question: str, context_chunks: list[RankedChunk]) -> str:
        context = _build_context_prompt(context_chunks)
        provider = self.settings.llm_provider
        if provider == "ollama":
            return self._generate_with_ollama(question, context, context_chunks)
        elif provider in {"openai", "azure"}:
            return self._generate_with_openai(question, context)
        elif provider == "anthropic":
            return self._generate_with_anthropic(question, context)
        else:
            return self._fallback_generation(question, context_chunks)

    # ------------------------------------------------------------------
    # System prompt shared across all providers
    # ------------------------------------------------------------------

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are a precise, factual question-answering assistant. "
            "Your task is to answer the user's question using ONLY the numbered context blocks provided below.\n\n"
            "Rules you must follow:\n"
            "1. Cite sources inline using the block number in square brackets, e.g. [1] or [2][3].\n"
            "2. If the context blocks contain the answer, explain it clearly and concisely with citations.\n"
            "3. If the context does NOT contain sufficient information to answer, reply with exactly: "
            "\"I don't know. The provided context does not contain this information.\"\n"
            "4. Never fabricate information. Never use knowledge outside the provided context.\n"
            "5. Multiple citations are allowed for a single claim, e.g. [1][3]."
        )

    @staticmethod
    def _user_prompt(question: str, context: str) -> str:
        return (
            f"Context blocks:\n\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer (with inline [n] citations):"
        )

    # ------------------------------------------------------------------
    # Ollama generator
    # ------------------------------------------------------------------

    def _generate_with_ollama(
        self, question: str, context: str, chunks: list[RankedChunk]
    ) -> str:
        url = f"{self.settings.ollama_base_url}/api/chat"
        payload = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(question, context)},
            ],
            "stream": False,
            "options": {"temperature": 0.0},
        }
        attempts = self.settings.retry_attempts
        timeout = self.settings.ollama_timeout

        for attempt in range(1, attempts + 2):
            try:
                start = time.time()
                resp = requests.post(url, json=payload, timeout=timeout)
                logger.info(
                    "Ollama responded in %.2fs (status=%d)", time.time() - start, resp.status_code
                )
                if resp.ok:
                    content = resp.json().get("message", {}).get("content", "").strip()
                    if content:
                        return content
                    return self._fallback_generation(question, chunks)
                raise requests.exceptions.RequestException(f"HTTP {resp.status_code}")
            except (requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout) as exc:
                logger.warning("Ollama server unreachable (%s). Switching to fast local fallback.", exc)
                return self._fallback_generation(question, chunks)
            except Exception as exc:
                if attempt > attempts:
                    logger.error("All Ollama attempts failed: %s", exc)
                    return self._fallback_generation(question, chunks)
                sleep = 2 ** attempt
                logger.warning("Ollama attempt %d/%d failed: %s. Retrying in %ds.", attempt, attempts + 1, exc, sleep)
                time.sleep(sleep)

        return self._fallback_generation(question, chunks)

    # ------------------------------------------------------------------
    # OpenAI generator (real implementation)
    # ------------------------------------------------------------------

    def _generate_with_openai(self, question: str, context: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set — falling back to local generation.")
            return self._fallback_generation(question, [])

        payload = {
            "model": self.settings.openai_model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(question, context)},
            ],
            "temperature": 0.0,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"].strip()
            logger.info("OpenAI generation complete (%d chars).", len(content))
            return content
        except Exception as exc:
            logger.error("OpenAI generation failed: %s", exc)
            return self._fallback_generation(question, [])

    # ------------------------------------------------------------------
    # Anthropic generator (real implementation)
    # ------------------------------------------------------------------

    def _generate_with_anthropic(self, question: str, context: str) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set — falling back to local generation.")
            return self._fallback_generation(question, [])

        payload = {
            "model": self.settings.anthropic_model,
            "max_tokens": 1024,
            "system": self._system_prompt(),
            "messages": [
                {"role": "user", "content": self._user_prompt(question, context)},
            ],
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = body["content"][0]["text"].strip()
            logger.info("Anthropic generation complete (%d chars).", len(content))
            return content
        except Exception as exc:
            logger.error("Anthropic generation failed: %s", exc)
            return self._fallback_generation(question, [])

    # ------------------------------------------------------------------
    # Local fallback (no LLM dependency)
    # ------------------------------------------------------------------

    def _fallback_generation(self, question: str, chunks: list[RankedChunk]) -> str:
        """Extracts a relevant sentence from chunks without an LLM."""
        if not chunks:
            return "I don't know. No relevant context was available to answer this question."

        stop_words = {
            "what", "when", "where", "which", "who", "whom", "this", "that",
            "have", "has", "does", "the", "and", "but", "for", "with", "from",
        }
        question_terms = [
            t for t in re.findall(r"[a-zA-Z0-9_]+", question.lower())
            if len(t) > 3 and t not in stop_words
        ]

        best_sentence = ""
        best_score = 0
        for chunk in chunks[:3]:
            sentences = re.split(r"(?<=[.!?])\s+", chunk.text)
            for sent in sentences:
                score = sum(1 for t in question_terms if t in sent.lower())
                if score > best_score:
                    best_score = score
                    best_sentence = sent.strip()

        if best_sentence and best_score > 0:
            return f"Based on the retrieved context [1]: {best_sentence}"

        evidence = [
            chunk.text.strip().replace("\n", " ")
            for chunk in chunks[:2]
            if chunk.text.strip()
        ]
        return "Based on the retrieved context [1]: " + " ".join(evidence[:1])

    # ------------------------------------------------------------------
    # Citation verification
    # ------------------------------------------------------------------

    def _verify_citation(self, question: str, citation_text: str) -> bool:
        if not self.settings.citation_verification_enabled:
            return True  # treat all as verified when disabled

        provider = self.settings.llm_provider
        if provider in {"openai", "azure"}:
            return self._llm_judge_openai(question, citation_text)
        elif provider == "anthropic":
            return self._llm_judge_anthropic(question, citation_text)
        return self._rule_based_judge(question, citation_text)

    def _llm_judge_openai(self, question: str, citation_text: str) -> bool:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
        if not api_key:
            return self._rule_based_judge(question, citation_text)
        payload = {
            "model": self.settings.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a citation verifier. Return ONLY 'yes' or 'no'. "
                        "Does the citation text provide direct evidence supporting an answer to the question?"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\nCitation: {citation_text}",
                },
            ],
            "temperature": 0.0,
            "max_tokens": 5,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            answer = body["choices"][0]["message"]["content"].strip().lower()
            return answer.startswith("yes")
        except Exception:
            return self._rule_based_judge(question, citation_text)

    def _llm_judge_anthropic(self, question: str, citation_text: str) -> bool:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return self._rule_based_judge(question, citation_text)
        payload = {
            "model": self.settings.anthropic_model,
            "max_tokens": 5,
            "system": (
                "You are a citation verifier. Return ONLY 'yes' or 'no'. "
                "Does the citation text provide direct evidence supporting an answer to the question?"
            ),
            "messages": [
                {"role": "user", "content": f"Question: {question}\nCitation: {citation_text}"},
            ],
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            answer = body["content"][0]["text"].strip().lower()
            return answer.startswith("yes")
        except Exception:
            return self._rule_based_judge(question, citation_text)

    def _rule_based_judge(self, question: str, citation_text: str) -> bool:
        """Fast keyword-overlap citation verifier (no API required)."""
        question_terms = {
            term for term in re.findall(r"[a-zA-Z0-9_]+", question.lower()) if len(term) > 3
        }
        citation_lower = citation_text.lower()
        if not question_terms:
            return False
        negations = ["not ", "no ", "never ", "doesn't", "don't", "cannot", "can't"]
        if any(neg in citation_lower for neg in negations):
            if any(term in citation_lower for term in question_terms):
                return False
        overlap = sum(1 for term in question_terms if term in citation_lower)
        return overlap > 0

    # ------------------------------------------------------------------
    # Completeness scoring
    # ------------------------------------------------------------------

    def _score_completeness(self, question: str, answer: str) -> float:
        """Heuristic completeness: does the answer look like it addresses the question?"""
        if self._is_dont_know(answer):
            return 0.0
        # Proxy: answer length relative to a reasonable full answer
        word_count = len(answer.split())
        if word_count >= 30:
            return 1.0
        elif word_count >= 10:
            return 0.6
        else:
            return 0.3

    def _is_dont_know(self, text: str) -> bool:
        markers = [
            "i don't know", "don't know", "do not know", "no relevant context",
            "insufficient context", "not mentioned", "no supporting context",
            "context does not contain",
        ]
        lower = text.lower()
        return any(m in lower for m in markers)