import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.io import loadmat, savemat

from uart_gui.model import AcquisitionModel, import_recording, smooth_values
from uart_gui.protocol import Description, PlotSamples, ScopeSamples, Values


class ModelTests(unittest.TestCase):
    def test_exact_legacy_routing_and_capacity(self):
        model = AcquisitionModel()
        commands = model.select_signal(6, 17)
        self.assertEqual(commands[:4], [(6, 13, 0), (17, 13, 1),
                                        (6, 3, 10), (17, 3, 15)])
        for column in range(14):
            model.select_signal(0, column)
        self.assertEqual(model.slots[10], (0, 9))
        self.assertIn((9, 14, 1), model.mapping_commands())
        with self.assertRaisesRegex(ValueError, "15"):
            model.select_signal(1, 0)
        model.select_signal(6, 17, False)
        self.assertIsNone(model.slots[0])
        self.assertEqual(model.mapping_commands()[:2], [(255, 13, 0), (255, 13, 1)])
        model.select_signal(1, 0)
        self.assertEqual(model.slots[0], (1, 0))

    def test_device_state_and_scope(self):
        model = AcquisitionModel()
        model.handle(Values(6, (2.5, 4)))
        model.handle(Description(6, 0, "Gain"))
        model.select_signal(6, 0)
        self.assertEqual(model.values[6, 1], 4)
        self.assertEqual(model.label(0), "Gain")
        model.handle(ScopeSamples(15, (1., 2., 3.)))
        np.testing.assert_equal(model.scope[15], [1, 2, 3])

    def test_backfill_sweep_wrap_and_bounded_history(self):
        model = AcquisitionModel(sample_period=.01, step=.01, window=.1, max_history=5)
        model.select_signal(0, 0)
        self.assertTrue(model.handle(PlotSamples(0, (1., 2.), 8)))
        model.handle(PlotSamples(0, (3., 4.), 12))
        times, values = model.history_data(0)
        np.testing.assert_allclose(times, [.09, .10, .11, .12, .13])
        np.testing.assert_equal(values, [2, 3, 3, 3, 4])
        self.assertEqual(model.vplot[0, 0], 3)
        self.assertEqual(model.vplot[3, 0], 4)
        self.assertFalse(model.handle(PlotSamples(0, (99.,), 11)))
        self.assertFalse(model.handle(PlotSamples(1, (99.,), 11)))

    def test_signed_int32_tick_wrap(self):
        model = AcquisitionModel(sample_period=.01, step=.01, window=.1, max_history=5)
        model.select_signal(0, 0)
        model.handle(PlotSamples(0, (1.,), -2))
        model.handle(PlotSamples(0, (2.,), 1))
        times, values = model.history_data(0)
        np.testing.assert_allclose(times, np.arange(4294967294, 4294967298) * .01)
        np.testing.assert_equal(values, [1, 2, 2, 2])

    def test_duplicate_packet_does_not_duplicate_history(self):
        model = AcquisitionModel()
        model.select_signal(0, 0)
        model.handle(PlotSamples(0, (1.,), 0))
        model.handle(PlotSamples(0, (2.,), 0))
        np.testing.assert_equal(model.history_data(0)[1], [2])

    def test_newer_overlapping_packets_replace_and_extend_history(self):
        model = AcquisitionModel(sample_period=.01, step=.01, window=2, max_history=20)
        model.select_signal(0, 0)
        model.handle(PlotSamples(0, (1., 2., 3., 4., 5.), 100))
        self.assertTrue(model.handle(PlotSamples(0, (10., 11., 12., 13., 14.), 102)))
        times, values = model.history_data(0)
        np.testing.assert_allclose(times, np.arange(100, 107) * .01)
        np.testing.assert_equal(values, [1, 2, 10, 11, 12, 13, 14])
        np.testing.assert_equal(model.vplot[100:107, 0], values)

        # A newer start need not extend the previous packet's tail. It still
        # updates retained overlapping points without shortening the history.
        model.handle(PlotSamples(0, (20., 21.), 103))
        np.testing.assert_equal(model.history_data(0)[1], [1, 2, 10, 20, 21, 13, 14])
        revisions = model.plot_revisions.copy()
        self.assertFalse(model.handle(PlotSamples(0, (99.,) * 10, 101)))
        self.assertEqual(model.plot_revisions, revisions)
        np.testing.assert_equal(model.history_data(0)[1], [1, 2, 10, 20, 21, 13, 14])

    def test_large_gap_fills_only_retained_live_and_history_samples(self):
        model = AcquisitionModel(max_history=5)
        model.select_signal(0, 0)
        model.handle(PlotSamples(0, (1.,), 0))
        model.handle(PlotSamples(0, (2., 3.), 1000000000))
        times, values = model.history_data(0)
        np.testing.assert_allclose(times, np.arange(9999997, 10000002) * .01)
        np.testing.assert_equal(values, [2, 2, 2, 2, 3])
        np.testing.assert_equal(model.vplot[2:-1, 0], 2)
        self.assertEqual(model.vplot[0, 0], 2)
        self.assertEqual(model.vplot[1, 0], 3)
        self.assertEqual(model.vplot[-1, 0], 2)

    def test_old_overlap_cannot_overwrite_newer_sweep_positions(self):
        model = AcquisitionModel(sample_period=.01, step=.01, window=.1, max_history=40)
        model.select_signal(0, 0)
        model.handle(PlotSamples(0, tuple(range(30)), 0))
        before = model.vplot[:, 0].copy()
        model.handle(PlotSamples(0, (100., 101.), 1))
        np.testing.assert_equal(model.vplot[:, 0], before)
        np.testing.assert_equal(model.history_data(0)[1][1:3], [100, 101])

    def test_ring_matches_chronological_reference_for_packet_overlap(self):
        model = AcquisitionModel(sample_period=.01, step=.01, window=.2, max_history=17)
        model.select_signal(0, 0)
        rng = np.random.default_rng(42)
        reference = {}
        start = 3
        highwater = None
        for _ in range(100):
            start += int(rng.integers(0, 8))
            packet = tuple(rng.normal(size=int(rng.integers(1, 13))))
            if highwater is not None:
                for index in range(highwater + 1, start):
                    reference[index] = packet[0]
            for index, value in enumerate(packet, start):
                reference[index] = value
            highwater = max(highwater if highwater is not None else start,
                            start + len(packet) - 1)
            self.assertTrue(model.handle(PlotSamples(0, packet, start)))
            retained = sorted(reference)[-17:]
            times, values = model.history_data(0)
            np.testing.assert_allclose(times, np.asarray(retained) * .01)
            np.testing.assert_allclose(values, [reference[index] for index in retained])
            live = np.full(len(model.tm), np.nan)
            for index in sorted(reference):
                if index > highwater - 20:
                    live[index % 20] = reference[index]
            live[-1] = live[0]
            np.testing.assert_equal(model.vplot[:, 0], live)

    def test_revisions_track_only_affected_plot_channels(self):
        model = AcquisitionModel()
        original = model.plot_revisions.copy()
        model.select_signal(0, 0)
        self.assertEqual(model.plot_revisions[0], original[0] + 1)
        self.assertEqual(model.plot_revisions[1:], original[1:])
        model.select_signal(0, 1)
        before = model.plot_revisions.copy()
        model.handle(PlotSamples(1, (1.,), 0))
        self.assertEqual(model.plot_revisions[0], before[0])
        self.assertEqual(model.plot_revisions[1], before[1] + 1)
        before = model.plot_revisions.copy()
        model.handle(Description(0, 0, "Speed"))
        self.assertEqual(model.plot_revisions[0], before[0] + 1)
        self.assertEqual(model.plot_revisions[1:], before[1:])
        before = model.plot_revisions.copy()
        model.clear()
        self.assertEqual(model.plot_revisions, [revision + 1 for revision in before])

    def test_positive_to_negative_signed_tick_boundary_is_continuous(self):
        model = AcquisitionModel(sample_period=.01, step=.01, window=.1, max_history=5)
        model.select_signal(0, 0)
        model.handle(PlotSamples(0, (1.,), 0x7fffffff))
        model.handle(PlotSamples(0, (2.,), -0x80000000))
        times, values = model.history_data(0)
        np.testing.assert_allclose(times, np.asarray([0x7fffffff, 0x80000000]) * .01)
        np.testing.assert_equal(values, [1, 2])

    def test_clear_and_reselect_remove_old_data(self):
        model = AcquisitionModel()
        model.select_signal(0, 0)
        model.handle(PlotSamples(0, (10.,), 0))
        model.select_signal(0, 0, False)
        self.assertTrue(np.isnan(model.vplot[:, 0]).all())
        self.assertEqual(len(model.history_data(0)[0]), 0)
        model.select_signal(0, 1)
        model.clear()
        self.assertEqual(model.slots[0], (0, 1))

    def test_export_mat_and_csv_roundtrip(self):
        model = AcquisitionModel()
        model.select_signal(6, 0)
        model.handle(Description(6, 0, "Gain, α"))
        model.handle(PlotSamples(0, (1., 2.), 0))
        model.handle(ScopeSamples(0, (3., 4.)))
        with tempfile.TemporaryDirectory() as directory:
            mat = Path(directory) / "record.mat"
            csv_file = Path(directory) / "record.csv"
            model.export_mat(mat)
            source = loadmat(mat)
            for key in ("tm", "vplot", "Tmem", "vmem", "vscope", "valid_lengths"):
                self.assertIn(key, source)
            np.testing.assert_equal(source["valid_lengths"][0], [2])
            np.testing.assert_equal(source["vmem"][:, 0], [1, 2])
            np.testing.assert_equal(source["vscope"][:, 0], [3, 4])
            recording = import_recording(mat)
            self.assertEqual(recording.labels[0], "Gain, α")
            np.testing.assert_allclose(recording.times, [0, .01])
            model.export_csv(csv_file)
            recording = import_recording(csv_file)
            np.testing.assert_equal(recording.values[:, 0], [1, 2])
            self.assertEqual(recording.labels, ("Gain, α",))

    def test_forward_average_and_legacy_import(self):
        np.testing.assert_allclose(smooth_values([1, 2, 3, 4], 3), [2, 3, 3.5, 4])
        averaged = smooth_values([1, np.nan, 3], 2)
        self.assertTrue(np.isnan(averaged[1]))
        self.assertEqual(averaged[0], 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Vecfile.mat"
            savemat(path, {"tm": [0, .01], "vplot": [[1, 2], [3, 4]]})
            recording = import_recording(path)
            np.testing.assert_equal(recording.values, [[1, 2], [3, 4]])

    def test_mat_preserves_actual_times_for_unequal_channels(self):
        model = AcquisitionModel()
        model.select_signal(0, 0)
        model.select_signal(0, 1)
        model.handle(Description(0, 0, "First"))
        model.handle(Description(0, 1, "Second"))
        model.handle(PlotSamples(0, (10., 20.), 1000))
        model.handle(PlotSamples(1, (30.,), 1200))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.mat"
            model.export_mat(path)
            recording = import_recording(path)
            np.testing.assert_allclose(recording.times, [.10, .11, .12])
            np.testing.assert_allclose(recording.values[:, :2],
                                       [[10, np.nan], [20, np.nan], [np.nan, 30]],
                                       equal_nan=True)
            self.assertEqual(recording.labels[:2], ("First", "Second"))

    def test_exports_preserve_chronological_ring_order_after_capacity_wrap(self):
        model = AcquisitionModel(sample_period=.01, step=.01, window=.1, max_history=5)
        model.select_signal(0, 0)
        model.handle(PlotSamples(0, (1., 2.), 8))
        model.handle(PlotSamples(0, (3., 4.), 12))
        with tempfile.TemporaryDirectory() as directory:
            for suffix in (".mat", ".csv"):
                path = Path(directory) / ("retained" + suffix)
                if suffix == ".mat":
                    model.export_mat(path)
                    source = loadmat(path)
                    np.testing.assert_equal(source["valid_lengths"][0], [5])
                    np.testing.assert_equal(source["vmem"][:, 0], [2, 3, 3, 3, 4])
                else:
                    model.export_csv(path)
                recording = import_recording(path)
                np.testing.assert_allclose(recording.times, [.09, .10, .11, .12, .13])
                np.testing.assert_equal(recording.values[:, 0], [2, 3, 3, 3, 4])

    def test_scope_only_export_and_import(self):
        model = AcquisitionModel(sample_period=.0002)
        model.handle(ScopeSamples(0, (1., 2., 3.)))
        model.handle(ScopeSamples(15, (4.,)))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scopefile.mat"
            model.export_scopes_mat(path)
            source = loadmat(path)
            np.testing.assert_equal(source["scope_lengths"][[0, 15], 0], [3, 1])
            recording = import_recording(path)
            np.testing.assert_allclose(recording.times, [0, .0002, .0004])
            np.testing.assert_equal(recording.values[:, 0], [1, 2, 3])
            np.testing.assert_allclose(recording.values[:, 15], [4, np.nan, np.nan],
                                       equal_nan=True)
            self.assertEqual(len(recording.labels), 16)


if __name__ == "__main__":
    unittest.main()
