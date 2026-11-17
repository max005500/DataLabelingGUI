"""Annotation editing, protected phases and training-format round trips."""

import csv
import json
from pathlib import Path
import tempfile
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from openpyxl import Workbook

from kfall_labeler.editor import AnnotationSource, normal_intervals
from labeling.kfall_manual_labels import load_manual_labels
from loaders.kfall_event_loader import window_activity_labels
from preprocess.preprocess_kfall import CHANNELS


def editor_fixture(root):
    sensors = root / "sensor_data" / "SA06"
    sensors.mkdir(parents=True)
    for subject, task in (("06", "01"), ("06", "15"), ("06", "20"), ("07", "01")):
        folder = sensors.parent / f"SA{subject}"
        folder.mkdir(exist_ok=True)
        with (folder / f"S{subject}T{task}R01.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["TimeStamp(s)", "FrameCounter", *CHANNELS])
            for frame in range(101, 121):
                writer.writerow([frame / 100, frame, *[frame / 100 * (channel + 1) for channel in range(6)]])
    labels = root / "label_data"
    labels.mkdir()
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Task Code (Task ID)", "Trial ID", "Fall_onset_frame", "Fall_impact_frame"])
    sheet.append(["F01 (20)", 1, 106, 110])
    workbook.save(labels / "SA06_label.xlsx")
    workbook.close()
    return AnnotationSource(root, root / "annotations.json", post_impact_seconds=0.05)


class LabelEditorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = editor_fixture(self.root)

    def test_default_catalog_includes_previously_excluded_tasks_with_descriptions(self):
        template = self.source.catalog[0]["file"]
        excluded_before = ("T05", "T13", "T14", "T15", "T16", "T18", "T19")
        for code in excluded_before:
            path = template.parent / f"S06{code}R01.csv"
            path.write_bytes(template.read_bytes())
        source = AnnotationSource(self.root, self.source.output, post_impact_seconds=0.05)
        rows = {row["code"]: row for row in source.filtered("SA06")}
        self.assertTrue(set(excluded_before).issubset(rows))
        self.assertIn("suelo", rows["T05"]["description"])
        self.assertIn("silla", rows["T13"]["description"])
        self.assertIn("sofá", rows["T16"]["description"])
        self.assertIn("cama", rows["T18"]["description"])
        for code in excluded_before:
            item = source.load(rows[code])
            self.assertEqual(item.record["code"], code)
        filtered = AnnotationSource(self.root, self.source.output, excluded_tasks=excluded_before,
                                    post_impact_seconds=0.05)
        self.assertTrue(all(row["code"] not in excluded_before for row in filtered.catalog))

    def test_native_frames_protection_undo_and_training_roundtrip(self):
        row = next(row for row in self.source.catalog if row["code"] == "T20")
        item = self.source.load(row)
        original = item.labels.copy()
        item.apply(0, item.duration, 10)
        np.testing.assert_array_equal(item.labels[item.protected], item.base[item.protected])
        item.apply(0, 0.02, 13)
        item.undo()
        self.assertTrue(np.all(item.labels[~item.protected] == 10))
        item.undo()
        np.testing.assert_array_equal(item.labels, original)
        self.assertFalse(item.dirty)
        item.apply(0, item.duration, 13)
        self.source.save(item)
        records, _ = load_manual_labels(self.source.output)
        self.assertEqual(records[item.key]["intervals"], [[101, 106, 2], [115, 121, 2]])
        saved = json.loads(self.source.output.read_text())["recordings"][item.key]
        self.assertEqual(saved["activity_intervals"], [[101, 106, 3], [115, 121, 3]])
        self.assertEqual(saved["label_scheme"], "uci_har")
        metadata = {**item.record, "manual_intervals": records[item.key]["intervals"]}
        np.testing.assert_array_equal(window_activity_labels(item.frames, metadata, self.source.config),
                                      item.training_labels)
        np.testing.assert_array_equal(self.source.load(row).labels, item.labels)
        self.assertFalse(item.dirty)

    def test_partial_clear_and_frame_gaps_remain_unlabelled(self):
        item = self.source.load(self.source.catalog[0])
        item.apply(0.01, 0.04, 10)
        item.apply(0.02, 0.03, -1)
        self.assertEqual(normal_intervals(item.frames, item.labels), [[102, 103, 1], [104, 105, 1]])
        self.assertEqual(normal_intervals(np.array([1, 2, 5]), np.array([1, 1, 1])),
                         [[1, 3, 1], [5, 6, 1]])
        with self.assertRaises(ValueError):
            item.apply(float("nan"), 0.1, 10)
        with self.assertRaises(ValueError):
            item.apply(0, 0.1, 1)
        with self.assertRaises(ValueError):
            item.apply(0.1, 0.1, 10)

    def test_ascending_descending_roundtrip_and_dynamic_training(self):
        row = next(row for row in self.source.catalog if row["code"] == "T20")
        item = self.source.load(row)
        item.apply(0, item.duration, 16)
        item.apply(0.14, item.duration, 17)
        np.testing.assert_array_equal(item.labels[item.protected], item.base[item.protected])
        self.source.save(item)
        document = json.loads(self.source.output.read_text())
        self.assertEqual(document["recordings"][item.key]["activity_intervals"],
                         [[101, 106, 6], [115, 121, 7]])
        self.assertEqual(document["activity_to_training"]["Dynamic"], [0, 1, 2, 6, 7])
        records, _ = load_manual_labels(self.source.output)
        metadata = {**item.record, "manual_intervals": records[item.key]["intervals"]}
        np.testing.assert_array_equal(window_activity_labels(item.frames, metadata, self.source.config),
                                      item.training_labels)
        self.assertTrue(np.all(item.training_labels[~item.protected] == 1))
        reopened = AnnotationSource(self.root, self.source.output, post_impact_seconds=0.05)
        np.testing.assert_array_equal(reopened.load(row).labels, item.labels)
        self.assertTrue(reopened.reviewed(row))
        self.assertNotIn(row, reopened.filtered(pending=True))

    def test_legacy_dynamic_static_entries_stay_pending_until_relabelled(self):
        item = self.source.load(self.source.catalog[0])
        item.apply(0, item.duration, 11)
        self.source.save(item)
        document = json.loads(self.source.output.read_text())
        entry = document["recordings"][item.key]
        del entry["activity_intervals"], entry["label_scheme"]
        self.source.output.write_text(json.dumps(document))
        source = AnnotationSource(self.root, self.source.output, post_impact_seconds=0.05)
        legacy = source.load(source.catalog[0])
        self.assertEqual(source.status(source.catalog[0]), "legacy")
        self.assertIn(source.catalog[0], source.filtered(pending=True))
        self.assertTrue(np.all(legacy.labels == 1))
        self.assertEqual(legacy.legacy, len(legacy.labels))

    def test_filters_exclusions_backup_import_and_concurrent_save(self):
        item = self.source.load(self.source.catalog[0])
        item.apply(0, item.duration, 10)
        self.source.save(item)
        backup = self.source.output.with_name("annotations.json.bak")
        self.source.output.rename(backup)
        original = backup.read_bytes()
        source = AnnotationSource(self.root, self.source.output, excluded_tasks=("T15",),
                                  post_impact_seconds=0.05)
        self.assertTrue(all(row["code"] != "T15" for row in source.catalog))
        self.assertEqual(len(source.filtered("SA07", True)), 1)
        self.assertEqual(len(source.filtered("SA06", True)), 1)
        row = source.catalog[0]
        item = source.load(row)
        item.apply(0, item.duration, 13)
        source.save(item)
        self.assertEqual(backup.read_bytes(), original)
        self.assertTrue(source.output.exists())
        item.apply(0, 0.01, 10)
        source.save(item)
        self.assertTrue(source.output.with_name("annotations.json.previous").exists())
        source.output.write_text(source.output.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "fuera del editor"):
            source.save(item)

    def test_protected_only_selection_and_empty_review_are_rejected(self):
        row = next(row for row in self.source.catalog if row["code"] == "T20")
        with self.assertRaisesRegex(ValueError, "editables"):
            self.source.load(row).apply(0.05, 0.09, 13)
        with self.assertRaisesRegex(ValueError, "al menos"):
            self.source.save(self.source.load(self.source.catalog[0]))


if __name__ == "__main__":
    unittest.main()
