"""Editable native-frame annotations compatible with the KFall training loader."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone

import numpy as np

from labeling.kfall_manual_labels import load_manual_labels
from loaders.kfall_event_loader import (
    KFallEventLoaderConfig, window_activity_labels,
)
from preprocess.preprocess_kfall import FILE_RE, load_fall_labels, load_record
from kfall_labeler.tasks import TASK_DESCRIPTIONS

UCI_HAR_ACTIVITIES = {
    0: "WALKING", 1: "WALKING_UPSTAIRS", 2: "WALKING_DOWNSTAIRS",
    3: "SITTING", 4: "STANDING", 5: "LAYING",
}
ACTIVITIES = {**UCI_HAR_ACTIVITIES, 6: "ASCENDING_TRANSITION", 7: "DESCENDING_TRANSITION",
              8: "CROUCHING_BENT"}
DYNAMIC_ACTIVITIES = (0, 1, 2, 6, 7)
STATIC_ACTIVITIES = tuple(activity for activity in ACTIVITIES if activity not in DYNAMIC_ACTIVITIES)
# Editor-only codes avoid colliding with KFall's Fall/Dynamic/Static/PostImpact ids.
UCI_CODE_OFFSET = 10
UCI_CODES = tuple(UCI_CODE_OFFSET + activity for activity in UCI_HAR_ACTIVITIES)
ACTIVITY_CODES = tuple(UCI_CODE_OFFSET + activity for activity in ACTIVITIES)


def training_label(label):
    """Walking and posture transitions are Dynamic; postures are Static."""
    label = np.asarray(label)
    dynamic = np.isin(label, [UCI_CODE_OFFSET + activity for activity in DYNAMIC_ACTIVITIES])
    return np.where(label >= UCI_CODE_OFFSET, np.where(dynamic, 1, 2), label)


def signal_digest(signal, frames):
    digest = hashlib.sha256(np.asarray(frames, dtype="<i8").tobytes())
    digest.update(np.asarray(signal, dtype="<f4").tobytes())
    return digest.hexdigest()


def _intervals(frames, labels, allowed):
    """Keep gaps in FrameCounter out of the half-open annotation ranges."""
    starts = np.r_[0, np.flatnonzero((np.diff(labels) != 0) | (np.diff(frames) != 1)) + 1]
    stops = np.r_[starts[1:], len(frames)]
    return [[int(frames[start]), int(frames[stop - 1]) + 1, int(labels[start])]
            for start, stop in zip(starts, stops) if labels[start] in allowed]


def normal_intervals(frames, labels):
    return _intervals(frames, training_label(labels), (1, 2))


def activity_intervals(frames, labels):
    return [[start, stop, label - UCI_CODE_OFFSET]
            for start, stop, label in _intervals(frames, labels, ACTIVITY_CODES)]


class EditableRecording:
    def __init__(self, signal, frames, record, base, entry):
        self.signal, self.frames, self.record, self.base = signal, frames, record, base
        self.key = f"{record['subject']}{record['code']}{record['trial']}"
        self.protected = np.isin(base, (0, 3))
        self.labels = np.where(self.protected, base, -1)
        if entry is not None:
            if entry.get("file") != Path(record["file"]).name:
                raise ValueError(f"{self.key}: annotation filename differs from the CSV.")
            if entry.get("signal_sha256") not in (None, signal_digest(signal, frames)):
                raise ValueError(f"{self.key}: signal differs from the saved annotation.")
            for start, stop, label in entry["intervals"]:
                if start < frames[0] or stop > frames[-1] + 1:
                    raise ValueError(f"{self.key}: annotation outside the recording.")
                self.labels[(frames >= start) & (frames < stop) & ~self.protected] = label
            previous = 0
            for interval in entry.get("activity_intervals", []):
                if (not isinstance(interval, list) or len(interval) != 3
                        or any(type(value) is not int for value in interval)):
                    raise ValueError(f"{self.key}: actividad UCI HAR mal formada.")
                start, stop, activity = interval
                if (activity not in ACTIVITIES or start < previous or stop <= start
                        or start < frames[0] or stop > frames[-1] + 1):
                    raise ValueError(f"{self.key}: intervalos UCI HAR invalidos.")
                mask = (frames >= start) & (frames < stop) & ~self.protected
                code = UCI_CODE_OFFSET + activity
                if np.any(self.labels[mask] != training_label(code)):
                    raise ValueError(f"{self.key}: UCI HAR no coincide con Dynamic/Static guardado.")
                self.labels[mask] = code
                previous = stop
        self.saved_labels = self.labels.copy()
        self.history = []

    @property
    def times(self):
        return (self.frames - self.frames[0]) / 100

    @property
    def duration(self):
        return float((self.frames[-1] - self.frames[0] + 1) / 100)

    @property
    def dirty(self):
        return not np.array_equal(self.labels, self.saved_labels)

    @property
    def unassigned(self):
        return int(np.count_nonzero(self.labels == -1))

    @property
    def legacy(self):
        return int(np.count_nonzero(np.isin(self.labels, (1, 2))))

    @property
    def training_labels(self):
        return training_label(self.labels)

    def apply(self, start, stop, label):
        if (label not in (-1, *ACTIVITY_CODES) or not np.isfinite([start, stop]).all()
                or not 0 <= start < stop <= self.duration):
            raise ValueError("Selecciona un intervalo valido dentro de la grabacion.")
        mask = (self.times >= start - 1e-9) & (self.times < stop - 1e-9) & ~self.protected
        if not np.any(mask):
            raise ValueError("La seleccion no contiene muestras editables.")
        if np.any(self.labels[mask] != label):
            self.history.append(self.labels.copy())
            self.labels[mask] = label

    def undo(self):
        if self.history:
            self.labels = self.history.pop()


class AnnotationSource:
    def __init__(self, dataset_root, output, *, label_dir=None, excluded_tasks=(),
                 post_impact_seconds=1.2, fall_policy="pre_impact"):
        root = Path(dataset_root).expanduser().resolve()
        sensor_root = root / "sensor_data" if (root / "sensor_data").is_dir() else root
        if not sensor_root.is_dir():
            raise FileNotFoundError(f"No existe el dataset: {sensor_root}")
        self.config = KFallEventLoaderConfig(post_impact_seconds=post_impact_seconds, fall_policy=fall_policy)
        self.output = Path(output).expanduser().resolve()
        fallback = self.output.with_name(self.output.name + ".bak")
        self.loaded_path = self.output if self.output.exists() else fallback if fallback.exists() else None
        self.loaded_content = None
        self.document = {
            "format": "kfall_manual_normal_labels", "version": 1, "dataset": "kfall",
            "sample_rate_hz": 100, "post_impact_seconds": post_impact_seconds,
            "fall_policy": fall_policy, "recordings": {},
        }
        if self.loaded_path is not None:
            load_manual_labels(self.loaded_path)
            self.loaded_content = self.loaded_path.read_bytes()
            self.document = json.loads(self.loaded_content)
            if (self.document.get("post_impact_seconds", post_impact_seconds) != post_impact_seconds
                    or self.document.get("fall_policy", fall_policy) != fall_policy):
                raise ValueError("Las fases de caida/postimpacto difieren del archivo de etiquetas.")
        self.catalog = []
        seen = set()
        for path in sorted(sensor_root.rglob("*")):
            if not path.is_file():
                continue
            match = FILE_RE.fullmatch(path.name)
            if match is None:
                continue
            subject, task, trial = match.groups()
            code = f"T{task}"
            key = f"SA{subject}{code}R{trial}"
            if key in seen:
                raise ValueError(f"Grabacion duplicada: {key}")
            seen.add(key)
            if code not in excluded_tasks:
                self.catalog.append({"key": key, "subject": f"SA{subject}", "code": code,
                                     "trial": f"R{trial}", "file": path,
                                     "description": TASK_DESCRIPTIONS[code]})
        if not self.catalog:
            raise ValueError("No hay grabaciones con las exclusiones seleccionadas.")
        if label_dir is None:
            label_dir = root / "label_data" if (root / "label_data").is_dir() else root.parent / "label_data"
        self.fall_labels = load_fall_labels(label_dir) if any(
            20 <= int(row["code"][1:]) <= 34 for row in self.catalog) else {}

    def status(self, row):
        entry = self.document["recordings"].get(row["key"])
        if entry is None:
            return "pending"
        return "uci" if entry.get("label_scheme") in ("uci_har", "uci_har_extended") else "legacy"

    def reviewed(self, row):
        return self.status(row) == "uci"

    def filtered(self, subject="", pending=False):
        return [row for row in self.catalog if (not subject or row["subject"] == subject)
                and (not pending or not self.reviewed(row))]

    def load(self, row):
        signal, frames, record = load_record(row["file"])
        if record["label_id"] == 0:
            identity = (record["subject"], record["task_id"], record["trial_id"])
            if identity not in self.fall_labels:
                raise ValueError(f"{row['key']}: faltan anotaciones oficiales de caida.")
            onset, impact = self.fall_labels[identity]
            if not np.isin([onset, impact], frames).all():
                raise ValueError(f"{row['key']}: onset/impact ausentes en FrameCounter.")
            record.update(fall_onset_frame=onset, fall_impact_frame=impact)
        base = window_activity_labels(frames, record, self.config)
        return EditableRecording(signal, frames, record, base, self.document["recordings"].get(row["key"]))

    def save(self, item):
        if self.loaded_path is not None and self.loaded_path.read_bytes() != self.loaded_content:
            raise ValueError("El archivo cambio fuera del editor. Reabre la GUI antes de guardar.")
        if self.loaded_path != self.output and self.output.exists():
            raise ValueError("Otro editor creo el archivo de destino. Reabre la GUI.")
        intervals = normal_intervals(item.frames, item.labels)
        if not intervals and np.any(~item.protected):
            raise ValueError("Asigna al menos un intervalo normal antes de marcar como revisada.")
        protected = np.where(item.protected, item.base, -1).astype("i1")
        digest = hashlib.sha256(np.asarray(item.frames, dtype="<i8").tobytes())
        digest.update(protected.tobytes())
        document = {**self.document, "recordings": dict(self.document["recordings"]),
                    "activity_label_scheme": "uci_har_extended",
                    "activity_labels": {str(k): v for k, v in ACTIVITIES.items()},
                    "activity_to_training": {"Dynamic": list(DYNAMIC_ACTIVITIES),
                                             "Static": list(STATIC_ACTIVITIES)}}
        extended = [UCI_CODE_OFFSET + activity for activity in ACTIVITIES if activity not in UCI_HAR_ACTIVITIES]
        scheme = "uci_har_extended" if np.any(np.isin(item.labels, extended)) else "uci_har"
        document["recordings"][item.key] = {
            "file": Path(item.record["file"]).name, "reviewed": True, "intervals": intervals,
            "activity_intervals": activity_intervals(item.frames, item.labels),
            "label_scheme": scheme if item.legacy == 0 else "mixed_legacy",
            "signal_sha256": signal_digest(item.signal, item.frames),
            "protected_sha256": digest.hexdigest(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        content = (json.dumps(document, indent=2, allow_nan=False) + "\n").encode()
        self.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.output.parent, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            load_manual_labels(temporary)
            if self.output.exists():
                shutil.copy2(self.output, self.output.with_name(self.output.name + ".previous"))
            os.replace(temporary, self.output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        self.document, self.loaded_path, self.loaded_content = document, self.output, content
        item.saved_labels = item.labels.copy()
