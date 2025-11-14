#!/usr/bin/env python3
"""
Compute CO2 per product from `data.csv`.

Usage:
  python compute_co2.py data.csv

Outputs:
  - `co2_per_product.csv` (original data + `co2_per_product` column)
  - `summary_by_product_type.csv` (mean, std, count per chosen category)
  - `top5_by_product_type.csv` (top 5 highest-impact types)
  - `top5_bar.png`, `boxplot_by_type.png`

Notes / assumptions:
  - The script looks for explicit percentage statements (e.g. "26% Recycled polyester")
    and also patterns like "Polyester 88%". It uses those where available.
  - If no explicit percentage information is found for a product the script will
    leave `co2_per_product` as NaN for that row and report how many were skipped.
  - A small fallback CO₂ factor dictionary is included for common material names.
"""
import sys
import re
import json
from collections import defaultdict

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


CO2_FACTORS = {
    # fibres and variants (kg CO2e per kg)
    "polyester": 9.5,  # treated as virgin polyester
    "virgin polyester": 9.5,
    "recycled polyester": 3.0,
    "cotton": 5.6,
    "organic cotton": 2.1,
    "viscose": 3.0,
    "lyocell": 2.25,
    "modal": 2.25,
    "wool": 23.0,
    "acrylic": 14.0,
    "elastane": 10.0,
    "spandex": 10.0,
    # practical fallbacks for other common materials in this dataset
    "polyurethane": 8.0,
    "pu": 8.0,
    "rubber": 6.0,
    "recycled rubber": 3.5,
    "ethylene vinyl acetate": 6.0,
    "eva": 6.0,
    "leather": 25.0,
    # additional common textiles / synthetics
    "nylon": 8.0,
    "polyamide": 8.0,
    "recycled nylon": 4.5,
    "polypropylene": 4.0,
    "linen": 3.0,
    "silk": 10.0,
    "nylon": 8.0,
    "polyurethane coated": 9.0,
    "polyester blend": 9.5,
    "recycled cotton": 2.5,
    "cotton blend": 5.6,
}


def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = name.lower()
    s = s.replace("%", "")
    s = re.sub(r"[^a-z0-9\s/\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # common synonyms
    s = s.replace("spandex", "elastane")
    s = s.replace("pu", "polyurethane")
    s = s.replace("eva", "ethylene vinyl acetate")
    s = s.replace("recycled ", "recycled ")
    return s


def extract_percentages(text: str) -> dict:
    """Return dict material -> percentage (0-100) parsed from text.

    Handles both patterns like "26% Recycled polyester" and "Polyester 88%".
    """
    if not isinstance(text, str):
        return {}
    s = text
    results = defaultdict(float)

    # pattern: '26% Recycled polyester' (percent first)
    for m in re.finditer(r"(\d{1,3})%\s*([A-Za-z][A-Za-z0-9\- /]+?)(?=[,\n\r]|$)", s):
        pct = float(m.group(1))
        mat = normalize_name(m.group(2))
        if mat:
            results[mat] += pct

    # pattern: 'Polyester 88%'
    for m in re.finditer(r"([A-Za-z][A-Za-z0-9\- /]+?)\s*(\d{1,3})%", s):
        mat = normalize_name(m.group(1))
        pct = float(m.group(2))
        if mat:
            results[mat] += pct

    # If nothing found, look for 'Material: Polyester' or 'Upper:Polyester 100%'
    if not results:
        # capture entries like 'Upper:Polyester 100%' or 'Upper: Polyester'
        for m in re.finditer(r"[:\n\r]\s*([A-Za-z][A-Za-z0-9\- /]+?)\s*(\d{1,3})?%?\b", s):
            mat = normalize_name(m.group(1))
            pct = m.group(2)
            if pct:
                results[mat] += float(pct)

    # If percentages sum to > 0 and <= 100, we're good. If they sum > 100, normalize.
    total = sum(results.values())
    if total > 0 and total != 100:
        # normalize to 100 (keep relative shares)
        results = {k: (v / total) * 100.0 for k, v in results.items()}

    return dict(results)


def compute_co2_for_row(text: str, co2_factors: dict) -> (float, dict, list):
    pats = extract_percentages(text)
    if not pats:
        return np.nan, {}, []

    co2 = 0.0
    used = {}
    unknown = []

    for mat_raw, pct in pats.items():
        # prefer exact matches, otherwise try tokens
        mat = mat_raw
        factor = None
        if mat in co2_factors:
            factor = co2_factors[mat]
        else:
            # try to find a known key as substring
            for k in co2_factors.keys():
                if k in mat:
                    factor = co2_factors[k]
                    break

        if factor is None:
            unknown.append(mat)
            continue

        used[mat] = {"pct": pct, "factor": factor}
        co2 += (pct / 100.0) * factor

    return co2, used, unknown


def main(csv_path: str):
    df = pd.read_csv(csv_path, dtype=str)

    # choose materials column
    materials_col = None
    for c in ["materials", "composition", "material", "details", "compositions"]:
        if c in df.columns:
            materials_col = c
            break

    if materials_col is None:
        print("No materials/composition-like column found in the CSV. Columns:", df.columns.tolist())
        sys.exit(1)

    # choose grouping column (prefer the ones user suggested)
    group_col = None
    for c in ["product_type_name", "product_group_name", "department_name", "mainCatCode", "productName"]:
        if c in df.columns:
            group_col = c
            break

    print(f"Using materials column: {materials_col}")
    if group_col:
        print(f"Using grouping column: {group_col}")
    else:
        print("No category column found (product_type_name etc.). Grouping will use index.")

    # compute
    co2_list = []
    used_list = []
    unknowns_all = []

    for i, text in df[materials_col].fillna("").items():
        co2_val, used, unknowns = compute_co2_for_row(text, CO2_FACTORS)
        co2_list.append(co2_val)
        used_list.append(json.dumps(used, ensure_ascii=False))
        unknowns_all.append(";".join(unknowns))

    df["co2_per_product"] = pd.Series(co2_list, index=df.index)
    df["materials_parsed"] = pd.Series(used_list, index=df.index)
    df["materials_unknown"] = pd.Series(unknowns_all, index=df.index)

    skipped = df["co2_per_product"].isna().sum()
    print(f"Computed CO2 for products. Skipped (no percentage info) = {skipped} rows")

    # Save full table with CO2
    out_full = "co2_per_product.csv"
    df.to_csv(out_full, index=False)
    print(f"Wrote {out_full}")

    # Grouping and summary
    if group_col:
        grp = df.groupby(group_col)["co2_per_product"].agg(["mean", "std", "count"]).rename(columns={"mean":"mean","std":"std","count":"count"})
        out_summary = "summary_by_product_type.csv"
        grp.to_csv(out_summary)
        print(f"Wrote {out_summary}")

        # Also save an ascending-ordered summary (most sustainable -> least)
        grp_ordered = grp.sort_values("mean", ascending=True)
        out_ordered = "summary_by_product_type_ordered.csv"
        grp_ordered.to_csv(out_ordered)
        print(f"Wrote {out_ordered} (most sustainable -> least)")

        # Top 5 highest-impact (worst)
        top5 = grp.sort_values("mean", ascending=False).head(5)
        top5.to_csv("top5_by_product_type.csv")
        print("Top 5 product types (by mean CO2):")
        print(top5)

        # Bottom 5 (most sustainable)
        bottom5 = grp.sort_values("mean", ascending=True).head(5)
        bottom5.to_csv("bottom5_by_product_type.csv")
        print("Bottom 5 product types (most sustainable):")
        print(bottom5)

        # Bar plot for top 5
        try:
            sns.set(style="whitegrid")

            # Full ordered bar (most sustainable -> least) — save a horizontal annotated bar for the top N categories
            grp_sorted = grp.sort_values("mean", ascending=True)
            top_n = 40
            sel = grp_sorted.head(top_n)
            plt.figure(figsize=(10, max(6, len(sel) * 0.25)))
            ax = sns.barplot(x="mean", y=sel.index, data=sel.reset_index(), palette="viridis")
            ax.set_xlabel("Mean CO2 per product (kg CO2e / kg)")
            ax.set_ylabel(group_col)
            ax.set_title(f"Mean CO2 per product by {group_col} (most sustainable → least) — top {top_n}")
            for p in ax.patches:
                x = p.get_width()
                if np.isfinite(x):
                    ax.text(x + 0.02 * grp['mean'].max(), p.get_y() + p.get_height() / 2, f"{x:.2f}", va='center')
            plt.tight_layout()
            plt.savefig("mean_co2_by_type.png", dpi=150)
            print("Saved mean_co2_by_type.png")

            # Boxplot for categories with >= 5 samples (select top variance candidates)
            sample_counts = grp[grp["count"] >= 5].sort_values("mean", ascending=False).head(12).index.tolist()
            if sample_counts:
                sel2 = df[df[group_col].isin(sample_counts)]
                plt.figure(figsize=(12, 6))
                sns.boxplot(x="co2_per_product", y=group_col, data=sel2, order=sample_counts, palette="Set2")
                plt.xlabel("CO2 per product (kg CO2e / kg)")
                plt.title("CO2 distribution by product type (categories with >=5 samples)")
                plt.tight_layout()
                plt.savefig("boxplot_by_type.png", dpi=150)
                print("Saved boxplot_by_type.png")
        except Exception as e:
            print("Could not create plots:", e)

        # Dominant materials per product type: parse `materials_parsed` JSON stored earlier
        try:
            import json as _json
            dominant = {}
            for name, group in df.groupby(group_col):
                mats = defaultdict(float)
                cnt = 0
                for js in group['materials_parsed'].fillna(''):
                    if not js:
                        continue
                    try:
                        d = _json.loads(js)
                    except Exception:
                        continue
                    for m, info in d.items():
                        mats[m] += info.get('pct', 0.0)
                    cnt += 1
                if cnt > 0:
                    # convert to average percentage
                    for k in mats:
                        mats[k] = mats[k] / cnt
                    # take top 3
                    topm = sorted(mats.items(), key=lambda x: x[1], reverse=True)[:3]
                    dominant[name] = topm
            # save dominant materials summary
            with open('dominant_materials_by_type.csv', 'w', encoding='utf8') as f:
                f.write('product_type,material,avg_pct\n')
                for pt, items in dominant.items():
                    for mat, avg in items:
                        f.write(f'"{pt}","{mat}",{avg:.2f}\n')
            print('Wrote dominant_materials_by_type.csv')
        except Exception as e:
            print('Could not compute dominant materials per type:', e)
    else:
        print("Skipping grouping/plots because no grouping column was found.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compute_co2.py data.csv")
        sys.exit(1)
    main(sys.argv[1])
