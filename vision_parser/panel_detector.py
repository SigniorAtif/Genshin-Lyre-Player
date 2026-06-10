"""Auto-detects the Genshin Lyre instrument panel in a video frame.

Finds the 21 key buttons (white circles in a 3×7 grid) using Hough circle
detection, then returns:
  - a PanelCrop that tightly wraps the detected grid (full-frame coordinates)
  - a list of ROIBox entries with coordinates relative to that crop

This makes the pipeline position-invariant across any recording resolution,
window size, or UI-scale setting without touching any detection thresholds.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from vision_parser.config.schema import PanelCrop, ROIBox

logger = logging.getLogger(__name__)

# Key assignment: row 0 = top (highest pitch), row 2 = bottom (lowest pitch).
# Within each row: left → right = ascending pitch.
_KEY_GRID: list[list[str]] = [
    ["Q", "W", "E", "R", "T", "Y", "U"],
    ["A", "S", "D", "F", "G", "H", "J"],
    ["Z", "X", "C", "V", "B", "N", "M"],
]

# Accept a detection with at least this many circles before grid-fitting.
_MIN_CIRCLES_FOR_FIT = 15
# ROI box half-side as a fraction of the detected median circle radius.
# 1.0 = box spans the full circle diameter; keep ≤ 1.0 to stay inside each key.
_ROI_RADIUS_FRACTION = 0.85


def detect_panel(
    bgr: np.ndarray,
) -> tuple[PanelCrop, list[ROIBox]] | tuple[None, None]:
    """Locate the Lyre panel in a full BGR video frame.

    Tries several HoughCircles sensitivity levels so it copes with varying
    video brightness/contrast. Stops at the first parameter set that yields a
    plausible 3×7 grid.

    Args:
        bgr: Full-resolution BGR frame from the video.

    Returns:
        ``(panel_crop, roi_boxes)`` on success — panel_crop in full-frame pixel
        space, roi_boxes relative to panel_crop origin.
        ``(None, None)`` if no valid Lyre grid was found.
    """
    h, w = bgr.shape[:2]

    # Key-button radius scales roughly with frame height.
    # At 1080p buttons are ~26 px radius; at 480p ~14 px.  Both ≈ 2-3 % of h.
    min_r = max(5, int(h * 0.018))
    max_r = max(min_r + 4, int(h * 0.042))

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    # Light blur smooths H.264 block noise while preserving circle edges.
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)

    # Try a range of accumulator thresholds (lower = more sensitive = more noise).
    for param2 in (22, 16, 30, 11):
        raw = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=int(min_r * 2.0),   # must be < actual key spacing
            param1=60,
            param2=param2,
            minRadius=min_r,
            maxRadius=max_r,
        )
        if raw is None:
            continue

        circles = np.round(raw[0]).astype(int)   # (N, 3): cx, cy, r
        logger.debug(
            "HoughCircles param2=%d → %d circles (r=[%d,%d] px)",
            param2, len(circles), min_r, max_r,
        )

        # Lyre panel is always in the lower ~70 % of the frame.
        circles = circles[circles[:, 1] > int(h * 0.30)]
        if len(circles) < _MIN_CIRCLES_FOR_FIT:
            continue

        result = _fit_grid(circles, w, h)
        if result[0] is not None:
            return result

    logger.debug("detect_panel: no valid 3×7 grid found")
    return None, None


# ──────────────────────────────────────────────────────────────────────────────
# Internal grid-fitting helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fit_grid(
    circles: np.ndarray,
    frame_w: int,
    frame_h: int,
) -> tuple[PanelCrop, list[ROIBox]] | tuple[None, None]:
    """Attempt to fit a 3-row × 7-column grid to the detected circles.

    Uses k-means (k=3) on the y-coordinates to split into rows, then picks
    the 7 most evenly-spaced circles per row.

    Returns ``(PanelCrop, [ROIBox])`` or ``(None, None)``.
    """
    # ── 1. Cluster into 3 rows by y-coordinate ────────────────────────────
    y_pts = circles[:, 1].astype(np.float32).reshape(-1, 1)

    # If fewer than 3 distinct y-levels, grid fitting makes no sense.
    if len(np.unique(y_pts.flatten())) < 3:
        return None, None

    _, labels, row_centers = cv2.kmeans(
        y_pts,
        3,
        None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1.0),
        5,
        cv2.KMEANS_PP_CENTERS,
    )
    labels = labels.flatten()

    # Sort rows top-to-bottom.
    row_order = np.argsort(row_centers.flatten())
    rows: list[np.ndarray] = []
    for label_idx in row_order:
        row_c = circles[labels == label_idx]
        row_c = row_c[np.argsort(row_c[:, 0])]   # left → right
        rows.append(row_c)

    row_counts = [len(r) for r in rows]
    logger.debug("Row counts after k-means: %s", row_counts)

    # ── 2. Each row must have a plausible number of circles ──────────────
    if not all(5 <= c <= 10 for c in row_counts):
        logger.debug("Rejecting: row counts %s not in [5,10]", row_counts)
        return None, None

    # ── 3. Pick 7 from each row (most evenly spaced) ─────────────────────
    rows_7 = [_pick_best_7(r) for r in rows]
    if any(r is None for r in rows_7):
        logger.debug("Could not find 7 evenly-spaced circles in a row")
        return None, None

    # ── 4. Verify rows are themselves evenly spaced vertically ──────────
    row_ys = [float(np.mean(r[:, 1])) for r in rows_7]
    row_gaps = np.diff(row_ys)
    if len(row_gaps) == 2 and row_gaps[0] > 0:
        gap_ratio = row_gaps[1] / row_gaps[0]
        if not (0.5 < gap_ratio < 2.0):
            logger.debug("Rejecting: uneven row spacing ratio %.2f", gap_ratio)
            return None, None

    # ── 5. Build panel crop and ROI boxes ────────────────────────────────
    all_c = np.vstack(rows_7)
    med_r  = int(np.median(all_c[:, 2]))
    roi_half = max(3, int(med_r * _ROI_RADIUS_FRACTION))

    margin = int(med_r * 1.6)
    px = max(0, int(all_c[:, 0].min()) - margin)
    py = max(0, int(all_c[:, 1].min()) - margin)
    pr = min(frame_w, int(all_c[:, 0].max()) + margin + med_r)
    pb = min(frame_h, int(all_c[:, 1].max()) + margin + med_r)
    panel = PanelCrop(x=px, y=py, w=pr - px, h=pb - py)

    roi_boxes: list[ROIBox] = []
    for row_c, key_row in zip(rows_7, _KEY_GRID):
        for circ, key_name in zip(row_c, key_row):
            cx = int(circ[0]) - px
            cy = int(circ[1]) - py
            roi_boxes.append(ROIBox(
                key=key_name,
                x=max(0, cx - roi_half),
                y=max(0, cy - roi_half),
                w=roi_half * 2,
                h=roi_half * 2,
            ))

    logger.info(
        "Lyre panel detected: crop=(%d,%d %d×%d)  med_r=%dpx  roi=%dpx",
        px, py, pr - px, pb - py, med_r, roi_half * 2,
    )
    return panel, roi_boxes


def _pick_best_7(row: np.ndarray) -> np.ndarray | None:
    """Select the 7 most evenly x-spaced circles from a row.

    Returns the chosen 7, or ``None`` if fewer than 5 circles are present.
    """
    n = len(row)
    if n == 7:
        return row
    if n < 5:
        return None

    best: np.ndarray | None = None
    best_cv = float("inf")

    window = 7 if n >= 7 else n
    for start in range(n - window + 1):
        sub = row[start : start + window]
        diffs = np.diff(sub[:, 0].astype(float))
        if diffs.mean() == 0:
            continue
        cv = float(np.std(diffs) / diffs.mean())   # coefficient of variation
        if cv < best_cv:
            best_cv = cv
            best = sub

    # Reject if spacing is wildly non-uniform (cv > 0.4 means 40 % std dev)
    if best_cv > 0.4:
        logger.debug("Row rejected: spacing cv=%.2f > 0.4", best_cv)
        return None

    return best
