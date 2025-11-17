#!/usr/bin/env python3
"""
Create four presentation-ready charts from H&M dataset:
 1) Stacked bar: Material mix by category
 2) Bar: CO2 footprint by category
 3) What-if: replace virgin polyester with recycled polyester
 4) Bubble: Material prioritization (impact vs viability)

Saves PNGs to `figures/`.
"""
import os
import json
from collections import defaultdict

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from adjustText import adjust_text
import matplotlib.patheffects as patheffects
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.font_manager import FontProperties

from compute_co2 import extract_percentages, normalize_name, CO2_FACTORS

# Semantic aggregation patterns: ordered list of (Group Name, list of prefix patterns)
AGG_CATEGORY_PATTERNS = [
    ("Ladies Dresses", ["ladies_dresses_"]),
    ("Men Shoes", ["men_shoes"]),
    ("Ladies Shoes", ["ladies_shoes_"]),
    # Sportswear Men: exclude jumpers/cardigans (kept separate) -> hoodies & t-shirts/tanks only
    ("Men Sportswear", ["men_hoodiessweatshirts_", "men_tshirtstanks_"]),
    # Add Women (Ladies) Sportswear symmetrical grouping (exclude jumpers/cardigans)
    ("Ladies Sportswear", ["ladies_hoodiessweatshirts_", "ladies_tshirtstanks_"]),
    ("Men Jackets & Coats", ["men_jacketscoats_"]),
    ("Ladies Jackets & Coats", ["ladies_jacketscoats_"]),
    ("Men Trousers", ["men_trousers_"]),
    ("Men Jeans", ["men_jeans_"]),
    ("Ladies Trousers", ["ladies_trousers_"]),
    ("Ladies Tops Long Sleeve", ["ladies_tops_longsleeve"]),
    ("Ladies Tops Short Sleeve", ["ladies_tops_shortsleeve"]),
    ("Ladies Basics Tops Long", ["ladies_basics_tops_longsleeve"]),
    ("Ladies Basics Tops Short", ["ladies_basics_tops_shortsleeve"]),
    ("Men Casual Shirts", ["men_shirts_casual"]),
    ("Ladies Shirts & Blouses", ["ladies_shirtsblouses_"]),
    ("Ladies Swimwear", ["ladies_swimwear_"]),
    ("Ladies Nightwear", ["ladies_nightwear_"]),
    ("Ladies Lingerie", ["ladies_lingerie_"]),
    ("Men Hoodies & Sweatshirts", ["men_hoodiessweatshirts_"]),
    ("Men Jumpers", ["men_cardigansjumpers_jumpers"]),
    ("Ladies Cardigans", ["ladies_cardigansjumpers_cardigans"]),
    ("Ladies Jumpers", ["ladies_cardigansjumpers_jumpers"]),
]

def aggregate_category(raw: str) -> str:
    if not isinstance(raw, str):
        return "Other"
    for group_name, patterns in AGG_CATEGORY_PATTERNS:
        for p in patterns:
            if raw.startswith(p):
                return group_name
    return "Other"


def ensure_fig_dir(path="figures"):
    os.makedirs(path, exist_ok=True)
    return path


def find_columns(df):
    materials_col = None
    for c in ["materials", "composition", "material", "details", "compositions"]:
        if c in df.columns:
            materials_col = c
            break

    group_col = None
    for c in ["product_type_name", "product_group_name", "department_name", "mainCatCode", "productName"]:
        if c in df.columns:
            group_col = c
            break

    return materials_col, group_col


def explode_material_percentages(df, materials_col, group_col):
    rows = []
    for idx, row in df.iterrows():
        text = row.get(materials_col, "")
        pats = extract_percentages(text)
        for mat, pct in pats.items():
            rows.append({
                "index": idx,
                "category": row.get(group_col, "Unknown") if group_col else "Unknown",
                "material": mat,
                "pct": float(pct),
            })
    return pd.DataFrame(rows)


def stacked_bar_material_mix(df_exploded, out_path):
    if df_exploded.empty:
        print('No data for material mix')
        return
    # Map to aggregated groups
    df_exploded['agg_category'] = df_exploded['category'].apply(aggregate_category)
    # Remove very small catch-all 'Other' if desired later (kept for now)

    # Sum percentages per (agg_category, material) then normalize within agg_category
    agg = df_exploded.groupby(['agg_category', 'material'])['pct'].sum()
    cat_totals = df_exploded.groupby('agg_category')['pct'].sum()
    share = (agg / cat_totals).reset_index(name='share_pct')

    # Group low-share materials (<3%) into 'Other' inside each aggregated category
    def group_low(g):
        major = g[g['share_pct'] * 100 >= 3.0]
        minor = g[g['share_pct'] * 100 < 3.0]
        if not minor.empty:
            other_row = pd.DataFrame({
                'agg_category': [g['agg_category'].iloc[0]],
                'material': ['Other'],
                'share_pct': [minor['share_pct'].sum()]
            })
            return pd.concat([major, other_row], ignore_index=True)
        return major

    grouped_rows = []
    for cat, g in share.groupby('agg_category'):
        grouped_rows.append(group_low(g))
    share_grouped = pd.concat(grouped_rows, ignore_index=True)

    pivot = share_grouped.pivot(index='agg_category', columns='material', values='share_pct').fillna(0) * 100

    # Order aggregated categories by total number of original products (descending)
    prod_counts = df_exploded.groupby('agg_category')['index'].nunique().sort_values(ascending=False)
    ordered_cats = prod_counts.index.tolist()
    pivot = pivot.loc[ordered_cats]

    # Limit to 30 aggregated categories max (most should fit well below)
    pivot = pivot.head(30)

    # Order materials globally (excluding Other last)
    material_order = pivot.mean().sort_values(ascending=False).index.tolist()
    if 'Other' in material_order:
        material_order = [m for m in material_order if m != 'Other'] + ['Other']
    pivot = pivot[material_order]

    sns.set(style='whitegrid')
    fig_height = max(6, pivot.shape[0] * 0.5)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    pivot.plot(kind='barh', stacked=True, ax=ax, width=0.85, colormap='tab20')
    ax.set_xlabel('Material share within aggregated category (%)')
    ax.set_ylabel('Category')
    ax.set_title('Material Mix by Aggregated Category')
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(lambda v, pos: f'{int(v)}%')
    ax.legend(title='Material', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9)

    # Annotate segments ≥18%
    for c_idx, cat in enumerate(pivot.index):
        left = 0
        for mat in material_order:
            val = pivot.loc[cat, mat]
            if val <= 0:
                continue
            if val >= 18:
                ax.text(left + val/2, c_idx, f'{mat}\n{val:.0f}%', ha='center', va='center', fontsize=7, color='white', weight='bold')
            left += val

    plt.tight_layout()
    fname = os.path.join(out_path, 'material_mix_by_category.png')
    plt.savefig(fname, dpi=200)
    plt.close(fig)
    print('Saved', fname)
    print('Aggregated categories used (material mix):', list(pivot.index))


def co2_by_category(df, out_path, raw_group_col):
    if 'co2_per_product' not in df.columns:
        raise RuntimeError('`co2_per_product` column not found. Run compute_co2.py first or compute co2.')
    if raw_group_col not in df.columns:
        print('Group column missing for CO2 chart')
        return
    # Build aggregated category on original df
    df['agg_category'] = df[raw_group_col].apply(aggregate_category)
    grp = df.groupby('agg_category')['co2_per_product'].agg(['mean', 'count'])
    grp = grp.dropna(subset=['mean'])
    # Order by product count desc
    grp = grp.sort_values('count', ascending=False)
    # Limit to 30 groups
    grp = grp.head(30)
    plot_df = grp['mean']

    labels = plot_df.index.tolist()
    sns.set(style='whitegrid')
    fig_height = max(6, len(plot_df) * 0.45)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    sns.barplot(x=plot_df.values, y=labels, palette='rocket', ax=ax)
    ax.set_xlabel('Mean CO$_2$ per product (kg CO$_2$ per kg)')
    ax.set_ylabel('Aggregated Category')
    ax.set_title('CO$_2$ Footprint by Aggregated Category')
    plt.subplots_adjust(left=0.35)
    ax.tick_params(axis='y', labelsize=10)
    xmax = plot_df.max()
    for p in ax.patches:
        x = p.get_width()
        y = p.get_y() + p.get_height() / 2
        label_txt = f"{x:.2f}"
        if x > 0.12 * xmax:
            ax.text(x - 0.01 * xmax, y, label_txt, va='center', ha='right', color='white', fontsize=9)
        else:
            ax.text(x + 0.01 * xmax, y, label_txt, va='center', ha='left', fontsize=9)
    plt.tight_layout()
    fname = os.path.join(out_path, 'co2_by_category.png')
    plt.savefig(fname, dpi=200)
    plt.close(fig)
    print('Saved', fname)
    print('Aggregated categories used (CO2):', labels)


def what_if_reduce_wool_nylon_leather(df_exploded, df_full, out_path):
    """What-if: reduce wool, nylon and leather by 30% across all categories.

    Approximation: use exploded material shares and CO2 factors to estimate
    the contribution of wool/nylon/leather across the full catalog, then
    apply a 30% reduction to that contribution and recompute a new total
    catalog CO2.
    """
    if 'co2_per_product' not in df_full.columns:
        print('co2_per_product not found; skipping wool/nylon/leather what-if')
        return

    df_exploded = df_exploded.copy()

    # Materials of interest
    target_materials = {'wool', 'nylon', 'leather'}

    # Known factors series for mapping
    factor_series = pd.Series(CO2_FACTORS, name='factor').astype(float)
    median_factor = factor_series.dropna().median() if not factor_series.empty else 5.0

    # Contribution of each exploded row (approximate, using factors and pct)
    df_exploded['co2_factor'] = df_exploded['material'].map(CO2_FACTORS).fillna(median_factor).astype(float)
    df_exploded['co2_contribution'] = (df_exploded['pct'].astype(float) / 100.0) * df_exploded['co2_factor']

    # Filter wool/nylon/leather rows (all categories)
    mask_target_mat = df_exploded['material'].str.lower().apply(
        lambda m: any(t in m for t in target_materials) if isinstance(m, str) else False
    )
    current_total_co2 = df_full['co2_per_product'].dropna().astype(float).sum()
    current_target_co2 = df_exploded.loc[mask_target_mat, 'co2_contribution'].sum()

    # Scenario: 30% reduction of these contributions
    reduction_frac = 0.30
    new_target_co2 = current_target_co2 * (1 - reduction_frac)
    new_total_co2 = current_total_co2 - current_target_co2 + new_target_co2

    # Build tiny dataframe for plotting
    res_df = pd.DataFrame([
        {'scenario': 'Baseline', 'total_co2': current_total_co2},
        {'scenario': '30% less wool/nylon/leather', 'total_co2': new_total_co2},
    ])

    # Plot
    sns.set(style='whitegrid')
    fig, ax = plt.subplots(figsize=(9, 5))

    labels = res_df['scenario'].tolist()
    vals = res_df['total_co2'].values
    colors = ['#4C72B0', '#DD8452']
    bars = ax.bar(labels, vals, color=colors, width=0.55)

    ax.set_ylabel('Total catalog CO$_2$ (relative units)', fontsize=12)
    ax.set_title('What-if: 30% Less Wool, Nylon and Leather', fontsize=14, weight='bold')
    ax.tick_params(axis='x', labelrotation=0, labelsize=10)
    ax.tick_params(axis='y', labelsize=11)

    baseline = vals[0]
    scen = vals[1]
    reduction_pct = (baseline - scen) / baseline * 100 if baseline > 0 else 0.0

    ymax = vals.max()
    for b, v in zip(bars, vals):
        x = b.get_x() + b.get_width() / 2.0
        ax.text(x, v + 0.015 * ymax, f"{v:.1f}", ha='center', va='bottom', fontsize=10, weight='medium')

    ax.text(bars[1].get_x() + bars[1].get_width() / 2.0,
            scen + 0.06 * ymax,
            f"−{reduction_pct:.1f}% vs baseline",
            ha='center', va='bottom', fontsize=11, color='#DD8452', fontweight='bold')

    ax.set_ylim(0, ymax * 1.22)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    plt.tight_layout(rect=[0.02, 0.02, 0.98, 0.98])

    fname = os.path.join(out_path, 'whatif_reduce_wool_nylon_leather.png')
    plt.savefig(fname, dpi=200)
    plt.close(fig)
    print('Saved', fname)


def what_if_replace_polyester(df_exploded, df_full, out_path):
    # Identify virgin polyester entries (material == 'polyester' but not 'recycled polyester')
    is_vp = df_exploded['material'].apply(lambda x: 'polyester' in x and 'recycled' not in x)
    vp_rows = df_exploded[is_vp]

    # total virgin polyester mass fraction across dataset (in % -> convert to fraction)
    total_vp_mass_frac = (vp_rows['pct'] / 100.0).sum()
    virgin_factor = CO2_FACTORS.get('polyester', CO2_FACTORS.get('virgin polyester', 9.5))
    recycled_factor = CO2_FACTORS.get('recycled polyester', 3.0)

    # current CO2 attributable to virgin polyester
    current_vp_co2 = total_vp_mass_frac * virgin_factor

    # current total CO2 (sum of co2_per_product across df_full rows)
    # `co2_per_product` in compute_co2 is per product (kg CO2e per kg); sum approximates total catalog intensity
    total_current_co2 = df_full['co2_per_product'].dropna().astype(float).sum()

    # Baseline (0%) + one scenario with 60% replacement by recycled polyester
    scenarios = [0.0, 0.60]
    results = []
    for idx, r in enumerate(scenarios):
        # Scenario logic:
        #  - idx == 0 (r = 0.0): baseline, no change
        #  - idx == 1: 60% of virgin polyester replaced by recycled polyester
        if idx == 1:
            new_vp_co2 = (1 - r) * total_vp_mass_frac * virgin_factor + r * total_vp_mass_frac * recycled_factor
        else:
            # baseline
            new_vp_co2 = current_vp_co2
        total_new_co2 = total_current_co2 - current_vp_co2 + new_vp_co2
        savings = total_current_co2 - total_new_co2
        results.append({'replace_pct': r*100, 'total_co2': total_new_co2, 'savings': savings})

    res_df = pd.DataFrame(results)

    # plot: show Baseline + one 60% replacement scenario, with presentation styling
    sns.set(style='whitegrid')
    fig, ax = plt.subplots(figsize=(8, 5))

    labels = ['Baseline', '60% replaced by recycled polyester']
    vals = res_df['total_co2'].values

    # order bars so the improved scenario appears after baseline
    colors = ['#4C72B0', '#55A868']
    bars = ax.bar(labels, vals, color=colors, width=0.55)

    ax.set_ylabel('Total catalog CO$_2$ (relative units)', fontsize=12)
    ax.set_title('What-if: 60% of Virgin Polyester Replaced by Recycled Polyester', fontsize=14, weight='bold')
    ax.tick_params(axis='x', labelrotation=0, labelsize=11)
    ax.tick_params(axis='y', labelsize=11)

    # percentage reduction vs baseline for the 60% replacement scenario
    baseline = vals[0]
    scen1 = vals[1]
    red1 = (baseline - scen1) / baseline * 100 if baseline > 0 else 0.0

    ymax = vals.max()
    for i, (b, v) in enumerate(zip(bars, vals)):
        x = b.get_x() + b.get_width() / 2.0
        ax.text(x, v + 0.015 * ymax, f"{v:.1f}", ha='center', va='bottom', fontsize=10, weight='medium')

        # annotate reduction above the 60% scenario bar
        ax.text(bars[1].get_x() + bars[1].get_width() / 2.0,
            scen1 + 0.06 * ymax,
            f"−{red1:.1f}% vs baseline",
            ha='center', va='bottom', fontsize=11, color='#55A868', fontweight='bold')

    # tidy axes for a cleaner, more professional look
    ax.set_ylim(0, ymax * 1.22)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    plt.tight_layout(rect=[0.02, 0.02, 0.98, 0.98])
    fname = os.path.join(out_path, 'whatif_replace_polyester.png')
    plt.savefig(fname, dpi=200)
    plt.close(fig)
    print('Saved', fname)


def bubble_chart_material_prioritization(df_exploded, out_path, label_top_n=15):
    # For each material compute: CO2 factor (x), viability (y), usage volume (size)
    # Usage volume: sum of % across dataset (higher => more used)
    usage = df_exploded.groupby('material')['pct'].sum()

    materials = usage.index.tolist()
    factors = [CO2_FACTORS.get(m, np.nan) for m in materials]

    # Manual viability scores (1=low viability to 5=high viability). These are example values and can be edited.
    default_viability = {
        'polyester': 4,
        'recycled polyester': 5,
        'nylon': 3,
        'recycled nylon': 4,
        'viscose': 2,
        'cotton': 3,
        'recycled cotton': 4,
        'wool': 2,
        'elastane': 2,
        'polyurethane': 2,
        'rubber': 3,
        'leather': 1,
    }

    viabilities = [default_viability.get(m.split()[0], 3) for m in materials]

    # Build DataFrame
    mm = pd.DataFrame({
        'material': materials,
        'usage_pct_total': usage.values,
        'co2_factor': factors,
        'viability': viabilities,
    })

    # Fill missing CO2 factors with median
    if mm['co2_factor'].isna().any():
        mm['co2_factor'] = mm['co2_factor'].fillna(mm['co2_factor'].median())

    # bubble size scale (slightly increased for presentation)
    mm['size'] = (mm['usage_pct_total'] / mm['usage_pct_total'].max()) * 2600 + 80

    # Styling: use a colorblind-friendly colormap, clear grid and larger fonts
    sns.set_theme(style='whitegrid', rc={'axes.titlesize': 18, 'axes.labelsize': 14, 'legend.fontsize': 12, 'xtick.labelsize':12, 'ytick.labelsize':12})
    # slightly narrower figure to reduce empty right-hand space
    fig, ax = plt.subplots(figsize=(28, 12))

    # Use 'viridis' (colorblind-friendly) for CO2 factor and dark edges for bubbles
    cmap = plt.cm.viridis
    norm = plt.Normalize(vmin=mm['co2_factor'].min(), vmax=mm['co2_factor'].max())

    # Draw the scatter at original data coordinates (no repulsion)
    sc = ax.scatter(mm['co2_factor'], mm['viability'], s=mm['size'], alpha=0.85,
                    c=mm['co2_factor'], cmap=cmap, norm=norm, edgecolors='black', linewidth=0.6)

    ax.set_xlabel('CO$_2$ factor (kg CO$_2$e per kg)')
    ax.set_ylabel('Viability (1 = low → 5 = high)')
    ax.set_title('Material Prioritization — Impact vs Viability')

    # Add median reference lines to form quadrants (helps interpretation)
    x_med = mm['co2_factor'].median()
    y_med = mm['viability'].median()
    ax.axvline(x=x_med, color='grey', linestyle='--', linewidth=0.9)
    ax.axhline(y=y_med, color='grey', linestyle='--', linewidth=0.9)

    # Lightly shade the high-impact / low-viability quadrant
    ax.axvspan(x_med, mm['co2_factor'].max(), ymin=0, ymax=(y_med - ax.get_ylim()[0]) / (ax.get_ylim()[1] - ax.get_ylim()[0]),
               color='#fde0dd', alpha=0.25)

    # Create a colorbar for CO2 factor
    cbar = plt.colorbar(sc, ax=ax)
    cbar.ax.set_ylabel('CO$_2$ factor', fontsize=14, rotation=90, labelpad=20)
    cbar.ax.yaxis.set_label_position('left')
    cbar.ax.tick_params(labelsize=13)

    # Create a size legend: pick a few representative sizes
    max_size = mm['size'].max()
    size_legend_vals = [0.25, 0.5, 1.0]
    size_labels = [f"{int(v*100)}% usage" for v in size_legend_vals]
    # Build custom legend handles using Line2D so we can control marker size
    legend_handles = []
    for v in size_legend_vals:
        s = max_size * v
        # scatter 's' is area in points^2; convert to marker diameter (points)
        msize = np.sqrt(s)
        # scale down a bit so markers don't touch when legend entries are stacked
        msize = msize * 0.65
        legend_handles.append(Line2D([0], [0], marker='o', linestyle='None', markeredgecolor='k', markerfacecolor='white', markersize=msize))

    # (Combined inset creation moved below after `label_df` is defined.)
    # Place labels for top-N materials inside the plotting area (near their points) and
    # use adjustText to reduce overlaps. This keeps labels readable while staying within the grid.
    top_n = int(label_top_n) if label_top_n is not None else 0
    if top_n and top_n < len(mm):
        label_df = mm.nlargest(top_n, 'usage_pct_total')
    else:
        label_df = mm.copy()

    x_min, x_max = mm['co2_factor'].min(), mm['co2_factor'].max()
    x_range = x_max - x_min if x_max > x_min else 1.0

    # Instead of leader lines, label the top-N bubbles with numbers (grouped
    # when multiple materials share coordinates) and place the numbered legend
    # outside the grid to the left.
    top_n = int(label_top_n) if label_top_n is not None else 0
    if top_n and top_n < len(mm):
        label_df = mm.nlargest(top_n, 'usage_pct_total').copy()
    else:
        label_df = mm.copy()

    # Assign numbers to the selected materials
    label_df = label_df.reset_index(drop=True)
    label_df['num'] = label_df.index + 1

    # Create explicit labels for each numbered material so numbers 1..top_n
    # appear individually on the plot. For single-number bubbles the number
    # is drawn inside the bubble; for multiple numbers a small box is drawn
    # offset from the bubble and a connector line links them.
    group_map = {}
    for _, row in label_df.iterrows():
        key = (round(float(row['co2_factor']), 4), round(float(row['viability']), 4))
        group_map.setdefault(key, []).append(row)

    texts = []
    xs = []
    ys = []
    y_min, y_max = mm['viability'].min(), mm['viability'].max()
    y_range = y_max - y_min if y_max > y_min else 1.0
    x_min, x_max = mm['co2_factor'].min(), mm['co2_factor'].max()
    x_range = x_max - x_min if x_max > x_min else 1.0
    # box sizing (in data units)
    box_w = 0.04 * x_range
    box_h = 0.04 * y_range
    # Use a single consistent font size for all numeric labels (slightly larger)
    label_fontsize = 18
    single_fontsize = label_fontsize
    multi_fontsize = label_fontsize

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    bubble_bboxes_all = []
    for _, row_all in mm.iterrows():
        cx_all, cy_all = ax.transData.transform((float(row_all['co2_factor']), float(row_all['viability'])))
        s_all = float(row_all['size'])
        diam_pts_all = np.sqrt(max(s_all, 1.0))
        radius_px_all = (diam_pts_all / 2.0) * fig.dpi / 72.0
        bubble_bboxes_all.append((cx_all - radius_px_all, cy_all - radius_px_all,
                                  cx_all + radius_px_all, cy_all + radius_px_all,
                                  cx_all, cy_all))

    placed_boxes = []
    bbox_pad_px = 18

    def expanded_text_bbox(text_obj):
        tb = text_obj.get_window_extent(renderer=renderer)
        return tb.expanded(1.0 + bbox_pad_px / max(1.0, tb.width),
                           1.0 + bbox_pad_px / max(1.0, tb.height))
    for key, rows in group_map.items():
        n = len(rows)
        rows_sorted = sorted(rows, key=lambda r: int(r['num']))
        # bubble center (original data coords)
        px = float(rows_sorted[0]['co2_factor'])
        py = float(rows_sorted[0]['viability'])
        if n == 1:
            num_text = str(int(rows_sorted[0]['num']))
            t = ax.text(px, py, num_text, ha='center', va='center', fontsize=single_fontsize, color='black', weight='bold', zorder=6)
            t.set_path_effects([patheffects.withStroke(linewidth=3, foreground='white')])
            texts.append(t)
            xs.append(px)
            ys.append(py)
        else:
            box_offset_x = 0.08 * x_range
            box_offset_y = 0.10 * y_range
            bx = px + box_offset_x
            by = py + box_offset_y
            if bx + box_w/2 > x_max:
                bx = px - box_offset_x
            if bx - box_w/2 < x_min:
                bx = px + box_offset_x
            if by + box_h/2 > y_max:
                by = py - box_offset_y
            if by - box_h/2 < y_min:
                by = py + box_offset_y

            joined = "\n".join([str(int(r['num'])) for r in rows_sorted])

            t = ax.text(bx, by, joined, ha='center', va='center', fontsize=multi_fontsize,
                        color='black', weight='bold', zorder=9)
            t.set_path_effects([patheffects.withStroke(linewidth=2, foreground='white')])

            cur_tbbox = expanded_text_bbox(t)

            px_disp, py_disp = ax.transData.transform((px, py))
            s_val = float(rows_sorted[0]['size']) if 'size' in rows_sorted[0].index else mm.loc[mm['material'] == rows_sorted[0]['material'], 'size'].iat[0]
            marker_diam_pts = np.sqrt(max(s_val, 1.0))
            px_per_point = fig.dpi / 72.0
            radius_px = (marker_diam_pts / 2.0) * px_per_point
            bubble_bbox = (px_disp - radius_px, py_disp - radius_px,
                           px_disp + radius_px, py_disp + radius_px, px_disp, py_disp)

            def overlaps_other_bubbles(tb):
                for bb in bubble_bboxes_all:
                    if abs(bb[4] - bubble_bbox[4]) < 1.0 and abs(bb[5] - bubble_bbox[5]) < 1.0:
                        continue
                    if not (tb.x1 < bb[0] or tb.x0 > bb[2] or tb.y1 < bb[1] or tb.y0 > bb[3]):
                        return True
                return False

            box_cx = (cur_tbbox.x0 + cur_tbbox.x1) / 2.0
            box_cy = (cur_tbbox.y0 + cur_tbbox.y1) / 2.0
            dir_x = box_cx - px_disp
            dir_y = box_cy - py_disp
            norm = np.hypot(dir_x, dir_y)
            if norm == 0:
                dir_x, dir_y = 1.0, 0.0
                norm = 1.0
            ux, uy = dir_x / norm, dir_y / norm

            step_px = 10
            max_iter = 25
            iter_count = 0
            shifted = False
            while iter_count < max_iter:
                overlap_self = not (cur_tbbox.x1 < bubble_bbox[0] or cur_tbbox.x0 > bubble_bbox[2] or
                                    cur_tbbox.y1 < bubble_bbox[1] or cur_tbbox.y0 > bubble_bbox[3])
                overlap_box = False
                for pb in placed_boxes:
                    if not (cur_tbbox.x1 < pb[0] or cur_tbbox.x0 > pb[2] or cur_tbbox.y1 < pb[1] or cur_tbbox.y0 > pb[3]):
                        overlap_box = True
                        break
                overlap_other = overlaps_other_bubbles(cur_tbbox)

                if not overlap_self and not overlap_box and not overlap_other:
                    break

                cur_tbbox = cur_tbbox.translated(ux * step_px, uy * step_px)
                iter_count += 1
                shifted = True

            if shifted:
                new_cx = (cur_tbbox.x0 + cur_tbbox.x1) / 2.0
                new_cy = (cur_tbbox.y0 + cur_tbbox.y1) / 2.0
                new_data_x, new_data_y = ax.transData.inverted().transform((new_cx, new_cy))
                t.set_position((new_data_x, new_data_y))
                cur_tbbox = expanded_text_bbox(t)

            def has_any_overlap(tb):
                if not (tb.x1 < bubble_bbox[0] or tb.x0 > bubble_bbox[2] or tb.y1 < bubble_bbox[1] or tb.y0 > bubble_bbox[3]):
                    return True
                for pb in placed_boxes:
                    if not (tb.x1 < pb[0] or tb.x0 > pb[2] or tb.y1 < pb[1] or tb.y0 > pb[3]):
                        return True
                if overlaps_other_bubbles(tb):
                    return True
                return False

            if has_any_overlap(cur_tbbox):
                base_pos = t.get_position()
                candidate_offsets = [
                    (0.14 * x_range, 0.18 * y_range),
                    (0.14 * x_range, -0.18 * y_range),
                    (-0.14 * x_range, 0.18 * y_range),
                    (-0.14 * x_range, -0.18 * y_range),
                    (0.0, 0.22 * y_range),
                    (0.0, -0.22 * y_range),
                    (0.22 * x_range, 0.0),
                    (-0.22 * x_range, 0.0)
                ]
                placed = False
                for dx_data, dy_data in candidate_offsets:
                    candidate_pos = (px + dx_data, py + dy_data)
                    t.set_position(candidate_pos)
                    candidate_tbbox = expanded_text_bbox(t)
                    if not has_any_overlap(candidate_tbbox):
                        cur_tbbox = candidate_tbbox
                        placed = True
                        break
                if not placed:
                    t.set_position(base_pos)
                    cur_tbbox = expanded_text_bbox(t)

            cur_tbbox = cur_tbbox.expanded(1.12, 1.18)

            x0_disp, y0_disp = cur_tbbox.x0, cur_tbbox.y0
            x1_disp, y1_disp = cur_tbbox.x1, cur_tbbox.y1
            (x0_data, y0_data) = ax.transData.inverted().transform((x0_disp, y0_disp))
            (x1_data, y1_data) = ax.transData.inverted().transform((x1_disp, y1_disp))
            w_data = x1_data - x0_data
            h_data = y1_data - y0_data

            rect_cx = x0_data + w_data / 2.0
            rect_cy = y0_data + h_data / 2.0
            ax.plot([px, rect_cx], [py, rect_cy], color='gray', linewidth=0.9, zorder=6)

            rect = Rectangle((x0_data, y0_data), w_data, h_data, transform=ax.transData,
                             facecolor='white', edgecolor='gray', linewidth=1.0, zorder=8, alpha=0.95)
            ax.add_patch(rect)
            t.set_zorder(10)

            placed_boxes.append([x0_disp, y0_disp, x1_disp, y1_disp])

    # Nudge labels if they overlap, but do not draw arrows
    try:
        adjust_text(texts, x=xs, y=ys, ax=ax,
                    expand_text=(1.02, 1.1), expand_points=(1.02, 1.1),
                    force_text=0.4, force_points=0.2,
                    arrowprops=None)
    except Exception:
        pass

    # Build left-side numbered legend text (material name -> number)
    items_sorted = label_df[['material', 'num']].sort_values('num').values.tolist()
    lines = [f"{int(num)}. {mat}" for mat, num in items_sorted]
    legend_text = "\n".join(lines)

    # Place the numbered legend to the right of the colorbar in a boxed callout
    # Reserve more room on the right by tightening the plotting area.
    # Move plotting right edge left so colorbar + legend fit at the right.
    plt.subplots_adjust(left=0.08, right=0.70)
    fig.canvas.draw()

    # Place a single combined inset (size legend + numbered materials) anchored to the
    # right of the CO2 colorbar. Compute the box dimensions from the text metrics so
    # the padding stays tight even with larger fonts.
    try:
        cbar_pos = cbar.ax.get_position()

        renderer = fig.canvas.get_renderer()

        font_size_list = 12
        font_prop_list = FontProperties(size=font_size_list)
        line_gap_px = font_size_list * fig.dpi / 72.0 * 0.4
        max_line_width_px = 0.0
        text_height_px = 0.0
        for line in lines:
            w, h, _ = renderer.get_text_width_height_descent(line, font_prop_list, ismath=False)
            max_line_width_px = max(max_line_width_px, w)
            text_height_px += h
        if lines:
            text_height_px += line_gap_px * (len(lines) - 1)

        size_marker_scale = 0.20
        size_marker_sizes = [max_size * v * size_marker_scale for v in size_legend_vals]
        size_label_fontsize = 12
        font_prop_size = FontProperties(size=size_label_fontsize)
        size_label_width_px = 0.0
        marker_diams_px = []
        for label, size_s in zip(size_labels, size_marker_sizes):
            w_lbl, _, _ = renderer.get_text_width_height_descent(label, font_prop_size, ismath=False)
            size_label_width_px = max(size_label_width_px, w_lbl)
            diam_pts = np.sqrt(max(size_s, 1.0))
            marker_diams_px.append(min(36.0, diam_pts * fig.dpi / 72.0))
        max_marker_diam_px = max(marker_diams_px) if marker_diams_px else 26.0
        size_line_height_px = max_marker_diam_px + 32
        size_section_height_px = len(size_labels) * size_line_height_px
        size_section_width_px = max_marker_diam_px + 8 + size_label_width_px

        padding_px = 6
        gap_px = 10

        content_width_px = max(size_section_width_px, max_line_width_px) + padding_px * 2
        content_height_px = size_section_height_px + gap_px + text_height_px + padding_px * 2

        fig_width_px = fig.get_figwidth() * fig.dpi
        fig_height_px = fig.get_figheight() * fig.dpi

        box_w = min(0.26, content_width_px / fig_width_px)
        box_h = min(0.64, content_height_px / fig_height_px)

        pad_x = max(0.04, cbar_pos.width * 1.3)
        box_x = min(0.97 - box_w, cbar_pos.x1 + pad_x)
        cbar_mid = (cbar_pos.y0 + cbar_pos.y1) / 2.0
        box_y = cbar_mid - box_h / 2.0
        box_y = max(0.02, min(box_y, 0.96 - box_h))

        ax_box = fig.add_axes([box_x, box_y, box_w, box_h])
        ax_box.set_zorder(cbar.ax.get_zorder() + 5)
        ax_box.set_xlim(0, 1)
        ax_box.set_ylim(0, 1)
        ax_box.axis('off')

        total_width_px = content_width_px
        total_height_px = content_height_px

        def px_to_ax_x(px):
            return px / total_width_px

        def px_to_ax_y(px):
            return px / total_height_px

        current_y_px = total_height_px - padding_px

        marker_x_center_px = padding_px + max_marker_diam_px / 2.0
        label_x_px = marker_x_center_px + max_marker_diam_px / 2.0 + 20

        for label, diam_px, size_s in zip(size_labels, marker_diams_px, size_marker_sizes):
            y_center_px = current_y_px - size_line_height_px / 2.0
            ax_box.scatter(px_to_ax_x(marker_x_center_px), px_to_ax_y(y_center_px),
                           s=size_s, c='white', edgecolors='black', linewidth=0.8,
                           transform=ax_box.transAxes, zorder=3, clip_on=False)
            ax_box.text(px_to_ax_x(label_x_px), px_to_ax_y(y_center_px), label,
                        fontsize=size_label_fontsize, va='center', ha='left',
                        transform=ax_box.transAxes, clip_on=False)
            current_y_px -= size_line_height_px

        current_y_px -= gap_px

        ax_box.text(px_to_ax_x(padding_px), px_to_ax_y(current_y_px), legend_text,
                    fontsize=font_size_list, va='top', ha='left', transform=ax_box.transAxes,
                    linespacing=1.15, clip_on=False)

        from matplotlib.patches import FancyBboxPatch
        patch = FancyBboxPatch((box_x, box_y), box_w, box_h,
                               boxstyle='round,pad=0.01', transform=fig.transFigure,
                               facecolor='white', edgecolor='gray', linewidth=1.1,
                               zorder=ax_box.get_zorder() - 1, alpha=0.99)
        fig.patches.append(patch)
    except Exception:
        # fallback: put a simple size legend on the figure
        legend1 = ax.legend(legend_handles, size_labels, title='Relative usage', frameon=True,
                            loc='upper left', bbox_to_anchor=(0.74, 0.88), bbox_transform=fig.transFigure,
                            prop={'size':14}, labelspacing=1.2, handletextpad=0.6, fancybox=True, borderpad=1.4)
        legend1.set_title('Relative usage')
        legend1.set_zorder(20)

    # Tight x-limits with a small margin so bubbles remain visible
    ax.set_xlim(x_min - 0.05 * x_range, x_max + 0.05 * x_range)

    # Improve layout and save high-resolution image
    fname = os.path.join(out_path, 'material_prioritization_bubble.png')
    plt.savefig(fname, dpi=400)
    plt.close(fig)
    print('Saved', fname)


def material_frequency(df_exploded, out_path, top_n=25, group_rest=True):
    """Bar chart of material frequency across products.

    - Frequency = number of unique products that include the material (based on original index).
    - Shows top_n materials; optionally groups the rest into 'Other'.
    """
    if df_exploded.empty:
        print('No exploded material data; skipping material frequency chart')
        return

    counts = df_exploded.groupby('material')['index'].nunique().sort_values(ascending=False)

    if top_n and len(counts) > top_n:
        top_counts = counts.head(top_n)
        if group_rest:
            other_sum = counts.iloc[top_n:].sum()
            top_counts = pd.concat([top_counts, pd.Series({'Other': other_sum})])
        plot_counts = top_counts
    else:
        plot_counts = counts

    sns.set(style='whitegrid')
    fig_height = max(6, len(plot_counts) * 0.35)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    sns.barplot(x=plot_counts.values, y=plot_counts.index.tolist(), palette='Blues_r', ax=ax)
    ax.set_xlabel('Number of products containing material')
    ax.set_ylabel('Material')
    ax.set_title('Material Frequency (Top {})'.format(min(top_n, len(counts))))

    # Annotate counts
    xmax = plot_counts.max()
    for p in ax.patches:
        x = p.get_width()
        y = p.get_y() + p.get_height() / 2
        label_txt = f"{int(x)}"
        if x > 0.12 * xmax:
            ax.text(x - 0.01 * xmax, y, label_txt, va='center', ha='right', color='white', fontsize=9)
        else:
            ax.text(x + 0.01 * xmax, y, label_txt, va='center', ha='left', fontsize=9)

    plt.tight_layout()
    fname = os.path.join(out_path, 'material_frequency.png')
    plt.savefig(fname, dpi=200)
    plt.close(fig)
    print('Saved', fname)

def co2_footprint_by_material(df_exploded, out_path, top_n=25, group_rest=True):
    """Estimate total CO₂ contribution per material across dataset.

    Contribution formula (approximation): sum over all exploded rows of
        (pct / 100) * CO2_FACTOR(material)
    This treats pct as mass fraction proxy.
    Materials lacking a factor use median of known factors.
    """
    if df_exploded.empty:
        print('No exploded material data; skipping CO2 footprint per material chart')
        return

    # Known factors series
    factor_series = pd.Series(CO2_FACTORS, name='factor')
    known_factors = factor_series.dropna().astype(float)
    median_factor = known_factors.median() if not known_factors.empty else 5.0

    # Map material -> factor
    df_exploded['co2_factor'] = df_exploded['material'].map(CO2_FACTORS).fillna(median_factor).astype(float)
    df_exploded['co2_contribution'] = (df_exploded['pct'].astype(float) / 100.0) * df_exploded['co2_factor']

    contrib = df_exploded.groupby('material')['co2_contribution'].sum().sort_values(ascending=False)
    total = contrib.sum()

    if top_n and len(contrib) > top_n:
        top_contrib = contrib.head(top_n)
        if group_rest:
            other_sum = contrib.iloc[top_n:].sum()
            top_contrib = pd.concat([top_contrib, pd.Series({'Other': other_sum})])
        plot_contrib = top_contrib
    else:
        plot_contrib = contrib

    # Percentage share of total for annotations
    shares = (plot_contrib / total) * 100

    sns.set(style='whitegrid')
    fig_height = max(6, len(plot_contrib) * 0.35)
    fig, ax = plt.subplots(figsize=(12, fig_height))
    sns.barplot(x=plot_contrib.values, y=plot_contrib.index.tolist(), palette='Reds', ax=ax)
    ax.set_xlabel('Estimated total CO$_2$ contribution (relative units)')
    ax.set_ylabel('Material')
    ax.set_title('CO$_2$ Footprint by Material (Top {})'.format(min(top_n, len(contrib))))

    xmax = plot_contrib.max()
    for i, p in enumerate(ax.patches):
        x = p.get_width()
        y = p.get_y() + p.get_height() / 2
        label_txt = f"{x:.1f} ({shares.iloc[i]:.1f}%)"
        if x > 0.18 * xmax:
            ax.text(x - 0.01 * xmax, y, label_txt, va='center', ha='right', color='white', fontsize=8)
        else:
            ax.text(x + 0.01 * xmax, y, label_txt, va='center', ha='left', fontsize=8)

    plt.tight_layout()
    fname = os.path.join(out_path, 'co2_by_material.png')
    plt.savefig(fname, dpi=200)
    plt.close(fig)
    print('Saved', fname)

def main():
    base = os.path.dirname(__file__)
    data_path = os.path.join(base, 'data.csv')
    if not os.path.exists(data_path):
        raise FileNotFoundError('data.csv not found in project folder')

    df = pd.read_csv(data_path, dtype=str)
    materials_col, group_col = find_columns(df)
    if materials_col is None:
        raise RuntimeError('Could not find materials/composition column in CSV')

    print('Using materials column:', materials_col)
    print('Using group/ category column:', group_col)

    out_dir = ensure_fig_dir(os.path.join(base, 'figures'))

    # Explode percentages
    df_exploded = explode_material_percentages(df, materials_col, group_col)

    # Ensure we have co2_per_product: try to load compute_co2 output if present
    co2_path = os.path.join(base, 'co2_per_product.csv')
    if os.path.exists(co2_path):
        df_full = pd.read_csv(co2_path)
    else:
        # attempt to compute by reusing compute_co2 logic (importing compute_co2 isn't safe here),
        # so we fall back to raising an informative error.
        raise RuntimeError('Please run `python compute_co2.py data.csv` first to create `co2_per_product.csv`.')

    # convert co2 column to numeric
    if 'co2_per_product' in df_full.columns:
        df_full['co2_per_product'] = pd.to_numeric(df_full['co2_per_product'], errors='coerce')

    # 1) Stacked bar (aggregated semantic groups)
    stacked_bar_material_mix(df_exploded, out_dir)

    # 2) CO2 by aggregated category
    if group_col is None:
        print('No category column found; skipping CO2 by category plot')
    else:
        co2_by_category(df_full, out_dir, group_col)

    # 3) What-if polyester replacement
    what_if_replace_polyester(df_exploded, df_full, out_dir)

    # 3b) What-if 30% reduction of wool/nylon/leather in key categories
    what_if_reduce_wool_nylon_leather(df_exploded, df_full, out_dir)

    # 4) Bubble chart
    bubble_chart_material_prioritization(df_exploded, out_dir)

    # 5) Material frequency (top 25)
    material_frequency(df_exploded, out_dir, top_n=25, group_rest=True)
    # 6) CO2 footprint per material (top 25)
    co2_footprint_by_material(df_exploded, out_dir, top_n=25, group_rest=True)


if __name__ == '__main__':
    main()
