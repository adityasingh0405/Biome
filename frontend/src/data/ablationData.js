/**
 * Empirical 18-Arm Ablation Study Data from ABLATION_RESULTS.md
 */

export const ABLATION_STUDY = {
  winner: 'hybrid_k10_no_rerank',
  winnerComposite: 0.4721,
  totalArms: 18,
  dataset: 'eval/golden_dataset.json',
  arms: [
    { rank: 1, id: 'hybrid_k10_no_rerank', mode: 'hybrid', top_k: 10, rerank: false, correctness: 0.203, faithfulness: 0.773, ctx_p: 0.780, ctx_r: 0.642, hall: 0.309, ans_rel: 0.402, sem_sim: 0.510, mrr: 0.540, composite: 0.4721, latency_ms: 19180 },
    { rank: 2, id: 'dense_k3_no_rerank', mode: 'dense', top_k: 3, rerank: false, correctness: 0.205, faithfulness: 0.733, ctx_p: 0.833, ctx_r: 0.440, hall: 0.310, ans_rel: 0.408, sem_sim: 0.523, mrr: 0.458, composite: 0.4549, latency_ms: 18497 },
    { rank: 3, id: 'hybrid_k5_no_rerank', mode: 'hybrid', top_k: 5, rerank: false, correctness: 0.203, faithfulness: 0.751, ctx_p: 0.767, ctx_r: 0.526, hall: 0.309, ans_rel: 0.402, sem_sim: 0.510, mrr: 0.533, composite: 0.4544, latency_ms: 19547 },
    { rank: 4, id: 'hybrid_k3_no_rerank', mode: 'hybrid', top_k: 3, rerank: false, correctness: 0.203, faithfulness: 0.744, ctx_p: 0.818, ctx_r: 0.461, hall: 0.309, ans_rel: 0.402, sem_sim: 0.510, mrr: 0.512, composite: 0.4541, latency_ms: 19150 },
    { rank: 5, id: 'dense_k5_no_rerank', mode: 'dense', top_k: 5, rerank: false, correctness: 0.205, faithfulness: 0.734, ctx_p: 0.811, ctx_r: 0.453, hall: 0.310, ans_rel: 0.408, sem_sim: 0.523, mrr: 0.466, composite: 0.4530, latency_ms: 18176 },
    { rank: 6, id: 'dense_k10_no_rerank', mode: 'dense', top_k: 10, rerank: false, correctness: 0.205, faithfulness: 0.734, ctx_p: 0.811, ctx_r: 0.453, hall: 0.310, ans_rel: 0.408, sem_sim: 0.523, mrr: 0.466, composite: 0.4530, latency_ms: 20020 },
    { rank: 7, id: 'hybrid_k10_rerank', mode: 'hybrid', top_k: 10, rerank: true, correctness: 0.206, faithfulness: 0.531, ctx_p: 0.785, ctx_r: 0.645, hall: 0.561, ans_rel: 0.345, sem_sim: 0.435, mrr: 0.587, composite: 0.4003, latency_ms: 29215 },
    { rank: 8, id: 'hybrid_k5_rerank', mode: 'hybrid', top_k: 5, rerank: true, correctness: 0.206, faithfulness: 0.517, ctx_p: 0.826, ctx_r: 0.589, hall: 0.564, ans_rel: 0.345, sem_sim: 0.437, mrr: 0.585, composite: 0.3981, latency_ms: 28120 },
    { rank: 9, id: 'hybrid_k3_rerank', mode: 'hybrid', top_k: 3, rerank: true, correctness: 0.207, faithfulness: 0.495, ctx_p: 0.849, ctx_r: 0.509, hall: 0.565, ans_rel: 0.345, sem_sim: 0.439, mrr: 0.576, composite: 0.3894, latency_ms: 27878 },
    { rank: 10, id: 'sparse_k10_no_rerank', mode: 'sparse', top_k: 10, rerank: false, correctness: 0.114, faithfulness: 0.764, ctx_p: 0.773, ctx_r: 0.519, hall: 0.335, ans_rel: 0.197, sem_sim: 0.261, mrr: 0.365, composite: 0.3840, latency_ms: 19990 },
    { rank: 11, id: 'dense_k3_rerank', mode: 'dense', top_k: 3, rerank: true, correctness: 0.207, faithfulness: 0.477, ctx_p: 0.821, ctx_r: 0.444, hall: 0.576, ans_rel: 0.332, sem_sim: 0.431, mrr: 0.503, composite: 0.3725, latency_ms: 30934 },
    { rank: 12, id: 'dense_k5_rerank', mode: 'dense', top_k: 5, rerank: true, correctness: 0.207, faithfulness: 0.477, ctx_p: 0.811, ctx_r: 0.453, hall: 0.576, ans_rel: 0.332, sem_sim: 0.431, mrr: 0.507, composite: 0.3718, latency_ms: 20562 },
    { rank: 13, id: 'dense_k10_rerank', mode: 'dense', top_k: 10, rerank: true, correctness: 0.207, faithfulness: 0.477, ctx_p: 0.811, ctx_r: 0.453, hall: 0.576, ans_rel: 0.332, sem_sim: 0.431, mrr: 0.507, composite: 0.3718, latency_ms: 20150 },
    { rank: 14, id: 'sparse_k5_no_rerank', mode: 'sparse', top_k: 5, rerank: false, correctness: 0.114, faithfulness: 0.742, ctx_p: 0.760, ctx_r: 0.403, hall: 0.335, ans_rel: 0.197, sem_sim: 0.261, mrr: 0.359, composite: 0.3659, latency_ms: 20939 },
    { rank: 15, id: 'sparse_k3_no_rerank', mode: 'sparse', top_k: 3, rerank: false, correctness: 0.114, faithfulness: 0.717, ctx_p: 0.721, ctx_r: 0.270, hall: 0.335, ans_rel: 0.197, sem_sim: 0.261, mrr: 0.330, composite: 0.3419, latency_ms: 18310 },
    { rank: 16, id: 'sparse_k10_rerank', mode: 'sparse', top_k: 10, rerank: true, correctness: 0.175, faithfulness: 0.364, ctx_p: 0.773, ctx_r: 0.519, hall: 0.729, ans_rel: 0.221, sem_sim: 0.322, mrr: 0.515, composite: 0.3110, latency_ms: 28178 },
    { rank: 17, id: 'sparse_k5_rerank', mode: 'sparse', top_k: 5, rerank: true, correctness: 0.175, faithfulness: 0.348, ctx_p: 0.782, ctx_r: 0.478, hall: 0.733, ans_rel: 0.221, sem_sim: 0.322, mrr: 0.515, composite: 0.3051, latency_ms: 30719 },
    { rank: 18, id: 'sparse_k3_rerank', mode: 'sparse', top_k: 3, rerank: true, correctness: 0.176, faithfulness: 0.324, ctx_p: 0.788, ctx_r: 0.415, hall: 0.738, ans_rel: 0.221, sem_sim: 0.325, mrr: 0.500, composite: 0.2952, latency_ms: 26110 },
  ],
  axes: {
    retrieval_mode: [
      { name: 'Hybrid (BM25 + Dense RRF)', composite: 0.4281, faithfulness: 0.635, correctness: 0.204 },
      { name: 'Dense Vector Only', composite: 0.4128, faithfulness: 0.605, correctness: 0.206 },
      { name: 'Sparse BM25 Only', composite: 0.3338, faithfulness: 0.543, correctness: 0.145 },
    ],
    top_k: [
      { k: 10, composite: 0.3987, faithfulness: 0.607 },
      { k: 5, composite: 0.3914, faithfulness: 0.595 },
      { k: 3, composite: 0.3847, faithfulness: 0.582 },
    ]
  }
};
