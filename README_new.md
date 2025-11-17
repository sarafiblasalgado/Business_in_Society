# H&M CO₂ Impact Analysis and Material Scenarios

This project estimates product-level CO₂ intensity for an H&M catalog and builds presentation‑ready visuals to explore:

- Which **categories** and **materials** drive CO₂.
- How the **material mix** differs across categories.
- Which **materials to prioritize** for reduction or substitution.
- What‑if scenarios:
  - Replacing virgin polyester with recycled polyester.
  - Reducing wool, nylon, and leather across the catalog.

The codebase is written in Python and relies on H&M product data with free‑text material compositions.

---

## 1. Setup and Data

### 1.1. Environment

Create and activate a virtual environment, then install dependencies:

```bash
cd "/Users/sarafibla/Desktop/Business in Society/H&M"

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Key libraries:

- `pandas`, `numpy` — data handling.
- `matplotlib`, `seaborn` — plotting.
- `adjustText` — collision‑aware label placement.

### 1.2. Input Data

The main input file is:

- `data.csv` — H&M products with at least:
  - A **materials/composition** column (e.g. `materials`, `composition`, `material`, `details`, or `compositions`).
  - A **group/category** column (e.g. `product_type_name`, `product_group_name`, `department_name`, `mainCatCode`, or `productName`).

The scripts automatically detect which columns to use.

---

## 2. CO₂ Calculation (`compute_co2.py`)

The script `compute_co2.py` parses the material composition text and applies material‑specific CO₂ factors to estimate a **per‑product CO₂ intensity**.

### 2.1. CO₂ Factors

CO₂ factors (kg CO₂e per kg material) are defined in the `CO2_FACTORS` dictionary in `compute_co2.py`, for example:

- `polyester` / `virgin polyester` — 9.5
- `recycled polyester` — 3.0
- `cotton` — 5.6
- `organic cotton` — 2.1
- `wool` — 40.0
- `leather` — 25.0
- `nylon`, `polyamide` — 8.0  
…and other common fibers and synthetics.

### 2.2. Parsing Material Percentages

The function `extract_percentages(text)`:

- Searches for patterns like:
  - `26% Recycled polyester`
  - `Polyester 88%`
- Optionally falls back to patterns like `Upper: Polyester 100%`.
- Aggregates shares per material and **normalizes to 100%** if the sum of percentages differs from 100.

The function `compute_co2_for_row(text, CO2_FACTORS)`:

- Uses `extract_percentages` to get material shares.
- Maps each parsed material to a CO₂ factor (exact match or substring fallback).
- Calculates product‑level CO₂ as the sum over materials of
  $$(pct_i/100) \cdot factor_i$$
  i.e. for one product with materials $i$:
  $$CO2_{product} = \sum_i \left(\frac{pct_i}{100}\right) \cdot factor_i.$$
- Returns:
  - `co2_per_product` (float or NaN),
  - `materials_parsed` (JSON with pct and factor),
  - `materials_unknown` (unmatched materials).

Rows with no usable percentages remain as NaN; the script reports how many were skipped.

### 2.3. Running the CO₂ Computation

Run:

```bash
python compute_co2.py data.csv
```

Main outputs:

- `co2_per_product.csv`  
  Original data plus:
  - `co2_per_product`
  - `materials_parsed` (JSON)
  - `materials_unknown` (semicolon‑separated names)

- Category‑level summaries:
  - `summary_by_product_type.csv` — mean, std, count by category (unsorted).
  - `summary_by_product_type_ordered.csv` — same, sorted by mean CO₂ ascending (most sustainable → least).
  - `top5_by_product_type.csv` — top 5 most carbon‑intensive categories.
  - `bottom5_by_product_type.csv` — 5 most sustainable categories.

- Plots:
  - `mean_co2_by_type.png` — horizontal bar chart of mean CO₂ by category.
  - `boxplot_by_type.png` — CO₂ distribution for selected categories.

- Dominant materials by category:
  - `dominant_materials_by_type.csv` — up to 3 dominant materials per category (average share across products).

---

## 3. Exploded Materials and Summaries

The file `materials_summary.csv` contains aggregated statistics per material across the catalog:

- `material` — normalized material name.
- `products_count` — number of products containing the material.
- `occurrences` — number of exploded rows in `df_exploded`.
- `avg_pct` — average mass fraction %.
- `avg_factor` — average CO₂ factor used.
- `avg_contribution` — approximate contribution of the material to catalog CO₂.

Concretely, if we explode each product $p$ into materials $m$ with shares $pct_{p,m}$:

- `products_count(m)` = number of products $p$ where $m$ appears.
- `occurrences(m)` = number of exploded rows for $m$.
- `avg_pct(m)` = mean of $pct_{p,m}$ across all its occurrences.
- `avg_factor(m)` = mean CO₂ factor assigned to $m$.
- `avg_contribution(m)` ≈ $$\sum_p \left(\frac{pct_{p,m}}{100}\right) \cdot factor_m,$$ an approximate contribution of material $m$ to catalog CO₂.

This is derived from the exploded materials table (`df_exploded`) built in `h_and_m_visualizations.py`.

---

## 4. Visualization Suite (`h_and_m_visualizations.py`)

Once `co2_per_product.csv` exists, the script `h_and_m_visualizations.py` generates several presentation‑ready charts.

Run:

```bash
python h_and_m_visualizations.py
```

This will:

- Load `data.csv` and `co2_per_product.csv`.
- Explode material percentages per product.
- Generate multiple PNGs in the `figures/` folder.

### 4.1. Material Mix by Aggregated Category

**File:** `figures/material_mix_by_category.png`  
**Function:** `stacked_bar_material_mix(df_exploded, out_path)`

- Aggregates raw categories into semantic groups (e.g. `Ladies Dresses`, `Men Shoes`, `Men Sportswear`, etc.) via `AGG_CATEGORY_PATTERNS`.
- For each aggregated category, the material percentages are summed and normalized to 100%.
- Rare materials (< 3% share within a category) are grouped into `Other`.
- Draws a **horizontal stacked bar chart**:
  - X‑axis: material share (%).
  - Y‑axis: aggregated categories (limited to top 30 by product count).
  - Colors: `tab20` palette.
  - Labels: segments ≥ 18% are annotated with material name and % inside the bar.

Formally, for an aggregated category $c$ and material $m$ with exploded shares $pct_{p,m}$ for products $p$ in $c$:
$$share_{c,m} = \frac{\sum_{p \in c} pct_{p,m}}{\sum_{p \in c} \sum_k pct_{p,k}} \times 100\%.$$

This chart answers: *Which categories have the highest share of certain materials?*

### 4.2. CO₂ Footprint by Aggregated Category

**File:** `figures/co2_by_category.png`  
**Function:** `co2_by_category(df_full, out_path, raw_group_col)`

- Uses `co2_per_product` and the same aggregated categories.
- Computes mean CO₂ per product for each category and sorts by product count (top 30).
- Creates a **horizontal bar chart**:
  - X‑axis: mean CO₂ per product (kg CO₂/kg).
  - Y‑axis: aggregated category.
  - Annotates each bar with its value; large bars are labeled inside with white text.

If $P_c$ is the set of products in category $c$ and $CO2_p$ the CO₂ for product $p$, then the value plotted is:
$$mean\_CO2(c) = \frac{1}{|P_c|} \sum_{p \in P_c} CO2_p.$$

Shows which product categories are most carbon‑intensive on average.

### 4.3. Material Frequency

**File:** `figures/material_frequency.png`  
**Function:** `material_frequency(df_exploded, out_path, top_n=25, group_rest=True)`

- Counts how many **distinct products** contain each material.
- Plots the top N materials (optionally grouping the rest into `Other`) as a horizontal bar chart.
- Annotates each bar with the number of products.

Answers: *Which materials appear in the most products?*

### 4.4. CO₂ Footprint by Material

**File:** `figures/co2_by_material.png`  
**Function:** `co2_footprint_by_material(df_exploded, out_path, top_n=25, group_rest=True)`

- Uses exploded material shares and CO₂ factors to estimate **total CO₂ contribution** per material:
  - for each exploded row, a contribution
    $$contrib_{p,m} = \left(\frac{pct_{p,m}}{100}\right) \cdot factor_m,$$
    and then
    $$CO2_m = \sum_p contrib_{p,m}$$
    for material $m$.
- Aggregates and ranks materials, optionally grouping the tail into `Other`.
- Plots a horizontal bar chart (top N materials) with labels showing:
  - absolute contribution (relative units),
  - share of total catalog CO₂ (%).

The share of catalog CO₂ for material $m$ is
$$share_m = \frac{CO2_m}{\sum_j CO2_j} \times 100\%.$$

This graph highlights **which materials are the biggest CO₂ drivers** overall.

---

## 5. Material Prioritization Bubble Chart

**File:** `figures/material_prioritization_bubble.png`  
**Function:** `bubble_chart_material_prioritization(df_exploded, out_path, label_top_n=15)`

This chart positions materials in a 2D space of **impact vs. viability**, with bubble size representing usage:

- **X‑axis:** CO₂ factor (kg CO₂e per kg).
- **Y‑axis:** viability score (1 = low viability, 5 = high), from a manual mapping (e.g. `recycled polyester` higher viability, `leather` lower).
- **Bubble size:** total catalog usage (% share) of each material.
- **Color:** CO₂ factor (`viridis` colormap) with a colorbar.

For each material $m$:

- $impact\_x(m)$ = CO₂ factor used for $m$.
- $viability\_y(m)$ = manually assigned score between 1 and 5.
- $usage\_size(m)$ is proportional to its catalog share,
  $$usage\_size(m) \propto \frac{\sum_p pct_{p,m}}{\sum_p \sum_k pct_{p,k}} \times 100\%,$$
  and then rescaled into bubble areas for plotting.

Additional design elements:

- Median vertical and horizontal lines create four quadrants.
- A shaded top‑right quadrant highlights **high‑impact, low‑viability** materials.
- The top N materials by usage are **numbered**:
  - Single materials: numbers drawn inside the bubble with a white outline.
  - Overlapping materials: numbers grouped into small labeled boxes connected to bubbles; placement uses collision‑aware logic.
- To the right of the colorbar, a combined inset box shows:
  - A **size legend** (e.g., 25%, 50%, 100% usage bubbles).
  - A **numbered list** mapping each number to its material name.

This figure is intended as a **prioritization tool**: it shows at a glance which materials combine high CO₂, low viability, and high usage.

---

## 6. What‑If Scenarios

There are two independent what‑if analyses, each with its own chart.

### 6.1. Replacing Virgin Polyester with Recycled Polyester

**File:** `figures/whatif_replace_polyester.png`  
**Function:** `what_if_replace_polyester(df_exploded, df_full, out_path)`

Goal: estimate the effect on total catalog CO₂ of replacing **60% of virgin polyester** with **recycled polyester**.

Method:

1. Identify rows where material is polyester but not recycled.
2. Sum their mass fraction to get total virgin polyester share.
3. Compute current CO₂ contributed by virgin polyester and current total CO₂.
4. Scenario: 60% of virgin polyester mass is replaced by recycled polyester:
   - New CO₂ = `(1 - r) * virgin_factor + r * recycled_factor`, with `r = 0.6`.

Let $CO2_{baseline}$ be the total catalog CO₂, $CO2_{virgin}$ the contribution from virgin polyester, $f_{virgin}$ its factor and $f_{recycled}$ the recycled polyester factor. The scenario total is approximated as:
$$CO2_{scenario} = CO2_{baseline} - CO2_{virgin} + CO2_{virgin} \cdot \frac{(1-r) f_{virgin} + r f_{recycled}}{f_{virgin}},$$
with $r = 0.6$. The percentage change is
$$\Delta\% = \frac{CO2_{scenario} - CO2_{baseline}}{CO2_{baseline}} \times 100\%.$$

Output chart:

- Two bars:
  - `Baseline`
  - `60% replaced by recycled polyester`
- Y‑axis: total catalog CO₂ (relative units).
- Each bar labeled with its CO₂ value.
- The scenario bar annotated with relative change:
  - `−X.X% vs baseline`.

This is a clear, focused visualization of **polyester decarbonization potential**.

### 6.2. 30% Less Wool, Nylon and Leather Across the Catalog

**File:** `figures/whatif_reduce_wool_nylon_leather.png`  
**Function:** `what_if_reduce_wool_nylon_leather(df_exploded, df_full, out_path)`

Goal: estimate the effect of reducing **wool, nylon and leather** content by **30%** across all products.

Method (approximate):

1. Use `df_exploded` (materials exploded from `data.csv`):
   - Compute `co2_contribution` per exploded row as:
     - `(pct/100) * CO2_factor(material)`.
2. Filter rows where material name contains any of:
   - `wool`, `nylon`, `leather`.
3. Sum their contribution to get `current_target_co2`.
4. Apply a 30% reduction:
   - `new_target_co2 = current_target_co2 * (1 - 0.30)`.
5. Adjust total catalog CO₂:
   - `new_total_co2 = current_total_co2 - current_target_co2 + new_target_co2`.

If $CO2_{baseline}$ is total catalog CO₂ and $CO2_{target}$ is the summed contribution from wool/nylon/leather, then the scenario total is:
$$CO2_{scenario} = CO2_{baseline} - 0.30 \cdot CO2_{target},$$
and the plotted percentage change is
$$\Delta\% = \frac{CO2_{scenario} - CO2_{baseline}}{CO2_{baseline}} \times 100\%.$$

Output chart:

- Two bars:
  - `Baseline`
  - `30% less wool/nylon/leather`
- Y‑axis: total catalog CO₂ (relative units).
- Each bar labeled with its value.
- The scenario bar annotated with:
  - `−X.X% vs baseline`.

This scenario illustrates the potential impact of **targeted reductions in high‑impact fibers**.

---

## 7. How to Regenerate All Figures

Once `co2_per_product.csv` has been created by `compute_co2.py`, regenerate all figures with:

```bash
python h_and_m_visualizations.py
```

This will (re)write:

- `figures/material_mix_by_category.png`
- `figures/co2_by_category.png`
- `figures/whatif_replace_polyester.png`
- `figures/whatif_reduce_wool_nylon_leather.png`
- `figures/material_prioritization_bubble.png`
- `figures/material_frequency.png`
- `figures/co2_by_material.png`

---

