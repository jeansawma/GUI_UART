"""Device state, fifteen-channel acquisition, and MATLAB-compatible recordings.

Addresses and channel numbers in this module are zero-based. The live display
uses the original 20-second sweep. Gaps use the first value of the new packet,
matching Serial_receive_fcn.m; this is intentionally a backfill rather than
interpolation. Historical data is retained chronologically in NumPy ring buffers.
Newer packets may overlap earlier packet tails. They replace overlapping samples
and append only genuinely new timestamps, rather than reproducing MATLAB's
duplicate historical entries. Counter unwrapping and NaN missing-data semantics
are independent of rendering and remain unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import math
from pathlib import Path

import numpy as np
from scipy.io import loadmat, savemat


@dataclass(frozen=True)
class Recording:
    times: np.ndarray
    values: np.ndarray
    labels: tuple[str, ...]


class AcquisitionModel:
    CHANNELS = 15

    def __init__(self, sample_period: float = 0.0001, step: float = 0.01,
                 window: float = 20.0, max_history: int = 100000):
        if not all(math.isfinite(v) and v > 0 for v in (sample_period, step, window)):
            raise ValueError("Sample period, display step and window must be positive.")
        if not isinstance(max_history, int) or max_history < 1:
            raise ValueError("History capacity must be a positive integer.")
        self.sample_period = float(sample_period)
        self.step = float(step)
        self.window = float(window)
        self.max_history = max_history
        self._buckets = round(window / step)
        if self._buckets < 1 or not math.isclose(self._buckets * step, window):
            raise ValueError("Display window must be an integer multiple of its step.")
        self.tm = np.arange(self._buckets + 1, dtype=float) * self.step
        self.values: dict[tuple[int, int], float] = {}
        self.descriptions: dict[tuple[int, int], str] = {}
        self.slots: list[tuple[int, int] | None] = [None] * self.CHANNELS
        self.plot_revisions = [0] * self.CHANNELS
        self.clear()

    def clear(self):
        """Clear acquisitions while preserving device state and signal selection."""
        self.vplot = np.full((len(self.tm), self.CHANNELS), np.nan)
        self.scope: dict[int, np.ndarray] = {}
        # Absolute display indices map directly into these rings. History is
        # dense between its retained endpoints because gaps are backfilled.
        self._history = [np.empty(self.max_history) for _ in range(self.CHANNELS)]
        self._history_counts = [0] * self.CHANNELS
        self._last_index: list[int | None] = [None] * self.CHANNELS
        self._last_tick: list[int | None] = [None] * self.CHANNELS
        self._tick_time: list[int | None] = [None] * self.CHANNELS
        for channel in range(self.CHANNELS):
            self.plot_revisions[channel] += 1

    def _clear_channel(self, channel: int):
        self.vplot[:, channel] = np.nan
        self._history_counts[channel] = 0
        self._last_index[channel] = None
        self._last_tick[channel] = None
        self._tick_time[channel] = None
        self.plot_revisions[channel] += 1

    def select_signal(self, row: int, column: int, enabled: bool = True):
        """Allocate the first free slot and return firmware routing commands.

        Sending all mappings preserves the exact Plot_Fill_UART behavior,
        including its legacy row-3 mirror addresses for the first ten slots.
        """
        if not (isinstance(row, int) and isinstance(column, int)
                and 0 <= row < 200 and 0 <= column < 100):
            raise ValueError("Signal address must be row 0–199, column 0–99.")
        address = (row, column)
        if enabled and address not in self.slots:
            try:
                channel = self.slots.index(None)
            except ValueError:
                raise ValueError("All 15 plot channels are in use.") from None
            self.slots[channel] = address
            self._clear_channel(channel)
        elif not enabled and address in self.slots:
            channel = self.slots.index(address)
            self.slots[channel] = None
            self._clear_channel(channel)
        return self.mapping_commands()

    def mapping_commands(self):
        commands = []
        for channel, address in enumerate(self.slots):
            row, column = address if address is not None else (255, 255)
            target_row = 13 if channel < 10 else 14
            offset = channel if channel < 10 else channel - 10
            commands.extend(((row, target_row, offset * 2),
                             (column, target_row, offset * 2 + 1)))
            if channel < 10:
                commands.extend(((row, 3, 10 + channel), (column, 3, 15 + channel)))
        return commands

    def label(self, channel: int) -> str:
        address = self.slots[channel]
        if address is None:
            return f"Channel {channel + 1}"
        return self.descriptions.get(address) or f"R{address[0]} · C{address[1]}"

    def handle(self, event) -> bool:
        """Apply a decoded protocol event, returning whether state changed."""
        # Local import lets offline recordings work without opening a transport.
        from .protocol import Description, PlotSamples, ScopeSamples, Values

        if isinstance(event, Values):
            for column, value in enumerate(event.values):
                self.values[event.row, column] = float(value)
            return True
        if isinstance(event, Description):
            address = (event.row, event.column)
            if self.descriptions.get(address) != event.text and address in self.slots:
                self.plot_revisions[self.slots.index(address)] += 1
            self.descriptions[address] = event.text
            return True
        if isinstance(event, ScopeSamples):
            if 0 <= event.channel <= self.CHANNELS:
                self.scope[event.channel] = np.asarray(event.values, dtype=float)
                return True
            return False
        if isinstance(event, PlotSamples):
            return self._plot_samples(event.channel, event.values, event.tick)
        return False

    def _plot_samples(self, channel, values, tick):
        if not 0 <= channel < self.CHANNELS or self.slots[channel] is None or not len(values):
            return False
        raw_tick = int(tick) & 0xffffffff
        previous_tick = self._last_tick[channel]
        if previous_tick is None:
            tick_time = raw_tick
        else:
            delta = (raw_tick - previous_tick) & 0xffffffff
            if delta >= 0x80000000:
                return False  # stale packet, rather than a forward counter wrap
            tick_time = self._tick_time[channel] + delta
        self._last_tick[channel] = raw_tick
        self._tick_time[channel] = tick_time
        scaled_tick = tick_time * (self.sample_period / self.step)
        target = math.floor(scaled_tick + max(1e-7, math.ulp(scaled_tick)))
        last = self._last_index[channel]
        packet = np.asarray(values, dtype=float)
        end = target + len(packet) - 1
        highwater = end if last is None else max(last, end)
        if last is not None and target > last + 1:
            # Fill only retained positions, using array slices even when the
            # elapsed gap spans millions of sample buckets.
            self._write_run(channel, last + 1, float(packet[0]), target - last - 1,
                            highwater)
        self._write_run(channel, target, packet, len(packet), highwater)
        added = len(packet) if last is None else max(0, highwater - last)
        self._history_counts[channel] = min(self.max_history,
                                            self._history_counts[channel] + added)
        self._last_index[channel] = highwater
        self.plot_revisions[channel] += 1
        return True

    def _write_run(self, channel, start, values, count, highwater):
        """Write a contiguous scalar/array run to the live and historical rings."""
        for destination in (self.vplot[:-1, channel], self._history[channel]):
            # An overlap older than the retained sweep must not overwrite a
            # newer point that happens to have the same modular position.
            skip = max(0, highwater - len(destination) + 1 - start)
            retained = count - skip
            if retained <= 0:
                continue
            position = (start + skip) % len(destination)
            first = min(retained, len(destination) - position)
            if np.isscalar(values):
                destination[position:position + first] = values
                destination[:retained - first] = values
            else:
                destination[position:position + first] = values[skip:skip + first]
                destination[:retained - first] = values[skip + first:count]
        self.vplot[-1, channel] = self.vplot[0, channel]

    def plot_data(self, channel: int):
        return self.tm, self.vplot[:, channel]

    def history_data(self, channel: int):
        count = self._history_counts[channel]
        if not count:
            return np.empty(0), np.empty(0)
        end = self._last_index[channel]
        indices = np.arange(end - count + 1, end + 1, dtype=np.int64)
        return indices * self.step, self._history[channel][indices % self.max_history]

    def _recording_arrays(self):
        lengths = np.asarray(self._history_counts, dtype=np.int32)
        size = int(lengths.max(initial=0))
        memory = np.full((size, self.CHANNELS), np.nan)
        actual_times = np.full_like(memory, np.nan)
        for channel in range(self.CHANNELS):
            times, data = self.history_data(channel)
            memory[:len(data), channel] = data
            actual_times[:len(data), channel] = times
        return lengths, memory, actual_times

    def _scope_arrays(self):
        scope_lengths = np.zeros(self.CHANNELS + 1, dtype=np.int32)
        scope_size = max((len(v) for v in self.scope.values()), default=0)
        scope = np.full((scope_size, self.CHANNELS + 1), np.nan)
        for channel, data in self.scope.items():
            scope[:len(data), channel] = data
            scope_lengths[channel] = len(data)
        return scope, scope_lengths

    def export_scopes_mat(self, path):
        """Write a scopefile.mat-compatible recording for scope-only playback."""
        scope, scope_lengths = self._scope_arrays()
        savemat(str(path), {
            "vscope": scope, "scope_lengths": scope_lengths,
            "sample_period": self.sample_period,
        }, do_compression=True, oned_as="column")

    def export_mat(self, path):
        """Write original variable names plus lengths, addresses and true times."""
        lengths, memory, actual_times = self._recording_arrays()
        scope, scope_lengths = self._scope_arrays()
        savemat(str(path), {
            "tm": self.tm, "vplot": self.vplot,
            "Tmem": np.arange(len(memory), dtype=float) * self.step,
            "vmem": memory, "vscope": scope,
            "recorded_times": actual_times,
            "valid_lengths": lengths, "scope_lengths": scope_lengths,
            "signal_addresses": np.asarray([s if s is not None else (-1, -1)
                                             for s in self.slots], dtype=np.int32),
            "signal_labels": np.asarray([self.label(c) for c in range(self.CHANNELS)],
                                         dtype=object),
            "sample_period": self.sample_period, "display_step": self.step,
        }, do_compression=True, oned_as="column")

    def export_csv(self, path):
        """Export timestamped long-form data, preserving unequal channel lengths."""
        with Path(path).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("time_s", "channel", "row", "column", "label", "value"))
            for channel in range(self.CHANNELS):
                address = self.slots[channel] or (-1, -1)
                for timestamp, value in zip(*self.history_data(channel)):
                    writer.writerow((format(timestamp, ".12g"), channel + 1,
                                     *address, self.label(channel), format(value, ".12g")))


def smooth_values(values, window: int = 51):
    """Forward moving mean used by Dessinee, including shortened final windows.

    A window of 51 corresponds to the original inclusive MATLAB i:i+50 slice.
    NaNs remain missing rather than contaminating neighboring valid samples.
    """
    if not isinstance(window, int) or window < 1:
        raise ValueError("Smoothing window must be a positive integer.")
    data = np.asarray(values, dtype=float)
    if data.ndim not in (1, 2):
        raise ValueError("Expected a vector or a sample-by-channel matrix.")
    matrix = data[:, None] if data.ndim == 1 else data
    valid = np.isfinite(matrix)
    total = np.vstack((np.zeros((1, matrix.shape[1])),
                       np.cumsum(np.where(valid, matrix, 0), axis=0)))
    count = np.vstack((np.zeros((1, matrix.shape[1])), np.cumsum(valid, axis=0)))
    starts = np.arange(len(matrix))
    ends = np.minimum(starts + window, len(matrix))
    sums = total[ends] - total[starts]
    counts = count[ends] - count[starts]
    result = np.full_like(matrix, np.nan)
    np.divide(sums, counts, out=result, where=counts > 0)
    result[~valid] = np.nan
    return result[:, 0] if data.ndim == 1 else result


def import_recording(path) -> Recording:
    """Load Python CSV or legacy MATLAB Vecfile/VecfileMEM/scopefile data."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            return Recording(np.empty(0), np.empty((0, 0)), ())
        required = {"time_s", "channel", "label", "value"}
        if not required.issubset(rows[0]):
            raise ValueError("CSV must contain time_s, channel, label and value columns.")
        timestamps = sorted({float(row["time_s"]) for row in rows})
        channels = sorted({int(row["channel"]) for row in rows})
        indices = {time: i for i, time in enumerate(timestamps)}
        columns = {channel: i for i, channel in enumerate(channels)}
        values = np.full((len(timestamps), len(channels)), np.nan)
        labels = [f"Channel {channel}" for channel in channels]
        for row in rows:
            column = columns[int(row["channel"])]
            values[indices[float(row["time_s"])], column] = float(row["value"])
            labels[column] = row["label"] or labels[column]
        return Recording(np.asarray(timestamps), values, tuple(labels))
    if path.suffix.lower() != ".mat":
        raise ValueError("Choose a .mat or .csv recording.")
    source = loadmat(path)
    if "vmem" in source and "Tmem" in source:
        values = np.asarray(source["vmem"], dtype=float)
        times = np.asarray(source["Tmem"], dtype=float).ravel()
        if "recorded_times" in source:
            actual_times = np.asarray(source["recorded_times"], dtype=float)
            if actual_times.shape != values.shape:
                raise ValueError("Recorded timestamps and sample dimensions do not match.")
            times = np.unique(actual_times[np.isfinite(actual_times)])
            aligned = np.full((len(times), values.shape[1]), np.nan)
            for channel in range(values.shape[1]):
                valid = np.isfinite(actual_times[:, channel])
                indices = np.searchsorted(times, actual_times[valid, channel])
                aligned[indices, channel] = values[valid, channel]
            values = aligned
    elif "vplot" in source and "tm" in source:
        values = np.asarray(source["vplot"], dtype=float)
        times = np.asarray(source["tm"], dtype=float).ravel()
    elif "vscope" in source:
        values = np.asarray(source["vscope"], dtype=float)
        period = float(np.asarray(source.get("sample_period", [[0.0001]])).ravel()[0])
        times = np.arange(len(values)) * period
    else:
        raise ValueError("MAT file needs Tmem/vmem, tm/vplot, or vscope variables.")
    if values.ndim != 2 or len(times) != len(values):
        raise ValueError("Recording time and sample dimensions do not match.")
    labels = []
    for item in np.asarray(source.get("signal_labels", []), dtype=object).ravel():
        labels.append(str(np.asarray(item).ravel()[0]) if np.asarray(item).size else "")
    labels = (labels + [f"Channel {i + 1}" for i in range(values.shape[1])])[:values.shape[1]]
    return Recording(times, values, tuple(labels))
