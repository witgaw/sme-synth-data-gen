# RAG Evaluation Leaderboard

| # | Name | Model | Score | % | Full | Partial | Wrong | Temporal | Not answered |
|---|------|-------|------:|--:|-----:|--------:|------:|:--------:|-------------:|
| 1 | sub_claude_cowork_sonnet_4_6_extended_thinking | anthropic/claude-sonnet-4-6 | 46.0/50 | 92.0% | 44 | 4 | 2 | 0/3 | 14 |
| 2 | sub_claude_cowork_opus_4_6_extended_thinking_pageindex | anthropic/claude-opus-4-6 | 45.5/50 | 91.0% | 44 | 3 | 3 | 2/3 | 14 |
| 3 | baseline | qwen2.5:7b | 14.5/29 | 50.0% | 14 | 1 | 14 | 0/3 | 35 |
| 4 | reranker_on | qwen2.5:7b | 14.5/29 | 50.0% | 14 | 1 | 14 | 0/3 | 35 |
| 5 | chunk_large | qwen2.5:7b | 12.5/29 | 43.1% | 11 | 3 | 15 | 0/3 | 35 |
| 6 | gemini | google/gemini-2.5-pro | 19.5/50 | 39.0% | 18 | 3 | 29 | 0/3 | 14 |
| 7 | opus | anthropic/claude-opus-4-6 | 18.0/50 | 36.0% | 13 | 10 | 27 | 0/3 | 14 |
| 8 | sonnet | anthropic/claude-sonnet-4-6 | 16.0/50 | 32.0% | 11 | 10 | 29 | 0/3 | 14 |
| 9 | ocr_openrouter | qwen2.5:7b | 15.0/50 | 30.0% | 14 | 2 | 34 | 0/3 | 14 |
| 10 | ocr | qwen2.5:7b | 15.0/50 | 30.0% | 14 | 2 | 34 | 0/3 | 14 |

## Submission Details

### 1. sub_claude_cowork_sonnet_4_6_extended_thinking

> Manual run via macOS desktop app using Cowork option, Sonnet 4.6 model and extended thinking switched on.

- **File:** `sub_claude_cowork_sonnet_4_6_extended_thinking.json`
- **Model:** anthropic/claude-sonnet-4-6 (anthropic)
- **Reranker:** no
- **Score:** 46.0/50 (92.0%) — 44 full, 4 partial, 2 wrong
- **Temporal filter:** 0/3 passed
- **Not answered:** 14
- **Requires human review:** 5 questions

**By category:**

| Category | Score | % |
|----------|------:|--:|
| exact_match_questions | 18.5/19 | 97% |
| multi_document_synthesis_questions | 4.0/5 | 80% |
| multi_hop_ocr_questions | 3.5/5 | 70% |
| negative_questions | 5.0/5 | 100% |
| ocr_questions | 15.0/16 | 94% |
| temporal_filter_questions | 0.0/3 | 0% |

### 2. sub_claude_cowork_opus_4_6_extended_thinking_pageindex

> Manual run via macOS desktop app using Cowork option, Opus 4.6 model, extended thinking switched on and access to PageIndex for OCR on PDFs.

- **File:** `sub_claude_cowork_opus_4_6_extended_thinking_pageindex.json`
- **Model:** anthropic/claude-opus-4-6 (anthropic)
- **Reranker:** no
- **Score:** 45.5/50 (91.0%) — 44 full, 3 partial, 3 wrong
- **Temporal filter:** 2/3 passed
- **Not answered:** 14
- **Requires human review:** 5 questions

**By category:**

| Category | Score | % |
|----------|------:|--:|
| exact_match_questions | 18.5/19 | 97% |
| multi_document_synthesis_questions | 5.0/5 | 100% |
| multi_hop_ocr_questions | 3.0/5 | 60% |
| negative_questions | 5.0/5 | 100% |
| ocr_questions | 14.0/16 | 88% |
| temporal_filter_questions | 2.0/3 | 67% |

### 3. baseline

> Standard chunking, top_k=10, no reranker — reference config

- **File:** `sub_qwen2.5-7b_baseline.json`
- **Model:** qwen2.5:7b (ollama)
- **Reranker:** no
- **Score:** 14.5/29 (50.0%) — 14 full, 1 partial, 14 wrong
- **Temporal filter:** 0/3 passed
- **Not answered:** 35
- **Requires human review:** 5 questions

**By category:**

| Category | Score | % |
|----------|------:|--:|
| exact_match_questions | 9.5/19 | 50% |
| multi_document_synthesis_questions | 1.0/5 | 20% |
| negative_questions | 4.0/5 | 80% |
| temporal_filter_questions | 0.0/3 | 0% |

### 4. reranker_on

> Cross-encoder reranking enabled — same chunking as baseline

- **File:** `sub_qwen2.5-7b_reranker.json`
- **Model:** qwen2.5:7b (ollama)
- **Reranker:** yes
- **Score:** 14.5/29 (50.0%) — 14 full, 1 partial, 14 wrong
- **Temporal filter:** 0/3 passed
- **Not answered:** 35
- **Requires human review:** 5 questions

**By category:**

| Category | Score | % |
|----------|------:|--:|
| exact_match_questions | 9.5/19 | 50% |
| multi_document_synthesis_questions | 1.0/5 | 20% |
| negative_questions | 4.0/5 | 80% |
| temporal_filter_questions | 0.0/3 | 0% |

### 5. chunk_large

> Larger chunks (2000/400) — more context per retrieved passage

- **File:** `sub_qwen2.5-7b_chunk_large.json`
- **Model:** qwen2.5:7b (ollama)
- **Reranker:** no
- **Score:** 12.5/29 (43.1%) — 11 full, 3 partial, 15 wrong
- **Temporal filter:** 0/3 passed
- **Not answered:** 35
- **Requires human review:** 5 questions

**By category:**

| Category | Score | % |
|----------|------:|--:|
| exact_match_questions | 7.5/19 | 39% |
| multi_document_synthesis_questions | 1.0/5 | 20% |
| negative_questions | 4.0/5 | 80% |
| temporal_filter_questions | 0.0/3 | 0% |

### 6. gemini

> Gemini 2.5 Pro via OpenRouter with Gemini Flash OCR

- **File:** `sub_gemini-2.5-pro_ocr_gemini-flash-1.5.json`
- **Model:** google/gemini-2.5-pro (openrouter)
- **OCR model:** google/gemini-flash-1.5
- **Reranker:** no
- **Score:** 19.5/50 (39.0%) — 18 full, 3 partial, 29 wrong
- **Temporal filter:** 0/3 passed
- **Not answered:** 14
- **Requires human review:** 5 questions

**By category:**

| Category | Score | % |
|----------|------:|--:|
| exact_match_questions | 11.0/19 | 58% |
| multi_document_synthesis_questions | 3.0/5 | 60% |
| multi_hop_ocr_questions | 0.5/5 | 10% |
| negative_questions | 4.0/5 | 80% |
| ocr_questions | 1.0/16 | 6% |
| temporal_filter_questions | 0.0/3 | 0% |

### 7. opus

> Claude Opus 4.6 via OpenRouter with Gemini Flash OCR

- **File:** `sub_claude-opus-4-6_ocr_gemini-flash-1.5.json`
- **Model:** anthropic/claude-opus-4-6 (openrouter)
- **OCR model:** google/gemini-flash-1.5
- **Reranker:** no
- **Score:** 18.0/50 (36.0%) — 13 full, 10 partial, 27 wrong
- **Temporal filter:** 0/3 passed
- **Not answered:** 14
- **Requires human review:** 5 questions

**By category:**

| Category | Score | % |
|----------|------:|--:|
| exact_match_questions | 8.5/19 | 45% |
| multi_document_synthesis_questions | 2.5/5 | 50% |
| multi_hop_ocr_questions | 0.0/5 | 0% |
| negative_questions | 5.0/5 | 100% |
| ocr_questions | 2.0/16 | 12% |
| temporal_filter_questions | 0.0/3 | 0% |

### 8. sonnet

> Claude Sonnet 4.6 via OpenRouter with Gemini Flash OCR

- **File:** `sub_claude-sonnet-4-6_ocr_gemini-flash-1.5.json`
- **Model:** anthropic/claude-sonnet-4-6 (openrouter)
- **OCR model:** google/gemini-flash-1.5
- **Reranker:** no
- **Score:** 16.0/50 (32.0%) — 11 full, 10 partial, 29 wrong
- **Temporal filter:** 0/3 passed
- **Not answered:** 14
- **Requires human review:** 5 questions

**By category:**

| Category | Score | % |
|----------|------:|--:|
| exact_match_questions | 8.0/19 | 42% |
| multi_document_synthesis_questions | 1.5/5 | 30% |
| multi_hop_ocr_questions | 0.0/5 | 0% |
| negative_questions | 5.0/5 | 100% |
| ocr_questions | 1.5/16 | 9% |
| temporal_filter_questions | 0.0/3 | 0% |

### 9. ocr_openrouter

> OCR via OpenRouter Gemini Flash — hosted vision model for scanned PDFs

- **File:** `sub_qwen2.5-7b_ocr_gemini-flash-1.5.json`
- **Model:** qwen2.5:7b (ollama)
- **OCR model:** google/gemini-flash-1.5
- **Reranker:** no
- **Score:** 15.0/50 (30.0%) — 14 full, 2 partial, 34 wrong
- **Temporal filter:** 0/3 passed
- **Not answered:** 14
- **Requires human review:** 5 questions

**By category:**

| Category | Score | % |
|----------|------:|--:|
| exact_match_questions | 9.5/19 | 50% |
| multi_document_synthesis_questions | 1.0/5 | 20% |
| multi_hop_ocr_questions | 0.0/5 | 0% |
| negative_questions | 4.0/5 | 80% |
| ocr_questions | 0.5/16 | 3% |
| temporal_filter_questions | 0.0/3 | 0% |

### 10. ocr

> OCR enabled via vision model — includes OCR and multi-hop OCR questions

- **File:** `sub_qwen2.5-7b_ocr_llava-7b.json`
- **Model:** qwen2.5:7b (ollama)
- **OCR model:** llava:7b
- **Reranker:** no
- **Score:** 15.0/50 (30.0%) — 14 full, 2 partial, 34 wrong
- **Temporal filter:** 0/3 passed
- **Not answered:** 14
- **Requires human review:** 5 questions

**By category:**

| Category | Score | % |
|----------|------:|--:|
| exact_match_questions | 9.5/19 | 50% |
| multi_document_synthesis_questions | 1.0/5 | 20% |
| multi_hop_ocr_questions | 0.0/5 | 0% |
| negative_questions | 4.0/5 | 80% |
| ocr_questions | 0.5/16 | 3% |
| temporal_filter_questions | 0.0/3 | 0% |
