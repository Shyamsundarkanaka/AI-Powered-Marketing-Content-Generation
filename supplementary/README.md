# Supplementary material

Paper: *A Constrained LangGraph Workflow for Brand-Compliant Short-Video Marketing Content from Shopify Product Pages*.

| Folder | Contents |
|---|---|
| `system/` | The workflow source referenced in the paper: graph topology (`pipeline.py`), shared state (`state.py`), all node prompts (`prompts.py`), validators and repair messages (`schemas.py`), LLM gateway and JSON extractor (`llm.py`). |
| `brand/` | The machine-readable brand file used in every run (`brand.yaml`) and its compliance notes. |
| `outputs/<product>/` | Text artefacts and run metadata of the seven evaluated pipeline packages (version 1). Videos and audio are omitted for size. |
| `baseline/` | Single-prompt baseline: exact prompts (`prompts/`), parsed replies (`*.json`) and the run log (`_log.csv`). |
| `annotation/` | Claim-labelling guideline, scraped product records, `annotator_A.prefilled.csv` (LLM pre-labels, blind to condition), `annotator_A.csv` (labels reviewed by a human annotator, 6 of 360 changed; used for all results), `key.csv` (item to condition), and `annotator_blind_36.csv` with `BLIND_SHEET_INSTRUCTIONS.md` (blank 10% sample for an independent human labelling; score with `scripts/blind_kappa.py`). The reviewer started from the pre-filled labels, so the 98.3% agreement with the LLM (κ = 0.97) is anchored, not independent. |
| `results/` | `results.md` (claim support, CIs, sign test), `rule_check.md` (12 deterministic rules, sign and McNemar tests), `pipeline_stats.md` (job outcomes, latency, repair attempts). |
| `scripts/` | Read-only evaluation scripts that regenerate every number from the application database and outputs. |

Labels: S supported, C contradicted, N not in the record, X not a factual claim. Unsupported = N + C.

Model: `gemini-2.5-flash` (free tier, provider-default sampling). Narration: ElevenLabs, with Piper as local fallback (4 and 3 of the 7 packages respectively; see each `_meta.json`).
