# Case Study

## Problem framing

This project demonstrates a production-style RAG pipeline for internal documentation.

## Architecture decisions

- Hybrid retrieval is preferred over dense-only retrieval because it combines semantic and keyword signals.
- RRF is used to fuse dense and sparse rankings without depending on a library implementation.
- A separate citation verification pass is used to keep answers grounded and auditable.

## Chunking strategy comparison

| Strategy | Strengths | Trade-offs |
| --- | --- | --- |
| Fixed | Simple and predictable | Less structure-aware |
| Structure-aware | Preserves document headings | Can be less semantically coherent |
| Semantic | Better topic boundaries | More compute-intensive |

## Headline metrics

- Correctness: [TODO: fill in from eval report]
- Faithfulness: [TODO: fill in from eval report]
- Retrieval relevance: [TODO: fill in from eval report]
- Citation accuracy: [TODO: fill in from eval report]

## What I would do differently at scale

- Add persistent vector storage and a more robust embedding backend.
- Introduce asynchronous ingestion and background reindexing.
- Add more evaluation coverage and human review loops.
