# Sediment Mobility

Python routine for calculating sediment-mobility parameters from sediment samples and plotting the sampling distribution of large and nested small grids.

The workflow calculates dimensionless grain size, critical Shields parameter, critical shear stress, critical shear velocity, and settling velocity from sediment and fluid properties. It also exports coordinate metadata and quality-control information so that centroid reference points are kept visible but excluded from sediment-sample calculations.

## Features

- Reads Excel workbooks with one or more sampling sheets.
- Supports `centroid` rows as grid reference points.
- Excludes centroid rows from sediment-mobility calculations and sample-density contours.
- Calculates sediment-mobility parameters from `D50`, sediment density, seawater density, kinematic viscosity, and gravity.
- Exports a structured Excel workbook with results, coordinates, summary statistics, metadata, and excluded rows.
- Produces PNG and PDF sampling-location plots.
- Includes a small artificial example workbook for testing.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If you use Anaconda or Spyder, you can also install the packages in your active environment.

## Input Format

The input file must be an Excel workbook. Each sheet must contain at least:

- `sample`
- `x`
- `y`
- `rho_sed`
- `rho_sw`
- `nu`
- `g`
- `D50`

Optional:

- `date/time`

Rows where `sample` is equal to `centroid` are treated as reference points. They are exported and plotted, but they are not used in the sediment-mobility calculations.

The example file in `examples/example_sediment_mobility_input.xlsx` is artificial and is provided only to demonstrate the expected structure.

## Usage

Run the included artificial example:

```bash
python sediment_mobility.py
```

Run with your own Excel workbook:

```bash
python sediment_mobility.py --input path/to/your_input.xlsx --output results/sediment_mobility_results.xlsx
```

Disable sample-density contours:

```bash
python sediment_mobility.py --input path/to/your_input.xlsx --no-density
```

## Outputs

The default outputs are:

- `results/sediment_mobility_results.xlsx`
- `results/plots/sediment_sample_locations.png`
- `results/plots/sediment_sample_locations.pdf`

The Excel workbook includes:

- `Sediment_Parameters`
- `Sample_Coordinates`
- `Summary_Statistics`
- `Global_Statistics`
- `Metadata`
- `QC_Excluded_Rows`

## Notes

The density contours in the plot represent relative sampling coverage only. They should not be interpreted as sediment concentration, sediment mobility, or hydrodynamic forcing.

Do not upload unpublished or confidential field datasets to this repository. Use the `examples` folder only for small artificial demonstration files or data that are explicitly approved for public release.

## Citation

If you use this routine, please cite the archived Zenodo release and the GitHub repository. Citation metadata are provided in `CITATION.cff`.

