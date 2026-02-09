"""
Capim Visualization Utilities

Shared utilities for creating consistent, high-quality charts across all projects.

Usage:
    from scripts.plot_utils import setup_capim_theme, create_dual_panel_figure
    
    setup_capim_theme()
    fig, ax1, ax2 = create_dual_panel_figure()
    # ... plot your data ...
    save_figure(fig, 'output/chart.png')

Version: 1.0
Last Updated: 2026-02-03
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from matplotlib.dates import MonthLocator, DateFormatter


def setup_capim_theme():
    """
    Apply standard Capim visual theme.
    
    Call once at the beginning of your script before creating plots.
    
    Theme characteristics:
    - whitegrid: Clean background with subtle gridlines
    - talk: Larger fonts for readability
    - pastel: Soft colors that don't fatigue eyes
    """
    sns.set_theme(
        style="whitegrid",
        context="talk",
        palette="pastel"
    )
    
    plt.rcParams.update({
        'grid.alpha': 0.25,
        'axes.edgecolor': '0.85',
        'axes.linewidth': 1.0,
        'xtick.color': '0.25',
        'ytick.color': '0.25',
    })


def create_dual_panel_figure(figsize=(12, 10), sharex=True):
    """
    Create dual-panel figure (stacked vertically).
    
    Ideal for showing volume (absolute) and share (relative) metrics.
    
    Args:
        figsize: Figure size in inches (width, height)
        sharex: Whether panels share x-axis (default True)
    
    Returns:
        fig, ax_top, ax_bottom
    
    Example:
        fig, ax1, ax2 = create_dual_panel_figure()
        ax1.plot(dates, volumes)
        ax2.plot(dates, shares)
    """
    fig, axes = plt.subplots(2, 1, figsize=figsize, sharex=sharex)
    fig.subplots_adjust(hspace=0.30)
    
    return fig, axes[0], axes[1]


def create_single_panel_figure(figsize=(12, 6)):
    """
    Create single-panel figure.
    
    Args:
        figsize: Figure size in inches (width, height)
    
    Returns:
        fig, ax
    """
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    return fig, ax


def format_axis_labels(ax, xlabel=None, ylabel=None, fontsize=12, labelpad=14):
    """
    Set axis labels with proper spacing.
    
    Args:
        ax: Matplotlib axis
        xlabel: X-axis label (optional)
        ylabel: Y-axis label (optional)
        fontsize: Font size for labels
        labelpad: Padding between label and axis
    """
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=fontsize, labelpad=labelpad)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=fontsize, labelpad=labelpad)


def format_date_axis(ax, interval=3, date_format='%Y-%m', rotation=20):
    """
    Format x-axis for monthly dates.
    
    Args:
        ax: Matplotlib axis
        interval: Tick interval in months (e.g., 3 = quarterly)
        date_format: Date format string (default: YYYY-MM)
        rotation: Label rotation angle in degrees
    
    Example:
        format_date_axis(ax, interval=2)  # Show every 2 months
    """
    ax.xaxis.set_major_locator(MonthLocator(interval=interval))
    ax.xaxis.set_major_formatter(DateFormatter(date_format))
    ax.tick_params(axis='x', labelsize=10, rotation=rotation)
    plt.setp(ax.xaxis.get_majorticklabels(), ha='right')


def add_legend_outside(ax, labels=None, fontsize=10):
    """
    Add legend outside plot area (right side).
    
    Prevents legend from obscuring data.
    
    Args:
        ax: Matplotlib axis
        labels: Optional list of labels (uses ax.legend() if None)
        fontsize: Legend font size
    
    Note:
        Call fig.subplots_adjust(right=0.80) after to reserve space
    """
    if labels:
        ax.legend(
            labels,
            bbox_to_anchor=(1.01, 1.0),
            loc='upper left',
            frameon=True,
            fontsize=fontsize
        )
    else:
        ax.legend(
            bbox_to_anchor=(1.01, 1.0),
            loc='upper left',
            frameon=True,
            fontsize=fontsize
        )


def annotate_latest_value(ax, dates, values, format_str='{:,.0f}', 
                          offset_x=10, offset_y=10):
    """
    Annotate most recent datapoint with its value.
    
    Args:
        ax: Matplotlib axis
        dates: Series or array of dates
        values: Series or array of values
        format_str: Format string for value (default: thousand separator)
        offset_x: X offset in points (adjust to avoid overlap)
        offset_y: Y offset in points (adjust to avoid overlap)
    
    Format examples:
        - '{:,.0f}': 1,234 (integers with thousand separator)
        - '{:.1%}': 45.3% (percentages with 1 decimal)
        - 'R$ {:,.2f}': R$ 1,234.56 (currency)
    """
    last_date = dates.iloc[-1] if hasattr(dates, 'iloc') else dates[-1]
    last_value = values.iloc[-1] if hasattr(values, 'iloc') else values[-1]
    
    ax.annotate(
        format_str.format(last_value),
        xy=(last_date, last_value),
        xytext=(offset_x, offset_y),
        textcoords='offset points',
        fontsize=9,
        bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='none', alpha=0.8),
        arrowprops=dict(arrowstyle='->', lw=0.5, color='gray')
    )


def add_footer(fig, period_start, period_end, source, caveats=None):
    """
    Add traceability footer to figure.
    
    MANDATORY for all production charts.
    
    Args:
        fig: Matplotlib figure
        period_start: Start date (str or datetime)
        period_end: End date (str or datetime)
        source: Data source (e.g., "SCHEMA.TABLE")
        caveats: Optional caveats/assumptions
    
    Example:
        add_footer(fig, '2024-01-01', '2024-12-31', 
                   'CAPIM_DATA.ANALYTICS.MONTHLY_METRICS',
                   caveats='POS(MRI)=snapshot as-of 2026-02-01')
    """
    footer_text = f'Period: {period_start} → {period_end} | Source: {source}'
    if caveats:
        footer_text += f' | Caveats: {caveats}'
    
    fig.text(
        0.5, 0.01,
        footer_text,
        ha='center',
        fontsize=8,
        style='italic',
        color='0.4'
    )


def save_figure(fig, filename, dpi=220):
    """
    Save figure with high quality settings.
    
    Args:
        fig: Matplotlib figure
        filename: Output path (e.g., 'output/chart.png')
        dpi: Resolution (default 220 for presentations)
    
    Settings:
        - dpi=220: High quality for presentations
        - bbox_inches='tight': No whitespace cutoff
    """
    fig.savefig(filename, dpi=dpi, bbox_inches='tight')


def adjust_layout_dual_panel(fig):
    """
    Adjust layout for dual-panel figures with legend outside.
    
    Call after creating all plot elements.
    
    Args:
        fig: Matplotlib figure
    """
    fig.subplots_adjust(
        right=0.80,   # Space for legend
        bottom=0.18,  # Space for rotated x-labels
        hspace=0.30   # Space between panels
    )


def adjust_layout_single_panel(fig):
    """
    Adjust layout for single-panel figures with legend outside.
    
    Call after creating all plot elements.
    
    Args:
        fig: Matplotlib figure
    """
    fig.subplots_adjust(
        right=0.80,   # Space for legend
        bottom=0.18,  # Space for rotated x-labels
        left=0.10     # Space for y-axis label
    )
