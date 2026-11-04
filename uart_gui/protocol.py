"""Binary UART protocol translated from the supplied MATLAB callbacks.

TX and RX have *different* headers. The host transmits ``stx`` followed by
row, column, command, zero, then an IEEE-754 little-endian float32. Incoming
frames use a 10-byte header: marker[0:3], reserved[3], row[4], count[5],
flag[6], reserved[7:10], then payload[10:]. These receive offsets follow
``Serial_receive_fcn.m`` exactly; the reserved bytes have no documented
meaning. No checksum, acknowledgement, or escaping is present in the source.
Actual firmware compatibility must therefore also be checked on hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import operator
import struct


@dataclass(frozen=True)
class Values:
    row: int
    values: tuple[float, ...]


@dataclass(frozen=True)
class Description:
    row: int
    column: int
    text: str


@dataclass(frozen=True)
class PlotSamples:
    channel: int
    values: tuple[float, ...]
    tick: int


@dataclass(frozen=True)
class ScopeSamples:
    channel: int
    values: tuple[float, ...]


Event = Values | Description | PlotSamples | ScopeSamples


def _byte(value: int, name: str) -> int:
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be an integer byte") from exc
    if not 0 <= result <= 255:
        raise ValueError(f"{name} must be between 0 and 255")
    return result


def encode_command(value: float, row: int, column: int, command: int | str = 0) -> bytes:
    """Encode a single write/read command, using zero-based wire addresses.

    ``command`` may be 0 or a one-character ASCII command such as ``'D'``.
    Nonfinite values are rejected so invalid edits cannot become hardware
    commands. Reading telemetry still preserves NaN/Inf sent by a device.
    """
    if isinstance(command, str):
        if len(command) != 1 or ord(command) > 127:
            raise ValueError("command must be a single ASCII character")
        command = ord(command)
    prefix = bytes((_byte(row, "row"), _byte(column, "column"), _byte(command, "command"), 0))
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("command value must be finite")
    try:
        payload = struct.pack("<f", value)
    except (OverflowError, struct.error) as exc:
        raise ValueError("command value is outside float32 range") from exc
    return b"stx" + prefix + payload


class StreamDecoder:
    """Incremental decoder tolerating fragmented packets and leading noise.

    Scope blocks contain raw floats after their header, even when a payload
    happens to contain a marker. Complete blocks are emitted atomically.
    Memory is bounded by the maximum 20,000 samples in the original scope.
    Call ``reset`` on reconnect; an interrupted raw scope block cannot be
    resynchronized reliably because the protocol has no escaping or CRC.
    """

    def __init__(self, max_scope_samples: int = 20_000) -> None:
        if max_scope_samples < 1:
            raise ValueError("max_scope_samples must be positive")
        self.max_scope_samples = max_scope_samples
        self._buffer = bytearray()
        self.discarded_bytes = 0
        self.malformed_frames = 0

    def reset(self) -> None:
        self._buffer.clear()
        self.discarded_bytes = 0
        self.malformed_frames = 0

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def _discard(self, size: int, malformed: bool = False) -> None:
        del self._buffer[:size]
        self.discarded_bytes += size
        self.malformed_frames += int(malformed)

    def feed(self, data: bytes | bytearray | memoryview) -> list[Event]:
        self._buffer.extend(data)
        events: list[Event] = []
        while len(self._buffer) >= 3:
            marker = bytes(self._buffer[:3])
            if marker not in (b"stx", b"std", b"stv"):
                # Retain the last two bytes: either can begin a split marker.
                candidates = [self._buffer.find(m) for m in (b"stx", b"std", b"stv")]
                candidates = [index for index in candidates if index >= 0]
                self._discard(min(candidates) if candidates else len(self._buffer) - 2)
                continue
            if len(self._buffer) < 10:
                break
            row, count, flag = self._buffer[4:7]
            if marker == b"std":
                size = 10 + flag
                if len(self._buffer) < size:
                    break
                text = bytes(self._buffer[10:size]).decode("latin-1").rstrip("\x00")
                events.append(Description(row, count, text))
            elif marker == b"stv":
                digits = self._buffer[5:8]
                length = digits[0] + 100 * digits[1] + 10_000 * digits[2]
                if not 1 <= row <= 16 or any(d > 99 for d in digits) or length > self.max_scope_samples:
                    self._discard(1, malformed=True)
                    continue
                size = 10 + length * 4
                if len(self._buffer) < size:
                    break
                values = struct.unpack_from(f"<{length}f", self._buffer, 10)
                events.append(ScopeSamples(row - 1, values))
            else:
                if count > 100 or (row < 200 and flag == 0):
                    self._discard(1, malformed=True)
                    continue
                size = 10 + count * 4 + (4 if row >= 200 else 0)
                if len(self._buffer) < size:
                    break
                values = struct.unpack_from(f"<{count}f", self._buffer, 10)
                if row >= 200:
                    tick = struct.unpack_from("<i", self._buffer, 10 + count * 4)[0]
                    events.append(PlotSamples(row - 200, values, tick))
                else:
                    events.append(Values(row, values))
            del self._buffer[:size]
        return events
