## Deterministic brand-rule check (7 products with both conditions)

| rule | pipeline passes | baseline passes |
|---|---|---|
| R1 caption <=300 chars | 7/7 | 0/7 |
| R2 caption first line <=70 chars | 7/7 | 0/7 |
| R3 caption emoji 1-3 | 7/7 | 7/7 |
| R4 hashtags 8-12 | 7/7 | 7/7 |
| R5 #radboards present | 7/7 | 7/7 |
| R6 no banned hashtags | 7/7 | 7/7 |
| R7 exactly 5 beats in order | 7/7 | 4/7 |
| R8 hook <=12 words | 7/7 | 6/7 |
| R9 script 32-40 s (2.4 words/s) | 6/7 | 5/7 |
| R10 sentences <=18 words | 6/7 | 7/7 |
| R11 no emoji in script | 7/7 | 7/7 |
| R12 no banned vocabulary | 6/7 | 7/7 |

- rule checks passed: pipeline 81/84, baseline 64/84
- packages passing ALL 12 rules: pipeline 4/7, baseline 0/7
- products where the pipeline passes more rules: 7, fewer: 0; two-sided sign test p = 0.0156
- rule-level discordant pairs: pipeline-only pass 20, baseline-only pass 3; exact McNemar p = 0.00049 (pooled over products; product-level test is primary)

Note: the pipeline's validators enforce a subset of these in code (counts, lengths, duration, beat order); the rest are prompt-only. Pipeline outputs here are the ones that passed validation (failed jobs produce no package).