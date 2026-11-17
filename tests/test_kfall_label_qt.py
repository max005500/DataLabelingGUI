"""Offscreen interaction tests for the PyQt6 annotation editor."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from PyQt6 import QtCore, QtGui, QtTest, QtWidgets
    import pyqtgraph as pg
except ImportError:
    QtWidgets = None

from test_kfall_label_editor import editor_fixture


@unittest.skipIf(QtWidgets is None, "Install kfall_labeler/requirements.txt for PyQt6 tests.")
class LabelQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from kfall_labeler.gui import LabelWindow
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.source = editor_fixture(Path(temporary.name))
        self.window = LabelWindow(self.source)
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.close_window)

    def close_window(self):
        with patch.object(self.window, "confirm_leave", return_value=True):
            self.window.close()

    def test_select_paint_undo_save_and_pending_filter(self):
        window = self.window
        window.select(0, window.current.duration)
        window.apply(14)
        self.assertTrue(window.current.dirty)
        window.undo()
        self.assertTrue(np.all(window.current.labels == -1))
        window.apply(10)
        window.save_button.click()
        self.assertFalse(window.current.dirty)
        self.assertTrue(self.source.output.exists())
        window.state_filter.setCurrentIndex(1)
        self.assertEqual(window.files.count(), 3)
        window.subject.setCurrentIndex(window.subject.findData("SA07"))
        self.assertEqual(window.files.count(), 1)
        self.assertEqual(window.current.record["subject"], "SA07")

    def test_activity_title_tracks_selection_and_reference_button_opens_kfall(self):
        from kfall_labeler.gui import KFALL_REFERENCE_URL, KFALL_TASK_REFERENCE_VIDEOS

        window = self.window
        window.select(0, 0.02)
        window.apply(10)
        self.assertEqual(window.activity_title.text(), "Caminando")

        window.select(0.03, 0.05)
        self.assertEqual(window.activity_title.text(), "Sin etiqueta")

        with patch("kfall_labeler.gui.QtGui.QDesktopServices.openUrl", return_value=True) as open_url:
            window.reference_button.click()
        open_url.assert_called_once_with(QtCore.QUrl(KFALL_TASK_REFERENCE_VIDEOS[1]))

        with patch.object(window, "confirm_leave", return_value=True):
            window.files.setCurrentRow(1)
        with patch("kfall_labeler.gui.QtGui.QDesktopServices.openUrl", return_value=True) as open_url:
            window.reference_button.click()
        open_url.assert_called_once_with(QtCore.QUrl(KFALL_TASK_REFERENCE_VIDEOS[15]))
        with patch.dict(window.current.record, task_id=3), patch(
                "kfall_labeler.gui.QtGui.QDesktopServices.openUrl", return_value=True) as open_url:
            window.reference_button.click()
        open_url.assert_called_once_with(QtCore.QUrl(KFALL_REFERENCE_URL))

    def test_task_descriptions_follow_navigation(self):
        window = self.window
        self.assertIn("Permanecer de pie", window.files.item(0).text())
        self.assertIn("Permanecer de pie", window.task_description.text())
        window.files.setCurrentRow(1)
        self.assertIn("T15", window.task_description.text())
        self.assertIn("desplomarse sobre la silla", window.task_description.text())
        self.assertIn("desplomarse sobre la silla", window.files.item(1).toolTip())

    def test_cli_shows_all_tasks_by_default(self):
        from kfall_labeler.editor import AnnotationSource
        from kfall_labeler.label_kfall_manual import main

        with patch("kfall_labeler.label_kfall_manual.AnnotationSource", wraps=AnnotationSource) as source:
            main(["--dataset-root", str(self.source.catalog[0]["file"].parents[2]),
                  "--output", str(self.source.output),
                  "--save-frame", str(self.source.output.with_suffix(".png"))])
        self.assertEqual(source.call_args.kwargs["excluded_tasks"], [])
        self.assertTrue(self.source.output.with_suffix(".png").is_file())

    def test_spanish_activity_buttons_and_new_shortcuts(self):
        window = self.window
        names = ("Caminando", "Subiendo escaleras", "Bajando escaleras",
                 "Sentado", "De pie", "Acostado", "Subiendo", "Bajando")
        for number, name in enumerate(names, start=1):
            self.assertEqual(window.activity_buttons[number + 9].text(), f"{number}   {name}")
        window.select(0, window.current.duration)
        window.activateWindow()
        window.setFocus()
        self.app.processEvents()
        for key, code, name in ((QtCore.Qt.Key.Key_7, 16, "Subiendo"),
                                (QtCore.Qt.Key.Key_8, 17, "Bajando")):
            QtTest.QTest.keyClick(window, key)
            self.assertTrue(np.all(window.current.labels == code))
            self.assertEqual(window.activity_title.text(), name)
        window.undo()
        self.assertTrue(np.all(window.current.labels == 16))

    def test_cancel_navigation_and_partial_save_protect_changes(self):
        window = self.window
        window.select(0, 0.02)
        window.apply(10)
        key = window.current.key
        with patch.object(QtWidgets.QMessageBox, "question",
                          return_value=QtWidgets.QMessageBox.StandardButton.Cancel):
            window.files.setCurrentRow(1)
        self.assertEqual(window.current.key, key)
        self.assertEqual(window.files.currentRow(), 0)
        with patch.object(QtWidgets.QMessageBox, "question",
                          return_value=QtWidgets.QMessageBox.StandardButton.No):
            self.assertFalse(window.save())
        self.assertFalse(self.source.output.exists())
        with patch.object(QtWidgets.QMessageBox, "question",
                          return_value=QtWidgets.QMessageBox.StandardButton.Cancel):
            window.subject.setCurrentIndex(window.subject.findData("SA07"))
        self.assertEqual(window.subject.currentData(), "")
        self.assertEqual(window.current.key, key)

    def drag(self, plot_index, start, stop, y=0.5):
        plot = self.window.plots[plot_index]
        view = plot.getViewBox()
        viewport = self.window.graphics.viewport()
        low, high = view.viewRange()[1]
        value = low + (high - low) * y

        def point(time):
            scene = view.mapViewToScene(QtCore.QPointF(time, value))
            return self.window.graphics.mapFromScene(scene)

        origin, destination = point(start), point(stop)
        QtTest.QTest.mouseMove(viewport, origin)
        QtTest.QTest.qWait(25)
        QtTest.QTest.mousePress(viewport, QtCore.Qt.MouseButton.LeftButton, pos=origin)
        for step in range(1, 6):
            position = origin + (destination - origin) * (step / 5)
            event = QtGui.QMouseEvent(
                QtCore.QEvent.Type.MouseMove, QtCore.QPointF(position),
                QtCore.QPointF(viewport.mapToGlobal(position)),
                QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.LeftButton,
                QtCore.Qt.KeyboardModifier.NoModifier)
            QtWidgets.QApplication.sendEvent(viewport, event)
            QtTest.QTest.qWait(25)
        QtTest.QTest.mouseRelease(viewport, QtCore.Qt.MouseButton.LeftButton, pos=destination)
        self.app.processEvents()

    def test_mouse_drag_selection_survives_redraw_and_empty_filter(self):
        window = self.window
        window.select(0.10, 0.15)
        for start, stop, label in ((0.01, 0.05, 10), (0.03, 0.07, 14)):
            self.app.processEvents()
            window.select(0.10, 0.15)
            self.drag(0, start, stop)
            np.testing.assert_allclose(window.selection, (start, stop), atol=0.01)
            window.apply(label)
        self.assertEqual(window.current.labels[1], 10)
        self.assertEqual(window.current.labels[3], 14)
        window.select(0, window.current.duration)
        window.apply(14)
        window.save()
        window.subject.setCurrentIndex(window.subject.findData("SA07"))
        window.select(0, window.current.duration)
        window.apply(10)
        window.save()
        window.state_filter.setCurrentIndex(1)
        self.assertEqual(window.files.count(), 0)
        self.assertIsNone(window.current)
        self.assertEqual(window.task_description.text(), "")
        window.start.setValue(0.01)

    def test_sensor_switch_uses_xyz_channels_and_preserves_view_and_labels(self):
        window = self.window
        window.select(0.01, 0.05)
        window.apply(10)
        labels = window.current.labels.copy()
        window.focus_selection()
        view = window.plots[0].viewRange()[0]
        for first in (3, 0):
            window.sensor.setCurrentIndex(window.sensor.findData(first))
            self.app.processEvents()
            for channel, curve in enumerate(window.curves):
                times, values = curve.getData()
                np.testing.assert_array_equal(times, window.current.times)
                np.testing.assert_array_equal(values, window.current.signal[:, first + channel])
            self.assertEqual(window.selection, (0.01, 0.05))
            np.testing.assert_array_equal(window.current.labels, labels)
            np.testing.assert_allclose(window.plots[0].viewRange()[0], view)
        self.assertEqual(len(window.curves), 3)
        self.assertEqual(len(window.plots), 4)

    def test_drag_move_resize_and_numeric_controls_synchronize_all_regions(self):
        window = self.window
        window.select(0.02, 0.08)
        self.drag(1, 0.05, 0.10)
        np.testing.assert_allclose(window.selection, (0.07, 0.13), atol=0.01)
        width = window.selection[1] - window.selection[0]
        self.assertAlmostEqual(width, 0.06, places=2)
        left, right = window.selection
        self.drag(2, right, right + 0.03)
        self.assertAlmostEqual(window.selection[0], left, places=2)
        self.assertAlmostEqual(window.selection[1], right + 0.03, places=2)
        self.app.processEvents()
        for region in window.regions:
            np.testing.assert_allclose(region.getRegion(), window.selection)
        self.assertAlmostEqual(window.start.value(), window.selection[0], places=2)
        self.assertAlmostEqual(window.stop.value(), window.selection[1], places=2)
        window.start.setValue(0.03)
        window.stop.setValue(0.18)
        self.assertFalse(window.current.dirty)
        for region in window.regions:
            np.testing.assert_allclose(region.getRegion(), (0.03, 0.18))
        window.apply(14)
        for region in window.regions:
            np.testing.assert_allclose(region.getRegion(), (0.03, 0.18))


if __name__ == "__main__":
    unittest.main()
