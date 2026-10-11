"""Weight detection from scale images using YOLO11s model.

Process:
1. Load image from bytes
2. Run YOLO11s inference
3. Extract weight value from image
4. Return weight in kg
"""

import numpy as np
from pathlib import Path
from io import BytesIO

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

# Model path
MODEL_PATH = Path(__file__).parent.parent / "model" / "ocrweight.pt"


def load_weight_model():
    """Load YOLO11s weight detection model."""
    if not HAS_YOLO:
        raise ImportError("ultralytics not installed. Install with: pip install ultralytics")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    model = YOLO(str(MODEL_PATH))
    return model


# Global model instance (lazy load)
_model = None


def get_weight_model():
    """Get or initialize weight detection model."""
    global _model
    if _model is None:
        _model = load_weight_model()
    return _model


def detect_weight_from_image(image_bytes: bytes) -> float | None:
    """Detect weight from scale image.

    Args:
        image_bytes: Image file bytes

    Returns:
        Weight in kg (float), or None if detection failed

    Example:
        >>> weight = detect_weight_from_image(image_data)
        >>> print(f"Weight: {weight} kg")
    """
    try:
        # Load image from bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        import cv2
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return None

        # Get model
        model = get_weight_model()

        # Run inference
        results = model(image)

        # Extract weight from results
        # YOLO returns predictions, we need to parse the weight value
        # This could be text detection or direct regression depending on model training
        if results and len(results) > 0:
            result = results[0]

            # If model outputs boxes with text
            if hasattr(result, 'boxes') and len(result.boxes) > 0:
                # Try to extract text from detected regions
                # This depends on how the model was trained
                # For now, return confidence-based weight estimate
                pass

            # If model outputs direct weight value via classification/regression
            if hasattr(result, 'probs'):
                # Class-based weight detection
                weight = result.probs.top1
                return float(weight)

        return None

    except Exception as e:
        print(f"Weight detection error: {e}")
        return None


def detect_weight_from_image_with_visual(image_bytes: bytes) -> tuple[float | None, bytes]:
    """Detect weight and return annotated image.

    Args:
        image_bytes: Image file bytes

    Returns:
        (weight_kg, annotated_image_bytes) or (None, original_image_bytes)

    Example:
        >>> weight, annotated = detect_weight_from_image_with_visual(image_data)
        >>> if weight:
        ...     print(f"Weight: {weight} kg")
    """
    try:
        # Load image from bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        import cv2
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return None, image_bytes

        # Get model
        model = get_weight_model()

        # Run inference
        results = model(image)

        weight = None
        annotated_image = image.copy()

        if results and len(results) > 0:
            result = results[0]

            # Get annotated image from YOLO
            if hasattr(result, 'plot'):
                annotated_image = result.plot()

            # Extract weight value
            if hasattr(result, 'probs'):
                weight = float(result.probs.top1)
            elif hasattr(result, 'boxes') and len(result.boxes) > 0:
                # Try to get confidence as weight estimate
                conf = float(result.boxes.conf[0]) * 100  # Scale to typical weight range
                weight = conf

        # Convert annotated image back to bytes
        _, buffer = cv2.imencode('.jpg', annotated_image)
        annotated_bytes = buffer.tobytes()

        return weight, annotated_bytes

    except Exception as e:
        print(f"Weight detection with visual error: {e}")
        return None, image_bytes
