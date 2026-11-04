"""Audit the Python control map against the preserved MATLAB source.

These tests recover addresses from independent original callbacks, rather than
repeating the Python catalog's generation rules.
"""
from pathlib import Path
import re

import pytest

from uart_gui.catalog import SECTIONS, START_COMMANDS, STOP_COMMANDS


LEGACY = Path(__file__).resolve().parents[1] / "legacy" / "matlab"
SOURCES = {
    "variables": "Plot_Generic.m",
    "parameters": "Par_Generic.m",
    "control": "Var_Generic.m",
    "observer": "OBS_Generic.m",
    "identification": "Ident_Generic.m",
    "others": "Others_Generic.m",
}


def _callbacks(source):
    """Read callback bodies without including adjacent function definitions."""
    for block in re.split(r"(?=^function )", source, flags=re.MULTILINE):
        if not block.startswith("function "):
            continue
        first_line, _, body = block.partition("\n")
        if "_Callback(" in first_line:
            # Ignore commented-out MATLAB statements.
            yield first_line, "\n".join(line.split("%", 1)[0] for line in body.splitlines())


def _individual_writes(source):
    writes = []
    for _, body in _callbacks(source):
        addresses = re.findall(r"TxUartCom\(val,\s*(\d+),\s*(\d+)\)", body)
        # ENTER ALL contains many writes; individual ENTER contains one.
        if len(addresses) == 1:
            writes.append(tuple(map(int, addresses[0])))
    return writes


def _plot_addresses(source):
    return [
        (int(row) - 1, int(column) - 1)
        for row, column in re.findall(
            r"Plot_Fill_UART\(handles\.radiobutton\d+\.Value,\s*(\d+),\s*(\d+)\)",
            source,
        )
    ]


@pytest.mark.parametrize("section", SECTIONS, ids=lambda section: section.key)
def test_section_matches_original_numeric_and_plot_callbacks(section):
    source = (LEGACY / SOURCES[section.key]).read_text(encoding="utf-8")
    writes = _individual_writes(source)
    plotted = _plot_addresses(source)
    assert [(field.row, field.column) for field in section.fields if field.editable] == writes
    assert [(field.row, field.column) for field in section.fields if field.plottable] == plotted
    # Dynamic description labels address exactly these fields as well.
    descriptions = {
        (int(row) - 1, int(column) - 1)
        for row, column in re.findall(r"Dvar\((\d+),\s*(\d+)\)", source)
    }
    assert {field.address for field in section.fields} == descriptions


def test_catalog_preserves_all_142_fields_and_66_plot_selectors():
    fields = [field for section in SECTIONS for field in section.fields]
    assert len(fields) == len({field.address for field in fields}) == 142
    assert sum(field.editable for field in fields) == 118
    assert sum(field.plottable for field in fields) == 66
    assert len(list(LEGACY.glob("*.m"))) == 12
    assert len(list(LEGACY.glob("*.fig"))) == 7


def test_start_and_stop_match_original_main_callbacks():
    source = (LEGACY / "INIT_Gui.m").read_text(encoding="utf-8")
    callbacks = dict(_callbacks(source))
    start_addresses = []
    stop_addresses = []
    for signature, body in callbacks.items():
        commands = [
            (float(value), int(row), int(column))
            for value, row, column in re.findall(
                r"TxUartCom\((\d+),\s*(\d+),\s*(\d+)\)", body
            )
        ]
        if any(f"pushbutton{index}_Callback" in signature for index in (4, 5, 6)):
            start_addresses.extend(commands)
        if "pushbutton7_Callback" in signature:
            stop_addresses.extend(commands)
    assert list(START_COMMANDS.values()) == start_addresses
    assert list(STOP_COMMANDS) == stop_addresses
