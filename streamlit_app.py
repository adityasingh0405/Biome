"""Biome RAG — Streamlit Dashboard

A rich UI for the Biome RAG pipeline featuring:
- Question answering with [n] citation highlighting
- Confidence breakdown bar chart
- Retrieved chunks ranked by score
- Hybrid vs dense-only comparison panel
- Document index browser
"""
from __future__ import annotations

import os
import re

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
PAGE_TITLE = "Biome RAG"

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — premium dark design
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Dark gradient background */
    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
        color: #e2e8f0;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: rgba(15, 15, 30, 0.95);
        border-right: 1px solid rgba(99, 102, 241, 0.2);
    }

    /* Headers */
    h1 { color: #818cf8; font-weight: 700; }
    h2 { color: #a5b4fc; font-weight: 600; }
    h3 { color: #c7d2fe; font-weight: 500; }

    /* Answer card */
    .answer-card {
        background: rgba(30, 27, 75, 0.6);
        border: 1px solid rgba(99, 102, 241, 0.4);
        border-radius: 12px;
        padding: 20px 24px;
        margin: 12px 0;
        backdrop-filter: blur(10px);
        line-height: 1.8;
    }

    /* Citation badge — verified */
    .citation-badge-verified {
        display: inline-block;
        background: rgba(16, 185, 129, 0.2);
        border: 1px solid rgba(16, 185, 129, 0.5);
        color: #6ee7b7;
        border-radius: 4px;
        padding: 1px 6px;
        font-size: 0.75em;
        font-weight: 600;
        cursor: pointer;
        margin: 0 1px;
    }

    /* Citation badge — unverified */
    .citation-badge-unverified {
        display: inline-block;
        background: rgba(245, 158, 11, 0.2);
        border: 1px solid rgba(245, 158, 11, 0.5);
        color: #fcd34d;
        border-radius: 4px;
        padding: 1px 6px;
        font-size: 0.75em;
        font-weight: 600;
        cursor: pointer;
        margin: 0 1px;
    }

    /* Chunk card */
    .chunk-card {
        background: rgba(30, 27, 75, 0.4);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 8px;
        padding: 14px 18px;
        margin: 8px 0;
    }

    .chunk-source {
        font-size: 0.75em;
        color: #818cf8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }

    .score-pill {
        display: inline-block;
        background: rgba(99, 102, 241, 0.15);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 20px;
        padding: 2px 10px;
        font-size: 0.72em;
        color: #a5b4fc;
        margin-right: 6px;
    }

    /* Compare panel */
    .compare-header {
        font-size: 0.85em;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 6px 12px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .hybrid-header { background: rgba(99, 102, 241, 0.25); color: #a5b4fc; }
    .dense-header  { background: rgba(16, 185, 129, 0.15); color: #6ee7b7; }

    /* Metric cards */
    .metric-row {
        display: flex;
        gap: 12px;
        margin: 12px 0;
    }
    .metric-card {
        flex: 1;
        background: rgba(30, 27, 75, 0.6);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 10px;
        padding: 14px;
        text-align: center;
    }
    .metric-value {
        font-size: 1.8em;
        font-weight: 700;
        color: #818cf8;
    }
    .metric-label {
        font-size: 0.72em;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Stbutton overrides */
    .stButton > button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.85; }

    /* Expander */
    .streamlit-expanderHeader {
        background: rgba(30, 27, 75, 0.4) !important;
        border-radius: 6px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def api_ask(question: str, mode: str) -> dict | None:
    try:
        resp = requests.post(
            f"{API_BASE}/v1/ask",
            json={"question": question, "retrieval_mode": mode},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"❌ API error: {exc}")
        return None


def api_compare(question: str) -> dict | None:
    try:
        resp = requests.post(f"{API_BASE}/v1/compare", json={"question": question}, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"❌ Compare API error: {exc}")
        return None


def api_documents() -> list[dict]:
    try:
        resp = requests.get(f"{API_BASE}/v1/documents", timeout=10)
        resp.raise_for_status()
        return resp.json().get("documents", [])
    except Exception:
        return []


def api_health() -> dict:
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def highlight_citations(text: str, citations: list[dict]) -> str:
    """Replace [n] in answer text with styled HTML citation badges."""
    # Build a map from chunk_index → verified
    verified_map: dict[int, bool] = {}
    for c in citations:
        idx = c.get("chunk_index", -1) + 1  # [n] is 1-indexed in the text
        verified_map[idx] = c.get("verified", False)

    def replacer(match: re.Match) -> str:
        n = int(match.group(1))
        verified = verified_map.get(n, False)
        cls = "citation-badge-verified" if verified else "citation-badge-unverified"
        status = "✓" if verified else "~"
        return f'<span class="{cls}" title="Citation {n} — {"verified" if verified else "unverified"}">[{n}{status}]</span>'

    return re.sub(r"\[(\d+)\]", replacer, text)


def render_confidence(conf: dict) -> None:
    """Render the four confidence dimensions as metric cards + a progress bar."""
    rc = conf.get("retrieval_confidence", 0.0)
    cc = conf.get("citation_coverage", 0.0)
    cm = conf.get("completeness", 0.0)
    composite = conf.get("composite", 0.0)

    color = "#10b981" if composite >= 0.7 else "#f59e0b" if composite >= 0.4 else "#ef4444"

    st.markdown(
        f"""
        <div class="metric-row">
            <div class="metric-card">
                <div class="metric-value" style="color:{color}">{composite:.0%}</div>
                <div class="metric-label">Composite</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{rc:.0%}</div>
                <div class="metric-label">Retrieval</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{cc:.0%}</div>
                <div class="metric-label">Citations</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{cm:.0%}</div>
                <div class="metric-label">Completeness</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(composite, text=f"Composite confidence: {composite:.0%}")


def render_chunks(chunks: list[dict], label: str = "Retrieved Chunks") -> None:
    if not chunks:
        st.caption("No chunks retrieved.")
        return
    st.markdown(f"**{label}** ({len(chunks)} results)")
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source", "unknown").split("\\")[-1].split("/")[-1]
        heading = chunk.get("section_heading") or ""
        with st.expander(f"#{i} — {source}{' · ' + heading if heading else ''}", expanded=(i == 1)):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(
                    f'<div class="chunk-card"><div class="chunk-source">{source}</div>{chunk.get("text", "")[:500]}{"..." if len(chunk.get("text", "")) > 500 else ""}</div>',
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(
                    f"""
                    <span class="score-pill">dense {chunk.get('dense_score', 0):.3f}</span><br>
                    <span class="score-pill">sparse {chunk.get('sparse_score', 0):.3f}</span><br>
                    <span class="score-pill">fused {chunk.get('fused_score', 0):.4f}</span><br>
                    <span class="score-pill">rerank {chunk.get('rerank_score', 0):.3f}</span>
                    """,
                    unsafe_allow_html=True,
                )


def render_result(result: dict) -> None:
    answer = result.get("answer", "")
    citations = result.get("citations", [])
    conf = result.get("confidence", {})
    chunks = result.get("retrieved_chunks", [])

    highlighted = highlight_citations(answer, citations)
    st.markdown(
        f'<div class="answer-card">{highlighted}</div>',
        unsafe_allow_html=True,
    )

    if citations:
        st.markdown("**Citations**")
        for c in citations:
            n = c["chunk_index"] + 1
            verified = c.get("verified", False)
            icon = "✅" if verified else "⚠️"
            with st.expander(f"{icon} [{n}] {'Verified' if verified else 'Unverified'} — {c['text'][:80]}..."):
                st.write(c["text"])

    st.markdown("**Confidence**")
    render_confidence(conf)
    render_chunks(chunks)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("# 🌿 Biome RAG")
    st.markdown("---")

    health = api_health()
    chunks_indexed = health.get("chunks_indexed", "?")
    status_icon = "🟢" if health.get("status") == "ok" else "🔴"
    st.markdown(f"{status_icon} **API** — {chunks_indexed} chunks indexed")

    st.markdown("---")
    st.markdown("### Settings")
    compare_mode = st.toggle("Hybrid vs Dense comparison", value=False)
    retrieval_mode = "hybrid"
    if not compare_mode:
        retrieval_mode = st.radio(
            "Retrieval mode",
            ["hybrid", "dense", "sparse"],
            index=0,
            horizontal=True,
        )

    st.markdown("---")
    st.caption(f"API: `{API_BASE}`")
    st.caption("LLM: `local` | Embeddings: `sentence-transformers`")

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

st.markdown("# 🌿 Biome RAG")
st.markdown("*Hybrid search · Grounded answers · Verified citations*")
st.markdown("---")

tab_ask, tab_docs = st.tabs(["💬 Ask", "📂 Documents"])

# ---------------------------------------------------------------------------
# Ask tab
# ---------------------------------------------------------------------------

with tab_ask:
    question = st.text_input(
        "Ask a question about your documentation",
        placeholder="e.g. How do I authenticate with the Biome API?",
        key="question_input",
    )

    col_ask, col_clear = st.columns([1, 5])
    with col_ask:
        ask_clicked = st.button("Ask", use_container_width=True)

    if ask_clicked and question.strip():
        if compare_mode:
            # --- Compare mode: side-by-side hybrid vs dense ---
            with st.spinner("Running hybrid and dense-only retrieval …"):
                compare_result = api_compare(question)

            if compare_result:
                st.markdown("## Side-by-Side Comparison")
                col_h, col_d = st.columns(2)

                with col_h:
                    st.markdown('<div class="compare-header hybrid-header">⚡ Hybrid (BM25 + Dense + RRF)</div>', unsafe_allow_html=True)
                    render_result(compare_result.get("hybrid", {}))

                with col_d:
                    st.markdown('<div class="compare-header dense-header">📐 Dense Only</div>', unsafe_allow_html=True)
                    render_result(compare_result.get("dense", {}))

        else:
            # --- Single mode ---
            with st.spinner(f"Searching ({retrieval_mode} mode) …"):
                result = api_ask(question, retrieval_mode)

            if result:
                st.markdown(f"## Answer <span style='font-size:0.6em; color:#64748b;'>({retrieval_mode})</span>", unsafe_allow_html=True)
                render_result(result)

    elif ask_clicked:
        st.warning("Please enter a question.")

    # Hint examples
    if not ask_clicked:
        st.markdown("#### Try these questions:")
        examples = [
            "How do I authenticate with the Biome API?",
            "What error code is returned for invalid credentials?",
            "Why is hybrid retrieval better than dense-only search?",
            "What is the BIOME_API_KEY?",
        ]
        for ex in examples:
            if st.button(ex, key=f"ex_{ex[:20]}"):
                st.session_state.question_input = ex
                st.rerun()

# ---------------------------------------------------------------------------
# Documents tab
# ---------------------------------------------------------------------------

with tab_docs:
    st.markdown("## 📂 Indexed Documents")
    docs = api_documents()
    if docs:
        st.markdown(f"**{len(docs)} documents** indexed across the knowledge base.")
        for doc in docs:
            source = doc.get("source", "unknown").split("\\")[-1].split("/")[-1]
            count = doc.get("chunk_count", "?")
            st.markdown(
                f'<div class="chunk-card"><div class="chunk-source">📄 {source}</div>'
                f'<span class="score-pill">{count} chunks</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No documents indexed yet. Run `python scripts/seed_index.py` to index the sample corpus.")
