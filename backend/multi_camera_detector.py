"""
Multi-Camera 2D Dimension Detection

Flow:
1. Camera 1: Measure NGANG_1 (width) + DOC_1 (height) → Reference
2. Camera 2: Use NGANG_1 as scale reference
             Measure DOC_2 + NGANG_2 using scale
3. Volume: NGANG_1 × DOC_1 × NGANG_2

Algorithm: Multi-line edge detection (9 scan lines per direction)
"""

import cv2
import numpy as np
import base64
from io import BytesIO

# ============================================================
# CONFIG
# ============================================================

# Calibration: 150 pixel = 5.5 cm (Camera 1) - adjusted for accuracy
CM_PER_PIXEL_CAM1 = 5.5 / 150  # 0.0367 cm/px

# ROI Expansion
ROI_EXPAND_RATIO = 0.10

# Canny Edge Detection
CANNY_LOW = 50
CANNY_HIGH = 150

# Multi-line scan config
NUM_LINES = 9
SCAN_RANGE = 0.25  # Scan ±25% around center
OUTER_SEARCH_RATIO = 0.35  # Only outer 35% edges
CLUSTER_DISTANCE = 8  # Group edges within 8px


# ============================================================
# CLUSTER EDGE POSITIONS
# ============================================================

def _cluster_positions(values):
    """Group edge positions that are close together."""
    if not values:
        return []

    values = sorted(int(v) for v in values)
    clusters = [[values[0]]]

    for value in values[1:]:
        current = clusters[-1]
        center = np.mean(current)

        if abs(value - center) <= CLUSTER_DISTANCE:
            current.append(value)
        else:
            clusters.append([value])

    result = []
    for cluster in clusters:
        result.append({
            "center": int(round(np.mean(cluster))),
            "count": len(cluster),
            "values": cluster
        })

    return result


# ============================================================
# SELECT STABLE EDGE
# ============================================================

def _select_stable_edge(values, side):
    """
    Choose the most stable edge based on frequency across scan lines.

    Args:
        values: List of edge positions from multiple scans
        side: "left"/"top" (prefer smaller) or "right"/"bottom" (prefer larger)

    Returns:
        int: Center position of most stable edge cluster
    """
    clusters = _cluster_positions(values)

    if not clusters:
        return None

    # Find cluster(s) with most occurrences
    max_count = max(c["count"] for c in clusters)
    candidates = [c for c in clusters if c["count"] == max_count]

    # Prefer extreme position based on side
    if side in ("left", "top"):
        best = min(candidates, key=lambda c: c["center"])
    else:
        best = max(candidates, key=lambda c: c["center"])

    return best["center"]


# ============================================================
# GET OUTER EDGES
# ============================================================

def _get_outer_edges(edge_positions, length):
    """Extract only outer edges (avoid logo/text in center)."""
    if len(edge_positions) == 0:
        return None, None

    left_limit = int(length * OUTER_SEARCH_RATIO)
    right_limit = int(length * (1.0 - OUTER_SEARCH_RATIO))

    left_candidates = edge_positions[edge_positions <= left_limit]
    right_candidates = edge_positions[edge_positions >= right_limit]

    left = int(np.min(left_candidates)) if len(left_candidates) > 0 else None
    right = int(np.max(right_candidates)) if len(right_candidates) > 0 else None

    return left, right


# ============================================================
# FIND SPAN (MULTI-LINE EDGE DETECTION)
# ============================================================

def find_span(image, orientation, canny_low=CANNY_LOW, canny_high=CANNY_HIGH):
    """
    Multi-line edge detection.

    Args:
        image: Input image
        orientation: "horizontal" or "vertical"
        canny_low, canny_high: Canny threshold

    Returns:
        dict with keys: start, end, distance_px, center, center_x, center_y, left_samples, right_samples
        or None if no edges found
    """
    if image is None or image.size == 0:
        return None

    if orientation not in ("horizontal", "vertical"):
        raise ValueError("orientation must be 'horizontal' or 'vertical'")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # --------------------------------------------------------
    # Determine scan positions
    # --------------------------------------------------------

    if orientation == "horizontal":
        center = h // 2
        half = int(h * SCAN_RANGE)
        start_pos = max(0, center - half)
        end_pos = min(h - 1, center + half)
        scan_positions = np.linspace(start_pos, end_pos, NUM_LINES).astype(int)
        line_length = w
    else:  # vertical
        center = w // 2
        half = int(w * SCAN_RANGE)
        start_pos = max(0, center - half)
        end_pos = min(w - 1, center + half)
        scan_positions = np.linspace(start_pos, end_pos, NUM_LINES).astype(int)
        line_length = h

    # --------------------------------------------------------
    # Scan multiple lines
    # --------------------------------------------------------

    left_samples = []
    right_samples = []

    for scan_pos in scan_positions:
        # Extract line
        if orientation == "horizontal":
            line = gray[scan_pos, :]
            line_img = line.reshape(1, -1)
        else:
            line = gray[:, scan_pos]
            line_img = line.reshape(-1, 1)

        # Edge detection
        edges = cv2.Canny(line_img, canny_low, canny_high)

        # Find edge positions
        if orientation == "horizontal":
            positions = np.where(edges[0] > 0)[0]
        else:
            positions = np.where(edges[:, 0] > 0)[0]

        # Get outer edges only
        left, right = _get_outer_edges(positions, line_length)

        if left is not None:
            left_samples.append(left)
        if right is not None:
            right_samples.append(right)

    # --------------------------------------------------------
    # Must have edges on both sides
    # --------------------------------------------------------

    if not left_samples or not right_samples:
        return None

    # --------------------------------------------------------
    # Select most stable edges
    # --------------------------------------------------------

    start = _select_stable_edge(left_samples, "left")
    end = _select_stable_edge(right_samples, "right")

    if start is None or end is None:
        return None

    distance_px = end - start

    if distance_px <= 0:
        return None

    # Return compatible format
    if orientation == "horizontal":
        return {
            "start": int(start),
            "end": int(end),
            "distance_px": int(distance_px),
            "center": int(center),
            "center_x": None,
            "center_y": int(center),
            "left_samples": left_samples,
            "right_samples": right_samples,
        }
    else:  # vertical
        return {
            "start": int(start),
            "end": int(end),
            "distance_px": int(distance_px),
            "center": int(center),
            "center_x": int(center),
            "center_y": None,
            "left_samples": left_samples,
            "right_samples": right_samples,
        }


# ============================================================
# EXPAND ROI
# ============================================================

def expand_roi(image, package_box, ratio=ROI_EXPAND_RATIO):
    """Expand ROI around package bounding box."""
    h, w = image.shape[:2]
    x1, y1, x2, y2 = map(int, package_box)

    bw = x2 - x1
    bh = y2 - y1

    expand_x = int(bw * ratio)
    expand_y = int(bh * ratio)

    rx1 = max(0, x1 - expand_x)
    ry1 = max(0, y1 - expand_y)
    rx2 = min(w, x2 + expand_x)
    ry2 = min(h, y2 + expand_y)

    roi = image[ry1:ry2, rx1:rx2].copy()

    return roi, (rx1, ry1, rx2, ry2)


# ============================================================
# CAMERA 1: REFERENCE MEASUREMENTS
# ============================================================

def measure_camera1(frame):
    """
    Measure width (NGANG_1) and height (DOC_1) from Camera 1.
    These serve as reference for Camera 2.

    Args:
        frame: Image from camera 1

    Returns:
        dict with measurements or None if detection failed
    """
    # Use full frame as ROI (no package detection needed)
    roi = frame.copy()
    h, w = frame.shape[:2]
    roi_box = (0, 0, w, h)
    rx1, ry1, rx2, ry2 = roi_box
    rx1, ry1, rx2, ry2 = roi_box

    if roi.size == 0:
        return None

    # --------------------------------------------------------
    # Multi-line edge detection
    # --------------------------------------------------------

    horizontal = find_span(roi, "horizontal")
    vertical = find_span(roi, "vertical")

    result = {
        "success": False,
        "ngang_1_px": None,
        "ngang_1_cm": None,
        "doc_1_px": None,
        "doc_1_cm": None,
        "ngang_points_global": None,
        "doc_points_global": None,
        "horizontal_debug": horizontal,
        "vertical_debug": vertical,
        "roi_box": roi_box,
        "center_global": (rx1 + roi.shape[1] // 2, ry1 + roi.shape[0] // 2),
    }

    # --------------------------------------------------------
    # NGANG_1 (horizontal)
    # --------------------------------------------------------

    if horizontal is not None:
        left = horizontal["start"]
        right = horizontal["end"]
        center_y = horizontal["center_y"]

        left_global = (rx1 + left, ry1 + center_y)
        right_global = (rx1 + right, ry1 + center_y)

        px = right - left
        cm = px * CM_PER_PIXEL_CAM1

        result["ngang_1_px"] = px
        result["ngang_1_cm"] = cm
        result["ngang_points_global"] = (left_global, right_global)

    # --------------------------------------------------------
    # DOC_1 (vertical)
    # --------------------------------------------------------

    if vertical is not None:
        top = vertical["start"]
        bottom = vertical["end"]
        center_x = vertical["center_x"]

        top_global = (rx1 + center_x, ry1 + top)
        bottom_global = (rx1 + center_x, ry1 + bottom)

        px = bottom - top
        cm = px * CM_PER_PIXEL_CAM1

        result["doc_1_px"] = px
        result["doc_1_cm"] = cm
        result["doc_points_global"] = (top_global, bottom_global)

    result["success"] = (result["ngang_1_cm"] is not None and result["doc_1_cm"] is not None)

    return result


# ============================================================
# CAMERA 2: DEPENDENT MEASUREMENTS
# ============================================================

def measure_camera2(frame, ngang_1_cm):
    """
    Measure height (DOC_2) and width (NGANG_2) from Camera 2.
    Uses NGANG_1_CM as reference scale.

    Args:
        frame: Image from camera 2
        ngang_1_cm: Reference width from camera 1 (in cm)

    Returns:
        dict with measurements or None if detection failed
    """
    # Use full frame as ROI (no package detection needed)
    roi = frame.copy()
    h, w = frame.shape[:2]
    roi_box = (0, 0, w, h)
    rx1, ry1, rx2, ry2 = roi_box

    if roi.size == 0:
        return None

    horizontal = find_span(roi, "horizontal")
    vertical = find_span(roi, "vertical")

    result = {
        "success": False,
        "doc_2_px": None,
        "doc_2_cm": None,
        "ngang_2_px": None,
        "ngang_2_cm": None,
        "scale_cam2": None,
        "doc_points_global": None,
        "ngang_points_global": None,
        "horizontal_debug": horizontal,
        "vertical_debug": vertical,
        "roi_box": roi_box,
    }

    # --------------------------------------------------------
    # DOC_2 (vertical)
    # --------------------------------------------------------

    if vertical is not None:
        top = vertical["start"]
        bottom = vertical["end"]
        center_x = vertical["center_x"]

        doc_2_px = bottom - top

        result["doc_2_px"] = doc_2_px
        result["doc_points_global"] = (
            (rx1 + center_x, ry1 + top),
            (rx1 + center_x, ry1 + bottom),
        )

        # Calculate scale using reference from Camera 1
        if ngang_1_cm is not None and doc_2_px > 0:
            scale = ngang_1_cm / doc_2_px
            result["scale_cam2"] = scale
            result["doc_2_cm"] = doc_2_px * scale

            # ------------------------------------------------
            # NGANG_2 (horizontal)
            # ------------------------------------------------

            if horizontal is not None:
                left = horizontal["start"]
                right = horizontal["end"]

                ngang_2_px = right - left
                result["ngang_2_px"] = ngang_2_px
                result["ngang_2_cm"] = ngang_2_px * scale

                result["ngang_points_global"] = (
                    (rx1 + left, ry1 + horizontal["center_y"]),
                    (rx1 + right, ry1 + horizontal["center_y"]),
                )

    result["success"] = (result["doc_2_cm"] is not None and result["ngang_2_cm"] is not None)

    return result


# ============================================================
# DRAW MEASUREMENTS ON IMAGE
# ============================================================

def draw_measurements(image, data):
    """Draw measurement lines and labels on image."""
    result = image.copy()

    # Draw ROI box
    rx1, ry1, rx2, ry2 = data.get("roi_box", (0, 0, image.shape[1], image.shape[0]))
    cv2.rectangle(result, (rx1, ry1), (rx2, ry2), (255, 255, 0), 2)

    # Draw NGANG (horizontal)
    ngang_points = data.get("ngang_points_global")
    if ngang_points is not None:
        p1, p2 = ngang_points
        cv2.line(result, p1, p2, (0, 255, 0), 3)
        cv2.circle(result, p1, 8, (0, 0, 255), -1)
        cv2.circle(result, p2, 8, (255, 0, 0), -1)
        if data.get("ngang_1_cm") is not None:
            cv2.putText(result, f"NGANG: {data['ngang_1_cm']:.2f}cm", (p1[0], p1[1]-15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Draw DOC (vertical)
    doc_points = data.get("doc_points_global")
    if doc_points is not None:
        p1, p2 = doc_points
        cv2.line(result, p1, p2, (255, 0, 0), 3)
        cv2.circle(result, p1, 8, (0, 0, 255), -1)
        cv2.circle(result, p2, 8, (255, 0, 0), -1)
        if data.get("doc_1_cm") is not None:
            cv2.putText(result, f"DOC: {data['doc_1_cm']:.2f}cm", (p1[0]+15, p1[1]),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

    return result


# ============================================================
# CALCULATE VOLUME
# ============================================================

def calculate_volume(ngang_1_cm, doc_1_cm, ngang_2_cm):
    """
    Calculate 3D volume from 3 dimensions.

    Applies correction factor to DOC_1 if needed.

    Args:
        ngang_1_cm: Width from camera 1 (cm)
        doc_1_cm: Height from camera 1 (cm)
        ngang_2_cm: Width from camera 2 (cm)

    Returns:
        float: Volume in cm³, or None
    """
    if ngang_1_cm is None or doc_1_cm is None or ngang_2_cm is None:
        return None

    # Apply correction factor to DOC_1
    doc_1_corrected = doc_1_cm * (
        1 + 0.1 * (doc_1_cm - ngang_1_cm) / min(doc_1_cm, ngang_1_cm)
    )

    volume = ngang_1_cm * doc_1_corrected * ngang_2_cm

    return volume


# ============================================================
# MEASURE MULTI-CAMERA (MAIN FUNCTION)
# ============================================================

def measure_multi_camera(frame1, frame2):
    """
    Full 2-camera measurement pipeline with visualization.

    Args:
        frame1: Image from camera 1 (reference)
        frame2: Image from camera 2 (dependent)

    Returns:
        dict with:
            - success: bool
            - ngang_1_cm, doc_1_cm: Camera 1 measurements
            - doc_2_cm, ngang_2_cm: Camera 2 measurements
            - volume_cm3: Calculated volume
            - cam1_image_base64: Annotated camera 1 image
            - cam2_image_base64: Annotated camera 2 image
            - error: Error message if failed
    """
    result = {
        "success": False,
        "ngang_1_cm": None,
        "doc_1_cm": None,
        "doc_2_cm": None,
        "ngang_2_cm": None,
        "volume_cm3": None,
        "cam1_image_base64": None,
        "cam2_image_base64": None,
        "error": None,
    }

    try:
        # ====================================================
        # CAMERA 1 (Reference)
        # ====================================================

        cam1_data = measure_camera1(frame1)

        if cam1_data is None or not cam1_data["success"]:
            result["error"] = "Camera 1: No edges detected"
            return result

        result["ngang_1_cm"] = cam1_data["ngang_1_cm"]
        result["doc_1_cm"] = cam1_data["doc_1_cm"]

        # Draw measurements on camera 1
        cam1_annotated = draw_measurements(frame1, cam1_data)
        _, cam1_encoded = cv2.imencode('.jpg', cam1_annotated)
        result["cam1_image_base64"] = base64.b64encode(cam1_encoded).decode()

        # ====================================================
        # CAMERA 2 (Dependent)
        # ====================================================

        cam2_data = measure_camera2(frame2, cam1_data["ngang_1_cm"])

        if cam2_data is None or not cam2_data["success"]:
            result["error"] = "Camera 2: No edges detected"
            return result

        result["doc_2_cm"] = cam2_data["doc_2_cm"]
        result["ngang_2_cm"] = cam2_data["ngang_2_cm"]

        # Draw measurements on camera 2
        cam2_annotated = draw_measurements(frame2, cam2_data)
        _, cam2_encoded = cv2.imencode('.jpg', cam2_annotated)
        result["cam2_image_base64"] = base64.b64encode(cam2_encoded).decode()

        # ====================================================
        # CALCULATE VOLUME
        # ====================================================

        volume = calculate_volume(
            result["ngang_1_cm"],
            result["doc_1_cm"],
            result["ngang_2_cm"],
        )

        result["volume_cm3"] = volume
        result["success"] = volume is not None

        if volume is not None:
            result["volume_cm3"] = round(volume, 1)

    except Exception as e:
        import traceback
        traceback.print_exc()
        result["error"] = f"Exception: {str(e)}"

    return result
