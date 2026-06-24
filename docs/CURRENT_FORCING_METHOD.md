# Current-Forcing Method

## Scope

`current_forcing_mobility.py` evaluates current-induced near-bed forcing. It is intended for environments in which currents are treated as the dominant forcing mechanism. It does not calculate wave orbital velocity, wave-induced stress, or combined wave-current stress.

## Required variables

| Column | Meaning | Unit |
|---|---|---|
| `Time` | Observation timestamp | datetime |
| `ve` | Eastward current component | m/s |
| `vn` | Northward current component | m/s |
| `D50` | Median grain diameter | m |
| `z` | Sensor height above bed | m |
| `tau_cr` | Critical bed shear stress | N/m2 |

The `tau_cr` values may be derived using `sediment_mobility.py`, provided the sediment properties are representative of the current-monitoring location and period.

## Equations

Current speed and toward-direction azimuth are

```text
u = sqrt(ve^2 + vn^2)
direction = atan2(ve, vn)
```

where direction is reported clockwise from north. The equivalent Nikuradse roughness and roughness length are

```text
kn = 2.5 D50
z0 = kn / 30
```

and the current friction factor is

```text
fc = 2 [kappa / ln(z/z0)]^2.
```

The current-induced shear velocity and bed shear stress are

```text
u_star_c = u sqrt(fc/2)
tau_c = 0.5 rho_w fc u^2 = rho_w u_star_c^2.
```

The critical shear velocity is obtained from the supplied critical stress:

```text
u_star_cr = sqrt(tau_cr/rho_w).
```

Sediment is classified as mobilized when `tau_c > tau_cr`. The equivalent `u_star_c > u_star_cr` flag is exported as a numerical consistency check.

## Time weighting

The routine reports both the fraction of records above threshold and a time-weighted percentage. Each observation is assumed to represent conditions until the following timestamp. Durations larger than `max_gap_factor` times the median sampling interval are capped; the default factor is 3. Interval summaries report sampling-interval variability, capped-gap count, represented duration, nominal interval duration, and coverage.

For regularly spaced observations, the record and time-weighted percentages should be nearly identical. For irregular observations, the time-weighted percentage is preferred, but intervals with poor coverage still require caution.

## Mixing-layer diagnostic

The optional diagnostic estimate is

```text
delta_mix = a max(tau_reference - tau_cr, 0) + b D50,
```

where the defaults are `a = 0.07 m3/N`, `b = 6`, and `tau_reference` is the interval 95th percentile of `tau_c`. These coefficients are exposed as command-line parameters because their empirical basis and applicability must be justified for each study. This estimate should not be presented as a universal physical law.

## Interpretation

Threshold exceedance indicates hydrodynamic conditions favorable for entrainment. It does not prove that sediment was transported at every exceedance, nor does it account for sediment availability, bed armoring, cohesive effects, biological stabilization, waves, or spatial variability outside the sensor location.
