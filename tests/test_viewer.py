import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from uart_gui.model import import_recording
from uart_gui.viewer import RecordingViewer


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def recording_file(tmp_path):
    source = tmp_path / "signals.csv"
    source.write_text(
        "time_s,channel,row,column,label,value\n"
        "0,1,0,0,Speed,1\n0.1,1,0,0,Speed,3\n0.2,1,0,0,Speed,5\n"
        "0,2,0,1,Current,10\n0.1,2,0,1,Current,20\n0.2,2,0,1,Current,30\n",
        encoding="utf-8",
    )
    return source


def test_load_and_select_channels(qt_app, recording_file):
    viewer = RecordingViewer()
    viewer.load_file(recording_file)
    assert viewer.channels.count() == 2
    assert len(viewer.plot.listDataItems()) == 2
    viewer.channels.clearSelection()
    viewer.channels.item(1).setSelected(True)
    assert len(viewer.plot.listDataItems()) == 1
    np.testing.assert_allclose(viewer.plot.listDataItems()[0].yData, [10, 20, 30])
    viewer.close()


def test_smoothing_export_round_trip(qt_app, recording_file, tmp_path):
    viewer = RecordingViewer()
    viewer.load_file(recording_file)
    viewer.window_spin.setValue(2)
    viewer.channels.clearSelection()
    viewer.channels.item(0).setSelected(True)
    viewer.smooth_checkbox.setChecked(True)
    assert len(viewer.plot.listDataItems()) == 2
    target = tmp_path / "smoothed.csv"
    viewer.export_smoothed(target)
    result = import_recording(target)
    assert result.labels == ("Speed",)
    np.testing.assert_allclose(result.values[:, 0], [2, 4, 5])
    viewer.close()


def test_failed_load_preserves_recording(qt_app, recording_file, tmp_path):
    viewer = RecordingViewer()
    viewer.load_file(recording_file)
    original = viewer.recording
    with pytest.raises(ValueError):
        viewer.load_file(tmp_path / "unsupported.bin")
    assert viewer.recording is original
    viewer.close()
