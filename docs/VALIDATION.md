# Validation

Validated on Debian 13 with Python 3.12.14. The desktop was run using Qt's
offscreen platform, including a 22-second simulated acquisition used for the
preview image. No physical serial device was attached.

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
# 45 passed

python -m pip check
# No broken requirements found.

uart-studio --help
# Installed command-line entry point works.
```

The tests cover exact transmit bytes, fragmented receive streams, descriptions,
plot and scope messages, malformed data, serial connection/removal/reconnection,
and a POSIX pseudoterminal read/write integration test using pyserial. They
independently compare 142 field addresses and 66 plot selectors against the
preserved MATLAB callbacks.

Model checks cover the 15-channel limit, routing mirrors, tick rollover, sweep
backfill, bounded histories, scope channel 16, and recording/smoothing round trips.
Qt checks exercise demo acquisition, signal search, pause without stopping
acquisition, numeric validation before batch writes, edit persistence, STOP during
routing, disconnect, MAT export, scope export, and the offline analysis viewer.

This establishes software behavior against the supplied source and simulated
serial devices. Hardware-dependent timing, reserved header bytes, device register
semantics, and actuator behavior still require the target firmware and hardware.
