import os
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = "scripts/report_gen/assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

# Set global matplotlib parameters for high academic quality
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman', 'DejaVu Serif', 'Liberation Serif']
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.titlesize'] = 14

def generate_ablation_chart():
    """Generates Figure 4.1: Composite Score Comparison Across 18 Experimental Arms."""
    arms = [
        "hybrid_k10_no_rerank", "dense_k3_no_rerank", "hybrid_k5_no_rerank",
        "hybrid_k3_no_rerank", "dense_k5_no_rerank", "dense_k10_no_rerank",
        "hybrid_k10_rerank", "hybrid_k5_rerank", "hybrid_k3_rerank",
        "sparse_k10_no_rerank", "dense_k3_rerank", "dense_k5_rerank",
        "dense_k10_rerank", "sparse_k5_no_rerank", "sparse_k3_no_rerank",
        "sparse_k10_rerank", "sparse_k5_rerank", "sparse_k3_rerank"
    ]
    scores = [
        0.4721, 0.4549, 0.4544, 0.4541, 0.4530, 0.4530,
        0.4003, 0.3981, 0.3894, 0.3840, 0.3725, 0.3718,
        0.3718, 0.3659, 0.3419, 0.3110, 0.3051, 0.2952
    ]
    colors = []
    for arm in arms:
        if "hybrid" in arm:
            colors.append("#059669") # Emerald / Hybrid
        elif "dense" in arm:
            colors.append("#2563EB") # Blue / Dense
        else:
            colors.append("#D97706") # Amber / Sparse

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    y_pos = np.arange(len(arms))
    ax.barh(y_pos, scores[::-1], color=colors[::-1], edgecolor='black', linewidth=0.6, height=0.7)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(arms[::-1], fontsize=9)
    ax.set_xlabel("Composite Evaluation Score", fontweight='bold')
    ax.set_title("Comprehensive Evaluation Leaderboard Across 18 Experimental Ablation Arms", fontweight='bold', pad=12)
    ax.set_xlim(0.25, 0.50)
    ax.grid(axis='x', linestyle='--', alpha=0.6)

    # Highlight winner
    ax.text(0.473, 17, "WINNER (0.4721)", color="#047857", fontweight='bold', va='center', fontsize=9)

    # Custom legend
    import matplotlib.patches as mpatches
    hybrid_patch = mpatches.Patch(color='#059669', label='Hybrid Retrieval (RRF)')
    dense_patch = mpatches.Patch(color='#2563EB', label='Dense-Only Retrieval')
    sparse_patch = mpatches.Patch(color='#D97706', label='Sparse-Only Retrieval (BM25)')
    ax.legend(handles=[hybrid_patch, dense_patch, sparse_patch], loc='lower right', framealpha=0.95)

    plt.tight_layout()
    out_path = os.path.join(ASSETS_DIR, "fig4_1_ablation_leaderboard.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Generated {out_path}")

def generate_retrieval_comparison_chart():
    """Generates Figure 4.2: Retrieval Mode Comparison: Exact-Term vs Paraphrased Recall."""
    modes = ['Hybrid (BGE-M3 + BM25)', 'Dense-Only (BGE-M3)', 'Sparse-Only (BM25)']
    exact_recall = [100.0, 42.0, 98.0]
    paraphrase_recall = [94.0, 92.0, 58.0]
    mean_relevance = [91.0, 76.0, 69.0]

    x = np.arange(len(modes))
    width = 0.25

    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=300)
    rects1 = ax.bar(x - width, exact_recall, width, label='Exact Technical Term Recall (%)', color='#0284C7', edgecolor='black', linewidth=0.6)
    rects2 = ax.bar(x, paraphrase_recall, width, label='Paraphrased Query Recall (%)', color='#10B981', edgecolor='black', linewidth=0.6)
    rects3 = ax.bar(x + width, mean_relevance, width, label='Mean Context Relevance (%)', color='#8B5CF6', edgecolor='black', linewidth=0.6)

    ax.set_ylabel('Recall and Relevance Rate (%)', fontweight='bold')
    ax.set_title('Comparative Retrieval Effectiveness Across Technical and Paraphrased Queries', fontweight='bold', pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(modes, fontweight='bold', fontsize=9.5)
    ax.legend(loc='upper right', framealpha=0.95)
    ax.set_ylim(0, 115)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.0f}%',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=8.5, fontweight='bold')

    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)

    plt.tight_layout()
    out_path = os.path.join(ASSETS_DIR, "fig4_2_retrieval_comparison.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Generated {out_path}")

def generate_latency_chart():
    """Generates Figure 4.3: Latency vs Context Window Depth."""
    top_k = [3, 5, 10]
    hybrid_no_rerank = [19.15, 19.55, 19.18]
    dense_no_rerank = [18.50, 18.18, 20.02]
    sparse_no_rerank = [18.31, 20.94, 19.99]
    hybrid_rerank = [27.88, 28.12, 29.22]
    dense_rerank = [30.93, 20.56, 20.15]

    fig, ax = plt.subplots(figsize=(8.5, 4.6), dpi=300)
    ax.plot(top_k, hybrid_no_rerank, marker='o', linewidth=2, color='#059669', label='Hybrid (No Rerank)')
    ax.plot(top_k, dense_no_rerank, marker='s', linewidth=2, color='#2563EB', label='Dense (No Rerank)')
    ax.plot(top_k, sparse_no_rerank, marker='^', linewidth=2, color='#D97706', label='Sparse (No Rerank)')
    ax.plot(top_k, hybrid_rerank, marker='D', linewidth=2, linestyle='--', color='#DC2626', label='Hybrid + Cross-Encoder Rerank')
    ax.plot(top_k, dense_rerank, marker='v', linewidth=2, linestyle='--', color='#7C3AED', label='Dense + Cross-Encoder Rerank')

    ax.set_xlabel('Context Depth (Top-k Candidate Chunks)', fontweight='bold')
    ax.set_ylabel('Total Evaluation Latency per Question (Seconds)', fontweight='bold')
    ax.set_title('End-to-End Evaluation Latency Across Retrieval Depth and Reranking Modes', fontweight='bold', pad=12)
    ax.set_xticks(top_k)
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='center left', framealpha=0.95)
    ax.set_ylim(15, 35)

    plt.tight_layout()
    out_path = os.path.join(ASSETS_DIR, "fig4_3_latency_analysis.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Generated {out_path}")

def generate_radar_chart():
    """Generates Figure 4.4: Radar Plot of Core RAG Metrics."""
    categories = ['Faithfulness', 'Context Precision', 'Context Recall', 'Answer Relevancy', 'Semantic Similarity']
    N = len(categories)

    # Values for winner arm (hybrid_k10_no_rerank) vs dense_k3_no_rerank vs sparse_k3_no_rerank
    winner_vals = [0.773, 0.780, 0.642, 0.402, 0.510]
    dense_vals = [0.733, 0.833, 0.440, 0.408, 0.523]
    sparse_vals = [0.717, 0.721, 0.270, 0.197, 0.261]

    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    winner_vals += winner_vals[:1]
    dense_vals += dense_vals[:1]
    sparse_vals += sparse_vals[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 5.5), subplot_kw=dict(polar=True), dpi=300)
    plt.xticks(angles[:-1], categories, color='black', size=10, fontweight='bold')
    ax.set_rlabel_position(0)
    plt.yticks([0.2, 0.4, 0.6, 0.8, 1.0], ["0.2", "0.4", "0.6", "0.8", "1.0"], color="grey", size=8)
    plt.ylim(0, 1.0)

    ax.plot(angles, winner_vals, linewidth=2, linestyle='solid', label='Winner: Hybrid (k=10)', color='#059669')
    ax.fill(angles, winner_vals, '#059669', alpha=0.15)

    ax.plot(angles, dense_vals, linewidth=2, linestyle='dashed', label='Runner-Up: Dense (k=3)', color='#2563EB')
    ax.fill(angles, dense_vals, '#2563EB', alpha=0.1)

    ax.plot(angles, sparse_vals, linewidth=2, linestyle='dotted', label='Baseline: Sparse (k=3)', color='#D97706')
    ax.fill(angles, sparse_vals, '#D97706', alpha=0.05)

    plt.title('Multi-Dimensional Quality Metric Radar: Hybrid vs Dense vs Sparse', size=12, fontweight='bold', y=1.1)
    plt.legend(loc='upper right', bbox_to_anchor=(1.25, 0.15), framealpha=0.95)

    plt.tight_layout()
    out_path = os.path.join(ASSETS_DIR, "fig4_4_radar_metrics.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Generated {out_path}")

def generate_ui_mockups():
    """Generates clean, aesthetic UI module illustrations matching the React frontend."""
    # 1. Neural Copilot Chat View
    w, h = 1200, 750
    img = Image.new('RGB', (w, h), color='#0F172A')
    draw = ImageDraw.Draw(img)

    # Top Navbar
    draw.rectangle([0, 0, w, 60], fill='#1E293B')
    draw.text((30, 20), "🌿 BIOME ENTERPRISE RAG  |  Neural Copilot Studio", fill='#10B981')
    draw.text((w - 280, 20), "Connected: Qdrant + Redis + Ollama (Llama 3.1 8B)", fill='#94A3B8')

    # Sidebar
    draw.rectangle([0, 60, 260, h], fill='#111827')
    draw.text((25, 80), "CONVERSATION SESSIONS", fill='#64748B')
    draw.rectangle([15, 110, 245, 150], fill='#1E293B', outline='#10B981', width=1)
    draw.text((25, 122), "- Session #048: RFQ Cable Specs", fill='#F8FAFC')
    draw.rectangle([15, 160, 245, 200], fill='#1E293B')
    draw.text((25, 172), "- Session #047: Coaxial Impedance", fill='#94A3B8')
    draw.rectangle([15, 210, 245, 250], fill='#1E293B')
    draw.text((25, 222), "- Session #046: ISO 9001 Compliance", fill='#94A3B8')

    # Main Chat Area
    draw.rectangle([280, 80, w - 30, 200], fill='#1E293B', outline='#334155', width=1)
    draw.text((300, 95), "User Query:", fill='#38BDF8')
    draw.text((300, 125), "\"What are the maximum voltage standing wave ratio (VSWR) limits for our 7/16 DIN connectors at 3 GHz?\"", fill='#F1F5F9')
    draw.rectangle([300, 160, 480, 185], fill='#064E3B', outline='#059669', width=1)
    draw.text((310, 165), "Route: SEMANTIC [Hybrid RAG]", fill='#34D399')

    # Response Box
    draw.rectangle([280, 220, w - 30, 620], fill='#1E293B', outline='#10B981', width=2)
    draw.text((300, 240), "Neural Copilot Grounded Response:", fill='#10B981')
    res_text = (
        "According to the Synergy Telecom RF Component Technical Specification Document [1],\n"
        "the maximum Voltage Standing Wave Ratio (VSWR) for 7/16 DIN Connectors operating up to 3.0 GHz is 1.15:1 [1].\n"
        "For precision BTS jumper assemblies operating under extreme climatic conditions (-40°C to +85°C),\n"
        "the insertion loss is certified at ≤ 0.05 dB per connector interface [2].\n\n"
        "Key Compliance Parameters (Table 4.2 of Product Catalog):\n"
        " - Characteristic Impedance: 50 Ohms (nominal) [1]\n"
        " - Frequency Range: DC to 7.5 GHz [1]\n"
        " - Intermodulation (PIM3 @ 2x20W): ≤ -160 dBc [2]\n"
        " - Dielectric Withstanding Voltage: 4,000 V RMS, 50 Hz [1]"
    )
    y_text = 275
    for line in res_text.split('\n'):
        draw.text((300, y_text), line, fill='#E2E8F0')
        y_text += 24

    # Confidence Radar and Verification pill
    draw.rectangle([300, 540, 520, 595], fill='#0F172A', outline='#059669', width=1)
    draw.text((315, 550), "Confidence Score: 0.94 / 1.00", fill='#34D399')
    draw.text((315, 570), "Citations: 2 Verified [1, 2] (100%)", fill='#94A3B8')

    draw.rectangle([540, 540, 780, 595], fill='#0F172A', outline='#3B82F6', width=1)
    draw.text((555, 550), "Retrieval Mode: Hybrid (RRF k=60)", fill='#60A5FA')
    draw.text((555, 570), "Reranker: BGE-Reranker-v2-M3", fill='#94A3B8')

    draw.rectangle([800, 540, w - 50, 595], fill='#0F172A', outline='#8B5CF6', width=1)
    draw.text((815, 550), "Observability: Langfuse Traced", fill='#A78BFA')
    draw.text((815, 570), "Latency: 284ms | Tokens: 342", fill='#94A3B8')

    # Input Bar
    draw.rectangle([280, 645, w - 30, 715], fill='#0F172A', outline='#334155', width=1)
    draw.text((300, 670), "Ask anything about telecom catalogs, engineering drawings, or operational tickets...", fill='#64748B')
    draw.rectangle([w - 140, 655, w - 45, 705], fill='#10B981')
    draw.text((w - 120, 672), "Send ->", fill='#0F172A')

    out_path = os.path.join(ASSETS_DIR, "fig3_1_neural_copilot_chat.png")
    img.save(out_path, dpi=(300, 300))
    print(f"Generated {out_path}")

    # 2. Side-by-Side Arena View
    img_arena = Image.new('RGB', (w, h), color='#0F172A')
    draw_a = ImageDraw.Draw(img_arena)
    draw_a.rectangle([0, 0, w, 60], fill='#1E293B')
    draw_a.text((30, 20), "🌿 BIOME RETRIEVAL ARENA  |  Hybrid (RRF) vs Dense-Only Head-to-Head", fill='#10B981')

    # Query
    draw_a.rectangle([30, 80, w - 30, 130], fill='#1E293B', outline='#334155', width=1)
    draw_a.text((50, 98), "Test Query: \"Find connector part code SY-DIN-M-716 and dielectric breakdown voltage\"", fill='#F8FAFC')

    # Left Column: Hybrid Search
    draw_a.rectangle([30, 150, 585, 700], fill='#1E293B', outline='#10B981', width=2)
    draw_a.text((50, 170), "⚡ HYBRID RETRIEVAL (BGE-M3 Dense + Sparse + RRF)", fill='#34D399')
    draw_a.text((50, 195), "Exact Keyword Recall: 100% | Mean Precision: 0.94", fill='#94A3B8')

    draw_a.rectangle([50, 230, 565, 360], fill='#0F172A', outline='#059669', width=1)
    draw_a.text((65, 245), "Rank 1 [RRF Score: 0.0328] — EXACT MATCH", fill='#10B981')
    draw_a.text((65, 270), "Doc: Synergy_RF_Catalog_2026.pdf (Section 3.4)", fill='#38BDF8')
    draw_a.text((65, 295), "Snippet: Part 'SY-DIN-M-716': 7/16 DIN Male connector\nfor 1/2 inch flexible feeder cable. Breakdown: 4000 V RMS.", fill='#E2E8F0')

    draw_a.rectangle([50, 380, 565, 510], fill='#0F172A', outline='#334155', width=1)
    draw_a.text((65, 395), "Rank 2 [RRF Score: 0.0294]", fill='#94A3B8')
    draw_a.text((65, 420), "Doc: BTS_Installation_Manual_Rev4.docx", fill='#38BDF8')
    draw_a.text((65, 445), "Snippet: Jumper interface grounding procedures for\nSY-DIN series connectors at cellular base station towers.", fill='#E2E8F0')

    draw_a.rectangle([50, 530, 565, 660], fill='#0F172A', outline='#334155', width=1)
    draw_a.text((65, 545), "Rank 3 [RRF Score: 0.0261]", fill='#94A3B8')
    draw_a.text((65, 570), "Doc: High_Power_Coaxial_Specs.html", fill='#38BDF8')
    draw_a.text((65, 595), "Snippet: Peak power handling capability and breakdown voltage\nratings across 7/16 DIN connector families.", fill='#E2E8F0')

    # Right Column: Dense-Only Search
    draw_a.rectangle([615, 150, w - 30, 700], fill='#1E293B', outline='#EF4444', width=2)
    draw_a.text((635, 170), "📐 DENSE-ONLY RETRIEVAL (BGE-M3 Cosine)", fill='#F87171')
    draw_a.text((635, 195), "Exact Keyword Recall: 42% (Missed exact code 'SY-DIN-M-716')", fill='#94A3B8')

    draw_a.rectangle([635, 230, w - 50, 360], fill='#0F172A', outline='#EF4444', width=1)
    draw_a.text((650, 245), "Rank 1 [Cosine: 0.684] — SEMANTIC PARAPHRASE", fill='#F87171')
    draw_a.text((650, 270), "Doc: General_Telecom_Glossary.md", fill='#38BDF8')
    draw_a.text((650, 295), "Snippet: High-frequency coaxial cables typically experience\ndielectric breakdown when voltage limits are exceeded.", fill='#E2E8F0')

    draw_a.rectangle([635, 380, w - 50, 510], fill='#0F172A', outline='#334155', width=1)
    draw_a.text((650, 395), "Rank 2 [Cosine: 0.662]", fill='#94A3B8')
    draw_a.text((650, 420), "Doc: Coaxial_Cables_Overview.pdf", fill='#38BDF8')
    draw_a.text((650, 445), "Snippet: Standard N-Type and BNC connectors operate\nat lower breakdown voltages compared to high-power DIN lines.", fill='#E2E8F0')

    draw_a.rectangle([635, 530, w - 50, 660], fill='#0F172A', outline='#334155', width=1)
    draw_a.text((650, 545), "Rank 3 [Cosine: 0.631]", fill='#94A3B8')
    draw_a.text((650, 570), "Doc: Electrical_Safety_Standards.pdf", fill='#38BDF8')
    draw_a.text((650, 595), "Snippet: Insulation resistance requirements for electrical\nsubstations and telecommunication towers.", fill='#E2E8F0')

    out_path_a = os.path.join(ASSETS_DIR, "fig3_2_arena_comparison.png")
    img_arena.save(out_path_a, dpi=(300, 300))
    print(f"Generated {out_path_a}")

    # 3. NL2SQL & Programmatic ACL Studio
    img_sql = Image.new('RGB', (w, h), color='#0F172A')
    draw_s = ImageDraw.Draw(img_sql)
    draw_s.rectangle([0, 0, w, 60], fill='#1E293B')
    draw_s.text((30, 20), "🌿 BIOME NL2SQL & ACL STUDIO  |  Sandboxed Execution with Programmatic Row-Level ACL", fill='#10B981')

    # Query bar
    draw_s.rectangle([30, 80, w - 30, 140], fill='#1E293B', outline='#334155', width=1)
    draw_s.text((50, 95), "Natural Language Query:", fill='#38BDF8')
    draw_s.text((50, 115), "\"Show the count of unresolved RF component RMA tickets and average resolution time grouped by priority\"", fill='#F8FAFC')

    # Guardrails and ACL scope badge
    draw_s.rectangle([30, 155, 420, 195], fill='#064E3B', outline='#059669', width=1)
    draw_s.text((45, 168), "Requester Scope: ['telecom_engineering', 'rf_lab']", fill='#34D399')
    draw_s.rectangle([440, 155, 780, 195], fill='#1E293B', outline='#3B82F6', width=1)
    draw_s.text((455, 168), "AST Guard: Read-Only SELECT | Semicolon Guard: Pass", fill='#60A5FA')
    draw_s.rectangle([800, 155, w - 30, 195], fill='#1E293B', outline='#8B5CF6', width=1)
    draw_s.text((815, 168), "Execution Limit: Injected LIMIT 50 | Timeout: 5.0s", fill='#A78BFA')

    # Injected SQL Box
    draw_s.rectangle([30, 215, w - 30, 365], fill='#111827', outline='#10B981', width=2)
    draw_s.text((50, 230), "Generated & Programmatically Secured SQL Query (Injected Row-Level ACL Subquery):", fill='#10B981')
    sql_code = (
        "SELECT priority, COUNT(*) AS ticket_count, ROUND(AVG(resolution_hours), 2) AS avg_resolution_hours\n"
        "FROM (\n"
        "    SELECT * FROM enterprise_tickets \n"
        "    WHERE lower(department) IN ('telecom_engineering', 'rf_lab')\n"
        ") AS enterprise_tickets\n"
        "WHERE status = 'unresolved'\n"
        "GROUP BY priority\n"
        "ORDER BY ticket_count DESC\n"
        "LIMIT 50;"
    )
    y_s = 255
    for line in sql_code.split('\n'):
        draw_s.text((50, y_s), line, fill='#38BDF8')
        y_s += 18

    # Tabular Results Box
    draw_s.rectangle([30, 385, w - 30, 715], fill='#1E293B', outline='#334155', width=1)
    draw_s.text((50, 405), "Sandboxed Execution Results (Database Table: enterprise_tickets):", fill='#F8FAFC')

    # Render Table
    headers = ["Priority", "Ticket Count", "Avg Resolution (Hours)", "Authorized Department Scope", "Status"]
    col_x = [60, 220, 420, 720, 1020]
    draw_s.rectangle([45, 435, w - 45, 470], fill='#0F172A')
    for idx, h_text in enumerate(headers):
        draw_s.text((col_x[idx], 445), h_text, fill='#34D399')

    rows = [
        ["CRITICAL", "14", "4.8 hrs", "telecom_engineering, rf_lab", "Active Inspection"],
        ["HIGH", "38", "16.4 hrs", "telecom_engineering, rf_lab", "In Triage"],
        ["MEDIUM", "92", "42.1 hrs", "telecom_engineering, rf_lab", "Queued"],
        ["LOW", "57", "86.5 hrs", "telecom_engineering, rf_lab", "Backlogged"]
    ]
    y_r = 480
    for r in rows:
        draw_s.rectangle([45, y_r, w - 45, y_r + 35], fill='#1E293B' if (y_r % 70 == 0) else '#182234')
        for idx, val in enumerate(r):
            draw_s.text((col_x[idx], y_r + 8), val, fill='#E2E8F0')
        y_r += 40

    draw_s.text((50, 670), "Telemetry: Query executed in 14.2ms against PostgreSQL 16. Programmatic ACL prevented cross-tenant leakage.", fill='#94A3B8')

    out_path_s = os.path.join(ASSETS_DIR, "fig3_3_sql_studio.png")
    img_sql.save(out_path_s, dpi=(300, 300))
    print(f"Generated {out_path_s}")

    # 4. Knowledge Base & Multi-Source Hub
    img_kb = Image.new('RGB', (w, h), color='#0F172A')
    draw_k = ImageDraw.Draw(img_kb)
    draw_k.rectangle([0, 0, w, 60], fill='#1E293B')
    draw_k.text((30, 20), "🌿 BIOME KNOWLEDGE BASE  |  Multi-Source Ingestion & Real-Time Sync Status", fill='#10B981')

    # 3 Source Cards
    sources = [
        ("PostgreSQL Database", "Active Sync (Watermark)", "14,280 Rows", "Status: Synced", "#10B981"),
        ("Slack Workspace", "Active Sync (Threads)", "1,420 Threads", "Status: Synced", "#10B981"),
        ("S3/MinIO Document Store", "IBM Docling Layout-Aware", "852 Documents", "Status: Synced", "#10B981")
    ]
    for idx, (title, sub, count, stat, col) in enumerate(sources):
        cx = 40 + idx * 380
        draw_k.rectangle([cx, 85, cx + 360, 205], fill='#1E293B', outline=col, width=2)
        draw_k.text((cx + 20, 105), title, fill='#F8FAFC')
        draw_k.text((cx + 20, 130), sub, fill='#94A3B8')
        draw_k.text((cx + 20, 155), count, fill='#38BDF8')
        draw_k.text((cx + 220, 155), stat, fill=col)

    # Document Catalog Table
    draw_k.rectangle([40, 230, w - 40, 710], fill='#1E293B', outline='#334155', width=1)
    draw_k.text((60, 250), "Document Ingestion Catalog & Hybrid Chunking Metadata:", fill='#F8FAFC')

    kb_headers = ["Document / Source Name", "Format", "Parser", "Chunking Strategy", "Chunks", "Vector Index"]
    kb_x = [60, 420, 520, 680, 920, 1030]
    draw_k.rectangle([55, 285, w - 55, 320], fill='#0F172A')
    for idx, h_text in enumerate(kb_headers):
        draw_k.text((kb_x[idx], 295), h_text, fill='#34D399')

    kb_rows = [
        ["Synergy_RF_Connectors_Catalog_2026.pdf", "PDF", "IBM Docling", "Docling HybridChunker", "312", "Dense+Sparse"],
        ["BTS_Coaxial_Jumper_Installation_Guide.docx", "DOCX", "IBM Docling", "Docling HybridChunker", "148", "Dense+Sparse"],
        ["RF_Passive_Components_Pricing_Q3.html", "HTML", "IBM Docling", "Oversized Table Split", "84", "Dense+Sparse"],
        ["enterprise_tickets (PostgreSQL)", "SQL", "SQLAlchemy", "Chonkie SentenceChunker", "420", "Dense+Sparse"],
        ["#engineering-rf-support (Slack)", "CHAT", "Slack SDK", "Chonkie SentenceChunker", "215", "Dense+Sparse"],
        ["Microwave_Dummy_Loads_Datasheet.pdf", "PDF", "IBM Docling", "Docling HybridChunker", "65", "Dense+Sparse"],
        ["ISO_9001_Quality_Audit_Procedures.pdf", "PDF", "IBM Docling", "Docling HybridChunker", "190", "Dense+Sparse"]
    ]
    y_k = 330
    for r in kb_rows:
        draw_k.rectangle([55, y_k, w - 55, y_k + 42], fill='#1E293B' if (y_k % 84 == 0) else '#182234')
        for idx, val in enumerate(r):
            draw_k.text((kb_x[idx], y_k + 12), val, fill='#E2E8F0')
        y_k += 48

    out_path_k = os.path.join(ASSETS_DIR, "fig3_4_knowledge_base.png")
    img_kb.save(out_path_k, dpi=(300, 300))
    print(f"Generated {out_path_k}")

    # 5. Enterprise ROI & Savings Calculator
    img_roi = Image.new('RGB', (w, h), color='#0F172A')
    draw_r = ImageDraw.Draw(img_roi)
    draw_r.rectangle([0, 0, w, 60], fill='#1E293B')
    draw_r.text((30, 20), "🌿 BIOME ROI & ECONOMIC CALCULATOR  |  Quantifying Enterprise Value Creation", fill='#10B981')

    # Top KPI summary cards
    kpis = [
        ("ANNUAL SAVINGS", "$184,320", "Direct labour reclaimed", "#10B981"),
        ("HOURS RECLAIMED", "6,144 Hrs", "Over 50 engineers/staff", "#38BDF8"),
        ("PAYBACK PERIOD", "1.4 Months", "Including compute/setup", "#F59E0B"),
        ("RFQ TIME ACCELERATION", "82% Faster", "From 4.5 hrs to 45 mins", "#8B5CF6")
    ]
    for idx, (title, val, desc, col) in enumerate(kpis):
        rx = 40 + idx * 280
        draw_r.rectangle([rx, 85, rx + 260, 215], fill='#1E293B', outline=col, width=2)
        draw_r.text((rx + 20, 105), title, fill='#94A3B8')
        draw_r.text((rx + 20, 135), val, fill=col)
        draw_r.text((rx + 20, 180), desc, fill='#CBD5E1')

    # Calculation parameters and breakdown
    draw_r.rectangle([40, 245, 560, 700], fill='#1E293B', outline='#334155', width=1)
    draw_r.text((60, 265), "Enterprise Economic Parameters (Configurable):", fill='#34D399')
    params = [
        ("Knowledge Workers (Engineers/Sales/Tech):", "50 Staff Members"),
        ("Average Loaded Hourly Compensation:", "$30.00 / Hour"),
        ("Weekly Hours Spent Searching Docs/Tickets:", "3.2 Hours / Worker"),
        ("Reduction in Search Latency with Biome RAG:", "75% Reduction"),
        ("Estimated Operational Inquiries / Day:", "420 Inquiries"),
        ("LLM Inference Cost (Llama 3.1 8B on-premise):", "$0.0004 / 1k Tokens"),
        ("Hardware Amortisation & Vector Storage (Qdrant):", "$180.00 / Month")
    ]
    yp = 310
    for p_name, p_val in params:
        draw_r.text((60, yp), p_name, fill='#E2E8F0')
        draw_r.text((420, yp), p_val, fill='#38BDF8')
        yp += 48

    # Right side: Comparative Benefit Chart Representation
    draw_r.rectangle([590, 245, w - 40, 700], fill='#1E293B', outline='#10B981', width=1)
    draw_r.text((610, 265), "Annual Cost & Efficiency Breakdown (Before vs After):", fill='#10B981')

    draw_r.rectangle([610, 310, w - 60, 460], fill='#0F172A', outline='#EF4444', width=1)
    draw_r.text((630, 325), "BEFORE BIOME IMPLEMENTATION (Legacy Manual Search):", fill='#EF4444')
    draw_r.text((630, 355), "- Annual Knowledge Searching Labour Cost: $249,600", fill='#F8FAFC')
    draw_r.text((630, 385), "- Average RFQ Turnaround Delay: 2.5 Business Days", fill='#F8FAFC')
    draw_r.text((630, 415), "- Error Rate in RF Part Number Matching: 8.4% of Orders", fill='#F8FAFC')

    draw_r.rectangle([610, 485, w - 60, 675], fill='#0F172A', outline='#10B981', width=1)
    draw_r.text((630, 500), "AFTER BIOME IMPLEMENTATION (Hybrid RAG + NL2SQL):", fill='#10B981')
    draw_r.text((630, 530), "- Total Annual Operating Cost: $65,280 (Labour + Compute)", fill='#F8FAFC')
    draw_r.text((630, 560), "- Average RFQ Turnaround Time: 45 Minutes (Instant Search)", fill='#F8FAFC')
    draw_r.text((630, 590), "- Error Rate in RF Part Matching: < 0.2% (Exact Hybrid Recall)", fill='#F8FAFC')
    draw_r.text((630, 625), " Net Value Created: $184,320 / Year (3.8x ROI Multiple)", fill='#34D399')

    out_path_r = os.path.join(ASSETS_DIR, "fig3_5_roi_calculator.png")
    img_roi.save(out_path_r, dpi=(300, 300))
    print(f"Generated {out_path_r}")

    # 6. Ablation Benchmark Explorer
    img_ab = Image.new('RGB', (w, h), color='#0F172A')
    draw_b = ImageDraw.Draw(img_ab)
    draw_b.rectangle([0, 0, w, 60], fill='#1E293B')
    draw_b.text((30, 20), "🌿 BIOME ABLATION EXPLORER  |  Interactive 18-Arm Empirical Evaluation Studio", fill='#10B981')

    # Filter Bar
    draw_b.rectangle([30, 80, w - 30, 130], fill='#1E293B', outline='#334155', width=1)
    draw_b.text((50, 98), "Filter by Mode: [ALL]  |  Top-K: [ALL]  |  Reranking: [ALL]  |  Metric Sort: Composite Score [DESC]", fill='#38BDF8')

    # Data Table
    draw_b.rectangle([30, 145, w - 30, 710], fill='#1E293B', outline='#334155', width=1)
    ab_headers = ["Rank", "Arm ID", "Mode", "top_k", "Rerank", "Faithfulness", "Ctx-P", "Ctx-R", "Hallucination↓", "Composite"]
    ab_x = [45, 110, 330, 420, 490, 580, 710, 810, 920, 1070]
    draw_b.rectangle([40, 160, w - 40, 195], fill='#0F172A')
    for idx, h_text in enumerate(ab_headers):
        draw_b.text((ab_x[idx], 170), h_text, fill='#34D399')

    ab_display_rows = [
        ["🥇 1", "hybrid_k10_no_rerank", "hybrid", "10", "No", "0.773", "0.780", "0.642", "0.309", "0.4721"],
        ["🥈 2", "dense_k3_no_rerank", "dense", "3", "No", "0.733", "0.833", "0.440", "0.310", "0.4549"],
        ["🥉 3", "hybrid_k5_no_rerank", "hybrid", "5", "No", "0.751", "0.767", "0.526", "0.309", "0.4544"],
        ["4", "hybrid_k3_no_rerank", "hybrid", "3", "No", "0.744", "0.818", "0.461", "0.309", "0.4541"],
        ["5", "dense_k5_no_rerank", "dense", "5", "No", "0.734", "0.811", "0.453", "0.310", "0.4530"],
        ["6", "dense_k10_no_rerank", "dense", "10", "No", "0.734", "0.811", "0.453", "0.310", "0.4530"],
        ["7", "hybrid_k10_rerank", "hybrid", "10", "Yes", "0.531", "0.785", "0.645", "0.561", "0.4003"],
        ["8", "hybrid_k5_rerank", "hybrid", "5", "Yes", "0.517", "0.826", "0.589", "0.564", "0.3981"],
        ["9", "hybrid_k3_rerank", "hybrid", "3", "Yes", "0.495", "0.849", "0.509", "0.565", "0.3894"],
        ["10", "sparse_k10_no_rerank", "sparse", "10", "No", "0.764", "0.773", "0.519", "0.335", "0.3840"]
    ]
    y_b = 205
    for r in ab_display_rows:
        draw_b.rectangle([40, y_b, w - 40, y_b + 42], fill='#064E3B' if ("🥇" in r[0]) else ('#1E293B' if (y_b % 84 == 0) else '#182234'))
        for idx, val in enumerate(r):
            draw_b.text((ab_x[idx], y_b + 12), val, fill='#34D399' if ("🥇" in r[0]) else '#E2E8F0')
        y_b += 48

    out_path_b = os.path.join(ASSETS_DIR, "fig3_6_ablation_explorer.png")
    img_ab.save(out_path_b, dpi=(300, 300))
    print(f"Generated {out_path_b}")

if __name__ == "__main__":
    generate_ablation_chart()
    generate_retrieval_comparison_chart()
    generate_latency_chart()
    generate_radar_chart()
    generate_ui_mockups()
    print("All diagrams generated successfully!")
