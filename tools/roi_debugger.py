"""Standalone ROI overlay visualizer for calibrating bounding boxes.

Usage:
    python tools/roi_debugger.py --video path/to/video.mp4
    python tools/roi_debugger.py --video path/to/video.mp4 --config config/roi_profiles/lyre_1080p.json
    python tools/roi_debugger.py --video path/to/video.mp4 --frame 300

Controls (OpenCV window):
    Space / Right arrow — advance one frame
    Left arrow          — rewind one frame (seeks to frame-1, may be slow on some codecs)
    q / Escape          — quit

The window shows the video frame with green ROI rectangles and key labels overlaid.
Use this to verify the config boxes align with the actual instrument keys before running
the full pipeline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from project root: python tools/roi_debugger.py
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2

from vision_parser.config.schema import InstrumentConfig
from vision_parser.roi_manager import ROIManager

_DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "roi_profiles" / "lyre_1080p.json"


def main() -> None:
    """Entry point for the ROI debugger."""
    parser = argparse.ArgumentParser(description="Visualize ROI bounding boxes on a video frame.")
    parser.add_argument("--video", required=True, help="Path to input video.")
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_CONFIG),
        help="ROI profile JSON. Default: config/roi_profiles/lyre_1080p.json",
    )
    parser.add_argument(
        "--frame",
        type=int,
        default=0,
        help="Starting frame index. Default: 0.",
    )
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"ERROR: Cannot open video '{args.video}'", file=sys.stderr)
        sys.exit(1)

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video: {w}x{h}, {total} frames")

    cfg = InstrumentConfig.from_json(args.config)
    roi_manager = ROIManager(cfg, w, h)
    print(f"Loaded {len(roi_manager.roi_boxes)} ROIs from '{args.config}'")

    frame_idx = args.frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, bgr = cap.read()
        if not ret:
            print(f"End of video at frame {frame_idx}")
            frame_idx = max(0, frame_idx - 1)
            continue

        overlay = roi_manager.debug_overlay(bgr)
        cv2.putText(
            overlay,
            f"Frame {frame_idx}/{total}  [Space/→ next] [← prev] [q quit]",
            (10, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 0),
            1,
            cv2.LINE_AA,
        )
        cv2.imshow("ROI Debugger", overlay)

        key = cv2.waitKey(0) & 0xFF
        if key in (ord("q"), 27):  # q or Escape
            break
        elif key in (ord(" "), 83, 0):  # Space, Right arrow
            frame_idx = min(frame_idx + 1, total - 1)
        elif key == 81:  # Left arrow
            frame_idx = max(0, frame_idx - 1)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
