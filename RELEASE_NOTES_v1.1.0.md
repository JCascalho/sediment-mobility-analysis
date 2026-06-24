# Sediment Mobility v1.1.0

Version 1.1.0 adds a current-only near-bed forcing workflow while preserving the original sediment-threshold analysis.

## Highlights

- New current-induced shear velocity and bed shear stress calculations.
- Remobilization flags based on critical bed shear stress.
- Time-weighted threshold-exceedance duration and percentage.
- Interval summaries with sampling regularity, temporal coverage, and gap diagnostics.
- Current shear-velocity plots with critical-threshold overlays.
- Artificial example data and focused tests.

## Scientific scope

The new module is explicitly current-only. Wave forcing and combined wave-current stress are outside this release. The mixing-layer output is an empirical diagnostic whose coefficients must be justified for the application.

## Compatibility

The existing `sediment_mobility.py` workflow remains backward compatible. The new `current_forcing_mobility.py` module uses a separate input format and can consume critical-stress values derived from the sediment workflow.
