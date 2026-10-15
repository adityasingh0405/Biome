import docx
import os
from docx.shared import Pt, Cm, RGBColor
from styles import (
    add_body_p, add_bullet_p, add_heading_1, add_heading_2, add_heading_3,
    create_styled_table, add_table_caption, add_figure_caption, add_callout_box
)

def build_chapter_3(doc):
    """Constructs Chapter 3: User Interface & Implementation Details."""
    
    # Chapter Title
    add_heading_1(doc, "CHAPTER 3: USER INTERFACE & IMPLEMENTATION DETAILS", is_chapter=True)
    
    # 3.1 Frontend Architectural Evolution
    add_heading_2(doc, "3.1 Frontend Architectural Evolution (Streamlit to React 18 + Vite SPA)")
    add_body_p(doc, 
        "During the initial exploratory phase of the project, a rapid prototype dashboard was developed utilizing Streamlit (streamlit_app.py). "
        "While Streamlit allowed rapid verification of Python retrieval scripts, it quickly proved inadequate for enterprise deployment at "
        "Synergy Telecom. Streamlit executes a complete top-to-bottom script rerun upon every user interaction, introducing noticeable UI latency, "
        "preventing smooth token streaming, and making it impossible to render complex multi-column comparison arenas or custom dark-glassmorphic "
        "aesthetics required by executive stakeholders."
    )
    
    add_body_p(doc, 
        "To provide a commercial-grade, responsive user experience, the entire frontend was re-architected as a decoupled Single-Page Application (SPA) "
        "built with React 18, Vite 5.4, and Tailwind CSS v4. The application communicates asynchronously with the FastAPI backend via standard REST "
        "endpoints and Server-Sent Events (SSE). The frontend codebase is organized modularly under frontend/src/components, separating view state, "
        "interactive business logic, and API client adapters."
    )

    # 3.2 Design System & Aesthetics
    add_heading_2(doc, "3.2 Design System, Dark Glassmorphism & Visual Aesthetics")
    add_body_p(doc, 
        "The user interface adheres to a curated dark glassmorphism design system inspired by modern industrial command centers. "
        "Key aesthetic tokens include:"
    )
    
    design_tokens = [
        ("Color Palette: ", 
         "Built on a Deep Slate background canvas (#0F172A and #1E293B) accented with vibrant Emerald Green (#10B981 and #059669) as the primary "
         "action and status indicator, symbolizing precision and system health. Secondary accents include Sky Blue (#38BDF8) for technical citations, "
         "Purple (#8B5CF6) for observability metadata, and Amber/Rose (#F59E0B / #EF4444) for system alerts and security restrictions."),
        
        ("Glassmorphic Depth & Elevation: ", 
         "Cards and panels utilize semi-transparent backdrop filters (backdrop-blur-md) with subtle 1px border strokes (#334155), creating visual "
         "hierarchy and separation without heavy solid dividers."),
        
        ("Responsive Typography & Micro-Interactions: ", 
         "Standardized on clean geometric sans-serif typography with high contrast ratios (WCAG AAA compliant), complemented by smooth transition "
         "animations for hover states, modal dialogues, and real-time status badges.")
    ]
    for d_lbl, d_desc in design_tokens:
        add_bullet_p(doc, d_desc, bold_prefix=d_lbl)
        
    add_table_caption(doc, "Table 3.1", "Frontend UI Component Hierarchy, View Architecture, and State Management Protocols")
    comp_headers = ["Module Component", "File Location", "Primary Functional Responsibility", "State Management & API Integration"]
    comp_data = [
        ["Neural Copilot", "frontend/.../ChatView.jsx", "Multi-turn conversational chat, citation pills, confidence radar", "React useState + LocalStorage + /v1/chat API"],
        ["Retrieval Arena", "frontend/.../CompareView.jsx", "Side-by-side comparative inspection (Hybrid RRF vs Dense)", "Synchronous dual-fetch calling /v1/compare"],
        ["NL2SQL Studio", "frontend/.../SqlView.jsx", "Natural language query console, schema browser, department ACL", "Interactive SQL execution calling /v1/ask (route: sql)"],
        ["Knowledge Base Hub", "frontend/.../KnowledgeBaseView.jsx", "Document catalog, drag-drop uploader, indexing crawler", "REST integration with /v1/documents & /v1/index"],
        ["ROI Calculator", "frontend/.../RoiCalculatorView.jsx", "Dynamic financial modeling, hours reclaimed, payback multiples", "Pure client-side reactive mathematical simulation engine"],
        ["Ablation Explorer", "frontend/.../AblationView.jsx", "Interactive 18-arm ablation data grid, metric filters, sorting", "Loads and sorts benchmark data from ABLATION_RESULTS.md"]
    ]
    create_styled_table(doc, comp_headers, comp_data, col_widths=[3.2, 4.0, 4.8, 4.25])

    # 3.3 Module 1: Neural Copilot
    add_heading_2(doc, "3.3 Module 1: Neural Copilot (Conversational Chat Studio)")
    add_body_p(doc, 
        "The Neural Copilot serves as the primary conversational interface for Synergy Telecom personnel. It provides an intuitive, ChatGPT-style "
        "dialogue window powered by the FastAPI /v1/chat endpoint with Redis-backed session memory. Figure 3.1 displays the Neural Copilot interface "
        "resolving a technical RF connector query."
    )
    
    # Embed Figure 3.1
    copilot_img = "scripts/report_gen/assets/fig3_1_neural_copilot_chat.png"
    if os.path.exists(copilot_img):
        p_img = doc.add_paragraph()
        p_img.alignment = docx.enum.text.WD_PARAGRAPH_ALIGNMENT.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture(copilot_img, width=Cm(15.5))
        add_figure_caption(doc, "Figure 3.1", "Neural Copilot Studio: Conversational Chat Interface with Real-time Inline Citations and Confidence Radar")

    add_body_p(doc, 
        "As illustrated in Figure 3.1, key features of the Neural Copilot include:"
    )
    chat_features = [
        ("Session Management Sidebar: ", "Allows users to create, switch between, and delete named conversational sessions, persisted across browser refreshes."),
        ("Route Intelligence Badge: ", "Displays whether the query was classified as RouteDecision.SEMANTIC (hybrid RAG) or RouteDecision.STRUCTURED (NL2SQL)."),
        ("Verified Inline Citation Pills: ", "Generated answers include clickable citation tags ([1✓], [2✓]). Clicking a pill reveals the underlying document snippet, author, and exact heading breadcrumb in an inspectable side drawer."),
        ("Confidence Radar & Telemetry Box: ", "Renders real-time metrics including composite confidence score (e.g., 0.94), citation verification percentage (100%), retrieval mode (Hybrid RRF k=60), Langfuse trace ID, and token latency.")
    ]
    for c_lbl, c_desc in chat_features:
        add_bullet_p(doc, c_desc, bold_prefix=c_lbl)

    # 3.4 Module 2: Retrieval Arena
    add_heading_2(doc, "3.4 Module 2: Hybrid vs Dense Comparative Retrieval Arena")
    add_body_p(doc, 
        "To empirically demonstrate the superiority of hybrid retrieval to executive leadership, the Retrieval Arena provides a split-screen "
        "comparison console calling the /v1/compare endpoint. Figure 3.2 illustrates the Arena evaluating an exact part number query: "
        "'Find connector part code SY-DIN-M-716 and dielectric breakdown voltage'."
    )
    
    # Embed Figure 3.2
    arena_img = "scripts/report_gen/assets/fig3_2_arena_comparison.png"
    if os.path.exists(arena_img):
        p_img = doc.add_paragraph()
        p_img.alignment = docx.enum.text.WD_PARAGRAPH_ALIGNMENT.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture(arena_img, width=Cm(15.5))
        add_figure_caption(doc, "Figure 3.2", "Retrieval Arena: Side-by-Side Comparative Inspection of Hybrid RRF vs Dense-Only Search on Exact Part Codes")

    add_body_p(doc, 
        "Figure 3.2 highlights the dramatic performance disparity: Hybrid search achieves 100% precision, placing the exact datasheet at Rank 1 "
        "via BM25 token boost. In sharp contrast, Dense-Only search projects the exact alphanumeric code near general impedance articles, "
        "completely failing to retrieve the required part datasheet in the top 3 candidates."
    )

    # 3.5 Module 3: NL2SQL Studio
    add_heading_2(doc, "3.5 Module 3: NL2SQL & Programmatic ACL Console")
    add_body_p(doc, 
        "The NL2SQL Studio allows authorized operational personnel to execute analytical queries over relational tables (such as enterprise_tickets) "
        "using plain English. Figure 3.3 illustrates the execution of an RMA ticket aggregation query under simulated department-level access control."
    )
    
    # Embed Figure 3.3
    sql_img = "scripts/report_gen/assets/fig3_3_sql_studio.png"
    if os.path.exists(sql_img):
        p_img = doc.add_paragraph()
        p_img.alignment = docx.enum.text.WD_PARAGRAPH_ALIGNMENT.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture(sql_img, width=Cm(15.5))
        add_figure_caption(doc, "Figure 3.3", "NL2SQL & Programmatic ACL Studio: Interactive SQL Console, Injected Subquery Viewer, and Tabular Results")

    add_body_p(doc, 
        "As shown in Figure 3.3, the console displays: (1) the active user access scope; (2) the AST and semicolon validation badges; (3) the "
        "programmatically injected SQL query demonstrating the subquery injection; and (4) the rendered Markdown results table returned from PostgreSQL "
        "in 14.2 milliseconds."
    )

    # 3.6 Module 4: Knowledge Base Hub
    add_heading_2(doc, "3.6 Module 4: Multi-Source Knowledge Base & Ingestion Hub")
    add_body_p(doc, 
        "The Knowledge Base Hub provides administrators with real-time operational visibility into data synchronization status across PostgreSQL, "
        "Slack, and MinIO. Figure 3.4 shows the active ingestion catalog."
    )
    
    # Embed Figure 3.4
    kb_img = "scripts/report_gen/assets/fig3_4_knowledge_base.png"
    if os.path.exists(kb_img):
        p_img = doc.add_paragraph()
        p_img.alignment = docx.enum.text.WD_PARAGRAPH_ALIGNMENT.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture(kb_img, width=Cm(15.5))
        add_figure_caption(doc, "Figure 3.4", "Enterprise Knowledge Base: Multi-Source Document Catalog & Real-Time Sync Status Hub")

    add_body_p(doc, 
        "The hub includes top-level health summary cards displaying total synced records (14,280 SQL rows, 1,420 Slack threads, 852 documents), "
        "alongside an interactive data table displaying document names, formats, parsing engines, chunking strategies, total chunks, and vector index sync."
    )

    # 3.7 Module 5: ROI Calculator
    add_heading_2(doc, "3.7 Module 5: Enterprise ROI & Financial Savings Calculator")
    add_body_p(doc, 
        "To articulate the business value of AI engineering to corporate leadership, the frontend features an interactive ROI & Economic Calculator. "
        "Figure 3.5 depicts the financial modeling console."
    )
    
    # Embed Figure 3.5
    roi_img = "scripts/report_gen/assets/fig3_5_roi_calculator.png"
    if os.path.exists(roi_img):
        p_img = doc.add_paragraph()
        p_img.alignment = docx.enum.text.WD_PARAGRAPH_ALIGNMENT.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture(roi_img, width=Cm(15.5))
        add_figure_caption(doc, "Figure 3.5", "Enterprise ROI Calculator: Dynamic Financial Modeling of Knowledge Worker Time Savings and Capital Payback")

    add_body_p(doc, 
        "As demonstrated in Figure 3.5, based on 50 knowledge workers at an average loaded rate of $30/hour, reducing document search time by 75% "
        "reclaims 6,144 engineering hours annually, producing $184,320 in net value creation with a payback period of just 1.4 months."
    )

    # 3.8 Module 6: Ablation Explorer
    add_heading_2(doc, "3.8 Module 6: 18-Arm Ablation Benchmark Explorer")
    add_body_p(doc, 
        "The Ablation Explorer visualizes the results of the 18-arm empirical study conducted in Phase 7. Figure 3.6 presents the interactive data table."
    )
    
    # Embed Figure 3.6
    ab_img = "scripts/report_gen/assets/fig3_6_ablation_explorer.png"
    if os.path.exists(ab_img):
        p_img = doc.add_paragraph()
        p_img.alignment = docx.enum.text.WD_PARAGRAPH_ALIGNMENT.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture(ab_img, width=Cm(15.5))
        add_figure_caption(doc, "Figure 3.6", "18-Arm Ablation Benchmark Explorer: Interactive Quality Metric Visualizer & Empirical Data Grid")

    # 3.9 Backend API Architecture
    add_heading_2(doc, "3.9 Backend API Architecture & FastAPI Routing Contracts")
    add_body_p(doc, 
        "The application layer is implemented in Python utilizing FastAPI, providing high-concurrency asynchronous execution, automatic OpenAPI schema "
        "generation, and strict Pydantic payload validation. Table 3.2 details the primary REST endpoints, payload schemas, and service level agreements (SLAs)."
    )
    
    add_table_caption(doc, "Table 3.2", "Core FastAPI REST API Endpoints, HTTP Methods, Payload Schemas, and Response SLA")
    api_headers = ["Endpoint Route", "HTTP Method", "Request Payload Schema", "Response Contract", "Target Service SLA"]
    api_data = [
        ["/v1/ask", "POST", "AskRequest (question, route_override, requester_scope)", "AskResponse (answer, citations, confidence, route)", "< 450 ms"],
        ["/v1/chat", "POST", "ChatRequest (question, session_id, requester_scope)", "ChatResponse (answer, citations, confidence, session_id)", "< 550 ms"],
        ["/v1/compare", "POST", "CompareRequest (question, top_k=5)", "CompareResponse (hybrid_result, dense_result, latency_ms)", "< 350 ms"],
        ["/v1/evaluate", "POST", "EvaluateRequest (golden_path, thresholds_preset)", "EvaluateResponse (metrics, arm_id, quality_gate_pass)", "< 25.0 s"],
        ["/v1/documents", "GET", "Query params (source_type, limit, offset)", "DocumentListResponse (documents, total_count, sync_status)", "< 50 ms"],
        ["/v1/session/{id}", "DELETE", "Path parameter (session_id string)", "StatusMessage (status: 'session_cleared_from_redis')", "< 15 ms"]
    ]
    create_styled_table(doc, api_headers, api_data, col_widths=[2.8, 2.2, 4.8, 4.4, 2.05])

    # 3.10 Observability via Langfuse
    add_heading_2(doc, "3.10 Observability, Request Tracing & Telemetry via Langfuse")
    add_body_p(doc, 
        "In production enterprise systems, black-box AI behavior is unacceptable. Biome embeds Langfuse request-level observability "
        "(LangfuseTracer) directly into the API request lifecycle. Every invocation of /v1/ask or /v1/chat generates a unique trace_id "
        "containing nested telemetry spans: (1) retrieval span, recording query embeddings, Qdrant search latency, and top-k similarity scores; "
        "(2) re-ranking span, logging cross-encoder logit distributions; and (3) generation span, tracking prompt token counts, completion tokens, "
        "and time-to-first-token (TTFT). Operators can inspect these traces in real time via the self-hosted Langfuse dashboard at http://localhost:3000."
    )
