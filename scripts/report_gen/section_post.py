import docx
from docx.shared import Pt, Cm, RGBColor
from styles import (
    add_body_p, add_bullet_p, add_heading_1, add_heading_2, add_heading_3,
    create_styled_table, add_table_caption, add_callout_box
)

def build_references_and_appendices(doc):
    """Constructs References and Appendices with IEEE citations and technical specifications."""
    
    # REFERENCES
    add_heading_1(doc, "REFERENCES", is_chapter=True)
    
    references = [
        "[1] A. Vaswani, N. Shazeer, N. Parmar, J. Uszkoreit, L. Jones, A. N. Gomez, L. Kaiser, and I. Polosukhin, \"Attention is all you need,\" in Advances in Neural Information Processing Systems (NeurIPS), vol. 30, pp. 5998–6008, 2017.",
        "[2] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. Rocktäschel, S. Riedel, and D. Kiela, \"Retrieval-augmented generation for knowledge-intensive NLP tasks,\" in Advances in Neural Information Processing Systems (NeurIPS), vol. 33, pp. 9459–9474, 2020.",
        "[3] S. Robertson, H. Zaragoza, et al., \"The probabilistic relevance framework: BM25 and beyond,\" Foundations and Trends® in Information Retrieval, vol. 3, no. 4, pp. 333–389, 2009.",
        "[4] G. V. Cormack, C. L. Clarke, and S. Buettcher, \"Reciprocal rank fusion outperforms condorcet and individual rank learning methods,\" in Proceedings of the 32nd International ACM SIGIR Conference on Research and Development in Information Retrieval, pp. 758–759, 2009.",
        "[5] S. Xiao, Z. Liu, P. Zhang, and N. Muennighoff, \"C-Pack: Packaged resources to advance general Chinese embedding,\" arXiv preprint arXiv:2309.07597, Beijing Academy of Artificial Intelligence (BAAI), 2023.",
        "[6] J. Chen, S. Xiao, P. Zhang, K. Luo, D. Lian, and Z. Liu, \"BGE M3-Embedding: Multi-lingual, multi-functionality, multi-granularity text embeddings through self-knowledge distillation,\" arXiv preprint arXiv:2402.03216, 2024.",
        "[7] R. Nogueira and K. Cho, \"Passage re-ranking with BERT,\" arXiv preprint arXiv:1901.04085, 2019.",
        "[8] N. Reimers and I. Gurevych, \"Sentence-BERT: Sentence embeddings using Siamese BERT-networks,\" in Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing (EMNLP), pp. 3982–3992, 2019.",
        "[9] O. Khattab and M. Zaharia, \"ColBERT: Efficient and effective passage search via contextualized late interaction over BERT,\" in Proceedings of the 43rd International ACM SIGIR Conference on Research and Development in Information Retrieval, pp. 39–48, 2020.",
        "[10] S. Es, J. James, L. R. E. Ceballos, and B. S. R. V. K. V. S. R. G. S. J. S. A. S., \"Ragas: Automated evaluation of retrieval augmented generation,\" in Proceedings of the 18th Conference of the European Chapter of the Association for Computational Linguistics (EACL), pp. 150–158, 2024.",
        "[11] Confident AI, \"DeepEval: The open-source evaluation framework for LLMs and RAG pipelines,\" Available: https://confident-ai.com, 2024.",
        "[12] IBM Research, \"IBM Docling: Layout-aware visual document parsing and structural JSON extraction,\" IBM Technical Report, Version 2.0, 2024.",
        "[13] Qdrant Team, \"Qdrant: Open-source high-performance vector search engine and payload database,\" Version 1.10.0, Available: https://qdrant.tech, 2024.",
        "[14] S. Sanfilippo et al., \"Redis: In-memory data structures, list pipelines, and sliding-window session storage,\" Version 7.2, Available: https://redis.io, 2023.",
        "[15] S. Ramírez (tiangolo), \"FastAPI: Modern, high-performance web framework for building APIs with Python 3.8+,\" Version 0.115.0, Available: https://fastapi.tiangolo.com, 2024.",
        "[16] Meta AI, \"Llama 3.1: Open foundation and fine-tuned large language models for reasoning and synthesis,\" Meta AI Research Whitepaper, 2024.",
        "[17] Langfuse Team, \"Langfuse: Open-source LLM engineering platform, telemetry tracing, and prompt management,\" Version 2.0, Available: https://langfuse.com, 2024.",
        "[18] Prefect Technologies, \"Prefect 3.0: Workflow orchestration, automated pipelines, and reactive state management,\" Available: https://prefect.io, 2024.",
        "[19] N. Thakur, N. Reimers, A. Rücklé, A. Srivastava, and I. Gurevych, \"BEIR: A heterogeneous benchmark for zero-shot evaluation of information retrieval models,\" in Thirty-fifth Conference on Neural Information Processing Systems Datasets and Benchmarks Track, 2021.",
        "[20] V. Karpukhin, B. Oguz, S. Min, P. Lewis, L. Wu, S. Edunov, D. Chen, and W. Yih, \"Dense passage retrieval for open-domain question answering,\" in Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP), pp. 6769–6781, 2020.",
        "[21] G. Izacard, P. Lewis, M. Lomeli, L. Hosseini, F. Petroni, T. Schick, J. Dwivedi-Yu, A. Joulin, S. Riedel, and E. Grave, \"Few-shot learning with retrieval augmented language models,\" arXiv preprint arXiv:2208.03299, 2022.",
        "[22] Y. Gao, Y. Xiong, X. Gao, K. Jia, J. Pan, Y. Bi, Y. Dai, J. Sun, and H. Wang, \"Retrieval-augmented generation for large language models: A survey,\" arXiv preprint arXiv:2312.10997, 2024.",
        "[23] D. Edge, H. Trinh, N. Cheng, J. Bradley, A. Chao, A. Mody, S. Truitt, and J. Larson, \"From local to global: A graph RAG approach to query-focused summarization,\" Microsoft Research Whitepaper, arXiv:2404.16130, 2024.",
        "[24] A. Asai, Z. Wu, Y. Wang, A. Sil, and H. Hajishirzi, \"Self-RAG: Learning to retrieve, generate, and critique through self-reflection,\" in International Conference on Learning Representations (ICLR), 2024.",
        "[25] International Electrotechnical Commission, \"IEC 60169-4: Radio-frequency connectors - Part 4: RF coaxial connectors with inner diameter of outer conductor 16 mm (7/16 DIN),\" IEC Standard Catalogue, Geneva, Switzerland.",
        "[26] Department of Defense, \"MIL-STD-202: Department of Defense Test Method Standard for Electronic and Electrical Component Parts,\" United States Military Standard, Washington D.C.",
        "[27] International Organization for Standardization, \"ISO 9001:2015 Quality Management Systems — Requirements,\" ISO Central Secretariat, Geneva, Switzerland, 2015.",
        "[28] Pydantic Team, \"Pydantic: Fast data validation and settings management using Python type hints,\" Version 2.8, 2024.",
        "[29] M. Bayer et al., \"SQLAlchemy: The Python SQL toolkit and Object Relational Mapper,\" Version 2.0, 2024.",
        "[30] Meta Platforms, \"React: A declarative, efficient, and flexible JavaScript library for building user interfaces,\" Version 18.3, 2024.",
        "[31] E. You et al., \"Vite: Next generation frontend tooling,\" Version 5.4, 2024.",
        "[32] Tailwind Labs, \"Tailwind CSS: A utility-first CSS framework for rapid UI development,\" Version 4.0, 2025.",
        "[33] MinIO Inc., \"MinIO: High performance, S3-compatible enterprise object storage,\" Available: https://min.io, 2024.",
        "[34] Chonkie Project, \"Chonkie: Ultra-fast token-budgeted sentence and semantic text chunking,\" Version 0.4.0, 2024.",
        "[35] Ollama Project, \"Ollama: Lightweight, extensible framework for building and running LLMs locally,\" Version 0.3.0, 2024."
    ]
    
    for ref_str in references:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.first_line_indent = Cm(-0.8)
        
        r = p.add_run(ref_str)
        r.font.name = 'Times New Roman'
        r.font.size = Pt(10.5)

    # APPENDIX A
    add_heading_1(doc, "APPENDIX A: PRODUCTION ENVIRONMENT CONFIGURATION", is_chapter=True)
    add_body_p(doc, 
        "The following configuration parameters define the production environment specification (.env.example) developed and deployed "
        "for the Biome Enterprise RAG system at Synergy Telecom (P) LTD:"
    )
    
    env_lines = [
        "# ====================================================================",
        "# BIOME ENTERPRISE RAG — PRODUCTION CONFIGURATION (.env)",
        "# ====================================================================",
        "APP_ENV=production",
        "LOG_LEVEL=INFO",
        "API_HOST=0.0.0.0",
        "API_PORT=8000",
        "",
        "# Vector Database Configuration (Qdrant v1.10.0)",
        "QDRANT_HOST=localhost",
        "QDRANT_PORT=6333",
        "QDRANT_COLLECTION=biome_enterprise_catalog",
        "QDRANT_HYBRID_PREFETCH_LIMIT=30",
        "",
        "# Dense & Sparse Embedding Models",
        "EMBEDDING_PROVIDER=bge-m3",
        "EMBEDDING_MODEL=BAAI/bge-m3",
        "EMBEDDING_DIMENSION=1024",
        "SPARSE_INDEX_ENABLED=true",
        "RRF_DENSE_WEIGHT=0.70",
        "RRF_SPARSE_WEIGHT=0.30",
        "RRF_SMOOTHING_K=60",
        "",
        "# Cross-Encoder Re-Ranking Configuration",
        "RERANKER_ENABLED=true",
        "RERANKER_MODEL=BAAI/bge-reranker-v2-m3",
        "RERANK_TOP_K=5",
        "",
        "# Multi-Turn Session Memory (Redis 7.2)",
        "REDIS_HOST=localhost",
        "REDIS_PORT=6379",
        "REDIS_SESSION_TTL=3600",
        "SESSION_MAX_TURNS=10",
        "",
        "# Observability & Tracing (Langfuse)",
        "LANGFUSE_ENABLED=true",
        "LANGFUSE_PUBLIC_KEY=pk-lf-prod-synergy-2026",
        "LANGFUSE_SECRET_KEY=sk-lf-prod-synergy-secure",
        "LANGFUSE_HOST=http://localhost:3000"
    ]
    add_callout_box(doc, "Production Environment Specification (.env)", env_lines)

    # APPENDIX B
    add_heading_1(doc, "APPENDIX B: CORE PYDANTIC SCHEMAS & REST API MODELS", is_chapter=True)
    add_body_p(doc, 
        "The following Pydantic schemas enforce type safety and input/output contracts across all FastAPI routes:"
    )
    
    schema_lines = [
        "class AskRequest(BaseModel):",
        "    question: str = Field(..., min_length=3, description=\"User technical query\")",
        "    session_id: Optional[str] = Field(None, description=\"Redis session key\")",
        "    route_override: Optional[Literal[\"auto\", \"structured\", \"semantic\"]] = \"auto\"",
        "    requester_scope: List[str] = Field(default_factory=lambda: [\"public\"])",
        "",
        "class CitationItem(BaseModel):",
        "    citation_index: int",
        "    document_name: str",
        "    heading_path: str",
        "    snippet: str",
        "    verified: bool",
        "",
        "class AskResponse(BaseModel):",
        "    answer: str",
        "    citations: List[CitationItem]",
        "    confidence_score: float",
        "    route: str",
        "    sql_query: Optional[str] = None",
        "    latency_ms: float",
        "    trace_id: Optional[str] = None"
    ]
    add_callout_box(doc, "FastAPI Core Request and Response Models", schema_lines)

    # APPENDIX C
    add_heading_1(doc, "APPENDIX C: PRODUCTION GROUNDING PROMPTS & SYSTEM GUARDRAILS", is_chapter=True)
    add_body_p(doc, 
        "The system prompt guarantees strict factual grounding, citation adherence, and hallucination rejection:"
    )
    
    prompt_lines = [
        "SYSTEM_GROUNDING_PROMPT = \"\"\"",
        "You are the Biome Enterprise Technical Copilot for Synergy Telecom (P) LTD.",
        "Your mission is to provide authoritative, mathematically grounded answers to engineering and operational inquiries.",
        "",
        "MANDATORY INSTRUCTIONS:",
        "1. Base your answer EXCLUSIVELY on the numbered context blocks [n] provided below.",
        "2. For EVERY factual claim, technical specification, part number, or numerical value, you MUST cite the",
        "   corresponding context block using bracketed inline markers, e.g., 'The VSWR limit is 1.15:1 [1]'.",
        "3. DO NOT fabricate, extrapolate, or introduce external technical facts not explicitly stated in the context.",
        "4. If the provided context does not contain sufficient factual evidence to answer the question completely,",
        "   you MUST state: 'The available enterprise documentation does not contain sufficient context to verify this specification.'",
        "   Do not guess.",
        "\"\"\""
    ]
    add_callout_box(doc, "Production LLM Grounding System Guardrail", prompt_lines)

    # APPENDIX D
    add_heading_1(doc, "APPENDIX D: SAMPLE GOLDEN BENCHMARK EVALUATION RECORDS", is_chapter=True)
    add_body_p(doc, 
        "Table D.1 displays representative question-answer records extracted from the 55-question golden benchmark dataset (eval/golden_dataset.json):"
    )
    
    add_table_caption(doc, "Table D.1", "Sample Golden Benchmark Evaluation Dataset Records Across Four Question Categories")
    d_headers = ["Category", "Benchmark Question", "Ground-Truth Reference Answer", "Target Verification Passage"]
    d_data = [
        ["Factoid Lookup", "What is the maximum VSWR for 7/16 DIN connectors at 3.0 GHz?", "Maximum VSWR is 1.15:1 for 7/16 DIN series up to 3.0 GHz.", "Synergy_RF_Connectors_Catalog_2026.pdf (Section 3.4, Table 4.2)"],
        ["Multi-Hop", "Which connector is recommended for 1/2 inch feeder cable in outdoor base stations?", "SY-DIN-M-716 male connector with weatherproofing boot seal is certified for 1/2 inch feeder.", "BTS_Installation_Manual_Rev4.docx (Chapter 2, Section 2.1)"],
        ["Negative Constraint", "What is the certified operating depth for BNC-50 underwater marine immersion?", "INSUFFICIENT CONTEXT. BNC-50 is rated for indoor/chassis use only and has no marine immersion rating.", "Negative test constraint (asserts system refusal)."],
        ["Structured SQL", "What is the average resolution time for CRITICAL tickets in telecom_engineering?", "Average resolution time is 4.8 hours across 14 resolved tickets.", "enterprise_tickets table (WHERE dept='telecom_engineering' AND priority='CRITICAL')"]
    ]
    create_styled_table(doc, d_headers, d_data, col_widths=[2.8, 4.4, 4.8, 4.25])
