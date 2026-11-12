## Claim annotation

- items labelled by A: 360 of 360

| condition | factual claims | supported | not in source | contradicted | unsupported rate (Wilson 95% CI) | unsupported (product-cluster bootstrap CI) |
|---|---|---|---|---|---|---|
| baseline | 100 | 91 | 9 | 0 | 9.0% [4.8%, 16.2%] | [3.0%, 14.4%] |
| pipeline | 95 | 90 | 3 | 2 | 5.3% [2.3%, 11.7%] | [1.0%, 10.6%] |

Paired by product (baseline minus pipeline, unsupported rate): mean diff +3.2 pp over 7 products; baseline worse in 4, better in 2, tied 1; two-sided sign test p = 0.688.
- proof points in baseline: 28; supported 26 (92.9%); each carries an LLM-written 'source' string, so provenance label != verification
- proof points in pipeline: 27; supported 26 (96.3%); each carries an LLM-written 'source' string, so provenance label != verification
- numeric check: human `numbers_ok` vs automatic number-in-record test agree on 133/137 items (97.1%); items humans flagged N: 2

## Inter-annotator agreement (A vs B, n = 125 items)

- 4-label Cohen's kappa = 1.00 (raw agreement 100.0%)
- 3-label (Supported / Unsupported / Not-a-claim) kappa = 1.00 (raw agreement 100.0%)