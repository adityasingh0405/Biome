"""Biome RAG — Production Hybrid RAG Dashboard

A rich UI for the Biome RAG pipeline featuring:
- Question answering with [n] verified citation highlighting
- Multi-Source Document Ingestion (Files upload, local directory crawler, raw text)
- Confidence breakdown (Retrieval, Citation coverage, Completeness, Composite)
- Retrieved chunks ranked by dense, sparse, RRF, and Cross-Encoder score
- Hybrid vs dense-only side-by-side comparison panel
- Knowledge base & corpus browser
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
# Custom CSS — premium dark glassmorphism design
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
        background: linear-gradient(135deg, #090a16 0%, #12132b 50%, #0d1b38 100%);
        color: #e2e8f0;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: rgba(10, 11, 26, 0.95);
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

    /* Ingest card */
    .ingest-box {
        background: rgba(30, 27, 75, 0.4);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# API Helpers
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


def api_upload_files(files) -> dict | None:
    try:
        file_tuples = [("files", (f.name, f.getvalue(), f.type or "application/octet-stream")) for f in files]
        resp = requests.post(f"{API_BASE}/v1/ingest/upload", files=file_tuples, timeout=180)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"❌ Upload failed: {exc}")
        return None


def api_ingest_directory(dir_path: str, recursive: bool = True) -> dict | None:
    try:
        resp = requests.post(
            f"{API_BASE}/v1/ingest/directory",
            json={"directory_path": dir_path, "recursive": recursive},
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"❌ Directory ingestion failed: {exc}")
        return None


def api_ingest_text(title: str, content: str) -> dict | None:
    try:
        resp = requests.post(
            f"{API_BASE}/v1/ingest/text",
            json={"title": title, "content": content},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"❌ Text ingestion failed: {exc}")
        return None


def highlight_citations(text: str, citations: list[dict]) -> str:
    verified_map: dict[int, bool] = {}
    for c in citations:
        idx = c.get("chunk_index", -1) + 1
        verified_map[idx] = c.get("verified", False)

    def replacer(match: re.Match) -> str:
        n = int(match.group(1))
        verified = verified_map.get(n, False)
        cls = "citation-badge-verified" if verified else "citation-badge-unverified"
        status = "✓" if verified else "~"
        return f'<span class="{cls}" title="Citation {n} — {"verified" if verified else "unverified"}">[{n}{status}]</span>'

    return re.sub(r"\[(\d+)\]", replacer, text)


def render_confidence(conf: dict) -> None:
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
                    f'<div class="chunk-card"><div class="chunk-source">{source}</div>{chunk.get("text", "")[:600]}{"..." if len(chunk.get("text", "")) > 600 else ""}</div>',
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
    st.markdown(f"{status_icon} **Knowledge Base** — **{chunks_indexed}** chunks indexed")

    st.markdown("---")
    st.markdown("### Search Settings")
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
    st.caption(f"Backend: `{API_BASE}`")
    st.caption("Cross-Encoder: `ms-marco-MiniLM-L-6-v2`")
    st.caption("Dense Index: `ChromaDB` | Sparse: `BM25`")


# ---------------------------------------------------------------------------
# Main Application Tabs
# ---------------------------------------------------------------------------

st.markdown("# 🌿 Biome Production RAG")
st.markdown("*Multi-Source Ingestion · Hybrid Search (BM25 + Dense + RRF) · Verified Inline Citations*")
st.markdown("---")

tab_ask, tab_ingest, tab_docs = st.tabs(["💬 Ask & Retrieve", "📥 Ingest Sources", "📂 Corpus Browser"])

# ---------------------------------------------------------------------------
# Tab 1: Ask & Retrieve
# ---------------------------------------------------------------------------

with tab_ask:
    question = st.text_input(
        "Ask any question about your indexed documentation",
        placeholder="e.g. How do I authenticate with the API? What are the deployment error codes?",
        key="question_input",
    )

    col_ask, col_clear = st.columns([1, 5])
    with col_ask:
        ask_clicked = st.button("Ask Question", use_container_width=True)

    if ask_clicked and question.strip():
        if compare_mode:
            with st.spinner("Running side-by-side hybrid and dense retrieval …"):
                compare_result = api_compare(question)

            if compare_result:
                st.markdown("## ⚖️ Side-by-Side Comparison")
                col_h, col_d = st.columns(2)

                with col_h:
                    st.markdown('<div class="compare-header hybrid-header">⚡ Hybrid (BM25 + Dense + RRF + Cross-Encoder)</div>', unsafe_allow_html=True)
                    render_result(compare_result.get("hybrid", {}))

                with col_d:
                    st.markdown('<div class="compare-header dense-header">📐 Dense Only (Embeddings only)</div>', unsafe_allow_html=True)
                    render_result(compare_result.get("dense", {}))

        else:
            with st.spinner(f"Retrieving and generating ({retrieval_mode} mode) …"):
                result = api_ask(question, retrieval_mode)

            if result:
                st.markdown(f"## Answer <span style='font-size:0.6em; color:#64748b;'>({retrieval_mode})</span>", unsafe_allow_html=True)
                render_result(result)

    elif ask_clicked:
        st.warning("Please enter a question.")

    if not ask_clicked:
        st.markdown("#### Sample Questions:")
        examples = [
            "How do I authenticate with the Biome API?",
            "What error code indicates invalid credentials?",
            "What is the deployment target error code?",
            "What are the environment variable requirements?",
        ]
        for ex in examples:
            if st.button(ex, key=f"ex_{ex[:20]}"):
                st.session_state.question_input = ex
                st.rerun()


# ---------------------------------------------------------------------------
# Tab 2: Ingest Sources (Multi-Source Collection)
# ---------------------------------------------------------------------------

with tab_ingest:
    st.markdown("## 📥 Ingest Documentation From Multiple Sources")
    st.markdown("Collect and index documents across your system into both the Chroma vector store and BM25 index.")

    ingest_type = st.radio(
        "Select ingestion source",
        ["📁 Upload Document Files", "💻 Crawl Local System Directory", "📝 Ingest Raw Text / Markdown"],
        horizontal=True,
    )

    if ingest_type == "📁 Upload Document Files":
        st.markdown('<div class="ingest-box">', unsafe_allow_html=True)
        st.markdown("### Upload Documents")
        st.markdown("Supported: **PDF, Markdown (.md), Plain Text (.txt, .log), HTML, JSON, CSV, and Code files (.py, .js, .ts, .yaml, .sql)**")
        uploaded_files = st.file_uploader(
            "Choose files to ingest",
            accept_multiple_files=True,
            type=["pdf", "md", "markdown", "txt", "log", "rst", "html", "htm", "json", "csv", "tsv", "py", "js", "ts", "yaml", "yml", "sql"],
        )
        if st.button("🚀 Ingest Uploaded Files", use_container_width=True):
            if uploaded_files:
                with st.spinner(f"Chunking, deduplicating, and indexing {len(uploaded_files)} files..."):
                    res = api_upload_files(uploaded_files)
                if res and res.get("status") == "ok":
                    st.success(f"✅ Ingested {len(res.get('files_uploaded', []))} files! Total active chunks: {res.get('total_chunks')} (Skipped {res.get('duplicates_skipped', 0)} near-duplicates).")
                    st.rerun()
            else:
                st.warning("Please select at least one file to upload.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif ingest_type == "💻 Crawl Local System Directory":
        st.markdown('<div class="ingest-box">', unsafe_allow_html=True)
        st.markdown("### Crawl Local Folder on System")
        st.markdown("Enter any folder path on your machine. Biome will discover all documents, chunk them with multi-strategy chunkers, and synchronize dense and sparse indexes.")
        dir_input = st.text_input("Local Directory Path", placeholder="e.g. C:\\Users\\Aditya Singh\\Documents\\CompanyDocs or /data/docs")
        recursive_check = st.checkbox("Include subdirectories (recursive crawl)", value=True)
        if st.button("🚀 Scan & Ingest Directory", use_container_width=True):
            if dir_input.strip():
                with st.spinner(f"Scanning and indexing '{dir_input}'..."):
                    res = api_ingest_directory(dir_input.strip(), recursive=recursive_check)
                if res and res.get("status") == "ok":
                    st.success(f"✅ Indexed {res.get('files_found')} files from '{dir_input}'! Total chunks: {res.get('total_chunks')}.")
                    st.rerun()
            else:
                st.warning("Please provide a directory path.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif ingest_type == "📝 Ingest Raw Text / Markdown":
        st.markdown('<div class="ingest-box">', unsafe_allow_html=True)
        st.markdown("### Ingest Raw Documentation Snippet")
        doc_title = st.text_input("Document Title / Source Label", placeholder="e.g. quarterly_architecture_notes")
        doc_body = st.text_area("Document Content (Markdown or Plain Text)", height=250, placeholder="Paste policy, wiki, or release notes here...")
        if st.button("🚀 Ingest Text", use_container_width=True):
            if doc_title.strip() and doc_body.strip():
                with st.spinner("Ingesting document..."):
                    res = api_ingest_text(doc_title, doc_body)
                if res and res.get("status") == "ok":
                    st.success(f"✅ Ingested document '{res.get('document')}'! Total chunks: {res.get('total_chunks')}.")
                    st.rerun()
            else:
                st.warning("Please provide both a title and content.")
        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab 3: Corpus Browser
# ---------------------------------------------------------------------------

with tab_docs:
    st.markdown("## 📂 Indexed Knowledge Base Documents")
    docs = api_documents()
    if docs:
        st.markdown(f"**{len(docs)} documents** currently indexed across the knowledge base.")
        col_search, _ = st.columns([2, 2])
        with col_search:
            search_doc = st.text_input("Filter documents by name", placeholder="Filter...")
        
        for doc in docs:
            source = doc.get("source", "unknown").split("\\")[-1].split("/")[-1]
            if search_doc and search_doc.lower() not in source.lower():
                continue
            count = doc.get("chunk_count", "?")
            st.markdown(
                f'<div class="chunk-card"><div class="chunk-source">📄 {source}</div>'
                f'<span class="score-pill">{count} chunks</span> <span style="font-size:0.8em; color:#94a3b8;">Path: {doc.get("source")}</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No documents indexed yet. Use the 'Ingest Sources' tab to add documents.")
