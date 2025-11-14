#!/usr/bin/env python3
"""
Aggregate materials across `co2_per_product.csv` and create summaries + plots.

Outputs:
 - `materials_summary.csv` (per-material: products_count, avg_pct, avg_factor, avg_contribution)
 - `materials_by_contribution.png` (bar plot top materials by avg contribution)
 - `materials_by_occurrence.csv` (materials ordered by how many products they appear in)

Usage:
  python materials_summary.py

This expects `co2_per_product.csv` to be present (created by `compute_co2.py`).
"""
import json
from collections import defaultdict
import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


def safe_load(s):
    try:
        return json.loads(s) if isinstance(s, str) and s.strip() else {}
    except Exception:
        return {}


def main():
    df = pd.read_csv('co2_per_product.csv', dtype=str)
    if 'materials_parsed' not in df.columns:
        print('materials_parsed column not found in co2_per_product.csv. Run compute_co2.py first.')
        return

    # Ensure numeric
    df['co2_per_product'] = pd.to_numeric(df.get('co2_per_product', pd.Series([np.nan]*len(df))), errors='coerce')

    # Aggregators
    stats = {}
    # stats[material] = { 'products': set(productIds), 'sum_pct': float, 'sum_contrib': float, 'sum_factor': float, 'occurrences': int }

    for idx, row in df.iterrows():
        product_id = row.get('productId', f'idx_{idx}')
        parsed = safe_load(row.get('materials_parsed', ''))
        # parsed is expected to be dict material->{pct,factor}
        for mat, info in parsed.items():
            pct = float(info.get('pct', 0.0)) if info.get('pct') is not None else 0.0
            factor = float(info.get('factor', math.nan)) if info.get('factor') is not None else math.nan
            contrib = (pct / 100.0) * factor if not math.isnan(factor) else math.nan

            if mat not in stats:
                stats[mat] = {'products': set(), 'sum_pct': 0.0, 'sum_contrib': 0.0, 'sum_factor': 0.0, 'occurrences': 0}

            stats[mat]['products'].add(product_id)
            stats[mat]['sum_pct'] += pct
            if not math.isnan(contrib):
                stats[mat]['sum_contrib'] += contrib
            if not math.isnan(factor):
                stats[mat]['sum_factor'] += factor
            stats[mat]['occurrences'] += 1

    # Build DataFrame
    rows = []
    for mat, d in stats.items():
        prod_count = len(d['products'])
        occurrences = d['occurrences']
        avg_pct = d['sum_pct'] / occurrences if occurrences else 0.0
        avg_factor = d['sum_factor'] / occurrences if occurrences else np.nan
        avg_contrib = d['sum_contrib'] / occurrences if occurrences else np.nan
        rows.append({'material': mat,
                     'products_count': prod_count,
                     'occurrences': occurrences,
                     'avg_pct': avg_pct,
                     'avg_factor': avg_factor,
                     'avg_contribution': avg_contrib})

    mat_df = pd.DataFrame(rows)
    mat_df = mat_df.sort_values('avg_contribution', ascending=False)
    mat_df.to_csv('materials_summary.csv', index=False)
    print('Wrote materials_summary.csv')

    # Also save by occurrences
    occ_df = mat_df.sort_values('occurrences', ascending=False)
    occ_df.to_csv('materials_by_occurrence.csv', index=False)
    print('Wrote materials_by_occurrence.csv')

    # Plots: top 20 by avg_contribution
    sns.set(style='whitegrid')
    topn = mat_df.head(20)
    if not topn.empty:
        plt.figure(figsize=(10, max(4, len(topn)*0.35)))
        ax = sns.barplot(x='avg_contribution', y='material', data=topn, palette='magma')
        ax.set_xlabel('Average CO2 contribution (kg CO2e per product)')
        ax.set_ylabel('Material')
        ax.set_title('Top 20 materials by average per-product CO2 contribution')
        for p in ax.patches:
            x = p.get_width()
            if np.isfinite(x):
                ax.text(x + 0.01 * topn['avg_contribution'].max(), p.get_y() + p.get_height() / 2, f"{x:.2f}", va='center')
        plt.tight_layout()
        plt.savefig('materials_by_contribution.png', dpi=150)
        print('Saved materials_by_contribution.png')

    # Also a scatter: occurrences vs avg_contribution
    plt.figure(figsize=(8,6))
    sns.scatterplot(data=mat_df, x='occurrences', y='avg_contribution', size='products_count', legend=False, alpha=0.7)
    plt.xscale('log')
    plt.xlabel('Occurrences (number of parsed entries, log scale)')
    plt.ylabel('Average CO2 contribution (kg CO2e per product)')
    plt.title('Material prevalence vs average contribution')
    plt.tight_layout()
    plt.savefig('materials_prevalence_vs_contribution.png', dpi=150)
    print('Saved materials_prevalence_vs_contribution.png')


if __name__ == '__main__':
    main()
