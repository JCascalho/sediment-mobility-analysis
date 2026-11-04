# M3 — Native Sediment Mobility (Vilamoura lower shoreface)

**Critical mobility parameters of native sediments and fluorescent tracers**

This study-specific module adapts the validated `M_2_sediment_mobility_NO_ROTATION.py` workflow for the Vilamoura lower-shoreface study. The scientific calculations and processing logic are unchanged. `M3` is the methodological module number in the study, not the general software version.

## Scope

- Calculates entrainment thresholds for **both native sediments and fluorescent tracer material**.
- Implements Soulsby (1997) calculations for dimensionless grain size (`D_star`), critical Shields parameter (`Theta_cr`), critical shear stress (`Tau_cr`, Pa), critical shear velocity (`u_star_cr`, m/s), and settling velocity (`w_s`, m/s).
- Retains the original projected coordinates (`x`, `y`): **no coordinate rotation**.
- Exports sample-level and grouped Excel results.

This workflow estimates *critical thresholds*, not time-resolved transport or actual sediment flux. Hydrodynamic forcing and exceedance are assessed separately.

## Study files

- `M3_native_sediment_mobility.py` — the executable scientific workflow.
- `make_example_input.py` — creates a **small synthetic** example input workbook. It contains no field observations.

The Vilamoura source workbook includes sediment sheets `Tracer`, `Av_Native_Sed`, and `C1`–`C7`, with 224 processed entries. An `ADCP` sheet is skipped because it does not contain the required sediment parameters. The original observational workbook is **not included** in this publicly shareable example package.

## Input workbook

The script reads `INPUT_SEDIMENT_PARAMETERS.xlsx` in the current working directory. Sheets should contain:

| Column | Meaning | Unit |
| --- | --- | --- |
| `x`, `y` | Original projected coordinates | m |
| `D50` | Median grain size | m |
| `rho_sed` | Sediment density | kg/m³ |
| `rho_sw` | Seawater density | kg/m³ |
| `nu` | Kinematic viscosity | m²/s |
| `g` | Gravitational acceleration | m/s² |

Optional: `Sample_GIS`, `Sed_Camp`, `Local`, `date`, `delta_mix`. For a sheet whose name starts with `Tracer`, existing code retains rows where `Sed_Camp == "Tracer"`. For sheets starting with `Nat_Sed` or `Native`, it retains rows where `Sed_Camp == "Av_Native_Sed"`. Other sheets are processed using the supplied data.

Input values should be physically valid and positive; this historical workflow does not add a new formal physical-validity checking layer.

## Demonstration

From this case-study directory, run:

```bash
python -m pip install numpy pandas openpyxl
python make_example_input.py
python M3_native_sediment_mobility.py
```

The generator will **not overwrite** an existing `INPUT_SEDIMENT_PARAMETERS.xlsx`. To process real field observations, use the corresponding input workbook instead. Run the script with the working directory set to the directory containing the workbook.

## Output

`OUTPUT_M3_SEDIMENT_MOBILITY_PARAMETERS_NO_ROTATION.xlsx` contains:

- `Sediment_Parameters` — all processed rows and computed parameters.
- `Campaign_Statistics` — selected sample-level variables.
- `Summary_Statistics` — grouped statistics.
- `Max_Mixing_Thickness` — only if `delta_mix` is supplied.
- `Global_Statistics` — overall sample count and mean `D50`.

The optional `delta_mix` is carried through and summarized, **not calculated** here.

## Scientific provenance

The script is based on the author's validated May 2026 NO_ROTATION workflow, with updated naming and documentation for M3. The Soulsby (1997) formulae and the no-rotation treatment remain unchanged.

Reference: Soulsby, R. L. (1997). *Dynamics of Marine Sands*. Thomas Telford, London.

General-purpose repository: https://github.com/JCascalho/sediment-mobility-analysis

Author: João Cascalho (FCUL / IDL — University of Lisbon).

For reproducible scientific referencing, cite the immutable tag of the case-study release after it has been published, rather than the mutable `main` branch.
