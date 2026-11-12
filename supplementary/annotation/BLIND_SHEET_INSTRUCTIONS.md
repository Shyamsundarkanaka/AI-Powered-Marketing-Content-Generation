# Blind labelling: 36 units, about 20 minutes

Send the annotator ONLY: `annotation/annotator_blind_36.csv`, the `annotation/records/` folder, and `GUIDELINE_annotation.md`.
Do NOT send annotator_A.csv, annotator_A.prefilled.csv, annotator_B.csv or key.csv.

1. Read the guideline (S supported, C contradicted, N not in the record, X not a factual claim).
2. For each row, read `claim_text`, open `records/<product>.txt`, and type one letter in `label`. If the sentence has a number or price, type Y or N in `numbers_ok` (Y = all match the record).
3. Judge only against the record. Work alone, from the blank sheet; do not look at any other sheet.
4. Save as CSV UTF-8 under the same name and return it.

Then: `python eval/blind_kappa.py` gives kappa with a 95% bootstrap CI against the reviewed labels and the LLM pre-labels. With 36 items the interval is wide; report it as an independent check on a 10% random sample.
