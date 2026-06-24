# Changelog

All notable changes to this project are documented in this file.

## [1.1.0] - 2026-06-24

### Added

- `current_forcing_mobility.py` for current-only near-bed forcing analysis.
- Current speed and toward-direction azimuth from eastward/northward components.
- Log-profile friction factor, current-induced shear velocity, and bed shear stress.
- Critical-threshold comparison using `tau_cr` supplied by the sediment workflow or another justified source.
- Time-weighted remobilization percentages and durations based on observation timestamps.
- Sampling-regularity, coverage, and capped-gap diagnostics.
- Interval-specific Excel outputs and current-shear-velocity figures.
- Configurable empirical mixing-layer diagnostics using mean, 95th-percentile, or maximum interval stress.
- Artificial current time series and interval examples.
- Unit tests for physical equivalence, interval generation, and time-gap handling.

### Changed

- Project metadata and documentation now describe both threshold and current-forcing workflows.
- Improved sampling-location figure spacing and axis-label readability.
- Repository version increased from 1.0.0 to 1.1.0.

### Compatibility

- `sediment_mobility.py` retains its v1.0.0 input and output behavior.
- The new current-forcing workflow is additive and does not replace the sediment-threshold workflow.

## [1.0.0] - 2026-06-09

- Initial public release of the sediment-mobility threshold workflow.
