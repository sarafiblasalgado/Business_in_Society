# CO₂-per-product analysis (improved)

This repository provides a small pipeline to estimate per-product CO₂ (kg CO₂e/kg) from H&M product composition text. The method parses percentage shares where they are present, applies fiber/material CO₂ factors, and aggregates results by category.

Quick start

1. Create and activate a Python virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the processor on your dataset:

```bash
python compute_co2.py data.csv
```

Outputs (written to the current folder)
- `co2_per_product.csv` — original rows plus `co2_per_product`, `materials_parsed`, and `materials_unknown`.
- `summary_by_product_type.csv` — grouped statistics (mean, std, count) unsorted.
- `summary_by_product_type_ordered.csv` — grouped statistics ordered by mean CO₂ (ascending: most sustainable → least).
- `top5_by_product_type.csv`, `bottom5_by_product_type.csv` — quick CSVs for top/bottom categories.
- `mean_co2_by_type.png`, `boxplot_by_type.png`, `top5_bar.png` — plots saved for presentation.
- `dominant_materials_by_type.csv` — dominant materials (avg % per product) per product type.

Notes & assumptions
- The parser looks for explicit percentage shares (e.g. `26% Recycled polyester` or `Polyester 88%`). If a product lacks explicit shares it is left as NaN (count of skipped rows printed by the script).\
- CO₂ factors live in `compute_co2.py` in the `CO2_FACTORS` dictionary — update those values if you have literature-sourced numbers.

Next steps you might want me to do
- Update CO₂ factors to a published LCA table you provide.\
- Add heuristics to infer material shares when percentages are missing.\
- Produce a PDF/slide deck summarising the top offenders and dominant materials (I can generate this from the notebook).

If you want one of the next steps implemented, tell me which and I will proceed.


