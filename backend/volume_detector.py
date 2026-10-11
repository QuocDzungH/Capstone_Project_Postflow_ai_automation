"""Volume detection from box images using edge detection.

Process:
1. Load 3 images (length, width, height sides)
2. Detect edges using Canny
3. Find leftmost/rightmost edge points on a line
4. Convert pixel distance to cm using calibration ratio
5. Return (length_cm, width_cm, height_cm)
6. Draw edge lines on image for visualization
"""
import cv2
import numpy as np
from io import BytesIO
import base64


def detect_dimension_from_image(image_bytes: bytes, cm_per_pixel: float, y_ratio: float = 0.55, draw_edges: bool = False) -> tuple[float, bytes] | float:
    """Detect one dimension from image and optionally draw edges.

    Args:
        image_bytes: Image file bytes
        cm_per_pixel: Calibration ratio (cm per pixel)
        y_ratio: Vertical position ratio (0.57 = ~57% from top)
        draw_edges: If True, return (dimension_cm, annotated_image_bytes)

    Returns:
        If draw_edges=False: Dimension in cm, or None if detection failed
        If draw_edges=True: (dimension_cm, annotated_image_bytes) or (None, original_image_bytes)
    """
    # Load image from bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        return (None, image_bytes) if draw_edges else None

    h, w, _ = image.shape

    # Line position (57% from top)
    y = int(y_ratio * h)

    # Extract line pixels
    line_pixels = image[y, :, :]

    # Convert to grayscale
    gray_line = cv2.cvtColor(line_pixels.reshape(1, w, 3), cv2.COLOR_BGR2GRAY)

    # Optional: Reduce noise with Gaussian blur (comment out if too blurry)
    # blurred_line = cv2.GaussianBlur(gray_line, (5, 5), 0)

    # Edge detection (Canny) - lower threshold to detect faint edges
    edges_line = cv2.Canny(gray_line, 30, 100)

    # Find edge positions (pixels where edge exists)
    edge_positions = np.where(edges_line[0] > 0)[0]

    if len(edge_positions) == 0:
        return (None, image_bytes) if draw_edges else None

    # Find leftmost and rightmost edges
    leftmost = np.min(edge_positions)
    rightmost = np.max(edge_positions)

    # Calculate pixel distance
    pixel_distance = rightmost - leftmost

    # Convert to cm
    real_distance_cm = float(pixel_distance * cm_per_pixel)

    # Draw edges if requested
    if draw_edges:
        image_copy = image.copy()
        # Draw horizontal line at detection position
        cv2.line(image_copy, (0, y), (w, y), (0, 255, 0), 2)
        # Draw vertical lines at leftmost and rightmost edges
        cv2.line(image_copy, (leftmost, y - 50), (leftmost, y + 50), (0, 0, 255), 3)
        cv2.line(image_copy, (rightmost, y - 50), (rightmost, y + 50), (0, 0, 255), 3)
        # Add text showing detected distance
        text = f"{real_distance_cm:.2f} cm"
        cv2.putText(image_copy, text, (leftmost + 10, y - 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Convert back to bytes
        _, buffer = cv2.imencode('.jpg', image_copy)
        annotated_bytes = buffer.tobytes()
        return (real_distance_cm, annotated_bytes)

    return real_distance_cm


def detect_dimensions_with_images(image_bytes_list: list[bytes], cm_per_pixel: float) -> dict:
    """Detect dimensions and return annotated images with edges drawn.

    Args:
        image_bytes_list: List of 3 image bytes [length, width, height]
        cm_per_pixel: Calibration ratio

    Returns:
        {
            "length_cm": float,
            "width_cm": float,
            "height_cm": float,
            "volume_cm3": float,
            "status": "success" | "partial" | "failed",
            "errors": [list of failed dimensions],
            "length_image": base64_image,
            "width_image": base64_image,
            "height_image": base64_image
        }
    """
    if len(image_bytes_list) != 3:
        return {
            "status": "failed",
            "error": "Cần 3 ảnh (dài, rộng, cao)"
        }

    results = {}
    errors = []
    images = {}
    dimension_names = ["length_cm", "width_cm", "height_cm"]
    image_keys = ["length_image", "width_image", "height_image"]

    for image_bytes, dim_name, img_key in zip(image_bytes_list, dimension_names, image_keys):
        try:
            dimension, annotated_image = detect_dimension_from_image(image_bytes, cm_per_pixel, draw_edges=True)
            if isinstance(dimension, tuple):
                dimension, annotated_image = dimension

            if dimension is None or dimension <= 0:
                errors.append(f"{dim_name}: không phát hiện được cạnh")
                results[dim_name] = None
                images[img_key] = "data:image/jpeg;base64," + base64.b64encode(annotated_image).decode()
            else:
                results[dim_name] = round(dimension, 2)
                images[img_key] = "data:image/jpeg;base64," + base64.b64encode(annotated_image).decode()
        except Exception as e:
            errors.append(f"{dim_name}: {str(e)}")
            results[dim_name] = None
            images[img_key] = None

    # Determine status
    if all(v is not None for v in [results["length_cm"], results["width_cm"], results["height_cm"]]):
        status = "success"
        volume = results["length_cm"] * results["width_cm"] * results["height_cm"]
        results["volume_cm3"] = round(volume, 2)
    elif any(v is not None for v in results.values()):
        status = "partial"
    else:
        status = "failed"

    results["status"] = status
    if errors:
        results["errors"] = errors

    # Add annotated images
    results.update(images)

    return results


def detect_dimensions(image_bytes_list: list[bytes], cm_per_pixel: float) -> dict:
    """Detect 3 dimensions from 3 images.

    Args:
        image_bytes_list: List of 3 image bytes [length, width, height]
        cm_per_pixel: Calibration ratio

    Returns:
        {
            "length_cm": float,
            "width_cm": float,
            "height_cm": float,
            "volume_cm3": float,
            "status": "success" | "partial" | "failed",
            "errors": [list of failed dimensions]
        }
    """
    if len(image_bytes_list) != 3:
        return {
            "status": "failed",
            "error": "Cần 3 ảnh (dài, rộng, cao)"
        }

    results = {}
    errors = []
    dimension_names = ["length_cm", "width_cm", "height_cm"]

    for i, (image_bytes, dim_name) in enumerate(zip(image_bytes_list, dimension_names)):
        try:
            dimension = detect_dimension_from_image(image_bytes, cm_per_pixel)
            if dimension is None or dimension <= 0:
                errors.append(f"{dim_name}: không phát hiện được cạnh")
                results[dim_name] = None
            else:
                results[dim_name] = round(dimension, 2)
        except Exception as e:
            errors.append(f"{dim_name}: {str(e)}")
            results[dim_name] = None

    # Determine status
    if all(v is not None for v in [results["length_cm"], results["width_cm"], results["height_cm"]]):
        status = "success"
        volume = results["length_cm"] * results["width_cm"] * results["height_cm"]
        results["volume_cm3"] = round(volume, 2)
    elif any(v is not None for v in results.values()):
        status = "partial"
    else:
        status = "failed"

    results["status"] = status
    if errors:
        results["errors"] = errors

    return results
