# H&M CO2 Impact Analysis

Estimating product-level carbon intensity for an H&M catalog and modeling reduction scenarios. The project was built around a simple question: which materials and product categories drive the most CO2, and what happens if you start substituting them?

## What it does

Parses free-text material compositions from H&M product data (e.g. "88% Polyester, 12% Elastane"), applies material-specific CO2 factors (kg CO2e per kg), and calculates an estimated footprint per product. From there it generates category-level breakdowns, material prioritization charts, and two what-if scenarios:

- Replacing 60% of virgin polyester with recycled polyester
- Reducing wool, nylon, and leather by 30% across the catalog

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python compute_co2.py data.csv
python h_and_m_visualizations.py
```

All charts are saved to `figures/`.

## Files

- `compute_co2.py` - parses material text and calculates CO2 per product
- `h_and_m_visualizations.py` - generates all charts
- `co2_analysis.ipynb` - exploratory analysis notebook
- `figures/` - output charts
- `H&M_Group7.pdf` - full report
