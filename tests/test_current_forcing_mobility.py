import unittest

import numpy as np
import pandas as pd

from current_forcing_mobility import (
    PhysicalConfig,
    calculate_current_metrics,
    duration_weights,
    load_intervals,
    validate_input,
)


class CurrentForcingTests(unittest.TestCase):
    def sample_data(self):
        return pd.DataFrame(
            {
                "Time": pd.date_range("2026-01-01", periods=4, freq="1min"),
                "ve": [0.05, 0.20, 0.40, 0.10],
                "vn": [0.00, 0.05, 0.10, 0.00],
                "D50": [0.00025] * 4,
                "z": [0.13] * 4,
                "tau_cr": [0.18] * 4,
            }
        )

    def test_stress_and_shear_velocity_are_equivalent(self):
        valid, qc = validate_input(self.sample_data())
        self.assertTrue(qc.empty)
        result = calculate_current_metrics(valid, PhysicalConfig())
        reconstructed_tau = 1025.0 * result["u_star_c"] ** 2
        np.testing.assert_allclose(result["tau_c"], reconstructed_tau)
        self.assertTrue(result["mobility_flags_agree"].all())

    def test_default_interval_covers_full_record(self):
        valid, _ = validate_input(self.sample_data())
        intervals = load_intervals(None, valid)
        self.assertEqual(len(intervals), 1)
        self.assertEqual(intervals[0].label, "FULL_RECORD")
        self.assertLessEqual(intervals[0].start, valid["Time"].min())
        self.assertGreater(intervals[0].end, valid["Time"].max())

    def test_large_time_gap_is_capped(self):
        times = pd.Series(
            pd.to_datetime(
                [
                    "2026-01-01 00:00:00",
                    "2026-01-01 00:01:00",
                    "2026-01-01 00:02:00",
                    "2026-01-01 00:10:00",
                ]
            )
        )
        durations, diagnostics = duration_weights(
            times,
            pd.Timestamp("2026-01-01 00:11:00"),
            max_gap_factor=3.0,
        )
        self.assertEqual(diagnostics["median_dt_seconds"], 60.0)
        self.assertEqual(diagnostics["capped_gap_count"], 1)
        self.assertLessEqual(float(np.max(durations)), 180.0)


if __name__ == "__main__":
    unittest.main()
