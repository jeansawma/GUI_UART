"""Repeatable software-only plotting benchmark; no device commands are sent.

Run from the project directory: python -m tools.benchmark_plotting --channels 1
On headless Linux, set QT_QPA_PLATFORM=offscreen. A Windows run uses a real window.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from uart_gui.app import MainWindow
from uart_gui.model import AcquisitionModel
from uart_gui.protocol import PlotSamples
from uart_gui.style import STYLESHEET


def gap_benchmark(model_type, channels, repeats=5):
    durations = []
    for _ in range(repeats):
        model = model_type()
        for channel in range(channels):
            model.select_signal(0, channel)
            model.handle(PlotSamples(channel, (1.0,), 0))
        started = time.perf_counter()
        for channel in range(channels):
            model.handle(PlotSamples(channel, (2.0,), 1_000_000_000))
        durations.append((time.perf_counter() - started) * 1000)
    return {"median_ms": round(statistics.median(durations), 3),
            "max_ms": round(max(durations), 3), "runs": repeats}


def load_reference(ref):
    source = subprocess.check_output(
        ["git", "show", f"{ref}:uart_gui/model.py"],
        cwd=Path(__file__).resolve().parents[1], text=True,
    )
    module = types.ModuleType("uart_gui._benchmark_reference")
    module.__package__ = "uart_gui"
    sys.modules[module.__name__] = module
    exec(compile(source, f"<git:{ref}:model.py>", "exec"), module.__dict__)
    return module.AcquisitionModel


def gui_benchmark(channels, seconds):
    application = QApplication.instance() or QApplication([])
    application.setStyle("Fusion")
    application.setStyleSheet(STYLESHEET)
    window = MainWindow()
    for channel in range(channels):
        window.model.select_signal(0, channel)
    window._refresh_plot()
    window.show()
    # Complete layout/font initialization before measuring steady-state work.
    application.processEvents()
    emitted = {}
    latencies = []
    heartbeats = []
    rendered = []
    original_handle = window.model.handle

    def handle(event):
        stamp = emitted.pop((event.channel, event.tick))
        result = original_handle(event)
        latencies.append((time.perf_counter() - stamp) * 1000)
        return result

    window.model.handle = handle
    for curve in window._curves.values():
        original = curve.setData

        def capture(*args, _original=original, **kwargs):
            rendered.append(time.perf_counter())
            return _original(*args, **kwargs)

        curve.setData = capture
    started = time.perf_counter()
    tick = 0
    frames = 0
    inserted_gap = False
    max_pending = 0

    def emit():
        nonlocal tick, frames, inserted_gap, max_pending
        # Five samples per packet at 20 packets/s = 100 samples/s/channel.
        # A 15-channel stream is 10,200 bytes/s with the existing wire format.
        if not inserted_gap and time.perf_counter() - started >= seconds / 2:
            tick += 1_000_000_000
            inserted_gap = True
        for channel in range(channels):
            packet = PlotSamples(channel, tuple(np.sin(np.arange(5) / 5 + frames / 4 + channel)), tick)
            emitted[channel, tick] = time.perf_counter()
            window.session.events.put_nowait(packet)
        max_pending = max(max_pending, window.session.events.qsize())
        frames += 1
        tick += 500

    producer = QTimer()
    producer.timeout.connect(emit)
    producer.start(50)
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: heartbeats.append(time.perf_counter()))
    heartbeat.start(5)
    try:
        while time.perf_counter() - started < seconds:
            application.processEvents()
            time.sleep(.001)
        producer.stop()
        heartbeat.stop()
        while not window.session.events.empty():
            window._receive()
        assert window._events_count == frames * channels
        assert not emitted
        elapsed = time.perf_counter() - started
        return {
            "duration_s": round(elapsed, 3), "channels": channels,
            "plot_packets_applied": window._events_count,
            "packet_apply_p95_ms": round(float(np.percentile(latencies, 95)), 3),
            "max_gui_heartbeat_gap_ms": round(float(np.max(np.diff(heartbeats))) * 1000, 3),
            "plot_updates_per_channel_s": round(len(rendered) / channels / elapsed, 2),
            "max_pending_packets": max_pending,
            "dropped_packets": window.session.dropped_events,
            "large_timestamp_gap_injected": inserted_gap,
        }
    finally:
        producer.stop()
        heartbeat.stop()
        window.close()
        application.processEvents()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channels", type=int, choices=range(1, 16), default=1)
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--compare-ref", help="Optional Git commit for the previous model; requires Git")
    args = parser.parse_args()
    if not np.isfinite(args.seconds) or args.seconds < 1:
        parser.error("--seconds must be at least 1")
    result = {"model_gap": gap_benchmark(AcquisitionModel, args.channels)}
    if args.compare_ref:
        result["reference_model_gap"] = gap_benchmark(load_reference(args.compare_ref), args.channels)
    result["gui"] = gui_benchmark(args.channels, args.seconds)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
