"""Native interactions with the initially empty, collapsible Library surface."""

from PySide6.QtWidgets import QApplication, QLabel
import pytest

from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import resize_workspace, wait_until


def test_library_toggle_preserves_workspace_and_recording(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    assert not window.library.toggle_button.isChecked()
    assert not window.library.panel.isVisible()
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    window.navigation.position.setValue(4000)
    window.inspector.first.setValue(3000)
    window.inspector.last.setValue(6000)
    window.plot.axis_x.setRange(60, 100)
    QApplication.processEvents()
    data = window.data
    minimum = window.minimumSizeHint()
    workspace_width = window.workspace.width()
    size = window.size()

    for language, caption in ((0, "Library"), (1, "Bibliothek"), (2, "Bibliothèque")):
        window.set_ui_language(language)
        QApplication.processEvents()
        window.library.toggle_button.click()
        QApplication.processEvents()
        assert window.library.panel.isVisible()
        assert window.library.toggle_button.text() == caption
        assert window.library.toggle_button.accessibleName() == caption
        assert window.library.toggle_button.toolTip() == caption
        assert window.library.panel.findChildren(QLabel)[0].text() == caption
        assert window.workspace.width() < workspace_width
        assert window.size() == size
        width = window.library.panel.width()
        window.library.setSizes([width + 40, window.workspace.width() - 40])
        QApplication.processEvents()
        assert window.library.panel.width() > width
        window.library.toggle_button.click()
        QApplication.processEvents()
        assert not window.library.panel.isVisible()
        assert window.workspace.width() == workspace_width
        assert window.data is data
        assert window.navigation.position.value() == 4000
        assert (window.inspector.first.value(), window.inspector.last.value()) == (3000, 6000)
        assert window.plot.axis_x.min() == pytest.approx(60)
        assert window.plot.axis_x.max() == pytest.approx(100)

    window.set_ui_language(0)
    QApplication.processEvents()
    assert window.minimumSizeHint() == minimum
    resize_workspace(window, 720, 480)
    compact_size = window.size()
    for _ in range(2):
        window.library.toggle_button.click()
        QApplication.processEvents()
        assert window.library.panel.isVisible() == window.library.toggle_button.isChecked()
        assert window.size() == compact_size
