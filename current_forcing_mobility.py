"""Current-only near-bed forcing and sediment-remobilization analysis.

This module complements ``sediment_mobility.py``. The sediment module derives
critical entrainment thresholds from grain-size properties; this module compares
those thresholds with a near-bed current time series.

The routine is intended for current-dominated conditions. It does not include
wave orbital velocity or combined wave-current stress.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


VERSION = "1.1.0"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "examples" / "example_current_forcing_input.xlsx"
DEFAULT_OUTPUT = SCRIPT_DIR / "results" / "current_forcing_mobility_results.xlsx"
DEFAULT_FIGURE_PNG = SCRIPT_DIR / "results" / "plots" / "current_forcing_mobility.png"
DEFAULT_FIGURE_PDF = SCRIPT_DIR / "results" / "plots" / "current_forcing_mobility.pdf"

REQUIRED_COLUMNS = ("Time", "ve", "vn", "D50", "z", "tau_cr")


@dataclass(frozen=True)
class PhysicalConfig:
    """Physical and diagnostic settings."""

    rho_seawater: float = 1025.0
    roughness_factor: float = 2.5
    von_karman: float = 0.41
    mixing_stress_coefficient: float = 0.07
    mixing_grain_factor: float = 6.0
    mixing_reference: str = "p95"
    max_gap_factor: float = 3.0


@dataclass(frozen=True)
class FileConfig:
    """Input and output settings."""

    input_file: Path
    output_file: Path
    figure_png: Path
    figure_pdf: Path
    intervals_csv: Optional[Path]
    sheet_name: Optional[str]
    make_plots: bool
    physical: PhysicalConfig


@dataclass(frozen=True)
class TimeInterval:
    """Named, non-overlapping analysis interval."""

    start: pd.Timestamp
    end: pd.Timestamp
    label: str


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common column-name variants."""
    out = df.copy()
    out.columns = [str(col).strip() for col in out.columns]
    aliases = {
        "VE": "ve",
        "Ve": "ve",
        "east_velocity": "ve",
        "u_east": "ve",
        "VN": "vn",
        "Vn": "vn",
        "north_velocity": "vn",
        "v_north": "vn",
        "d50": "D50",
        "D_50": "D50",
        "sensor_height": "z",
        "height_above_bed": "z",
        "time": "Time",
        "date/time": "Time",
        "Datetime": "Time",
        "datetime": "Time",
        "Tau_cr": "tau_cr",
        "TAU_CR": "tau_cr",
        "taucr": "tau_cr",
        "Taucr": "tau_cr",
    }
    return out.rename(columns={key: value for key, value in aliases.items() if key in out.columns})


def read_input_table(path: Path, sheet_name: Optional[str]) -> pd.DataFrame:
    """Read CSV or Excel current data."""
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet_name or 0)
    raise ValueError("Input must be a CSV or Excel workbook.")


def validate_input(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate the time series and retain excluded rows for auditability."""
    out = normalize_columns(df)
    missing = [column for column in REQUIRED_COLUMNS if column not in out.columns]
    if missing:
        raise KeyError("Missing required columns: " + ", ".join(missing))

    out["Time"] = pd.to_datetime(out["Time"], errors="coerce", dayfirst=False)
    numeric = ["ve", "vn", "D50", "z", "tau_cr"]
    for column in numeric:
        out[column] = pd.to_numeric(out[column], errors="coerce")

    issue = pd.Series("", index=out.index, dtype="object")
    missing_mask = out[["Time", *numeric]].isna().any(axis=1)
    issue.loc[missing_mask] = "Missing or non-numeric required value"

    domain_mask = (
        (out["D50"] <= 0)
        | (out["z"] <= 0)
        | (out["tau_cr"] <= 0)
    ) & ~missing_mask
    issue.loc[domain_mask] = "D50, z and tau_cr must be positive"

    duplicate_mask = out["Time"].duplicated(keep="first") & ~missing_mask
    issue.loc[duplicate_mask] = "Duplicate timestamp; first occurrence retained"

    excluded_mask = issue.ne("")
    qc = out.loc[excluded_mask].copy()
    qc["QC_Issue"] = issue.loc[excluded_mask]
    valid = out.loc[~excluded_mask].copy().sort_values("Time").reset_index(drop=True)

    if valid.empty:
        raise ValueError("No valid rows remain after input validation.")
    if len(valid) < 2:
        raise ValueError("At least two valid timestamps are required.")
    return valid, qc


def median_sampling_interval_seconds(times: pd.Series) -> float:
    """Return the median positive interval between observations."""
    diffs = times.sort_values().diff().dt.total_seconds()
    diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    if diffs.empty:
        return 1.0
    return float(diffs.median())


def load_intervals(path: Optional[Path], data: pd.DataFrame) -> list[TimeInterval]:
    """Load intervals or create one full-record interval."""
    if path is None:
        dt = median_sampling_interval_seconds(data["Time"])
        return [
            TimeInterval(
                start=pd.Timestamp(data["Time"].min()),
                end=pd.Timestamp(data["Time"].max()) + pd.to_timedelta(dt, unit="s"),
                label="FULL_RECORD",
            )
        ]

    if not path.exists():
        raise FileNotFoundError(f"Interval CSV not found: {path}")
    table = pd.read_csv(path)
    table.columns = [str(column).strip().lower() for column in table.columns]
    required = {"start", "end", "label"}
    if not required.issubset(table.columns):
        raise KeyError("Interval CSV must contain start, end and label columns.")

    intervals = []
    for row in table.itertuples(index=False):
        start = pd.to_datetime(row.start, errors="raise")
        end = pd.to_datetime(row.end, errors="raise")
        if end <= start:
            raise ValueError(f"Interval end must follow start: {row.label}")
        intervals.append(TimeInterval(start=start, end=end, label=str(row.label)))

    intervals.sort(key=lambda item: item.start)
    for previous, current in zip(intervals, intervals[1:]):
        if current.start < previous.end:
            raise ValueError(
                f"Intervals overlap: '{previous.label}' and '{current.label}'."
            )
    return intervals


def current_speed(ve, vn):
    return np.hypot(ve, vn)


def current_azimuth(ve, vn):
    """Direction toward which the current flows, clockwise from north."""
    return (np.degrees(np.arctan2(ve, vn)) + 360.0) % 360.0


def calculate_current_metrics(data: pd.DataFrame, cfg: PhysicalConfig) -> pd.DataFrame:
    """Calculate current-induced stress and mobility diagnostics."""
    out = data.copy()
    out["u"] = current_speed(out["ve"], out["vn"])
    out["dir_c"] = current_azimuth(out["ve"], out["vn"])
    out["kn"] = cfg.roughness_factor * out["D50"]
    out["z0"] = out["kn"] / 30.0
    out["z_over_z0"] = out["z"] / out["z0"]
    out["calculation_valid"] = out["z_over_z0"] > 1.0

    log_argument = out["z_over_z0"].where(out["calculation_valid"])
    out["fc"] = 2.0 * (cfg.von_karman / np.log(log_argument)) ** 2
    out["u_star_c"] = out["u"] * np.sqrt(out["fc"] / 2.0)
    out["tau_c"] = 0.5 * cfg.rho_seawater * out["fc"] * out["u"] ** 2
    out["u_star_cr"] = np.sqrt(out["tau_cr"] / cfg.rho_seawater)

    out["tau_excess"] = np.maximum(out["tau_c"] - out["tau_cr"], 0.0)
    out["u_star_excess"] = np.maximum(out["u_star_c"] - out["u_star_cr"], 0.0)
    out["mobility_ratio_tau"] = out["tau_c"] / out["tau_cr"]
    out["mobility_ratio_u_star"] = out["u_star_c"] / out["u_star_cr"]
    out["is_mobilized_tau"] = out["tau_c"] > out["tau_cr"]
    out["is_mobilized_u_star"] = out["u_star_c"] > out["u_star_cr"]
    out["mobility_flags_agree"] = out["is_mobilized_tau"].eq(out["is_mobilized_u_star"])
    out["is_mobilized"] = out["is_mobilized_tau"] & out["calculation_valid"]

    out["interval_label"] = pd.NA
    out["record_duration_seconds"] = np.nan
    out["tau_c_interval_mean"] = np.nan
    out["tau_c_interval_p95"] = np.nan
    out["tau_c_interval_max"] = np.nan
    out["delta_mix_mean_tau_c"] = np.nan
    out["delta_mix_p95_tau_c"] = np.nan
    out["delta_mix_max_tau_c"] = np.nan
    out["delta_mix"] = np.nan
    return out


def duration_weights(
    times: pd.Series,
    interval_end: pd.Timestamp,
    max_gap_factor: float,
) -> tuple[np.ndarray, dict[str, float | bool]]:
    """Calculate sample-and-hold observation durations with gap capping."""
    ordered = pd.Series(pd.to_datetime(times)).reset_index(drop=True)
    diffs = ordered.shift(-1) - ordered
    seconds = diffs.dt.total_seconds().to_numpy(float)
    positive = seconds[np.isfinite(seconds) & (seconds > 0)]
    median_dt = float(np.median(positive)) if positive.size else 1.0
    mean_dt = float(np.mean(positive)) if positive.size else median_dt
    std_dt = float(np.std(positive, ddof=1)) if positive.size > 1 else 0.0
    cv = std_dt / mean_dt if mean_dt > 0 else 0.0
    max_gap = median_dt * max_gap_factor if max_gap_factor > 0 else float("inf")

    last_duration = max((pd.Timestamp(interval_end) - ordered.iloc[-1]).total_seconds(), 0.0)
    seconds[-1] = last_duration if last_duration > 0 else median_dt
    seconds = np.where(np.isfinite(seconds) & (seconds > 0), seconds, median_dt)
    capped = seconds > max_gap
    seconds = np.minimum(seconds, max_gap)

    diagnostics = {
        "median_dt_seconds": median_dt,
        "mean_dt_seconds": mean_dt,
        "max_observed_gap_seconds": float(np.max(positive)) if positive.size else median_dt,
        "sampling_interval_cv": cv,
        "sampling_regular_cv_le_0_05": bool(cv <= 0.05),
        "capped_gap_count": int(np.sum(capped)),
    }
    return seconds, diagnostics


def annotate_intervals(
    processed: pd.DataFrame,
    intervals: list[TimeInterval],
    cfg: PhysicalConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Annotate records and calculate interval mobility statistics."""
    out = processed.copy()
    interval_rows: list[dict] = []
    mobile_rows: list[dict] = []

    for interval in intervals:
        mask = (out["Time"] >= interval.start) & (out["Time"] < interval.end)
        subset = out.loc[mask].sort_values("Time").copy()
        if subset.empty:
            logging.warning("Interval '%s' contains no observations.", interval.label)
            continue

        durations, diagnostics = duration_weights(
            subset["Time"], interval.end, cfg.max_gap_factor
        )
        subset["record_duration_seconds"] = durations
        total_seconds = float(np.sum(durations))
        mobile_mask = subset["is_mobilized"].to_numpy(bool)
        mobile_seconds = float(np.sum(durations[mobile_mask]))
        record_percent = 100.0 * float(np.mean(mobile_mask))
        time_percent = 100.0 * mobile_seconds / total_seconds if total_seconds > 0 else np.nan

        tau_mean = float(subset["tau_c"].mean())
        tau_p95 = float(subset["tau_c"].quantile(0.95))
        tau_max = float(subset["tau_c"].max())
        references = {"mean": tau_mean, "p95": tau_p95, "max": tau_max}
        selected_tau = references[cfg.mixing_reference]

        def mixing_depth(reference_tau: float) -> pd.Series:
            return (
                cfg.mixing_stress_coefficient
                * np.maximum(reference_tau - subset["tau_cr"], 0.0)
                + cfg.mixing_grain_factor * subset["D50"]
            )

        mix_mean = mixing_depth(tau_mean)
        mix_p95 = mixing_depth(tau_p95)
        mix_max = mixing_depth(tau_max)
        mix_selected = mixing_depth(selected_tau)

        indexes = subset.index
        out.loc[indexes, "interval_label"] = interval.label
        out.loc[indexes, "record_duration_seconds"] = durations
        out.loc[indexes, "tau_c_interval_mean"] = tau_mean
        out.loc[indexes, "tau_c_interval_p95"] = tau_p95
        out.loc[indexes, "tau_c_interval_max"] = tau_max
        out.loc[indexes, "delta_mix_mean_tau_c"] = mix_mean.to_numpy()
        out.loc[indexes, "delta_mix_p95_tau_c"] = mix_p95.to_numpy()
        out.loc[indexes, "delta_mix_max_tau_c"] = mix_max.to_numpy()
        out.loc[indexes, "delta_mix"] = mix_selected.to_numpy()

        nominal_seconds = float((interval.end - interval.start).total_seconds())
        coverage_percent = 100.0 * total_seconds / nominal_seconds if nominal_seconds > 0 else np.nan
        if not diagnostics["sampling_regular_cv_le_0_05"]:
            logging.warning(
                "Interval '%s' has irregular sampling (CV %.3f). Use the time-weighted percentage.",
                interval.label,
                diagnostics["sampling_interval_cv"],
            )

        interval_rows.append(
            {
                "Interval": interval.label,
                "Start": interval.start,
                "End": interval.end,
                "Total_records": int(len(subset)),
                "Median_sampling_interval_seconds": diagnostics["median_dt_seconds"],
                "Mean_sampling_interval_seconds": diagnostics["mean_dt_seconds"],
                "Sampling_interval_CV": diagnostics["sampling_interval_cv"],
                "Sampling_regular_CV_le_0_05": diagnostics["sampling_regular_cv_le_0_05"],
                "Max_observed_gap_seconds": diagnostics["max_observed_gap_seconds"],
                "Capped_gap_count": diagnostics["capped_gap_count"],
                "Represented_duration_seconds": total_seconds,
                "Represented_duration_minutes": total_seconds / 60.0,
                "Nominal_interval_seconds": nominal_seconds,
                "Coverage_percent": coverage_percent,
                "Mobilized_records": int(np.sum(mobile_mask)),
                "Mobilized_record_percent": record_percent,
                "Mobilized_time_seconds": mobile_seconds,
                "Mobilized_time_minutes": mobile_seconds / 60.0,
                "Mobilized_time_hours": mobile_seconds / 3600.0,
                "Mobilized_time_percent": time_percent,
                "Mean_U": subset["u"].mean(),
                "P95_U": subset["u"].quantile(0.95),
                "Max_U": subset["u"].max(),
                "Mean_tau_c": tau_mean,
                "P95_tau_c": tau_p95,
                "Max_tau_c": tau_max,
                "Mean_tau_cr": subset["tau_cr"].mean(),
                "Mean_u_star_c": subset["u_star_c"].mean(),
                "P95_u_star_c": subset["u_star_c"].quantile(0.95),
                "Max_u_star_c": subset["u_star_c"].max(),
                "Mean_u_star_cr": subset["u_star_cr"].mean(),
                "Mean_mobility_ratio_tau": subset["mobility_ratio_tau"].mean(),
                "P95_mobility_ratio_tau": subset["mobility_ratio_tau"].quantile(0.95),
                "Max_mobility_ratio_tau": subset["mobility_ratio_tau"].max(),
                "Selected_mixing_reference": cfg.mixing_reference,
                "Selected_delta_mix_mean": mix_selected.mean(),
            }
        )

        mobile = subset.loc[subset["is_mobilized"]]
        if not mobile.empty:
            mobile_rows.append(
                {
                    "Interval": interval.label,
                    "Mobilized_records": int(len(mobile)),
                    "Mobilized_time_minutes": mobile_seconds / 60.0,
                    "Mobilized_time_percent": time_percent,
                    "Mean_tau_c_mobile": mobile["tau_c"].mean(),
                    "P95_tau_c_mobile": mobile["tau_c"].quantile(0.95),
                    "Max_tau_c_mobile": mobile["tau_c"].max(),
                    "Mean_u_star_c_mobile": mobile["u_star_c"].mean(),
                    "P95_u_star_c_mobile": mobile["u_star_c"].quantile(0.95),
                    "Max_u_star_c_mobile": mobile["u_star_c"].max(),
                }
            )

    return out, pd.DataFrame(interval_rows), pd.DataFrame(mobile_rows)


def safe_sheet_name(name: str, used: set[str]) -> str:
    replacements = {":": "-", "\\": "-", "/": "-", "?": "", "*": "", "[": "(", "]": ")"}
    clean = str(name)
    for old, new in replacements.items():
        clean = clean.replace(old, new)
    clean = clean.strip().strip("'") or "Sheet"
    base = clean[:31]
    candidate = base
    index = 1
    while candidate in used:
        suffix = f"_{index}"
        candidate = base[: 31 - len(suffix)] + suffix
        index += 1
    used.add(candidate)
    return candidate


def metadata_table(cfg: FileConfig, intervals: list[TimeInterval]) -> pd.DataFrame:
    physical = cfg.physical
    rows = [
        ("module", "current_forcing_mobility"),
        ("version", VERSION),
        ("input_file", str(cfg.input_file)),
        ("forcing_scope", "current-only; waves and wave-current interaction excluded"),
        ("rho_seawater_kg_m3", physical.rho_seawater),
        ("roughness_factor_kn_over_D50", physical.roughness_factor),
        ("von_karman", physical.von_karman),
        ("n_intervals", len(intervals)),
        ("current_speed_formula", "u = sqrt(ve^2 + vn^2)"),
        ("current_direction_convention", "toward direction; degrees clockwise from north"),
        ("nikuradse_roughness_formula", "kn = roughness_factor * D50"),
        ("roughness_length_formula", "z0 = kn / 30"),
        ("current_friction_factor_formula", "fc = 2 * (kappa / ln(z / z0))^2"),
        ("current_shear_velocity_formula", "u_star_c = u * sqrt(fc / 2)"),
        ("current_bed_shear_stress_formula", "tau_c = 0.5 * rho_seawater * fc * u^2"),
        ("critical_shear_velocity_formula", "u_star_cr = sqrt(tau_cr / rho_seawater)"),
        ("mobility_condition", "tau_c > tau_cr"),
        ("mobility_time_method", "sample-and-hold duration weighting from timestamps"),
        ("gap_cap", "record duration capped at max_gap_factor * median sampling interval"),
        ("max_gap_factor", physical.max_gap_factor),
        ("mixing_layer_status", "diagnostic empirical estimate; coefficient must be justified by the study"),
        ("mixing_stress_coefficient_m3_N", physical.mixing_stress_coefficient),
        ("mixing_grain_factor", physical.mixing_grain_factor),
        ("mixing_reference", physical.mixing_reference),
        (
            "mixing_layer_formula",
            "delta_mix = stress_coefficient * max(tau_reference - tau_cr, 0) + grain_factor * D50",
        ),
    ]
    return pd.DataFrame(rows, columns=["parameter", "value"])


def save_results(
    cfg: FileConfig,
    processed: pd.DataFrame,
    interval_stats: pd.DataFrame,
    mobile_stats: pd.DataFrame,
    qc: pd.DataFrame,
    intervals: list[TimeInterval],
) -> None:
    cfg.output_file.parent.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    sheet_map: list[dict] = []

    with pd.ExcelWriter(cfg.output_file, engine="openpyxl") as writer:
        def write(table: pd.DataFrame, requested: str) -> None:
            sheet = safe_sheet_name(requested, used)
            table.to_excel(writer, sheet_name=sheet, index=False)
            sheet_map.append({"requested_sheet_name": requested, "excel_sheet_name": sheet})

        write(processed, "All_Data")
        write(interval_stats, "Interval_Summary")
        write(mobile_stats, "Mobile_Summary")
        for interval in intervals:
            subset = processed.loc[processed["interval_label"].eq(interval.label)]
            if not subset.empty:
                write(subset, interval.label)
                mobile = subset.loc[subset["is_mobilized"]]
                if not mobile.empty:
                    write(mobile, f"{interval.label}_Mobile")
        write(metadata_table(cfg, intervals), "Metadata")
        write(qc, "QC_Excluded_Rows")
        write(pd.DataFrame(sheet_map), "SheetName_Map")


def make_plots(
    processed: pd.DataFrame,
    intervals: list[TimeInterval],
    png_path: Path,
    pdf_path: Path,
) -> None:
    """Plot current shear velocity and the critical threshold by interval."""
    available = [
        interval
        for interval in intervals
        if processed["interval_label"].eq(interval.label).any()
    ]
    if not available:
        return

    fig, axes = plt.subplots(len(available), 1, figsize=(9.0, 2.4 * len(available)), squeeze=False)
    for ax, interval in zip(axes[:, 0], available):
        subset = processed.loc[processed["interval_label"].eq(interval.label)].sort_values("Time")
        ax.plot(subset["Time"], subset["u_star_c"], color="#1769AA", linewidth=1.1, label=r"$u_{*c}$")
        ax.plot(subset["Time"], subset["u_star_cr"], color="#C62828", linestyle="--", linewidth=1.0, label=r"$u_{*cr}$")
        ax.fill_between(
            subset["Time"],
            subset["u_star_c"],
            subset["u_star_cr"],
            where=subset["is_mobilized"].to_numpy(bool),
            color="#F9A825",
            alpha=0.25,
            interpolate=True,
            label="Mobilized",
        )
        ax.set_title(interval.label, loc="left", fontsize=10, fontweight="bold")
        ax.set_ylabel(r"$u_*$ (m s$^{-1}$)")
        ax.grid(True, linewidth=0.4, alpha=0.25)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))
        ax.legend(loc="upper right", frameon=False, ncol=3, fontsize=8)

    axes[-1, 0].set_xlabel("Time")
    fig.suptitle("Current-induced shear velocity and sediment-mobility threshold", fontsize=12)
    fig.tight_layout()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def run(cfg: FileConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the complete current-forcing workflow."""
    raw = read_input_table(cfg.input_file, cfg.sheet_name)
    valid, qc = validate_input(raw)
    intervals = load_intervals(cfg.intervals_csv, valid)
    processed = calculate_current_metrics(valid, cfg.physical)
    processed, interval_stats, mobile_stats = annotate_intervals(
        processed, intervals, cfg.physical
    )

    invalid_calculations = int((~processed["calculation_valid"]).sum())
    if invalid_calculations:
        logging.warning("%d rows have z <= z0 and no valid log-profile calculation.", invalid_calculations)
    if not bool(processed["mobility_flags_agree"].all()):
        logging.warning("Stress and shear-velocity mobility flags disagree in at least one row.")

    save_results(cfg, processed, interval_stats, mobile_stats, qc, intervals)
    if cfg.make_plots:
        make_plots(processed, intervals, cfg.figure_png, cfg.figure_pdf)

    logging.info("Saved workbook: %s", cfg.output_file)
    if cfg.make_plots:
        logging.info("Saved figures: %s and %s", cfg.figure_png, cfg.figure_pdf)
    for row in interval_stats.itertuples(index=False):
        logging.info(
            "%s: %.2f%% mobilized time (%.2f min)",
            row.Interval,
            row.Mobilized_time_percent,
            row.Mobilized_time_minutes,
        )
    return processed, interval_stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calculate current-only near-bed forcing and sediment-remobilization metrics."
    )
    parser.add_argument("-i", "--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sheet", default=None)
    parser.add_argument("--intervals-csv", type=Path, default=None)
    parser.add_argument("--figure-png", type=Path, default=DEFAULT_FIGURE_PNG)
    parser.add_argument("--figure-pdf", type=Path, default=DEFAULT_FIGURE_PDF)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--rho-seawater", type=float, default=1025.0)
    parser.add_argument("--roughness-factor", type=float, default=2.5)
    parser.add_argument("--von-karman", type=float, default=0.41)
    parser.add_argument("--mixing-stress-coefficient", type=float, default=0.07)
    parser.add_argument("--mixing-grain-factor", type=float, default=6.0)
    parser.add_argument("--mixing-reference", choices=["mean", "p95", "max"], default="p95")
    parser.add_argument("--max-gap-factor", type=float, default=3.0)
    return parser


def config_from_args(argv: Optional[list[str]] = None) -> FileConfig:
    args = build_parser().parse_args(argv)
    if args.rho_seawater <= 0 or args.roughness_factor <= 0 or args.von_karman <= 0:
        raise ValueError("Physical constants must be positive.")
    if args.mixing_stress_coefficient < 0 or args.mixing_grain_factor < 0:
        raise ValueError("Mixing-layer coefficients cannot be negative.")
    if args.max_gap_factor <= 0:
        raise ValueError("max-gap-factor must be positive.")

    physical = PhysicalConfig(
        rho_seawater=args.rho_seawater,
        roughness_factor=args.roughness_factor,
        von_karman=args.von_karman,
        mixing_stress_coefficient=args.mixing_stress_coefficient,
        mixing_grain_factor=args.mixing_grain_factor,
        mixing_reference=args.mixing_reference,
        max_gap_factor=args.max_gap_factor,
    )
    return FileConfig(
        input_file=args.input,
        output_file=args.output,
        figure_png=args.figure_png,
        figure_pdf=args.figure_pdf,
        intervals_csv=args.intervals_csv,
        sheet_name=args.sheet,
        make_plots=not args.no_plots,
        physical=physical,
    )


def main(argv: Optional[list[str]] = None) -> int:
    setup_logging()
    run(config_from_args(argv))
    return 0


if __name__ == "__main__":
    main()
