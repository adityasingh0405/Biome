from docx.shared import Pt, Cm, RGBColor
from styles import (
    add_body_p, add_bullet_p, add_heading_1, add_heading_2, add_heading_3,
    create_styled_table, add_table_caption, add_callout_box
)

def build_chapter_1(doc):
    """Constructs Chapter 1: Introduction with comprehensive academic and industrial depth."""
    
    # Chapter Title
    add_heading_1(doc, "CHAPTER 1: INTRODUCTION", is_chapter=True)
    
    # 1.1 About the Organization
    add_heading_2(doc, "1.1 About the Organization: Synergy Telecom (P) LTD")
    add_body_p(doc, 
        "Synergy Telecom (P) LTD is an internationally recognized, ISO 9001:2015 certified engineering and manufacturing "
        "enterprise headquartered in Vikas Puri, New Delhi, India. Established under Corporate Identity Number (CIN) "
        "U74998DL2004PTC129420, the company has operated at the forefront of the telecommunications hardware, radio frequency (RF) "
        "engineering, and microwave component industry for over two decades. The organization specializes in the design, precision fabrication, "
        "quality testing, and international distribution of advanced telecommunication infrastructure hardware, encompassing five core "
        "technological product lines:"
    )
    
    products = [
        ("Radio Frequency (RF) Connectors: ", 
         "Precision-machined coaxial connector assemblies spanning 7/16 DIN, N-Type, SMA, SMB, BNC, TNC, Mini-UHF, and MCX form factors. "
         "These components are engineered for low Voltage Standing Wave Ratio (VSWR ≤ 1.15:1) up to 7.5 GHz, high dielectric withstanding voltages "
         "(up to 4,000 V RMS), and third-order intermodulation distortion (PIM3 ≤ -160 dBc @ 2×20 W) in demanding cellular base stations."),
        
        ("Coaxial Feeder Cables & Jumper Assemblies: ", 
         "Low-loss corrugated copper coaxial feeder cables (1/4\", 1/2\", 7/8\", 1-1/4\", and 1-5/8\") alongside superflexible jumper "
         "cables designed for cellular tower runs, satellite earth stations, and high-density distributed antenna systems (DAS)."),
        
        ("RF Passive Microwave Components: ", 
         "Directional couplers, hybrid combiners, multi-way power dividers, high-power dummy loads, fixed and variable RF attenuators, "
         "and DC blocks operating across the UHF, L, S, and C frequency bands (500 MHz to 18 GHz)."),
        
        ("Base Transceiver Station (BTS) & In-Building Solutions (IBS): ", 
         "Turnkey antenna installation hardware, lightning surge arrestors, grounding kits, cable clamps, weatherproofing boot systems, "
         "and structural mounting apparatus deployed across major Indian and global telecommunication operator networks."),
         
        ("National & Solar Power Connectors: ", 
         "High-reliability IP68-rated photovoltaic (PV) DC connectors, waterproof junction enclosures, and terminal power distribution "
         "blocks for renewable energy infrastructure."
    )
    ]
    for p_lbl, p_desc in products:
        add_bullet_p(doc, p_desc, bold_prefix=p_lbl)
        
    add_body_p(doc, 
        "Synergy Telecom serves an extensive industrial client base comprising national telecom service providers (including Reliance Jio, "
        "Bharti Airtel, and Vodafone Idea), defense research institutions, broadcast networks, cellular tower infrastructure companies "
        "(Indus Towers), and original equipment manufacturers (OEMs). The company operates modern impedance analyzer test benches, "
        "passive intermodulation (PIM) test chambers, and environmental stress chambers to guarantee strict adherence to international "
        "standards including IEC 60169, MIL-STD-202, and RoHS/REACH environmental compliance directives."
    )
    
    # 1.2 The Enterprise Unstructured Documentation Crisis
    add_heading_2(doc, "1.2 The Enterprise Unstructured Documentation Crisis & Information Silos")
    add_body_p(doc, 
        "Modern telecommunication hardware manufacturing is characterized by immense documentation complexity. Synergy Telecom manages "
        "a catalog exceeding 5,000 distinct product Stock Keeping Units (SKUs), each governed by intricate mechanical drawings, electrical "
        "datasheets, insertion loss curves, quality control inspection logs, and client-specific customization specifications. Over two "
        "decades of operations, this organizational knowledge has fragmented across disparate, disconnected enterprise repositories:"
    )
    
    silos = [
        ("Unstructured Engineering Archives: ", 
         "Over 12,000 technical PDF datasheets, DOCX installation guides, PPTX technical training decks, and HTML product specifications "
         "stored across shared local servers and object storage buckets. These documents feature multi-column layouts, technical schematic diagrams, "
         "and complex parameter tables."),
        
        ("Relational Operational Databases: ", 
         "PostgreSQL databases storing enterprise operational records, return merchandise authorizations (RMAs), batch testing records, "
         "and department-specific customer support tickets spanning thousands of relational rows."),
        
        ("Synchronous Collaborative Chat Streams: ", 
         "Internal communication channels (Slack workspaces and internal messaging platforms) where platform engineers, RF design specialists, "
         "and field technicians exchange critical troubleshooting solutions, deployment fixes, and product application notes in conversational threads."
    )
    ]
    for s_lbl, s_desc in silos:
        add_bullet_p(doc, s_desc, bold_prefix=s_lbl)
        
    add_body_p(doc, 
        "This architectural fragmentation has precipitated what enterprise knowledge theorists term the 'enterprise dark data crisis'. "
        "Knowledge workers—including sales engineers compiling Requests for Quotation (RFQs), quality assurance auditors, and field support technicians—"
        "spend between 3.2 and 5.5 hours per week manually locating relevant technical parameters. When a prospective client inquires whether a specific "
        "connector (e.g. 'SY-DIN-M-716') is certified for 3.8 GHz 5G mid-band deployment with a return loss exceeding 26 dB, the required parameters "
        "are often buried within a multi-page PDF table, an internal support ticket, or an unindexed chat thread."
    )
    
    add_body_p(doc, 
        "Conventional computational approaches fail catastrophically when applied to this environment. Lexical search engines (such as traditional "
        "SQL LIKE queries or basic BM25 keyword matchers) are inherently brittle: they fail completely when users express queries using conceptual "
        "paraphrasing or domain synonyms (e.g., searching for 'signal reflection damping' instead of 'VSWR optimization'). Conversely, modern "
        "dense vector embedding models (e.g., OpenAI text-embedding-3-small, standard MiniLM) project text into smooth continuous mathematical "
        "hyperspaces. While exceptional at broad semantic matching, dense embeddings suffer from what information retrieval researchers define as "
        "the 'exact-token collapse': dense encoders blur fine-grained alphanumeric tokens. As a result, critical part codes (e.g. 'SY-DIN-M-716'), "
        "software error codes (e.g. 'E1001'), and precise electrical ratings are projected near irrelevant general texts, causing dense-only search "
        "to miss up to 58% of exact technical queries."
    )
    
    # 1.3 Problem Statement
    add_heading_2(doc, "1.3 Problem Statement & Technical Challenges in Telecommunication Engineering")
    add_body_p(doc, 
        "The overarching technical problem addressed in this industrial project is defined as follows:"
    )
    
    add_callout_box(doc, "Formal Problem Statement", [
        "\"To architect, engineer, and deploy an industry-grade, multi-source Retrieval-Augmented Generation (RAG) and Natural Language to SQL (NL2SQL) "
        "enterprise platform—named 'Biome'—capable of autonomously ingesting heterogeneous data (PostgreSQL, Slack transcripts, unstructured PDF/DOCX/HTML), "
        "executing layout-aware chunking without structural table destruction, performing hybrid dense-sparse vector retrieval with Reciprocal Rank Fusion (RRF), "
        "re-ranking candidates via cross-encoder attention, and generating hallucination-free grounded answers with verified inline citations, while sandboxing "
        "relational analytics under programmatic row-level access control (ACL).\""
    ])
    
    add_body_p(doc, 
        "Achieving this objective required overcoming five critical technical and algorithmic hurdles:"
    )
    
    challenges = [
        ("Table & Layout Destruction in Naive Chunking: ", 
         "Standard text-splitting libraries (e.g., recursive character splitters) treat text as flat strings, completely destroying tabular rows, "
         "column alignments, and heading hierarchies in engineering datasheets. When an electrical parameter table is split arbitrarily mid-row, "
         "the semantic association between the parameter name (e.g., 'Dielectric Breakdown') and its numerical value (e.g., '4,000 V RMS') is severed."),
        
        ("The Exact-Symbol vs Semantic Matching Dilemma: ", 
         "Neither dense embeddings nor sparse lexical matching alone can satisfy enterprise queries. The system must seamlessly resolve broad "
         "natural language conceptual queries ('How do we prevent moisture ingress at base station jumper joints?') alongside hyper-specific "
         "alphanumeric lookups ('What is the attenuation of cable SY-12-CF at 2.4 GHz?')."),
        
        ("Generative Hallucination & Citation Inaccuracy: ", 
         "Commercial large language models (LLMs) frequently fabricate plausible-sounding electrical values or invent non-existent part numbers "
         "when operating on domain-specific corpora. In RF engineering, an incorrect dielectric breakdown rating can lead to catastrophic hardware "
         "destruction or electrical fires. The system must implement deterministic post-generation citation verification to detect and abort hallucinations."),
        
        ("Security Vulnerabilities in Natural Language to SQL (NL2SQL): ", 
         "Allowing an LLM to generate raw SQL queries over enterprise relational databases introduces severe security vulnerabilities, including SQL injection "
         "(stacked queries with semicolons), unauthorized data mutations (DROP, DELETE, UPDATE), and computational denial-of-service via unindexed scans."),
         
        ("Tenant Isolation & Row-Level Access Control (ACL): ", 
         "Enterprise support tickets and financial data are departmentally scoped. Prompt-based instructions (e.g., telling an LLM 'only view RF lab tickets') "
         "are notoriously susceptible to adversarial prompt injection. Access control must be enforced programmatically at the AST execution level."
    )
    ]
    for c_lbl, c_desc in challenges:
        add_bullet_p(doc, c_desc, bold_prefix=c_lbl)
        
    # 1.4 Project Motivation & Objectives
    add_heading_2(doc, "1.4 Project Motivation, Objectives & Core Scope")
    add_body_p(doc, 
        "The motivation behind Project Biome stems from Synergy Telecom's commitment to industrial automation, operational efficiency, "
        "and technological self-reliance under its Industry-Academia Vision. By transitioning from manual document searching to an autonomous, "
        "AI-driven neural copilot, the organization aims to empower its workforce with instantaneous, mathematically grounded insights."
    )
    
    add_body_p(doc, "The targeted project objectives were formally established as follows:")
    objectives = [
        ("Multi-Source Ingestion Pipeline: ", "Engineer automated ingestion connectors for PostgreSQL tables, Slack conversation threads, and unstructured object storage (S3/MinIO), supporting incremental synchronization with watermark tracking and cryptographic content deduplication."),
        ("Layout-Aware Document Parsing: ", "Integrate state-of-the-art visual document parsing (IBM Docling) capable of extracting reading order, section hierarchies, and Markdown table structures from complex PDF/DOCX datasheets."),
        ("Oversized-Table Chunking Innovation: ", "Formulate and implement an oversized-table row-splitting algorithm that splits extensive tables exceeding token budgets while dynamically repeating table headers across every sub-chunk to preserve contextual schema."),
        ("Hybrid Dense-Sparse Vector Retrieval: ", "Deploy BAAI/bge-m3 to generate dual 1024-dimensional dense vectors and token-weighted sparse lexical vectors, indexing them within high-performance Qdrant vector collections and fusing results via Reciprocal Rank Fusion (RRF, k=60)."),
        ("Cross-Encoder Re-Ranking: ", "Implement a secondary re-ranking stage utilizing cross-encoder attention (BAAI/bge-reranker-v2-m3) to refine the top-30 candidate pool down to the 5 most semantically relevant passages prior to generation."),
        ("Sandboxed NL2SQL with Programmatic ACL: ", "Build an automated query router distinguishing structured analytics from semantic questions, executing sandboxed, read-only SELECT queries with programmatic row-level subquery injection based on user departmental scopes."),
        ("Grounded Generation & Citation Verification: ", "Implement an answer builder enforcing numbered bracketed citations [n] linked to retrieved passages, validated by an automated citation verification judge to prevent hallucination."),
        ("Empirical Evaluation & 18-Arm Ablation Study: ", "Construct an evaluation harness assessing Ragas and DeepEval metrics across a 55-question golden dataset, executing an 18-arm ablation study to prove the mathematical superiority of hybrid retrieval.")
    ]
    for o_lbl, o_desc in objectives:
        add_bullet_p(doc, o_desc, bold_prefix=o_lbl)

    # 1.5 Technological Stack
    add_heading_2(doc, "1.5 Technological Stack of Training & Architectural Roles")
    add_body_p(doc, 
        "To achieve enterprise-grade scalability, low retrieval latency, and complete deployment sovereignty without reliance on external "
        "cloud APIs, a carefully selected, state-of-the-art open-source software stack was employed throughout the internship. Table 1.1 "
        "details the technological stack, version specifications, and architectural roles across the system lifecycle."
    )
    
    add_table_caption(doc, "Table 1.1", "Core Technological Stack, Framework Versions, and System Architectural Roles")
    stack_headers = ["Layer / Subsystem", "Technology / Framework", "Version", "Architectural Role in Biome Enterprise RAG"]
    stack_data = [
        ["Core Language Runtime", "Python", "v3.11.9+", "Underlying high-performance asynchronous runtime for all backend pipelines."],
        ["Backend REST Framework", "FastAPI", "v0.115.0", "Asynchronous HTTP routing, Pydantic data validation, and OpenAPI documentation."],
        ["Visual Document Parser", "IBM Docling", "v2.0.0+", "Layout-aware parsing, bounding-box detection, and Markdown table extraction."],
        ["Document Chunker", "Docling HybridChunker", "v2.0+", "Structure-aware chunking with heading prefix injection and table header repetition."],
        ["Conversational Chunker", "Chonkie SentenceChunker", "v0.4.0+", "Fast token-budgeted sentence-level chunking for Slack and database entities."],
        ["Multi-Vector Embeddings", "BAAI/bge-m3", "v2.0", "Generates 1024-dim dense semantic embeddings + sparse token-weighted lexical vectors."],
        ["Cross-Encoder Reranker", "BAAI/bge-reranker-v2-m3", "v2.0", "Full-attention cross-encoder scoring top-30 candidates down to top-5."],
        ["Vector Database", "Qdrant", "v1.10.0", "High-concurrency vector store supporting native hybrid prefetch and RRF fusion."],
        ["Lexical Search Index", "BM25 (Custom Engine)", "Internal", "Inverted index providing token-frequency keyword matching for exact technical codes."],
        ["Session Memory Store", "Redis", "v7.2.0+", "In-memory key-value store managing sliding-window chat history (RPUSH + LTRIM)."],
        ["Local LLM Inference", "Ollama / Llama 3.1 8B", "v0.3.0+", "Local, sovereign generative inference providing high-faithfulness synthesis."],
        ["Cloud LLM Inference", "Groq / OpenAI API", "Cloud", "Optional high-throughput cloud inference with graceful offline fallback."],
        ["Pipeline Orchestration", "Prefect", "v3.0.0+", "Automated workflow management, task scheduling, and error retry graphs."],
        ["Observability & Tracing", "Langfuse", "v2.0.0+", "Full request-level tracing, latency telemetry, token accounting, and user feedback."],
        ["Evaluation Framework", "Ragas + DeepEval", "v0.1.20+", "Evaluation harness computing Faithfulness, Context Precision, Recall, and Hallucination."],
        ["Frontend UI Framework", "React + Vite", "v18.3 / v5.4", "Single-Page Application providing dark glassmorphism, chat studio, and analytics."],
        ["Frontend Styling", "Tailwind CSS", "v4.0+", "Curated Emerald design tokens, responsive typography, and glassmorphic micro-animations."]
    ]
    create_styled_table(doc, stack_headers, stack_data, col_widths=[3.5, 3.8, 1.8, 7.15])
    
    # 1.6 Industrial Relevance & Benefits
    add_heading_2(doc, "1.6 Industrial Relevance and Economic Benefits to Synergy Telecom (P) LTD")
    add_body_p(doc, 
        "The practical deployment of the Biome Enterprise RAG system yields profound commercial, operational, and technical dividends "
        "for Synergy Telecom (P) LTD. Historically, when high-value telecommunication infrastructure tenders or client RFQs arrived, "
        "sales engineering teams were forced to manually cross-reference customer requirements across dozens of PDF catalogs and internal "
        "ERP records. This manual verification process introduced significant delays—often taking 2 to 3 business days per complex RFQ—and "
        "carried an inherent risk of human error in part code selection."
    )
    
    add_body_p(doc, 
        "With the implementation of Biome's Neural Copilot and Hybrid Retrieval Arena, sales and technical support personnel can query the "
        "system using natural language or exact part codes, receiving fully verified, citation-backed technical responses in less than 500 "
        "milliseconds. Furthermore, the NL2SQL Studio enables engineering leads to query PostgreSQL operational databases—such as retrieving "
        "RMA failure rates or base station jumper inspection backlogs—without writing manual SQL queries or compromising tenant access boundaries."
    )
    
    add_body_p(doc, 
        "A formal economic impact analysis conducted as part of this project indicates that deploying Biome across Synergy Telecom's technical "
        "workforce of 50 knowledge workers reclaims an estimated 6,144 engineering hours annually, yielding direct labor savings of $184,320 per "
        "year with an estimated capital payback period of just 1.4 months."
    )
    
    # 1.7 Organization of the Report
    add_heading_2(doc, "1.7 Organization of the Report")
    add_body_p(doc, 
        "This Summer Training Report is systematically organized into four major chapters, followed by academic references and technical appendices:"
    )
    
    ch_overview = [
        ("Chapter 1 — Introduction: ", "Establishes the corporate profile of Synergy Telecom (P) LTD, articulates the enterprise dark data crisis, defines the formal technical problem statement, details the technological stack, and quantifies industrial benefits."),
        ("Chapter 2 — Project Architecture, Engineering & System Design: ", "Presents an exhaustive technical breakdown of the offline data ingestion pipeline and online query pipeline. Analyzes multi-source connectors, IBM Docling parsing, context-aware chunking, BGE-M3 multi-vector representations, Qdrant hybrid indexing, Reciprocal Rank Fusion (RRF), cross-encoder re-ranking, sandboxed NL2SQL with programmatic row-level ACL, and Redis session memory."),
        ("Chapter 3 — User Interface & Implementation Details: ", "Chronicles the frontend architectural evolution from Streamlit to React 18 + Vite, detailing the design system and providing comprehensive visual explanations for all six application modules (Neural Copilot, Retrieval Arena, NL2SQL Studio, Knowledge Base, ROI Calculator, and Ablation Explorer), alongside FastAPI backend routing contracts and Langfuse observability telemetry."),
        ("Chapter 4 — Discussion, Evaluation & Future Scope: ", "Presents the empirical evaluation methodology over a 55-question golden dataset, details the execution and results of an 18-arm ablation study, analyzes latency and hardware profiling, discusses real-world engineering hurdles and mitigations, outlines future technological extensions, and concludes the study."),
        ("References & Appendices: ", "Provides formal IEEE bibliographic citations and comprehensive appendices containing production environment configurations, Pydantic schemas, grounding prompts, and sample golden evaluation records.")
    ]
    for ch_lbl, ch_desc in ch_overview:
        add_bullet_p(doc, ch_desc, bold_prefix=ch_lbl)
