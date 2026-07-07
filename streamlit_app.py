import streamlit as st
import requests

API_BASE = "http://api:8000"

st.set_page_config(page_title="Biome RAG Dashboard", layout="wide")

st.title("Biome RAG Dashboard")

question = st.text_input("Ask a question")
if st.button("Ask") and question:
    with st.spinner("Searching..."):
        response = requests.post(f"{API_BASE}/v1/ask", json={"question": question}, timeout=30)
    if response.ok:
        result = response.json()
        st.subheader("Answer")
        st.write(result["answer"])
        st.subheader("Citations")
        for citation in result.get("citations", []):
            st.write(f"[{citation['chunk_index']}] {citation['text']}")
        st.subheader("Confidence")
        st.json(result.get("confidence", {}))
        st.subheader("Retrieved chunks")
        for chunk in result.get("retrieved_chunks", []):
            st.write(f"- {chunk['text']} (dense={chunk['dense_score']}, sparse={chunk['sparse_score']}, fused={chunk['fused_score']}, rerank={chunk['rerank_score']})")
    else:
        st.error("Request failed")
