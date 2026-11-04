"""Create a small entirely artificial input workbook for the Vilamoura M3 demonstration.

This utility does not contain or reproduce any Vilamoura field data.
It refuses to overwrite an existing input workbook.
"""
from pathlib import Path
import pandas as pd

OUTPUT = Path(__file__).resolve().parent / "INPUT_SEDIMENT_PARAMETERS.xlsx"


def main():
    if OUTPUT.exists():
        raise SystemExit(f"File already exists; not overwriting: {OUTPUT}")
    common = {"rho_sed": 2650.0, "rho_sw": 1025.0, "nu": 1.05e-6, "g": 9.81}
    sheets = {
        "Tracer": pd.DataFrame([{
            "Sample_GIS": "SYN_TRACER", "Sed_Camp": "Tracer", "Local": "Synthetic",
            "x": 500000.0, "y": 4100000.0, "D50": 0.00049, **common,
        }]),
        "Av_Native_Sed": pd.DataFrame([{
            "Sample_GIS": "SYN_NATIVE", "Sed_Camp": "Av_Native_Sed", "Local": "Synthetic",
            "x": 500000.0, "y": 4100000.0, "D50": 0.00062, **common,
        }]),
        "C1": pd.DataFrame([
            {"Sample_GIS": "SYN_C1_A", "Sed_Camp": "C1", "Local": "Synthetic",
             "x": 500010.0, "y": 4100005.0, "D50": 0.00058, **common},
            {"Sample_GIS": "SYN_C1_B", "Sed_Camp": "C1", "Local": "Synthetic",
             "x": 500020.0, "y": 4100010.0, "D50": 0.00065, **common},
        ]),
    }
    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        for name, data in sheets.items():
            data.to_excel(writer, sheet_name=name, index=False)
    print(f"Created artificial demonstration workbook: {OUTPUT}")


if __name__ == "__main__":
    main()
