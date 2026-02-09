# Visualization Standards - Capim Ecosystem

> **Purpose**: Design decisions and guidelines for creating charts across all projects  
> **Companion**: `scripts/plot_utils.py` (reusable code)  
> **Last Updated**: 2026-02-03  
> **Version**: 2.0 (Refactored: Doc + Code)

---

## Objective

Create **readable**, **non-overlapping** charts with **clear messaging** and **traceability** (period/source).

---

## Design Decisions

### Visual Theme: Why Whitegrid + Talk + Pastel?

**Choice**: Seaborn `whitegrid` style + `talk` context + `pastel` palette

**Rationale**:
- `whitegrid`: Clean, professional background with subtle gridlines
- `talk`: Larger fonts (ideal for presentations and screens)
- `pastel`: Soft colors that don't fatigue eyes during long analysis sessions
- Low grid alpha (0.25): Grid visible but not distracting

**Alternative considered**: `darkgrid` → Rejected (too heavy, distracts from data)

---

### Layout: Why Dual Panels for Volume + Share?

**Choice**: Stacked vertical panels (2 rows, 1 column)

**Rationale**:
- Avoids mixing scales (absolute vs relative)
- Clearer visual separation of metrics
- Easier to identify trends independently
- Standard in financial/operational reporting

**When to use**:
- Top panel: Volume/Count (absolute numbers)
- Bottom panel: Share/Percentage (relative %)

**When NOT to use**: If only one metric type → use single panel

---

### Legend: Why Outside Plot Area?

**Choice**: Legend positioned to the right (`bbox_to_anchor=(1.01, 1.0)`)

**Rationale**:
- Prevents obscuring data lines
- Always readable (not blocked by datapoints)
- Professional appearance (common in publications)

**Alternative considered**: `loc='best'` (matplotlib auto) → Rejected (unpredictable, often overlaps data)

---

### Annotations: Why Latest Month Only?

**Choice**: Annotate most recent datapoint with arrow + value

**Rationale**:
- Draws attention to current state
- Avoids clutter (annotating all points = noise)
- Answers immediate question: "What's the latest value?"

**Format conventions**:
- **Counts**: `1.234` (pt-BR thousand separator with `.`)
- **Shares**: `45.3%` (1 decimal place)
- **Currency**: `R$ 1.234,56` (pt-BR format)

---

### Traceability: Why Mandatory Footer?

**Choice**: Include `Period | Source | Caveats` in footer

**Rationale**:
- **Reproducibility**: Anyone can re-run the analysis
- **Validation**: Easier to spot data errors (wrong date range, wrong table)
- **Trust**: Transparent about limitations (snapshot data, exclusions, etc.)

**Required elements**:
1. **Period**: `YYYY-MM-DD → YYYY-MM-DD` (data range)
2. **Source**: `SCHEMA.TABLE` or view name
3. **Caveats**: Any important assumptions (e.g., "POS(MRI)=snapshot")

---

### Export: Why DPI 220?

**Choice**: `dpi=220` for PNG exports

**Rationale**:
- High quality for presentations (projectors, large screens)
- Not excessive (300 dpi = overkill for screen usage)
- Small file size vs quality balance

**Alternative considered**: `dpi=150` → Rejected (pixelated on 4K screens)

---

## Usage with plot_utils.py

### Quick Start

```python
from scripts.plot_utils import (
    setup_capim_theme,
    create_dual_panel_figure,
    format_axis_labels,
    format_date_axis,
    add_legend_outside,
    annotate_latest_value,
    add_footer,
    adjust_layout_dual_panel,
    save_figure
)

# 1. Setup theme (once per script)
setup_capim_theme()

# 2. Create figure
fig, ax1, ax2 = create_dual_panel_figure()

# 3. Plot data
ax1.plot(df['month'], df['volume'], marker='o', linewidth=2)
ax2.plot(df['month'], df['share_pct'], marker='o', linewidth=2, color='coral')

# 4. Format axes
format_axis_labels(ax1, ylabel='Volume')
format_axis_labels(ax2, xlabel='Month', ylabel='Share (%)')
format_date_axis(ax2, interval=3)

# 5. Add annotations
annotate_latest_value(ax1, df['month'], df['volume'], format_str='{:,.0f}')
annotate_latest_value(ax2, df['month'], df['share_pct'], format_str='{:.1%}', 
                     offset_y=15)  # Adjust offset to avoid overlap

# 6. Add legend
add_legend_outside(ax1, labels=['Total Volume'])

# 7. Adjust layout
adjust_layout_dual_panel(fig)

# 8. Add footer
add_footer(fig, 
          period_start='2024-01-01', 
          period_end='2024-12-31',
          source='CAPIM_DATA.ANALYTICS.MONTHLY_METRICS')

# 9. Save
save_figure(fig, 'output/monthly_analysis.png')
```

---

## Complete Example (Dual Panel)

```python
import pandas as pd
from src.utils.snowflake_connection import run_query
from scripts.plot_utils import *

# Setup theme
setup_capim_theme()

# Query data
query = """
SELECT 
    month,
    total_volume,
    share_pct
FROM CAPIM_DATA.ANALYTICS.MONTHLY_METRICS
WHERE month >= '2024-01-01'
ORDER BY month
"""

df = run_query(query)
df['month'] = pd.to_datetime(df['month'])

# Create figure
fig, ax1, ax2 = create_dual_panel_figure()

# Panel 1: Volume
ax1.plot(df['month'], df['total_volume'], marker='o', linewidth=2, label='Total')
format_axis_labels(ax1, ylabel='Volume')
annotate_latest_value(ax1, df['month'], df['total_volume'])
add_legend_outside(ax1)

# Panel 2: Share
ax2.plot(df['month'], df['share_pct'], marker='o', linewidth=2, color='coral', label='Share')
format_axis_labels(ax2, xlabel='Month', ylabel='Share (%)')
format_date_axis(ax2, interval=3)
add_legend_outside(ax2)

# Layout & Footer
adjust_layout_dual_panel(fig)
add_footer(fig, 
          period_start=df['month'].min().strftime('%Y-%m-%d'),
          period_end=df['month'].max().strftime('%Y-%m-%d'),
          source='CAPIM_DATA.ANALYTICS.MONTHLY_METRICS')

# Save
save_figure(fig, 'output/monthly_metrics.png')
```

---

## Anti-Patterns

### ❌ Don't

- Use default matplotlib styles (unprofessional appearance)
- Place legend over data lines (obscures information)
- Skip axis labels or use tiny fonts (< 10pt)
- Forget data period in footer (not reproducible)
- Use unbounded queries without LIMIT (performance risk)
- Assume column names exist without checking `df.columns`
- Save with low DPI (< 150) for presentations
- Rotate x-labels 90° (hard to read, prefer 15-25°)
- Use saturated colors (red, bright blue) for long analysis

### ✅ Do

- Use `setup_capim_theme()` at start of script
- Place legend outside with `add_legend_outside()`
- Set explicit fontsize (12) and labelpad (14)
- Always include footer with period + source + caveats
- Use LIMIT/SAMPLE for exploratory queries
- Validate `df.columns` before plotting
- Export at DPI 220 for production charts
- Use gentle rotation (20°) for date labels
- Stick to pastel palette for extended viewing

---

## Customization

### When to Deviate from Standards

**Allowed customizations**:
- Color palette for domain-specific categories (e.g., clinic tiers)
- Figure size for specific layouts (e.g., wider for many series)
- Annotation offsets to avoid overlap
- Legend labels for clarity

**Core principles (non-negotiable)**:
- Always include traceability footer
- Always place legend outside (never over data)
- Always annotate latest datapoint
- Always use high DPI for exports

---

## References

### Documentation
- **Seaborn**: https://seaborn.pydata.org/
- **Matplotlib**: https://matplotlib.org/
- **Code**: `scripts/plot_utils.py` (this project)

### Applied In
- `bnpl-funil/scripts/studies/` — BNPL funnel analysis
- `ontologia-saas/eda/` — SaaS operational metrics
- `client-voice-data/eda/` — VoC analysis (future)

---

## Version History

### v2.0 (2026-02-03)
- Refactored: Doc (decisions) + Code (plot_utils.py)
- Improved autonomy for multi-repo setup
- Added complete usage examples

### v1.0 (2026-02-03)
- Initial version (monolithic doc with embedded code)
- Established core design decisions
