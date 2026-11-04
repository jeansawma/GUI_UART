import math
import struct

import pytest

from uart_gui.protocol import Description, PlotSamples, ScopeSamples, StreamDecoder, Values, encode_command


def incoming(marker, row, count, flag=1, payload=b"", reserved=b"\x00\x00\x00"):
    return marker + bytes((0, row, count, flag)) + reserved + payload


def test_command_matches_matlab_float32_and_address_bytes():
    assert encode_command(1.5, 6, 17) == b"stx\x06\x11\x00\x00\x00\x00\xc0\x3f"
    assert encode_command(0, 0, 0, "D") == b"stx\x00\x00D\x00" + b"\x00" * 4
    assert encode_command(-2, 255, 255, 255)[3:7] == b"\xff\xff\xff\x00"


@pytest.mark.parametrize("args", [(math.nan, 0, 0), (math.inf, 0, 0), (1e100, 0, 0), (1, -1, 0),
                                   (1, 0, 256), (1, 1.5, 0), (1, 0, 0, "DD"), (1, 0, 0, "é")])
def test_invalid_commands_rejected_before_transmission(args):
    with pytest.raises(ValueError):
        encode_command(*args)


def test_incoming_stream_parses_all_message_types_at_every_split():
    frames = (
        incoming(b"stx", 7, 2, payload=struct.pack("<2f", 1.25, -4.5))
        + incoming(b"std", 7, 1, flag=8, payload=b"Courant\xe9")
        + incoming(b"stx", 214, 2, payload=struct.pack("<2fi", 4.0, 9.0, -1234))
        + incoming(b"stv", 16, 3, flag=0, reserved=b"\x00\x00\x00", payload=struct.pack("<3f", 2, 4, 6))
    )
    expected = [Values(7, (1.25, -4.5)), Description(7, 1, "Couranté"),
                PlotSamples(14, (4.0, 9.0), -1234), ScopeSamples(15, (2.0, 4.0, 6.0))]
    for split in range(len(frames) + 1):
        decoder = StreamDecoder()
        assert decoder.feed(frames[:split]) + decoder.feed(frames[split:]) == expected
        assert decoder.buffered_bytes == 0
    decoder = StreamDecoder()
    result = []
    for byte in frames:
        result.extend(decoder.feed(bytes((byte,))))
    assert result == expected


def test_split_markers_survive_noise_and_overlapping_prefixes():
    decoder = StreamDecoder()
    assert decoder.feed(b"noise\x00ss") == []
    frame = incoming(b"stx", 0, 1, payload=struct.pack("<f", 7.0))
    assert decoder.feed(frame[1:]) == [Values(0, (7.0,))]
    assert decoder.discarded_bytes == 7


def test_raw_payload_is_never_scanned_for_embedded_markers():
    bits = b"stx!std?stv."
    floats = struct.unpack("<3f", bits)
    decoder = StreamDecoder()
    frame = incoming(b"stv", 1, 3, flag=0, payload=bits)
    assert decoder.feed(frame[:14]) == []
    assert decoder.feed(frame[14:]) == [ScopeSamples(0, floats)]


def test_scope_length_is_base100_not_little_endian_integer():
    values = tuple(float(index) for index in range(123))
    frame = incoming(b"stv", 4, 23, flag=1, payload=struct.pack("<123f", *values))
    assert StreamDecoder().feed(frame) == [ScopeSamples(3, values)]


def test_invalid_headers_resynchronize_and_noise_memory_is_bounded():
    valid = incoming(b"stx", 0, 1, payload=struct.pack("<f", 5))
    invalid_count = incoming(b"stx", 0, 101)
    invalid_flag = incoming(b"stx", 0, 1, flag=0)
    invalid_scope = incoming(b"stv", 0, 1, flag=0)
    oversized_scope = incoming(b"stv", 1, 0, flag=0, reserved=b"\x03\x00\x00")
    decoder = StreamDecoder()
    assert decoder.feed(invalid_count + invalid_flag + invalid_scope + oversized_scope + valid) == [Values(0, (5.0,))]
    assert decoder.malformed_frames == 4
    assert decoder.feed(b"garbage" * 100_000) == []
    assert decoder.buffered_bytes <= 2


def test_zero_length_messages_and_nonfinite_telemetry_are_preserved():
    decoder = StreamDecoder()
    assert decoder.feed(incoming(b"std", 0, 1, flag=0)) == [Description(0, 1, "")]
    assert decoder.feed(incoming(b"stv", 1, 0, flag=0)) == [ScopeSamples(0, ())]
    event = decoder.feed(incoming(b"stx", 1, 1, payload=struct.pack("<f", math.nan)))[0]
    assert math.isnan(event.values[0])
    decoder.feed(b"stx\x00\x01")
    decoder.reset()
    assert decoder.buffered_bytes == decoder.discarded_bytes == decoder.malformed_frames == 0
