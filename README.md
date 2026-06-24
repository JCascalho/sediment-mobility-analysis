# Sediment Mobility

Python workflows for calculating sediment entrainment thresholds from grain-size data and evaluating current-induced near-bed forcing and remobilization conditions.

Version 1.1.0 contains two complementary modules:

1. `sediment_mobility.py` calculates sediment properties and critical entrainment thresholds.
2. `current_forcing_mobility.py` compares a near-bed current time series with a supplied critical bed shear stress and quantifies threshold exceedance.

The current-forcing module is additive. The v1.0.0 sediment workflow remains backward compatible.

## Features

### Sediment thresholds

- Reads Excel workbooks containing one or more sediment-sampling sheets.
- Excludes `centroid` reference rows from sediment calculations while retaining them in coordinate outputs.
- Calculates dimensionless grain size, critical Shields parameter, critical bed shear stress, critical shear velocity, and settling velocity.
- Produces Excel summaries and PNG/PDF sampling-location figures.

### Current forcing and remobilization

- Reads CSV or Excel near-bed current observations.
- Calculates current speed and toward-direction azimuth.
- Estimates log-profile friction factor, current-induced shear velocity, and bed shear stress.
- Compares current stress with a supplied critical stress.
- Reports both record-based and timestamp-weighted remobilization percentages.
- Diagnoses sampling regularity, temporal coverage, and long data gaps.
- Exports interval summaries, mobile-record subsets, metadata, and diagnostic figures.
- Provides configurable empirical mixing-layer diagnostics.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The routines require Python 3.10 or later. Anaconda and Spyder can also be used if the listed packages are installed in the active environment.

## Sediment-Threshold Input

Each Excel sheet supplied to `sediment_mobility.py` must contain:

- `sample`
- `x`, `y`
- `rho_sed`, `rho_sw`
- `nu`, `g`
- `D50`

The optional `date/time` field is retained when present. Rows named `centroid` are treated as coordinate references rather than sediment samples.

Run the artificial example:

```bash
python sediment_mobility.py
```

Run a user workbook:

```bash
python sediment_mobility.py --input path/to/sediment_input.xlsx
```

## Current-Forcing Input

`current_forcing_mobility.py` requires one current time series with:

- `Time`: timestamp
- `ve`, `vn`: eastward and northward current components in m/s
- `D50`: representative median grain diameter in m
- `z`: sensor height above the bed in m
- `tau_cr`: critical bed shear stress in N/m2

Run the full artificial example:

```bash
python current_forcing_mobility.py \
  --input examples/example_current_forcing_input.xlsx \
  --intervals-csv examples/example_current_intervals.csv
```

Without `--intervals-csv`, the entire current record is analyzed as one interval. A custom interval file must contain `start`, `end`, and `label` columns.

Example with user data:

```bash
python current_forcing_mobility.py \
  --input path/to/current_data.xlsx \
  --intervals-csv path/to/intervals.csv \
  --output results/my_current_results.xlsx
```

The default mixing-layer reference is the 95th percentile of interval current stress. Alternative references are selected with:

```bash
--mixing-reference mean
--mixing-reference p95
--mixing-reference max
```

## Current-Forcing Outputs

The default workbook is `results/current_forcing_mobility_results.xlsx`. It includes:

- `All_Data`
- `Interval_Summary`
- `Mobile_Summary`
- interval-specific data and mobile-record sheets
- `Metadata`
- `QC_Excluded_Rows`
- `SheetName_Map`

The default figures are written to `results/plots/`.

## Scientific Interpretation

The two modules represent consecutive analytical stages. A critical stress derived from sediment properties may be supplied to the current-forcing workflow when it is representative of the monitored bed.

The current-forcing module is explicitly current-only. It does not include wave orbital velocity or combined wave-current stress. Threshold exceedance identifies conditions favorable for entrainment; it is not a direct measurement of sediment flux.

Time-weighted percentages assume that each observation represents conditions until the next timestamp. Long gaps are capped and reported. Review coverage and sampling diagnostics before interpreting interval percentages.

The mixing-layer calculation is an empirical diagnostic. Its coefficients and applicability must be justified independently for the study environment. See `docs/CURRENT_FORCING_METHOD.md`.

## Testing

```bash
python -m unittest discover -s tests -v
```

## Data Policy

The files in `examples/` are artificial and are provided only to demonstrate input structure. Do not upload unpublished or confidential field data to the public repository.

## Citation

If you use these routines, cite the archived release and GitHub repository. Citation metadata are provided in `CITATION.cff`.
