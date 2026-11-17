#!/usr/bin/env python3
"""Create or edit KFall normal-activity labels with PyQt6."""

import argparse
import os
from pathlib import Path
import sys

TOOL_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOL_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kfall_labeler.editor import AnnotationSource  # noqa: E402
from loaders.kfall_event_loader import DEFAULT_EXCLUDED_TASKS, TASK_CODES  # noqa: E402


def default_dataset_root():
    """Prefer the labeller's own dataset folder, then the repository's data folder."""
    for candidate in (TOOL_DIR / "dataset" / "KFall", REPO_ROOT / "data" / "KFall"):
        if (candidate / "sensor_data").is_dir():
            return candidate
    return TOOL_DIR / "dataset" / "KFall"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=None,
                        help="Default: kfall_labeler/dataset/KFall, then data/KFall.")
    parser.add_argument("--label-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "annotations" / "kfall_manual_labels.json")
    parser.add_argument("--exclude-tasks", nargs="*", type=str.upper, choices=TASK_CODES,
                        default=list(DEFAULT_EXCLUDED_TASKS))
    parser.add_argument("--post-impact-seconds", type=float, default=1.2)
    parser.add_argument("--fall-policy", choices=("pre_impact", "annotated_interval"), default="pre_impact")
    parser.add_argument("--save-frame", type=Path, help="Export an offscreen preview and exit.")
    args = parser.parse_args(argv)
    args.dataset_root = args.dataset_root or default_dataset_root()
    if args.save_frame:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PyQt6 import QtWidgets
        from kfall_labeler.gui import LabelWindow
    except ImportError as exc:
        parser.error(f"{exc}. Instala: python -m pip install -r kfall_labeler/requirements.txt")
    try:
        source = AnnotationSource(args.dataset_root, args.output, label_dir=args.label_dir,
                                  excluded_tasks=args.exclude_tasks,
                                  post_impact_seconds=args.post_impact_seconds, fall_policy=args.fall_policy)
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
        window = LabelWindow(source)
        window.show()
        if args.save_frame:
            args.save_frame.parent.mkdir(parents=True, exist_ok=True)
            app.processEvents()
            if window.current is None:
                parser.error("No se pudo cargar una grabacion para la vista previa.")
            if not window.grab().save(str(args.save_frame)):
                parser.error(f"No se pudo guardar la vista previa: {args.save_frame}")
            window.close()
            return
        app.exec()
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
