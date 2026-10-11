"""Document processor: Classify document type + Detect & crop info region.

Pipeline:
1. Envelope_box_detection.pt → Classify: Thư từ (LETTER) or Hàng hóa (GOODS)
2. info.pt → Detect info region bounding box
3. Crop info region from original image
4. Return: service_type + cropped_image (for OCR input)
"""

import cv2
import numpy as np
from pathlib import Path
from io import BytesIO
from typing import Tuple, Optional

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

# Model paths
MODEL_DIR = Path(__file__).parent.parent / "model"
CLASSIFIER_MODEL_PATH = MODEL_DIR / "Envelope_box_detection.pt"
INFO_DETECTOR_MODEL_PATH = MODEL_DIR / "info.pt"

# Global model instances (lazy load)
_classifier_model = None
_info_detector_model = None


def load_classifier_model():
    """Load Envelope_box_detection.pt for document classification."""
    if not HAS_YOLO:
        raise ImportError("ultralytics not installed. Install with: pip install ultralytics")

    if not CLASSIFIER_MODEL_PATH.exists():
        raise FileNotFoundError(f"Classifier model not found: {CLASSIFIER_MODEL_PATH}")

    print(f"[DocumentProcessor] Loading classifier from {CLASSIFIER_MODEL_PATH}")
    model = YOLO(str(CLASSIFIER_MODEL_PATH))
    print(f"[DocumentProcessor] Classifier loaded successfully")
    return model


def load_info_detector_model():
    """Load info.pt for info region detection."""
    if not HAS_YOLO:
        raise ImportError("ultralytics not installed. Install with: pip install ultralytics")

    if not INFO_DETECTOR_MODEL_PATH.exists():
        raise FileNotFoundError(f"Info detector model not found: {INFO_DETECTOR_MODEL_PATH}")

    print(f"[DocumentProcessor] Loading info detector from {INFO_DETECTOR_MODEL_PATH}")
    model = YOLO(str(INFO_DETECTOR_MODEL_PATH))
    print(f"[DocumentProcessor] Info detector loaded successfully")
    return model


def get_classifier_model():
    """Get or initialize classifier model."""
    global _classifier_model
    if _classifier_model is None:
        _classifier_model = load_classifier_model()
    return _classifier_model


def get_info_detector_model():
    """Get or initialize info detector model."""
    global _info_detector_model
    if _info_detector_model is None:
        _info_detector_model = load_info_detector_model()
    return _info_detector_model


def image_bytes_to_cv2(image_bytes: bytes) -> Optional[np.ndarray]:
    """Convert image bytes to OpenCV format."""
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return image
    except Exception as e:
        print(f"[DocumentProcessor] Error converting image bytes: {e}")
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
        print(f"[DocumentProcessor] Error converting image to bytes: {e}")
        return b""


def classify_document(image: np.ndarray) -> Tuple[str, float]:
    """Classify document type using Envelope_box_detection.pt.

    Args:
        image: OpenCV image (BGR)

    Returns:
        (service_type, confidence)
        service_type: "LETTER" or "GOODS"
        confidence: confidence score (0.0-1.0)
    """
    try:
        model = get_classifier_model()
        results = model(image, verbose=False)

        if not results or len(results) == 0:
            print("[DocumentProcessor] No classification result")
            return "GOODS", 0.0

        result = results[0]

        # Get prediction class
        if hasattr(result, 'probs') and result.probs is not None:
            # Classification model output
            class_id = result.probs.top1
            confidence = float(result.probs.top1conf)
            class_name = result.names.get(class_id, "GOODS")
            print(f"[DocumentProcessor] Classified as: {class_name} (confidence: {confidence:.2f})")
            return class_name, confidence

        elif hasattr(result, 'boxes') and len(result.boxes) > 0:
            # Detection model fallback
            class_id = int(result.boxes.cls[0])
            confidence = float(result.boxes.conf[0])
            class_name = result.names.get(class_id, "GOODS")
            print(f"[DocumentProcessor] Classified as: {class_name} (confidence: {confidence:.2f})")
            return class_name, confidence

        else:
            print("[DocumentProcessor] Unknown classification result format")
            return "GOODS", 0.0

    except Exception as e:
        print(f"[DocumentProcessor] Classification error: {e}")
        return "GOODS", 0.0


def detect_info_region(image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Detect info region bounding box using info.pt.

    Args:
        image: OpenCV image (BGR)

    Returns:
        (x1, y1, x2, y2) bounding box, or None if detection failed
    """
    try:
        model = get_info_detector_model()
        results = model(image, verbose=False)

        if not results or len(results) == 0:
            print("[DocumentProcessor] No info region detected")
            return None

        result = results[0]

        # Get first detected box (largest/most confident)
        if hasattr(result, 'boxes') and len(result.boxes) > 0:
            boxes = result.boxes

            # Get first box (highest confidence by default)
            box = boxes[0]

            # Extract coordinates (x1, y1, x2, y2)
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            confidence = float(box.conf[0])

            print(f"[DocumentProcessor] Info region detected at ({x1}, {y1}, {x2}, {y2}), confidence: {confidence:.2f}")
            return (int(x1), int(y1), int(x2), int(y2))

        else:
            print("[DocumentProcessor] No boxes in detection result")
            return None

    except Exception as e:
        print(f"[DocumentProcessor] Info detection error: {e}")
        return None


def crop_region(image: np.ndarray, bbox: Tuple[int, int, int, int],
                padding: int = 0) -> np.ndarray:
    """Crop region from image based on bounding box.

    Args:
        image: OpenCV image (BGR)
        bbox: (x1, y1, x2, y2) bounding box
        padding: Extra pixels to add around bbox (optional)

    Returns:
        Cropped image region
    """
    try:
        x1, y1, x2, y2 = bbox
        h, w = image.shape[:2]

        # Apply padding with bounds checking
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(w, x2 + padding)
        y2 = min(h, y2 + padding)

        cropped = image[y1:y2, x1:x2]
        print(f"[DocumentProcessor] Cropped region: {cropped.shape}")
        return cropped

    except Exception as e:
        print(f"[DocumentProcessor] Crop error: {e}")
        return image


def process_document(image_bytes: bytes, padding: int = 10) -> dict:
    """Main pipeline: Classify + Detect info region + Crop.

    Args:
        image_bytes: Input image bytes
        padding: Extra padding around info region (pixels)

    Returns:
        {
            "success": bool,
            "service_type": str,  # "LETTER" or "GOODS"
            "service_confidence": float,
            "info_bbox": tuple or None,  # (x1, y1, x2, y2)
            "info_region_bytes": bytes,  # Cropped image for OCR input
            "original_image_bytes": bytes,  # Original image (unchanged)
            "error": str or None
        }
    """
    try:
        # Step 1: Load image
        image = image_bytes_to_cv2(image_bytes)
        if image is None:
            return {
                "success": False,
                "service_type": None,
                "service_confidence": 0.0,
                "info_bbox": None,
                "info_region_bytes": b"",
                "original_image_bytes": image_bytes,
                "error": "Failed to load image"
            }

        print(f"[DocumentProcessor] Image loaded: {image.shape}")

        # Step 2: Classify document type
        service_type, service_confidence = classify_document(image)

        # Step 3: Detect info region
        info_bbox = detect_info_region(image)

        if info_bbox is None:
            return {
                "success": False,
                "service_type": service_type,
                "service_confidence": service_confidence,
                "info_bbox": None,
                "info_region_bytes": b"",
                "original_image_bytes": image_bytes,
                "error": "Failed to detect info region"
            }

        # Step 4: Crop info region
        cropped_image = crop_region(image, info_bbox, padding=padding)
        cropped_bytes = cv2_to_image_bytes(cropped_image)

        print(f"[DocumentProcessor] Processing complete")
        return {
            "success": True,
            "service_type": service_type,
            "service_confidence": float(service_confidence),
            "info_bbox": info_bbox,
            "info_region_bytes": cropped_bytes,
            "original_image_bytes": image_bytes,
            "error": None
        }

    except Exception as e:
        print(f"[DocumentProcessor] Processing error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "service_type": None,
            "service_confidence": 0.0,
            "info_bbox": None,
            "info_region_bytes": b"",
            "original_image_bytes": image_bytes,
            "error": str(e)
        }
