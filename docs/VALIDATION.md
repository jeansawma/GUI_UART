# JS 1.1 validation

Validated on Debian 13 with Python 3.12.14, PySide6 6.12.0,
pyqtgraph 0.14.0, NumPy 2.3.5, SciPy 1.17.0, and pyserial 3.5.
Qt ran with its offscreen platform. The preview uses simulated acquisition;
no physical serial device was attached. Windows batch execution was not tested
in this Linux environment.

## Automated checks

Run from the project directory with the development environment activated:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
# 72 passed

python -m pip check

python -m uart_gui --help
```

Tests cover exact transmit bytes, fragmented receive streams, descriptions,
plot and scope messages, malformed data, serial connection/removal/reconnection,
and POSIX pseudoterminal read/write integration using pyserial. They independently
compare all 142 field addresses and 66 plot selectors against preserved MATLAB
callbacks.

Model checks cover the 15-channel limit, routing mirrors, tick rollover, sweep
backfill, overlapping packet tails, duplicate timestamps, large timestamp gaps,
bounded histories, scope channel 16, and recording/smoothing round trips.
Session checks cover the description handshake, fast signal routing, output-drain
completion, ordered routing boundaries, cancellation, and retained numeric batch
pacing. Qt checks cover receive budgets, changed-channel drawing, refresh rates,
initial sample-divider synchronization, timing changes, demo acquisition,
search, pause without stopping acquisition, edit validation and persistence,
STOP during routing, export, and the offline viewer.

## Plotting measurements

The previous implementation applied numeric-write delays to all 50 signal-routing
commands: 45 × 10 ms plus 5 × 300 ms, or 1.95 seconds of artificial waiting.
Signal routing now follows the MATLAB routine without those pauses and waits for
the serial output queue to drain. The 550 command bytes have a theoretical
47.7 ms wire time at 115200 baud/8N1; this calculation is not a measured device
response time.

A separate issue was large timestamp gaps causing up to 100,000 Python-level
sample writes per channel. Array buffer writes replace that loop. The benchmark
below compares JS 1.1 with commit `ee90896` in the same process. Each result is the
median of five runs with fresh default models: initialize a channel at tick zero,
then apply a one-value packet at tick 1,000,000,000. That stresses a 100,000-second
gap while retaining bounded history. Model setup and imports are outside the
timed section.

| Selected channels | Previous model | JS 1.1 model |
| --- | ---: | ---: |
| 1 | 30.746 ms | 0.183 ms |
| 15 | 477.044 ms | 2.768 ms |

These are sample-processing medians, not GUI frame rates. Allocation and first
memory access affect individual runs; they are not worst-case latency guarantees.

The GUI workload injects five samples per packet at 20 packets/second/channel,
using the default 20 Hz plot refresh, for approximately five seconds. A large
timestamp gap is inserted midway. It measures the Qt queue and drawing code
with synthetic decoded packets; it does not pass through a physical UART.

| Metric | 1 channel | 15 channels |
| --- | ---: | ---: |
| Packets applied | 99 | 1,485 |
| Packet application latency, 95th percentile | 9.815 ms | 7.690 ms |
| Maximum gap between 5 ms GUI heartbeat callbacks | 26.217 ms | 29.348 ms |
| Curve updates per channel per second | 19.80 | 19.79 |
| Maximum queued packets | 1 | 15 |
| Dropped packets | 0 | 0 |

Curve updates count calls to update plot data, rather than visible monitor frames.
The wire format would require 680 bytes/second for this one-channel workload or
10,200 bytes/second for 15 channels, but no serial-link throughput is measured by
this GUI workload.

Reproduce the software benchmark from the project directory:

```bash
QT_QPA_PLATFORM=offscreen python -m tools.benchmark_plotting --channels 1 --seconds 5 --compare-ref ee90896
QT_QPA_PLATFORM=offscreen python -m tools.benchmark_plotting --channels 15 --seconds 5 --compare-ref ee90896
```

On Windows, omit the `QT_QPA_PLATFORM=offscreen` prefix to use a visible window.
The optional comparison needs Git history containing `ee90896`; omit
`--compare-ref ee90896` when running from a source ZIP.

These results establish software behavior on the stated cloud machine with
simulated input. Physical waveform smoothness, serial-driver latency, reserved
header bytes, device register semantics, and actuator behavior still require the
target firmware and hardware. The default baud rate remains 115200.
