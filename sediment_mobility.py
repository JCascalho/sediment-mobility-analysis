"""
Sediment mobility parameters and sampling-distribution plotting

Author: Joao Cascalho (FCUL / IDL - University of Lisbon)
Repository version: 1.1.0

Purpose
-------
This routine calculates sediment-mobility parameters for measured sediment
samples from a barrier-island / salt-marsh environment where tidal currents are
the dominant forcing agent. It also produces a spatial figure showing the large
and nested small sampling grids.

Important data rule
-------------------
Rows named "centroid" are treated as reference points for the sampling grids.
They are not sediment samples and are therefore excluded from:

- sediment-mobility calculations
- sample summary statistics
- sample-density contours
- reported sediment-sample totals

Centroid rows are retained in the coordinate output and plotted as reference
markers.

Expected input
--------------
An Excel workbook containing one or more sheets with at least:

- sample
- x
- y
- rho_sed
- rho_sw
- nu
- g
- D50

Optional:

- date/time

Outputs
-------
- Excel workbook with sediment-mobility parameters and quality-control metadata
- PNG figure
- PDF figure

Notes for interpretation
------------------------
Kernel-density contours, when enabled, represent relative sampling density only.
They should not be interpreted as sediment concentration, sediment mobility, or
hydrodynamic forcing.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np
import pandas as pd

try:
    from scipy.stats import gaussian_kde

    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False


@dataclass(frozen=True)
class FileConfig:
    input_file: Path
    output_file: Path
    figure_png: Path
    figure_pdf: Path
    add_density: bool = True


@dataclass(frozen=True)
class SedimentConfig:
    d50_col: str = "D50"
    rho_sed_col: str = "rho_sed"
    rho_sw_col: str = "rho_sw"
    nu_col: str = "nu"
    g_col: str = "g"
    sample_col: str = "sample"
    date_col: str = "date/time"
    sed_camp_col: str = "Sed_Camp"
    local_col: str = "Local"
    source_sheet_col: str = "Source_Sheet"
    point_type_col: str = "Point_Type"


SED_CFG = SedimentConfig()

PLOT_STYLE = {
    "font_family": "DejaVu Sans",
    "font_size": 9,
    "axes_labelsize": 10,
    "legend_fontsize": 8.5,
    "tick_labelsize": 8.5,
    "figsize": (7.8, 5.2),
    "dpi_png": 600,
    "large_marker_size": 28,
    "small_marker_size": 26,
    "centroid_marker_size": 68,
    "large_edgecolor": "0.58",
    "small_facecolor": "#1f77b4",
    "small_edgecolor": "white",
    "centroid_color": "black",
    "grid_linestyle": "--",
    "grid_linewidth": 0.45,
    "grid_alpha": 0.25,
    "density_color": "0.35",
    "density_linewidth": 1.0,
    "density_alpha": 0.85,
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def normalize_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text).strip().lower())


def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = list(df.columns)
    norm_map = {normalize_name(c): c for c in cols}
    for cand in candidates:
        if cand in cols:
            return cand
        cand_norm = normalize_name(cand)
        if cand_norm in norm_map:
            return norm_map[cand_norm]
    return None


def resolve_required_columns(df: pd.DataFrame) -> dict[str, str | None]:
    return {
        "x": find_column(df, ["x", "X", "X (ETRS89_Portugal_TM06)", "X_ETRS89_Portugal_TM06"]),
        "y": find_column(df, ["y", "Y", "Y (ETRS89_Portugal_TM06)", "Y_ETRS89_Portugal_TM06"]),
        "D50": find_column(df, [SED_CFG.d50_col]),
        "rho_sed": find_column(df, [SED_CFG.rho_sed_col]),
        "rho_sw": find_column(df, [SED_CFG.rho_sw_col]),
        "nu": find_column(df, [SED_CFG.nu_col]),
        "g": find_column(df, [SED_CFG.g_col]),
        "sample": find_column(df, [SED_CFG.sample_col, "Sample", "SAMPLE_ID"]),
        "date": find_column(df, [SED_CFG.date_col, "Date", "Datetime", "DATE/TIME"]),
    }


def parse_datetime_value(value):
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value
    if isinstance(value, (int, float, np.integer, np.floating)):
        return pd.to_datetime(value, unit="D", origin="1899-12-30", errors="coerce")
    return pd.to_datetime(value, errors="coerce")


def standardize_dataframe(df: pd.DataFrame, sheet_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    mapping = resolve_required_columns(df)
    required = ["x", "y", "D50", "rho_sed", "rho_sw", "nu", "g"]
    missing = [key for key in required if mapping[key] is None]
    if missing:
        raise ValueError(f"Missing required fields in sheet '{sheet_name}': {missing}")

    df = df.copy()
    rename_pairs = {
        mapping["x"]: "x",
        mapping["y"]: "y",
        mapping["D50"]: SED_CFG.d50_col,
        mapping["rho_sed"]: SED_CFG.rho_sed_col,
        mapping["rho_sw"]: SED_CFG.rho_sw_col,
        mapping["nu"]: SED_CFG.nu_col,
        mapping["g"]: SED_CFG.g_col,
    }
    if mapping["sample"]:
        rename_pairs[mapping["sample"]] = SED_CFG.sample_col
    if mapping["date"]:
        rename_pairs[mapping["date"]] = SED_CFG.date_col

    df = df.rename(columns={k: v for k, v in rename_pairs.items() if k != v})

    if SED_CFG.sample_col not in df.columns:
        df[SED_CFG.sample_col] = [f"{sheet_name}_{i + 1:03d}" for i in range(len(df))]

    df[SED_CFG.sample_col] = df[SED_CFG.sample_col].astype(str).str.strip()
    df[SED_CFG.point_type_col] = np.where(
        df[SED_CFG.sample_col].str.lower().eq("centroid"),
        "centroid",
        "sample",
    )

    df[SED_CFG.sed_camp_col] = sheet_name
    df[SED_CFG.local_col] = sheet_name
    df[SED_CFG.source_sheet_col] = sheet_name

    if SED_CFG.date_col in df.columns:
        df[SED_CFG.date_col] = df[SED_CFG.date_col].apply(parse_datetime_value)

    numeric_cols = [
        "x",
        "y",
        SED_CFG.d50_col,
        SED_CFG.rho_sed_col,
        SED_CFG.rho_sw_col,
        SED_CFG.nu_col,
        SED_CFG.g_col,
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    invalid_mask = df[numeric_cols].isna().any(axis=1)
    qc_invalid = df.loc[invalid_mask].copy()
    qc_invalid["QC_Issue"] = "Missing or non-numeric required sediment/coordinate field"

    return df.loc[~invalid_mask].copy(), qc_invalid


def calculate_dimensionless_grain_size(d50, rho_s, rho_w, nu, g):
    return d50 * ((g * (rho_s - rho_w) / (rho_w * nu**2)) ** (1.0 / 3.0))


def calculate_critical_shields_parameter(d_star):
    return 0.30 / (1.0 + 1.2 * d_star) + 0.055 * (1.0 - np.exp(-0.020 * d_star))


def calculate_critical_shear_stress(theta_cr, d50, rho_s, rho_w, g):
    return theta_cr * (rho_s - rho_w) * g * d50


def calculate_critical_shear_velocity(theta_cr, d50, rho_s, rho_w, g):
    return np.sqrt(theta_cr * g * (rho_s - rho_w) * d50 / rho_w)


def calculate_settling_velocity(d50, rho_s, rho_w, nu, g):
    d_star = calculate_dimensionless_grain_size(d50, rho_s, rho_w, nu, g)
    return (nu / d50) * (np.sqrt(10.36**2 + 1.049 * d_star**3) - 10.36)


def process_sediment_samples(df: pd.DataFrame) -> pd.DataFrame:
    samples = df[df[SED_CFG.point_type_col].eq("sample")].copy()
    if samples.empty:
        raise ValueError("No sediment sample rows found after excluding centroid reference points.")

    samples["D_star"] = calculate_dimensionless_grain_size(
        samples[SED_CFG.d50_col],
        samples[SED_CFG.rho_sed_col],
        samples[SED_CFG.rho_sw_col],
        samples[SED_CFG.nu_col],
        samples[SED_CFG.g_col],
    )
    samples["Theta_cr"] = calculate_critical_shields_parameter(samples["D_star"])
    samples["Tau_cr"] = calculate_critical_shear_stress(
        samples["Theta_cr"],
        samples[SED_CFG.d50_col],
        samples[SED_CFG.rho_sed_col],
        samples[SED_CFG.rho_sw_col],
        samples[SED_CFG.g_col],
    )
    samples["u_star_cr"] = calculate_critical_shear_velocity(
        samples["Theta_cr"],
        samples[SED_CFG.d50_col],
        samples[SED_CFG.rho_sed_col],
        samples[SED_CFG.rho_sw_col],
        samples[SED_CFG.g_col],
    )
    samples["w_s"] = calculate_settling_velocity(
        samples[SED_CFG.d50_col],
        samples[SED_CFG.rho_sed_col],
        samples[SED_CFG.rho_sw_col],
        samples[SED_CFG.nu_col],
        samples[SED_CFG.g_col],
    )
    samples["Coordinate_System"] = "ETRS89 / Portugal TM06"
    samples["Coordinate_Mode"] = "absolute_xy"
    return samples


def add_coordinate_metadata(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["Coordinate_System"] = "ETRS89 / Portugal TM06"
    out["Coordinate_Mode"] = "absolute_xy"
    return out


def format_with_space_thousands(x, pos):
    return f"{int(round(x)):,}".replace(",", " ")


def contour_from_points(ax, x, y):
    if not SCIPY_AVAILABLE or len(x) < 5:
        return None

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    xmin, xmax = x.min(), x.max()
    ymin, ymax = y.min(), y.max()
    pad_x = max((xmax - xmin) * 0.18, 8.0)
    pad_y = max((ymax - ymin) * 0.18, 8.0)

    xx, yy = np.mgrid[
        (xmin - pad_x) : (xmax + pad_x) : 200j,
        (ymin - pad_y) : (ymax + pad_y) : 200j,
    ]
    positions = np.vstack([xx.ravel(), yy.ravel()])
    values = np.vstack([x, y])
    kde = gaussian_kde(values)
    density = np.reshape(kde(positions).T, xx.shape)
    positive = density[density > 0]
    levels = np.unique(np.quantile(positive, [0.60, 0.80, 0.92]))

    if len(levels) == 0:
        return None

    ax.contour(
        xx,
        yy,
        density,
        levels=levels,
        colors=[PLOT_STYLE["density_color"]],
        linewidths=PLOT_STYLE["density_linewidth"],
        alpha=PLOT_STYLE["density_alpha"],
        zorder=2,
    )
    return True


def make_figure(samples: pd.DataFrame, all_coordinates: pd.DataFrame, out_png: Path, out_pdf: Path, add_density=True):
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update(
        {
            "font.family": PLOT_STYLE["font_family"],
            "font.size": PLOT_STYLE["font_size"],
            "axes.labelsize": PLOT_STYLE["axes_labelsize"],
            "legend.fontsize": PLOT_STYLE["legend_fontsize"],
            "xtick.labelsize": PLOT_STYLE["tick_labelsize"],
            "ytick.labelsize": PLOT_STYLE["tick_labelsize"],
        }
    )
    fig, ax = plt.subplots(figsize=PLOT_STYLE["figsize"])

    large = samples[samples[SED_CFG.source_sheet_col].str.contains("large", case=False, na=False)]
    small = samples[samples[SED_CFG.source_sheet_col].str.contains("small", case=False, na=False)]
    centroids = all_coordinates[all_coordinates[SED_CFG.point_type_col].eq("centroid")]

    ax.scatter(
        large["x"],
        large["y"],
        s=PLOT_STYLE["large_marker_size"],
        facecolors="none",
        edgecolors=PLOT_STYLE["large_edgecolor"],
        linewidths=0.9,
        label="Large-area sediment samples",
        zorder=1,
    )

    density_drawn = False
    if add_density:
        density_drawn = bool(contour_from_points(ax, samples["x"], samples["y"]))

    ax.scatter(
        small["x"],
        small["y"],
        s=PLOT_STYLE["small_marker_size"],
        facecolors=PLOT_STYLE["small_facecolor"],
        edgecolors=PLOT_STYLE["small_edgecolor"],
        linewidths=0.45,
        label="Small-area sediment samples",
        zorder=3,
    )

    if not centroids.empty:
        ax.scatter(
            centroids["x"],
            centroids["y"],
            s=PLOT_STYLE["centroid_marker_size"],
            marker="+",
            c=PLOT_STYLE["centroid_color"],
            linewidths=1.4,
            label="Grid centroids (reference points)",
            zorder=4,
        )

    xmin, xmax = all_coordinates["x"].min(), all_coordinates["x"].max()
    ymin, ymax = all_coordinates["y"].min(), all_coordinates["y"].max()
    xpad = max((xmax - xmin) * 0.08, 5.0)
    ypad = max((ymax - ymin) * 0.08, 5.0)
    ax.set_xlim(xmin - xpad, xmax + xpad)
    ax.set_ylim(ymin - ypad, ymax + ypad)

    ax.set_xlabel("X coordinate (m)")
    ax.set_ylabel("Y coordinate (m)")
    ax.xaxis.set_major_formatter(FuncFormatter(format_with_space_thousands))
    ax.yaxis.set_major_formatter(FuncFormatter(format_with_space_thousands))
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.tick_params(axis="x", labelrotation=30)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")
    ax.grid(
        True,
        linestyle=PLOT_STYLE["grid_linestyle"],
        linewidth=PLOT_STYLE["grid_linewidth"],
        alpha=PLOT_STYLE["grid_alpha"],
        zorder=0,
    )

    handles, labels = ax.get_legend_handles_labels()
    if density_drawn:
        contour_proxy = Line2D([0], [0], color=PLOT_STYLE["density_color"], lw=PLOT_STYLE["density_linewidth"])
        handles.append(contour_proxy)
        labels.append("Relative sample-density contours")

    ax.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.16),
        borderaxespad=0,
        frameon=False,
        ncol=2,
    )
    ax.text(
        0.01,
        0.01,
        "Coordinates plotted in ETRS89 / Portugal TM06. Density contours show sampling coverage only.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8,
        color="0.28",
    )

    fig.tight_layout(rect=[0, 0.12, 1, 1])
    fig.savefig(out_png, dpi=PLOT_STYLE["dpi_png"], bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def calculate_summary_statistics(samples: pd.DataFrame, all_coordinates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    grouped = samples.groupby(SED_CFG.source_sheet_col).agg(
        {
            "x": ["count", "mean", "std", "min", "max"],
            "y": ["mean", "std", "min", "max"],
            SED_CFG.d50_col: ["mean", "std", "min", "max"],
            "Tau_cr": ["mean", "std", "min", "max"],
            "u_star_cr": ["mean", "std", "min", "max"],
            "w_s": ["mean", "std", "min", "max"],
        }
    ).reset_index()

    grouped.columns = [
        "__".join([str(x) for x in col if str(x) != ""]).strip("_") if isinstance(col, tuple) else str(col)
        for col in grouped.columns.to_flat_index()
    ]

    global_stats = pd.DataFrame(
        [
            {
                "sediment_sample_count": int(len(samples)),
                "centroid_reference_count": int(all_coordinates[SED_CFG.point_type_col].eq("centroid").sum()),
                "total_coordinate_rows": int(len(all_coordinates)),
                "total_sheets": int(all_coordinates[SED_CFG.source_sheet_col].nunique()),
                "coordinate_mode": "absolute_xy",
                "coordinate_system": "ETRS89 / Portugal TM06",
            }
        ]
    )
    return grouped, global_stats


def save_results(
    path: Path,
    input_file: Path,
    samples: pd.DataFrame,
    all_coordinates: pd.DataFrame,
    grouped: pd.DataFrame,
    global_stats: pd.DataFrame,
    qc_invalid: pd.DataFrame,
    add_density: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    metadata_df = pd.DataFrame(
        {
            "parameter": [
                "module",
                "input_file",
                "coordinate_mode",
                "coordinate_system",
                "centroids_used_as_samples",
                "centroids_included_in_coordinate_output",
                "density_contours_available",
                "density_contours_basis",
                "uses_rotated_coordinates",
                "figure_png_dpi",
            ],
            "value": [
                "sediment_mobility",
                input_file.name,
                "absolute_xy",
                "ETRS89 / Portugal TM06",
                False,
                True,
                bool(SCIPY_AVAILABLE and add_density),
                "sediment sample coordinates only; centroids excluded",
                False,
                PLOT_STYLE["dpi_png"],
            ],
        }
    )

    coord_cols = [
        SED_CFG.source_sheet_col,
        SED_CFG.point_type_col,
        SED_CFG.sample_col,
        SED_CFG.date_col,
        "x",
        "y",
        "Coordinate_System",
        "Coordinate_Mode",
    ]
    available_coord_cols = [c for c in coord_cols if c in all_coordinates.columns]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        samples.to_excel(writer, sheet_name="Sediment_Parameters", index=False)
        all_coordinates[available_coord_cols].to_excel(writer, sheet_name="Sample_Coordinates", index=False)
        grouped.to_excel(writer, sheet_name="Summary_Statistics", index=False)
        global_stats.to_excel(writer, sheet_name="Global_Statistics", index=False)
        metadata_df.to_excel(writer, sheet_name="Metadata", index=False)
        qc_invalid.to_excel(writer, sheet_name="QC_Excluded_Rows", index=False)


def build_config_from_args(argv: list[str] | None = None) -> FileConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate sediment-mobility parameters from sediment-sample workbooks "
            "and export tabular results plus sampling-location figures."
        )
    )
    parser.add_argument(
        "-i",
        "--input",
        default="examples/example_sediment_mobility_input.xlsx",
        help="Input Excel workbook. Default: examples/example_sediment_mobility_input.xlsx",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="results/sediment_mobility_results.xlsx",
        help="Output Excel workbook. Default: results/sediment_mobility_results.xlsx",
    )
    parser.add_argument(
        "--figure-png",
        default="results/plots/sediment_sample_locations.png",
        help="Output PNG figure. Default: results/plots/sediment_sample_locations.png",
    )
    parser.add_argument(
        "--figure-pdf",
        default="results/plots/sediment_sample_locations.pdf",
        help="Output PDF figure. Default: results/plots/sediment_sample_locations.pdf",
    )
    parser.add_argument("--no-density", action="store_true", help="Disable relative sample-density contours.")
    args = parser.parse_args(argv)

    return FileConfig(
        input_file=Path(args.input),
        output_file=Path(args.output),
        figure_png=Path(args.figure_png),
        figure_pdf=Path(args.figure_pdf),
        add_density=not args.no_density,
    )


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    cfg = build_config_from_args(argv)

    if not cfg.input_file.exists():
        raise FileNotFoundError(
            f"Input workbook not found: {cfg.input_file}. "
            "Use --input to provide the path to your workbook."
        )

    logging.info("Reading sediment dataset...")
    xls = pd.ExcelFile(cfg.input_file)
    all_coordinates = []
    excluded_rows = []

    for sheet in xls.sheet_names:
        raw_df = pd.read_excel(xls, sheet_name=sheet)
        valid_df, invalid_df = standardize_dataframe(raw_df, sheet)
        all_coordinates.append(add_coordinate_metadata(valid_df))
        if not invalid_df.empty:
            excluded_rows.append(invalid_df)
        sample_count = int(valid_df[SED_CFG.point_type_col].eq("sample").sum())
        centroid_count = int(valid_df[SED_CFG.point_type_col].eq("centroid").sum())
        logging.info(f"{sheet}: {sample_count} sediment samples; {centroid_count} centroid reference points")

    coordinate_df = pd.concat(all_coordinates, ignore_index=True)
    qc_invalid = pd.concat(excluded_rows, ignore_index=True) if excluded_rows else pd.DataFrame()

    samples = process_sediment_samples(coordinate_df)
    grouped, global_stats = calculate_summary_statistics(samples, coordinate_df)

    save_results(cfg.output_file, cfg.input_file, samples, coordinate_df, grouped, global_stats, qc_invalid, cfg.add_density)
    make_figure(samples, coordinate_df, cfg.figure_png, cfg.figure_pdf, add_density=cfg.add_density)

    logging.info(
        "Completed successfully. Sediment samples used in mobility calculations: "
        f"{len(samples)}. Centroid reference points excluded: "
        f"{int(coordinate_df[SED_CFG.point_type_col].eq('centroid').sum())}."
    )


if __name__ == "__main__":
    main()
