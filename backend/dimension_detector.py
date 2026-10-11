"""Dimension detection: Package detection + Edge detection + 2-camera reference measurement.

Pipeline:
1. Crop info region (from document_processor)
2. YOLO detect package ROI
3. Extract horizontal/vertical edges from ROI
4. Measure dimensions using 2-camera reference logic
5. Calculate volume

Also supports ESP32 sensor-based measurement:
- Fetch 3 distances from ESP32 ultrasonic sensors
- Return L×W×H directly

Based on logic from other/send/modules but integrated with new document processor.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from io import BytesIO
import requests

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

# Model paths
MODEL_DIR = Path(__file__).parent.parent / "model"
PACKAGE_DETECTOR_MODEL_PATH = MODEL_DIR / "box_detect.pt"
# PACKAGE_DETECTOR_MODEL_PATH = MODEL_DIR / "best.pt"

# Camera calibration (from send/modules/measurement.py)
CM_PER_PIXEL_CAM1 = 29 / 150  # 0.1933 cm/pixel

# Global model instance
_package_detector_model = None


def load_package_detector_model():
    """Load package detection YOLO model."""
    if not HAS_YOLO:
        raise ImportError("ultralytics not installed. Install with: pip install ultralytics")

    if not PACKAGE_DETECTOR_MODEL_PATH.exists():
        raise FileNotFoundError(f"Package detector model not found: {PACKAGE_DETECTOR_MODEL_PATH}")

    print(f"[DimensionDetector] Loading package detector from {PACKAGE_DETECTOR_MODEL_PATH}")
    model = YOLO(str(PACKAGE_DETECTOR_MODEL_PATH))
    print(f"[DimensionDetector] Package detector loaded successfully")
    return model


def get_package_detector_model():
    """Get or initialize package detector model."""
    global _package_detector_model
    if _package_detector_model is None:
        _package_detector_model = load_package_detector_model()
    return _package_detector_model


def image_bytes_to_cv2(image_bytes: bytes) -> Optional[np.ndarray]:
    """Convert image bytes to OpenCV format."""
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return image
    except Exception as e:
        print(f"[DimensionDetector] Error converting image bytes: {e}")
        return None


def cv2_to_image_bytes(image: np.ndarray, format: str = "jpg") -> bytes:
    """Convert OpenCV image to bytes."""
    try:
        if format.lower() in ["jpg", "jpeg"]:
            _, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        elif format.lower() == "png":
            _, buffer = cv2.imencode(".png", image)
        else:
            _, buffer = cv2.imencode(".jpg", image)
        return buffer.tobytes()
    except Exception as e:
        print(f"[DimensionDetector] Error converting image to bytes: {e}")
        return b""


def detect_package_roi(image: np.ndarray, conf: float = 0.4) -> Optional[Tuple[int, int, int, int]]:
    """Detect package bounding box using YOLO.

    Args:
        image: OpenCV image (BGR)
        conf: Confidence threshold

    Returns:
        (x1, y1, x2, y2) largest package box, or None if no package detected
    """
    try:
        model = get_package_detector_model()
        results = model(image, verbose=False, conf=conf)

        if not results or len(results) == 0:
            print("[DimensionDetector] No packages detected")
            return None

        result = results[0]

        if not hasattr(result, 'boxes') or len(result.boxes) == 0:
            print("[DimensionDetector] No boxes in detection result")
            return None

        # Get largest package by area
        boxes = result.boxes
        largest_box = None
        largest_area = 0

        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            area = (x2 - x1) * (y2 - y1)

            if area > largest_area:
                largest_area = area
                largest_box = (int(x1), int(y1), int(x2), int(y2))

        if largest_box:
            x1, y1, x2, y2 = largest_box
            print(f"[DimensionDetector] Package detected at ({x1}, {y1}, {x2}, {y2}), area: {largest_area}")
            return largest_box

        return None

    except Exception as e:
        print(f"[DimensionDetector] Package detection error: {e}")
        return None


def extract_roi(image: np.ndarray, bbox: Tuple[int, int, int, int],
                padding: int = 0) -> Optional[np.ndarray]:
    """Extract ROI from image based on bounding box.

    Args:
        image: OpenCV image (BGR)
        bbox: (x1, y1, x2, y2)
        padding: Extra padding around bbox

    Returns:
        Cropped ROI or None
    """
    try:
        x1, y1, x2, y2 = bbox
        h, w = image.shape[:2]

        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(w, x2 + padding)
        y2 = min(h, y2 + padding)

        roi = image[y1:y2, x1:x2]
        print(f"[DimensionDetector] ROI extracted: {roi.shape}")
        return roi

    except Exception as e:
        print(f"[DimensionDetector] ROI extraction error: {e}")
        return None


def find_horizontal_edges(roi: np.ndarray, canny_low: int = 50,
                         canny_high: int = 150) -> Optional[Dict[str, Any]]:
    """Find horizontal edges at center line of ROI.

    Detects left/right edges on the horizontal center line using Canny.

    Args:
        roi: Region of interest (OpenCV image)
        canny_low: Canny lower threshold
        canny_high: Canny upper threshold

    Returns:
        {
            "start": left_x,
            "end": right_x,
            "distance_px": width_px,
            "center": center_y
        }
        or None if detection failed
    """
    try:
        if roi is None or roi.size == 0:
            return None

        h, w = roi.shape[:2]
        center_y = h // 2

        # Extract horizontal line at center
        line = roi[center_y, :, :]

        # Convert to grayscale
        gray_line = cv2.cvtColor(line.reshape(1, w, 3), cv2.COLOR_BGR2GRAY)

        # Canny edge detection
        edges = cv2.Canny(gray_line, canny_low, canny_high)

        # Find edge positions
        edge_positions = np.where(edges[0] > 0)[0]

        if len(edge_positions) < 2:
            print("[DimensionDetector] Horizontal: Not enough edges found")
            return None

        left_x = int(np.min(edge_positions))
        right_x = int(np.max(edge_positions))
        distance_px = right_x - left_x

        print(f"[DimensionDetector] Horizontal edges: {left_x} - {right_x} (distance: {distance_px}px)")

        return {
            "start": left_x,
            "end": right_x,
            "distance_px": distance_px,
            "center": center_y
        }

    except Exception as e:
        print(f"[DimensionDetector] Horizontal edge detection error: {e}")
        return None


def find_vertical_edges(roi: np.ndarray, canny_low: int = 50,
                       canny_high: int = 150) -> Optional[Dict[str, Any]]:
    """Find vertical edges at center column of ROI.

    Detects top/bottom edges on the vertical center column using Canny.

    Args:
        roi: Region of interest (OpenCV image)
        canny_low: Canny lower threshold
        canny_high: Canny upper threshold

    Returns:
        {
            "start": top_y,
            "end": bottom_y,
            "distance_px": height_px,
            "center": center_x
        }
        or None if detection failed
    """
    try:
        if roi is None or roi.size == 0:
            return None

        h, w = roi.shape[:2]
        center_x = w // 2

        # Extract vertical line at center
        line = roi[:, center_x, :]

        # Convert to grayscale
        gray_line = cv2.cvtColor(line.reshape(h, 1, 3), cv2.COLOR_BGR2GRAY)

        # Canny edge detection
        edges = cv2.Canny(gray_line, canny_low, canny_high)

        # Find edge positions
        edge_positions = np.where(edges[:, 0] > 0)[0]

        if len(edge_positions) < 2:
            print("[DimensionDetector] Vertical: Not enough edges found")
            return None

        top_y = int(np.min(edge_positions))
        bottom_y = int(np.max(edge_positions))
        distance_px = bottom_y - top_y

        print(f"[DimensionDetector] Vertical edges: {top_y} - {bottom_y} (distance: {distance_px}px)")

        return {
            "start": top_y,
            "end": bottom_y,
            "distance_px": distance_px,
            "center": center_x
        }

    except Exception as e:
        print(f"[DimensionDetector] Vertical edge detection error: {e}")
        return None


def pixel_to_cm(pixel_distance: float, cm_per_pixel: float = CM_PER_PIXEL_CAM1) -> Optional[float]:
    """Convert pixel distance to cm.

    Args:
        pixel_distance: Distance in pixels
        cm_per_pixel: Calibration ratio (default: 29/150)

    Returns:
        Distance in cm or None
    """
    if pixel_distance is None:
        return None
    return pixel_distance * cm_per_pixel


def measure_camera1(horizontal_result: Optional[Dict],
                   vertical_result: Optional[Dict]) -> Dict[str, Optional[float]]:
    """Measure Camera 1 dimensions.

    Uses direct Canny edge detection on horizontal/vertical center lines.

    Args:
        horizontal_result: Result from find_horizontal_edges()
        vertical_result: Result from find_vertical_edges()

    Returns:
        {
            "ngang_1_px": horizontal distance in pixels,
            "ngang_1_cm": horizontal distance in cm,
            "doc_1_px": vertical distance in pixels,
            "doc_1_cm": vertical distance in cm
        }
    """
    ngang_1_px = None
    ngang_1_cm = None
    doc_1_px = None
    doc_1_cm = None

    if horizontal_result is not None:
        ngang_1_px = horizontal_result["distance_px"]
        ngang_1_cm = pixel_to_cm(ngang_1_px)

    if vertical_result is not None:
        doc_1_px = vertical_result["distance_px"]
        doc_1_cm = pixel_to_cm(doc_1_px)

    print(f"[DimensionDetector] Camera1: ngang={ngang_1_cm:.1f}cm ({ngang_1_px}px), doc={doc_1_cm:.1f}cm ({doc_1_px}px)")

    return {
        "ngang_1_px": ngang_1_px,
        "ngang_1_cm": ngang_1_cm,
        "doc_1_px": doc_1_px,
        "doc_1_cm": doc_1_cm
    }


def measure_camera2(horizontal_result: Optional[Dict],
                   vertical_result: Optional[Dict],
                   ngang_1_cm: Optional[float],
                   reference_mode: str = "VERTICAL") -> Dict[str, Optional[float]]:
    """Measure Camera 2 dimensions using reference from Camera 1.

    Two modes:
    - VERTICAL: NGANG_1 <-> DỌC_2 (same edge, different orientations)
    - HORIZONTAL: NGANG_1 <-> NGANG_2 (same edge, same orientation)

    Args:
        horizontal_result: Result from find_horizontal_edges()
        vertical_result: Result from find_vertical_edges()
        ngang_1_cm: Reference measurement from Camera 1 (horizontal)
        reference_mode: "VERTICAL" or "HORIZONTAL"

    Returns:
        {
            "ngang_2_px": horizontal distance in pixels,
            "ngang_2_cm": horizontal distance in cm,
            "doc_2_px": vertical distance in pixels,
            "doc_2_cm": vertical distance in cm,
            "reference": Reference relationship,
            "ratio": Pixel ratio used for calculation
        }
    """
    # Validation
    if (horizontal_result is None or vertical_result is None or ngang_1_cm is None):
        return {
            "ngang_2_px": None,
            "doc_2_px": None,
            "ngang_2_cm": None,
            "doc_2_cm": None,
            "reference": None,
            "ratio": None
        }

    if reference_mode not in ["VERTICAL", "HORIZONTAL"]:
        raise ValueError("reference_mode must be 'VERTICAL' or 'HORIZONTAL'")

    ngang_2_px = horizontal_result["distance_px"]
    doc_2_px = vertical_result["distance_px"]

    if ngang_2_px is None or doc_2_px is None or ngang_2_px <= 0 or doc_2_px <= 0:
        return {
            "ngang_2_px": ngang_2_px,
            "doc_2_px": doc_2_px,
            "ngang_2_cm": None,
            "doc_2_cm": None,
            "reference": None,
            "ratio": None
        }

    # VERTICAL mode: NGANG_1 <-> DỌC_2
    if reference_mode == "VERTICAL":
        doc_2_cm = ngang_1_cm
        ratio = ngang_2_px / doc_2_px
        ngang_2_cm = ratio * doc_2_cm
        reference = "NGANG_1 <-> DỌC_2"

    # HORIZONTAL mode: NGANG_1 <-> NGANG_2
    else:
        ngang_2_cm = ngang_1_cm
        ratio = doc_2_px / ngang_2_px
        doc_2_cm = ratio * ngang_2_cm
        reference = "NGANG_1 <-> NGANG_2"

    print(f"[DimensionDetector] Camera2 ({reference}): ngang={ngang_2_cm:.1f}cm, doc={doc_2_cm:.1f}cm, ratio={ratio:.2f}")

    return {
        "ngang_2_px": ngang_2_px,
        "doc_2_px": doc_2_px,
        "ngang_2_cm": ngang_2_cm,
        "doc_2_cm": doc_2_cm,
        "reference": reference,
        "ratio": ratio
    }


def calculate_volume(ngang_1_cm: Optional[float],
                    doc_1_cm: Optional[float],
                    ngang_2_cm: Optional[float]) -> Optional[float]:
    """Calculate package volume.

    Volume = NGANG_1 × DỌC_1 × NGANG_2 (cm³)

    Args:
        ngang_1_cm: Horizontal dimension from Camera 1 (cm)
        doc_1_cm: Vertical dimension from Camera 1 (cm)
        ngang_2_cm: Horizontal dimension from Camera 2 (cm)

    Returns:
        Volume in cm³ or None
    """
    if ngang_1_cm is None or doc_1_cm is None or ngang_2_cm is None:
        return None

    volume = ngang_1_cm * doc_1_cm * ngang_2_cm
    print(f"[DimensionDetector] Volume = {ngang_1_cm:.1f} × {doc_1_cm:.1f} × {ngang_2_cm:.1f} = {volume:.0f} cm³")
    return volume


def detect_dimensions_single(image_bytes: bytes,
                            padding: int = 5,
                            canny_low: int = 50,
                            canny_high: int = 150) -> Dict[str, Any]:
    """Measure single camera image: Detect package ROI + Extract edges.

    Args:
        image_bytes: Input image bytes
        padding: Extra padding around package ROI
        canny_low: Canny lower threshold
        canny_high: Canny upper threshold

    Returns:
        {
            "success": bool,
            "horiz_result": {...},  # Horizontal edge detection result
            "vert_result": {...},   # Vertical edge detection result
            "image": opencv_image,  # Original image
            "package_bbox": (x1, y1, x2, y2),  # Package ROI
            "roi": roi_image,  # Extracted ROI
            "camera_result": {...},  # measure_camera1() output
            "annotated_image_base64": str,
            "error": str or None
        }
    """
    try:
        # Load image
        image = image_bytes_to_cv2(image_bytes)
        if image is None:
            return {"success": False, "error": "Failed to load image"}

        print(f"[DimensionDetector] Image loaded: {image.shape}")

        # Detect package ROI
        package_bbox = detect_package_roi(image)
        if package_bbox is None:
            return {"success": False, "error": "Failed to detect package"}

        # Extract ROI
        roi = extract_roi(image, package_bbox, padding=padding)
        if roi is None:
            return {"success": False, "error": "Failed to extract ROI"}

        # Find edges
        horiz_result = find_horizontal_edges(roi, canny_low, canny_high)
        vert_result = find_vertical_edges(roi, canny_low, canny_high)

        if horiz_result is None or vert_result is None:
            return {"success": False, "error": "Failed to detect edges"}

        # Measure camera
        camera_result = measure_camera1(horiz_result, vert_result)

        # Draw annotations
        annotated = image.copy()
        x1, y1, x2, y2 = package_bbox
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(annotated, f"L:{camera_result['ngang_1_cm']:.1f}cm H:{camera_result['doc_1_cm']:.1f}cm",
                   (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        annotated_bytes = cv2_to_image_bytes(annotated)
        import base64
        annotated_base64 = base64.b64encode(annotated_bytes).decode("utf-8")

        return {
            "success": True,
            "horiz_result": horiz_result,
            "vert_result": vert_result,
            "image": image,
            "package_bbox": package_bbox,
            "roi": roi,
            "camera_result": camera_result,
            "annotated_image_base64": annotated_base64,
            "error": None
        }

    except Exception as e:
        print(f"[DimensionDetector] Single camera error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def detect_dimensions_dual(image_bytes_cam1: bytes,
                          image_bytes_cam2: bytes,
                          reference_mode: str = "VERTICAL",
                          padding: int = 5,
                          canny_low: int = 50,
                          canny_high: int = 150) -> Dict[str, Any]:
    """Measure 2 cameras with reference logic: CAM1 + CAM2 → L×W×H.

    Pipeline:
    1. Measure CAM1: NGANG_1 + DỌC_1
    2. Measure CAM2: NGANG_2 + DỌC_2
    3. Apply reference logic: NGANG_1 <-> DỌC_2 (or NGANG_1 <-> NGANG_2)
    4. Calculate final L×W×H + Volume

    Args:
        image_bytes_cam1: First camera image
        image_bytes_cam2: Second camera image
        reference_mode: "VERTICAL" or "HORIZONTAL"
        padding: Extra padding around package ROI
        canny_low: Canny lower threshold
        canny_high: Canny upper threshold

    Returns:
        {
            "success": bool,
            "length_cm": Length (cm),
            "width_cm": Width (cm),
            "height_cm": Height (cm),
            "volume_cm3": Volume (cm³),
            "camera1": {...},  # Camera 1 measurement details
            "camera2": {...},  # Camera 2 measurement details
            "reference": str,  # Reference relationship used
            "annotated_image_base64": str,
            "error": str or None
        }
    """
    try:
        # Process Camera 1
        print("\n[DimensionDetector] Processing CAMERA 1...")
        cam1_result = detect_dimensions_single(image_bytes_cam1, padding, canny_low, canny_high)

        if not cam1_result["success"]:
            return {
                "success": False,
                "length_cm": None,
                "width_cm": None,
                "height_cm": None,
                "volume_cm3": None,
                "camera1": None,
                "camera2": None,
                "reference": None,
                "annotated_image_base64": "",
                "error": f"Camera 1 failed: {cam1_result['error']}"
            }

        # Process Camera 2
        print("\n[DimensionDetector] Processing CAMERA 2...")
        cam2_result = detect_dimensions_single(image_bytes_cam2, padding, canny_low, canny_high)

        if not cam2_result["success"]:
            return {
                "success": False,
                "length_cm": None,
                "width_cm": None,
                "height_cm": None,
                "volume_cm3": None,
                "camera1": None,
                "camera2": None,
                "reference": None,
                "annotated_image_base64": "",
                "error": f"Camera 2 failed: {cam2_result['error']}"
            }

        # Extract measurements
        cam1_horiz = cam1_result["horiz_result"]
        cam1_vert = cam1_result["vert_result"]
        cam2_horiz = cam2_result["horiz_result"]
        cam2_vert = cam2_result["vert_result"]

        cam1_measure = cam1_result["camera_result"]
        ngang_1_cm = cam1_measure["ngang_1_cm"]

        # Apply reference logic
        print(f"\n[DimensionDetector] Applying reference logic: {reference_mode}")
        cam2_measure = measure_camera2(cam2_horiz, cam2_vert, ngang_1_cm, reference_mode)

        # Extract final dimensions
        length_cm = cam1_measure["ngang_1_cm"]      # NGANG_1
        width_cm = cam1_measure["doc_1_cm"]         # DỌC_1
        height_cm = cam2_measure["ngang_2_cm"]      # NGANG_2 (or DỌC_2 depending on mode)

        if reference_mode == "HORIZONTAL":
            height_cm = cam2_measure["doc_2_cm"]

        volume_cm3 = calculate_volume(length_cm, width_cm, height_cm)

        # Draw annotations on cam1
        annotated = cam1_result["image"].copy()
        x1, y1, x2, y2 = cam1_result["package_bbox"]
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(annotated, f"L:{length_cm:.1f}cm W:{width_cm:.1f}cm H:{height_cm:.1f}cm",
                   (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        annotated_bytes = cv2_to_image_bytes(annotated)
        import base64
        annotated_base64 = base64.b64encode(annotated_bytes).decode("utf-8")

        print(f"[DimensionDetector] 2-Camera detection complete")

        return {
            "success": True,
            "length_cm": float(length_cm) if length_cm else None,
            "width_cm": float(width_cm) if width_cm else None,
            "height_cm": float(height_cm) if height_cm else None,
            "volume_cm3": float(volume_cm3) if volume_cm3 else None,
            "camera1": cam1_measure,
            "camera2": cam2_measure,
            "reference": cam2_measure.get("reference"),
            "annotated_image_base64": annotated_base64,
            "error": None
        }

    except Exception as e:
        print(f"[DimensionDetector] Dual camera error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "length_cm": None,
            "width_cm": None,
            "height_cm": None,
            "volume_cm3": None,
            "camera1": None,
            "camera2": None,
            "reference": None,
            "annotated_image_base64": "",
            "error": str(e)
        }


def detect_dimensions(image_bytes: bytes,
                     reference_mode: str = "VERTICAL",
                     padding: int = 5,
                     canny_low: int = 50,
                     canny_high: int = 150) -> Dict[str, Any]:
    """Legacy single-camera wrapper. Use detect_dimensions_dual for 2-camera."""
    result = detect_dimensions_single(image_bytes, padding, canny_low, canny_high)

    if not result["success"]:
        return {
            "success": False,
            "length_cm": None,
            "width_cm": None,
            "height_cm": None,
            "volume_cm3": None,
            "camera1": None,
            "camera2": None,
            "annotated_image_base64": "",
            "error": result["error"]
        }

    camera_result = result["camera_result"]
    length_cm = camera_result["ngang_1_cm"]
    width_cm = camera_result["doc_1_cm"]
    height_cm = camera_result["ngang_1_cm"]  # Copy (not ideal)

    volume_cm3 = calculate_volume(length_cm, width_cm, height_cm)

    return {
        "success": True,
        "length_cm": float(length_cm) if length_cm else None,
        "width_cm": float(width_cm) if width_cm else None,
        "height_cm": float(height_cm) if height_cm else None,
        "volume_cm3": float(volume_cm3) if volume_cm3 else None,
        "camera1": camera_result,
        "camera2": None,
        "annotated_image_base64": result["annotated_image_base64"],
        "error": None
    }


# ========== ESP32 SENSOR-BASED MEASUREMENT ==========

def detect_dimensions_esp32(esp32_url: str = "http://esp32-buudien.local/distance",
                           timeout: int = 5) -> Dict[str, Any]:
    """Fetch dimensions from ESP32 ultrasonic sensors.

    ESP32 API returns:
    {
        "sensor1": {"success": true, "distance": 30.5},  # Length (cm)
        "sensor2": {"success": true, "distance": 20.3},  # Width (cm)
        "sensor3": {"success": true, "distance": 15.8}   # Height (cm)
    }

    Args:
        esp32_url: ESP32 API endpoint URL
        timeout: Request timeout in seconds

    Returns:
        {
            "success": bool,
            "length_cm": float or None,
            "width_cm": float or None,
            "height_cm": float or None,
            "volume_cm3": float or None,
            "sensor_data": {...},  # Raw sensor data
            "error": str or None
        }
    """
    try:
        print(f"[ESP32] Fetching from {esp32_url}")

        # Fetch from ESP32
        response = requests.get(esp32_url, timeout=timeout)
        response.raise_for_status()

        data = response.json()
        print(f"[ESP32] Response: {data}")

        # Extract sensor values
        sensor1 = data.get("sensor1", {})
        sensor2 = data.get("sensor2", {})
        sensor3 = data.get("sensor3", {})

        # Get distances
        length_cm = None
        width_cm = None
        height_cm = None

        if sensor1.get("success"):
            length_cm = float(sensor1.get("distance"))
            print(f"[ESP32] Sensor1 (Length): {length_cm} cm")
        else:
            print(f"[ESP32] Sensor1 FAILED")

        if sensor2.get("success"):
            width_cm = float(sensor2.get("distance"))
            print(f"[ESP32] Sensor2 (Width): {width_cm} cm")
        else:
            print(f"[ESP32] Sensor2 FAILED")

        if sensor3.get("success"):
            height_cm = float(sensor3.get("distance"))
            print(f"[ESP32] Sensor3 (Height): {height_cm} cm")
        else:
            print(f"[ESP32] Sensor3 FAILED")

        # Check if all sensors succeeded
        if not (length_cm and width_cm and height_cm):
            return {
                "success": False,
                "length_cm": length_cm,
                "width_cm": width_cm,
                "height_cm": height_cm,
                "volume_cm3": None,
                "sensor_data": data,
                "error": "Một hoặc nhiều cảm biến không hoạt động"
            }

        # Calculate volume
        volume_cm3 = length_cm * width_cm * height_cm
        print(f"[ESP32] Volume: {volume_cm3} cm³")

        return {
            "success": True,
            "length_cm": float(length_cm),
            "width_cm": float(width_cm),
            "height_cm": float(height_cm),
            "volume_cm3": float(volume_cm3),
            "sensor_data": data,
            "error": None
        }

    except requests.exceptions.Timeout:
        print(f"[ESP32] Timeout after {timeout}s")
        return {
            "success": False,
            "length_cm": None,
            "width_cm": None,
            "height_cm": None,
            "volume_cm3": None,
            "sensor_data": None,
            "error": f"ESP32 không phản hồi (timeout {timeout}s). Kiểm tra kết nối."
        }

    except requests.exceptions.ConnectionError as e:
        print(f"[ESP32] Connection error: {e}")
        return {
            "success": False,
            "length_cm": None,
            "width_cm": None,
            "height_cm": None,
            "volume_cm3": None,
            "sensor_data": None,
            "error": f"Không thể kết nối ESP32 tại {esp32_url}. Kiểm tra IP/URL."
        }

    except requests.exceptions.RequestException as e:
        print(f"[ESP32] Request error: {e}")
        return {
            "success": False,
            "length_cm": None,
            "width_cm": None,
            "height_cm": None,
            "volume_cm3": None,
            "sensor_data": None,
            "error": f"Lỗi kết nối ESP32: {str(e)}"
        }

    except (KeyError, ValueError, TypeError) as e:
        print(f"[ESP32] Parse error: {e}")
        return {
            "success": False,
            "length_cm": None,
            "width_cm": None,
            "height_cm": None,
            "volume_cm3": None,
            "sensor_data": None,
            "error": f"Dữ liệu ESP32 không đúng định dạng: {str(e)}"
        }

    except Exception as e:
        print(f"[ESP32] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "length_cm": None,
            "width_cm": None,
            "height_cm": None,
            "volume_cm3": None,
            "sensor_data": None,
            "error": f"Lỗi không xác định: {str(e)}"
        }
