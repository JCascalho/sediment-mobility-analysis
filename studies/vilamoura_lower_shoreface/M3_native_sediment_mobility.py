"""
====================================================
M3 — Native Sediment Mobility
Critical mobility parameters of native sediments and fluorescent tracers
File: M3_native_sediment_mobility.py
====================================================

Author: João Cascalho (FCUL / IDL – University of Lisbon)
Original revision: May 2026
M3 documentation and naming adaptation: November 2026

Purpose
-------
This workflow computes critical mobility parameters for both native sediments
and fluorescent tracer material following Soulsby (1997) from sediment-property
worksheets. It keeps the original projected coordinates
(x, y) unchanged.

IMPORTANT CONCEPTUAL CHANGE
---------------------------
This version does NOT compute shoreline-rotated coordinates (as, cs).
The alongshore/cross-shore decomposition of tracer TRANSPORT should instead be
performed later in the tracer-metrics workflow, by rotating the mean velocity
vector (Vm_x, Vm_y) by the shoreline angle. This avoids sign inconsistencies
caused by using pre-rotated point coordinates for vector transport.

Input
-----
Input Excel file:
    INPUT_SEDIMENT_PARAMETERS.xlsx

Each worksheet must contain:
    - x, y      : original projected coordinates (m), e.g. ETRS89 / UTM 29N
    - D50       : median sediment grain size (m)
    - rho_sed   : sediment density (kg/m³)
    - rho_sw    : seawater density (kg/m³)
    - nu        : kinematic viscosity (m²/s)
    - g         : gravitational acceleration (m/s²)

Optional columns:
    - Sample_GIS : sample identifier or code
    - Sed_Camp   : campaign name (created automatically if missing)
    - Local      : site/locality name
    - date       : sampling date
    - delta_mix  : mixing-layer thickness (if provided)

Output
------
OUTPUT_M3_SEDIMENT_MOBILITY_PARAMETERS_NO_ROTATION.xlsx containing:
    * Sediment_Parameters   : x, y and computed D*, θ_cr, τ_cr, u*_cr, w_s
    * Campaign_Statistics   : per-sample table
    * Summary_Statistics    : grouped mean/std by Local and Sed_Camp when present
    * Max_Mixing_Thickness  : maximum delta_mix by Local/Sed_Camp when present
    * Global_Statistics     : total sample count and global mean D50
"""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class MasterFileConfig:
    input_file: str = "INPUT_SEDIMENT_PARAMETERS.xlsx"
    output_file: str = "OUTPUT_M3_SEDIMENT_MOBILITY_PARAMETERS_NO_ROTATION.xlsx"


@dataclass
class SedimentConfig:
    x_col: str = "x"
    y_col: str = "y"
    d50_col: str = "D50"
    rho_sed_col: str = "rho_sed"
    rho_sw_col: str = "rho_sw"
    nu_col: str = "nu"
    g_col: str = "g"
    sed_camp_col: str = "Sed_Camp"
    sample_col: str = "Sample_GIS"
    local_col: str = "Local"
    date_col: str = "date"


MASTER = MasterFileConfig()
SED_CFG = SedimentConfig()


# =============================================================================
# LOGGING
# =============================================================================

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


# =============================================================================
# PHYSICAL FUNCTIONS
# =============================================================================

def calculate_dimensionless_grain_size(d50, rho_s, rho_w, nu, g):
    """Soulsby (1997) dimensionless grain size D*."""
    return d50 * ((g * (rho_s - rho_w) / (rho_w * nu**2)) ** (1.0 / 3.0))


def calculate_critical_shields_parameter(D_star):
    """Soulsby (1997) critical Shields parameter θ_cr."""
    return 0.30 / (1.0 + 1.2 * D_star) + 0.055 * (1.0 - np.exp(-0.020 * D_star))


def calculate_critical_shear_stress(theta_cr, d50, rho_s, rho_w, g):
    """Critical shear stress τ_cr [Pa]."""
    return theta_cr * (rho_s - rho_w) * g * d50


def calculate_critical_shear_velocity(theta_cr, d50, rho_s, rho_w, g):
    """Critical shear velocity u*_cr [m/s]."""
    return np.sqrt(theta_cr * g * (rho_s - rho_w) * d50 / rho_w)


def calculate_settling_velocity(d50, rho_s, rho_w, nu, g):
    """Soulsby (1997) settling velocity w_s [m/s]."""
    D_star = calculate_dimensionless_grain_size(d50, rho_s, rho_w, nu, g)
    return (nu / d50) * (np.sqrt(10.36**2 + 1.049 * D_star**3) - 10.36)


# =============================================================================
# PROCESSING
# =============================================================================

def process_sediment_sheet(df):
    """Compute D*, θ_cr, τ_cr, u*_cr, and w_s for one campaign sheet."""
    df = df.copy()

    df["D_star"] = df.apply(
        lambda r: calculate_dimensionless_grain_size(
            r[SED_CFG.d50_col],
            r[SED_CFG.rho_sed_col],
            r[SED_CFG.rho_sw_col],
            r[SED_CFG.nu_col],
            r[SED_CFG.g_col],
        ),
        axis=1,
    )

    df["Theta_cr"] = df["D_star"].apply(calculate_critical_shields_parameter)

    df["Tau_cr"] = df.apply(
        lambda r: calculate_critical_shear_stress(
            r["Theta_cr"],
            r[SED_CFG.d50_col],
            r[SED_CFG.rho_sed_col],
            r[SED_CFG.rho_sw_col],
            r[SED_CFG.g_col],
        ),
        axis=1,
    )

    df["u_star_cr"] = df.apply(
        lambda r: calculate_critical_shear_velocity(
            r["Theta_cr"],
            r[SED_CFG.d50_col],
            r[SED_CFG.rho_sed_col],
            r[SED_CFG.rho_sw_col],
            r[SED_CFG.g_col],
        ),
        axis=1,
    )

    df["w_s"] = df.apply(
        lambda r: calculate_settling_velocity(
            r[SED_CFG.d50_col],
            r[SED_CFG.rho_sed_col],
            r[SED_CFG.rho_sw_col],
            r[SED_CFG.nu_col],
            r[SED_CFG.g_col],
        ),
        axis=1,
    )

    return df


def calculate_summary_statistics(df):
    """Campaign and global stats for D50, Tau_cr, u_star_cr, w_s."""
    stats = {}

    keep_cols = [
        c for c in [
            SED_CFG.local_col,
            SED_CFG.sed_camp_col,
            SED_CFG.date_col,
            SED_CFG.sample_col,
            SED_CFG.x_col,
            SED_CFG.y_col,
            SED_CFG.d50_col,
            "Tau_cr",
            "u_star_cr",
            "w_s",
            "delta_mix",
        ] if c in df.columns
    ]
    stats["campaign_samples"] = df[keep_cols].copy() if keep_cols else df.copy()

    group_cols = []
    if SED_CFG.local_col in df.columns:
        group_cols.append(SED_CFG.local_col)
    if SED_CFG.sed_camp_col in df.columns:
        group_cols.append(SED_CFG.sed_camp_col)

    if group_cols:
        agg_map = {
            SED_CFG.d50_col: ["count", "mean", "std"],
            "Tau_cr": ["mean", "std", "min", "max"],
            "u_star_cr": ["mean", "std", "min", "max"],
            "w_s": ["mean", "std", "min", "max"],
        }
        stats["campaign_stats"] = df.groupby(group_cols).agg(agg_map)

        if "delta_mix" in df.columns:
            stats["max_delta_mix"] = (
                df.groupby(group_cols)["delta_mix"]
                .max()
                .reset_index()
            )

    stats["global_stats"] = {
        "total_samples": int(len(df)),
        "mean_D50": float(df[SED_CFG.d50_col].mean()) if SED_CFG.d50_col in df.columns else np.nan,
    }

    return stats


def save_results(path, df, stats):
    """Write results to Excel workbook."""
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="Sediment_Parameters", index=False)

        if "campaign_samples" in stats:
            stats["campaign_samples"].to_excel(
                writer,
                sheet_name="Campaign_Statistics",
                index=False,
            )

        if "campaign_stats" in stats:
            stats["campaign_stats"].to_excel(
                writer,
                sheet_name="Summary_Statistics",
            )

        if "max_delta_mix" in stats:
            stats["max_delta_mix"].to_excel(
                writer,
                sheet_name="Max_Mixing_Thickness",
                index=False,
            )

        pd.DataFrame([stats["global_stats"]]).to_excel(
            writer,
            sheet_name="Global_Statistics",
            index=False,
        )


# =============================================================================
# MAIN
# =============================================================================

def main():
    setup_logging()
    logging.info("M3: Processing native-sediment and tracer datasets without coordinate rotation...")

    xls = pd.ExcelFile(MASTER.input_file)

    required_cols = [
        SED_CFG.x_col,
        SED_CFG.y_col,
        SED_CFG.d50_col,
        SED_CFG.rho_sed_col,
        SED_CFG.rho_sw_col,
        SED_CFG.nu_col,
        SED_CFG.g_col,
    ]

    processed_all = []
    processed_sheet_names = []
    skipped_sheet_info = []

    for sheet in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet)

            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                msg = f"Sheet '{sheet}' skipped: missing required columns {missing}"
                logging.warning(msg)
                skipped_sheet_info.append(msg)
                continue

            df_non_empty = df.dropna(subset=required_cols, how="all").copy()
            if df_non_empty.empty:
                msg = f"Sheet '{sheet}' skipped: all rows have NaN in required fields."
                logging.warning(msg)
                skipped_sheet_info.append(msg)
                continue

            if SED_CFG.sed_camp_col not in df_non_empty.columns:
                df_non_empty[SED_CFG.sed_camp_col] = sheet

            if SED_CFG.local_col not in df_non_empty.columns:
                df_non_empty[SED_CFG.local_col] = sheet.split("_")[-1] if "_" in sheet else sheet

            # Keep the original logic that prevents accidental mixing in Tracer/native sheets.
            sheet_lower = sheet.lower()
            if sheet_lower.startswith("tracer"):
                expected_camp = "Tracer"
            elif sheet_lower.startswith("nat_sed") or sheet_lower.startswith("native"):
                expected_camp = "Av_Native_Sed"
            else:
                expected_camp = None

            if expected_camp and SED_CFG.sed_camp_col in df_non_empty.columns:
                df_non_empty = df_non_empty[df_non_empty[SED_CFG.sed_camp_col] == expected_camp].copy()

            if df_non_empty.empty:
                msg = f"Sheet '{sheet}' skipped: no rows match expected campaign '{expected_camp}'."
                logging.warning(msg)
                skipped_sheet_info.append(msg)
                continue

            df_proc = process_sediment_sheet(df_non_empty)

            # Explicitly preserve original projected coordinates only.
            # No as/cs columns are created in this workflow.
            processed_all.append(df_proc)
            processed_sheet_names.append(sheet)
            logging.info(f"Sheet '{sheet}': processed {len(df_proc)} valid samples.")

        except Exception as e:
            msg = f"Sheet '{sheet}' skipped due to error: {e}"
            logging.error(msg)
            skipped_sheet_info.append(msg)
            continue

    if not processed_all:
        logging.error("No valid sheets were processed. Check required columns and data content.")
        if skipped_sheet_info:
            logging.error("Skipped sheets summary:")
            for msg in skipped_sheet_info:
                logging.error("  - " + msg)
        sys.exit(1)

    final_df = pd.concat(processed_all, ignore_index=True)

    logging.info("SUMMARY OF SHEET PROCESSING:")
    logging.info(f"  Sheets processed ({len(processed_sheet_names)}): {processed_sheet_names}")
    if skipped_sheet_info:
        logging.info("  Sheets skipped:")
        for msg in skipped_sheet_info:
            logging.info("    - " + msg)
    logging.info(f"  Total valid samples in final dataset: {len(final_df)}")

    stats = calculate_summary_statistics(final_df)
    save_results(Path(MASTER.output_file), final_df, stats)

    logging.info("✔ Completed successfully.")
    logging.info(f"Output saved as: {MASTER.output_file}")


if __name__ == "__main__":
    main()
