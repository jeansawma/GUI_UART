"""Control addresses recovered from the supplied MATLAB GUIDE callbacks.

Addresses here are zero-based on the wire. MATLAB ``var``/``Dvar`` indices
were one-based. The .fig captions were all the placeholder ``Rs``: firmware
``std`` description messages supply the meaningful labels at runtime.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    row: int
    column: int
    label: str
    editable: bool = True
    plottable: bool = False

    @property
    def address(self) -> tuple[int, int]:
        return self.row, self.column

    @property
    def col(self) -> int:
        """Convenience alias for callers displaying wire addresses."""
        return self.column


@dataclass(frozen=True)
class SectionSpec:
    key: str
    title: str
    fields: tuple[FieldSpec, ...]


def _fields(
    blocks: tuple[tuple[int, int], ...],
    name: str,
    *,
    editable: bool = True,
    plottable: bool = False,
) -> tuple[FieldSpec, ...]:
    addresses = [(row, col) for row, count in blocks for col in range(count)]
    return tuple(
        FieldSpec(row, col, f"{name} {index:02d}", editable, plottable)
        for index, (row, col) in enumerate(addresses, start=1)
    )


SECTIONS: tuple[SectionSpec, ...] = (
    SectionSpec(
        "variables", "Variables",
        _fields(((0, 24),), "Variable", editable=False, plottable=True),
    ),
    SectionSpec(
        "parameters", "Parameters",
        _fields(((6, 18),), "Parameter"),
    ),
    SectionSpec(
        "control", "Control",
        _fields(((7, 10), (8, 10), (9, 4)), "Control", plottable=True),
    ),
    SectionSpec(
        "observer", "Observer",
        _fields(((10, 18),), "Observer"),
    ),
    SectionSpec(
        "identification", "Identification",
        _fields(((11, 10), (12, 8)), "Identification", plottable=True),
    ),
    SectionSpec(
        "others", "Others",
        _fields(((2, 20), (3, 20)), "Other"),
    ),
)
SECTION_BY_KEY = {section.key: section for section in SECTIONS}
FIELD_BY_ADDRESS = {field.address: field for section in SECTIONS for field in section.fields}

# INIT_Gui.m, pushbutton4/5/6/7 callbacks. Tuple order: value, row, column.
START_COMMANDS = {
    "Start W": (1.0, 2, 0),
    "Start I": (1.0, 2, 1),
    "Start Ident": (1.0, 2, 2),
}
STOP_COMMANDS = ((0.0, 2, 0), (0.0, 2, 1), (0.0, 2, 2))
PLOT_CAPACITY = 15
