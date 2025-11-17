# H&M CO₂ Impact Analysis & Material Scenario Modeling

 

This project estimates product-level CO₂ intensity for an H&M product catalog and generates presentation-ready visuals to explore:

 

- Which categories and materials drive most CO₂  

- How the material mix varies by category  

- Which materials to prioritize for reduction or substitution  

- What-if scenarios:

  - Replacing virgin polyester with recycled polyester

  - Reducing wool, nylon, and leather across the catalog

 

All analysis is implemented in Python using free-text material compositions extracted from H&M product data.

 

---

 

## 1. Setup & Data

 

### 1.1. Environment Setup

 

```bash

cd "/Users/sarafibla/Desktop/Business in Society/H&M"

 

python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

```

 

Key libraries: `pandas`, `numpy`, `matplotlib`, `seaborn`, `adjustText`.

 

### 1.2. Input Data Requirements

 

**Main input file:**

 

- `data.csv`, containing:

  - A materials/composition column (e.g., `materials`, `composition`, `details`, …)

  - A category/group column (e.g., `product_type_name`, `product_group_name`, `department_name`, …)

 

Columns are automatically detected by the scripts.

 

## 2. CO₂ Calculation (`compute_co2.py`)

 

The script parses material composition text and applies material-specific CO₂ factors to estimate a CO₂ value for each product.

 

### 2.1. CO₂ Factors

 

Defined in `CO2_FACTORS` (kg CO₂e per kg):

 

- Polyester (virgin): 9.5  

- Recycled polyester: 3.0  

- Cotton: 5.6  

- Organic cotton: 2.1  

- Wool: 40  

- Leather: 25  

- Nylon/Polyamide: 8  

- Plus additional fibers

 

### 2.2. Material Parsing Logic

 

`extract_percentages(text)`:

 

- Detects patterns such as `30% Cotton`, `Polyester 88%`, `Upper: Leather 100%`

- Aggregates and normalizes percentages to 100%

- Handles fallback multi-material cases

 

`compute_co2_for_row()`:

 

- Maps parsed materials to CO₂ factors

- Computes:  

  $CO2_{\text{product}} = \sum_i \left( \frac{pct_i}{100} \right) \cdot factor_i$

- Outputs CO₂ value, parsed materials (JSON), and unknown materials.

 

### 2.3. Running the Script

 

```bash

python compute_co2.py data.csv

```

 

Outputs:

 

- `co2_per_product.csv`

- Category summaries:

  - `summary_by_product_type.csv`

  - `summary_by_product_type_ordered.csv`

  - `top5_by_product_type.csv`

  - `bottom5_by_product_type.csv`

- Plots:

  - `mean_co2_by_type.png`

  - `boxplot_by_type.png`

- Material dominance:

  - `dominant_materials_by_type.csv`

 

## 3. Material-Level Summary

 

`materials_summary.csv` reports:

 

- Material name (normalized)

- Number of products containing each material

- Number of occurrences in exploded rows

- Average share (%)

- Average CO₂ factor

- Approximate catalog-level CO₂ contribution:

 

$$CO2_m \approx \sum_p \left( \frac{pct_{p,m}}{100} \right) \cdot factor_m$$

 

## 4. Visualization Suite (`h_and_m_visualizations.py`)

 

Generate all charts:

 

```bash

python h_and_m_visualizations.py

```

 

All charts are saved in the `figures/` directory.

 

### 4.1. Material Mix by Category

 

- Output: `material_mix_by_category.png`

- Aggregates categories using pattern matching

- Computes material share per category

- Groups rare materials (<3%) into "Other"

- Horizontal stacked bar chart

 

### 4.2. CO₂ by Category

 

- Output: `co2_by_category.png`

- Calculates mean CO₂ per product for each aggregated category

- Horizontal bar chart with numeric labels

 

### 4.3. Material Frequency

 

- Output: `material_frequency.png`

- Counts distinct products containing each material

- Plots top materials as a horizontal bar chart

 

### 4.4. CO₂ Contribution by Material

 

- Output: `co2_by_material.png`

- Computes total CO₂ contribution of each material:  

  $CO2_m = \sum_p \left( \frac{pct_{p,m}}{100} \right) \cdot factor_m$

- Ranks materials by total impact

- Horizontal bar chart

 

## 5. Material Prioritization Bubble Chart

 

- Output: `material_prioritization_bubble.png`

- Shows materials in terms of:

  - **X-axis:** CO₂ factor

  - **Y-axis:** viability score (1–5)

  - **Bubble size:** catalog usage

  - **Color:** CO₂ factor

- Includes quadrants, collision-aware labels, and bubble size legend.

 

## 6. What-If Scenarios

 

### 6.1. Replace Virgin Polyester with Recycled Polyester

 

- Output: `whatif_replace_polyester.png`

- Scenario: replace 60% of virgin polyester with recycled polyester.

- Compares baseline CO₂ vs. scenario CO₂ and reports percentage change.

 

### 6.2. Reduce Wool, Nylon & Leather by 30%

 

- Output: `whatif_reduce_wool_nylon_leather.png`

- Scenario calculation:

 

  $$CO2_{\text{scenario}} = CO2_{\text{baseline}} - 0.30 \cdot CO2_{\text{target}}$$

 

- Plots baseline vs. scenario and percentage change.

 

## 7. Regenerate All Figures

 

Once `co2_per_product.csv` exists:

 

```bash

python h_and_m_visualizations.py

```

 

Generates all outputs:

 

- Material mix

- CO₂ by category

- Polyester scenario

- Wool/Nylon/Leather scenario

- Material prioritization

- Material frequency

- CO₂ by material
