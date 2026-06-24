# Examples

This folder contains artificial files for testing both release workflows:

- `example_sediment_mobility_input.xlsx`: sediment samples used by `sediment_mobility.py`.
- `example_current_forcing_input.xlsx`: synthetic one-minute current time series used by `current_forcing_mobility.py`.
- `example_current_intervals.csv`: two analysis intervals for the synthetic current series.

Run the current-forcing example with:

```bash
python current_forcing_mobility.py \
  --input examples/example_current_forcing_input.xlsx \
  --intervals-csv examples/example_current_intervals.csv
```

All example data are artificial and must not be used for scientific interpretation.
