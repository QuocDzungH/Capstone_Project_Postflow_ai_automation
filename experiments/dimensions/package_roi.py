import cv2


def expand_box(box, image_shape, expand_ratio=0.10):

    x1, y1, x2, y2 = box

    h, w = image_shape[:2]

    box_width = x2 - x1
    box_height = y2 - y1

    expand_x = int(box_width * expand_ratio)
    expand_y = int(box_height * expand_ratio)

    new_x1 = max(0, x1 - expand_x)
    new_y1 = max(0, y1 - expand_y)

    new_x2 = min(w, x2 + expand_x)
    new_y2 = min(h, y2 + expand_y)

    return (
        new_x1,
        new_y1,
        new_x2,
        new_y2
    )


def extract_roi(
    image,
    package,
    expand_ratio=0.10
):

    if package is None:
        return None, None

    # BBOX package
    box = package["box"]

    # Mở rộng bbox
    roi_box = expand_box(
        box,
        image.shape,
        expand_ratio
    )

    x1, y1, x2, y2 = roi_box

    # Cắt ROI
    roi = image[
        y1:y2,
        x1:x2
    ].copy()

    if roi.size == 0:
        return None, None

    return roi, roi_box