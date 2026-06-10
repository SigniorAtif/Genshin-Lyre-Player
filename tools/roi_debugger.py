"""Standalone ROI overlay visualizer — shows only the key panel region.

Usage:
    python tools/roi_debugger.py --video path/to/video.mp4
    python tools/roi_debugger.py --video path/to/video.mp4 --config config/roi_profiles/lyre_1080p.json
    python tools/roi_debugger.py --video path/to/video.mp4 --frame 300
    python tools/roi_debugger.py --video path/to/video.mp4 --no-auto-detect

Controls (OpenCV window):
    Space / Right arrow — advance one frame
    Left arrow          — rewind one frame
    q / Escape          — quit

By default the debugger auto-detects the panel position in the current frame
(green boxes + yellow detected circles). Use --no-auto-detect to fall back to
the config file coordinates only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np

from vision_parser.config.schema import InstrumentConfig, ResolutionRef
from vision_parser.panel_detector import detect_panel
from vision_parser.roi_manager import ROIManager

_DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "roi_profiles" / "lyre_1080p.json"


def _build_roi_manager_from_detection(
    bgr: np.ndarray, cfg: InstrumentConfig
) -> tuple[ROIManager, bool]:
    """Try auto-detect; fall back to config if it fails.

    Returns (roi_manager, detected_flag).
    """
    h, w = bgr.shape[:2]
    panel_crop, roi_boxes = detect_panel(bgr)
    if panel_crop is not None:
        detected_cfg = InstrumentConfig(
            instrument=cfg.instrument,
            resolution=ResolutionRef(width=w, height=h),
            rois=roi_boxes,
            detection=cfg.detection,
            timing=cfg.timing,
            panel_crop=panel_crop,
        )
        return ROIManager(detected_cfg, w, h), True
    return ROIManager(cfg, w, h), False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize ROI bounding boxes cropped to the key panel."
    )
    parser.add_argument("--video", required=True, help="Path to input video.")
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_CONFIG),
        help="ROI profile JSON. Default: config/roi_profiles/lyre_1080p.json",
    )
    parser.add_argument("--frame", type=int, default=0, help="Starting frame index.")
    parser.add_argument(
        "--no-auto-detect",
        dest="auto_detect",
        action="store_false",
        default=True,
        help="Disable panel auto-detection; use config file coordinates as-is.",
    )
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"ERROR: Cannot open video '{args.video}'", file=sys.stderr)
        sys.exit(1)

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video: {w}×{h}, {total} frames")

    cfg = InstrumentConfig.from_json(args.config)
    print(f"Config: {args.config}")

    frame_idx = args.frame
    last_detection_frame = -1
    roi_manager: ROIManager | None = None
    detected = False

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, bgr = cap.read()
        if not ret:
            print(f"Cannot read frame {frame_idx}")
            frame_idx = max(0, frame_idx - 1)
            continue

        # Re-run detection when the frame changes (cheap enough per-frame).
        if args.auto_detect and frame_idx != last_detection_frame:
            roi_manager, detected = _build_roi_manager_from_detection(bgr, cfg)
            last_detection_frame = frame_idx
        elif roi_manager is None:
            roi_manager = ROIManager(cfg, w, h)
            detected = False

        # ── Build display: cropped to just the panel ──────────────────────
        display = roi_manager.debug_overlay_cropped(bgr)

        # Status line inside the cropped image
        status_color = (0, 255, 0) if detected else (0, 140, 255)
        detect_txt   = "AUTO-DETECTED" if detected else "CONFIG (no detection)"
        cv2.putText(
            display,
            f"Frame {frame_idx}/{total}   {detect_txt}",
            (4, 16),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_color, 1, cv2.LINE_AA,
        )
        cv2.putText(
            display,
            "[Space/-> next]  [<- prev]  [q quit]",
            (4, display.shape[0] - 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1, cv2.LINE_AA,
        )

        cv2.imshow("ROI Debugger — panel crop", display)

        key = cv2.waitKey(0) & 0xFF
        if key in (ord("q"), 27):
            break
        elif key in (ord(" "), 83, 0):   # Space / Right arrow
            frame_idx = min(frame_idx + 1, total - 1)
        elif key == 81:                  # Left arrow
            frame_idx = max(0, frame_idx - 1)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
