import cv2
import numpy as np

# ============================================================
# CẤU HÌNH
# ============================================================

CANNY_LOW = 50
CANNY_HIGH = 150

# Số đường quét quanh vùng giữa ROI
NUM_LINES = 9

# Phạm vi quét: 25% kích thước quanh tâm
# Ví dụ chiều cao ROI = 400:
# sẽ quét khoảng từ 100 -> 300
SCAN_RANGE = 0.25

# Chỉ lấy cạnh gần biên ngoài của ROI.
# Phần giữa ROI thường chứa logo/chữ/họa tiết.
OUTER_SEARCH_RATIO = 0.35

# Các vị trí cạnh cách nhau <= giá trị này
# sẽ được gom thành cùng một cụm.
CLUSTER_DISTANCE = 8


# ============================================================
# GOM CÁC VỊ TRÍ CẠNH THÀNH CỤM
# ============================================================

def _cluster_positions(values):
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
# CHỌN CẠNH ỔN ĐỊNH NHẤT
# ============================================================

def _select_stable_edge(values, side):
    """
    side = "left" / "top"  -> ưu tiên vị trí nhỏ
    side = "right" / "bottom" -> ưu tiên vị trí lớn

    Ưu tiên số lần xuất hiện trong nhiều đường quét.
    """

    clusters = _cluster_positions(values)

    if not clusters:
        return None

    max_count = max(
        c["count"]
        for c in clusters
    )

    candidates = [
        c for c in clusters
        if c["count"] == max_count
    ]

    if side in ("left", "top"):
        best = min(
            candidates,
            key=lambda c: c["center"]
        )
    else:
        best = max(
            candidates,
            key=lambda c: c["center"]
        )

    return best["center"]


# ============================================================
# TÌM CẠNH NGOÀI TRÊN MỘT ĐƯỜNG
# ============================================================

def _get_outer_edges(edge_positions, length):
    if len(edge_positions) == 0:
        return None, None

    left_limit = int(length * OUTER_SEARCH_RATIO)
    right_limit = int(length * (1.0 - OUTER_SEARCH_RATIO))

    left_candidates = edge_positions[
        edge_positions <= left_limit
    ]

    right_candidates = edge_positions[
        edge_positions >= right_limit
    ]

    left = None
    right = None

    if len(left_candidates) > 0:
        left = int(np.min(left_candidates))

    if len(right_candidates) > 0:
        right = int(np.max(right_candidates))

    return left, right


# ============================================================
# FIND SPAN
# ============================================================

def find_span(
    image,
    orientation,
    canny_low=CANNY_LOW,
    canny_high=CANNY_HIGH
):
    """
    Bản thử nghiệm multi-line.

    horizontal:
        quét nhiều dòng ngang -> tìm cạnh trái/phải.

    vertical:
        quét nhiều cột dọc -> tìm cạnh trên/dưới.

    Kết quả giữ format:
        start
        end
        distance_px
        orientation
        center

    để main_multi.py có thể vẽ trực tiếp.
    """

    if image is None or image.size == 0:
        return None

    if orientation not in ("horizontal", "vertical"):
        raise ValueError(
            "orientation phải là 'horizontal' hoặc 'vertical'"
        )

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    h, w = gray.shape

    # --------------------------------------------------------
    # Xác định các đường quét
    # --------------------------------------------------------

    if orientation == "horizontal":
        center = h // 2
        half = int(h * SCAN_RANGE)

        start_pos = max(0, center - half)
        end_pos = min(h - 1, center + half)

        scan_positions = np.linspace(
            start_pos,
            end_pos,
            NUM_LINES
        ).astype(int)

        line_length = w

    else:
        center = w // 2
        half = int(w * SCAN_RANGE)

        start_pos = max(0, center - half)
        end_pos = min(w - 1, center + half)

        scan_positions = np.linspace(
            start_pos,
            end_pos,
            NUM_LINES
        ).astype(int)

        line_length = h

    # --------------------------------------------------------
    # Lưu cạnh từ tất cả các đường
    # --------------------------------------------------------

    left_samples = []
    right_samples = []

    debug_lines = []

    for scan_pos in scan_positions:

        if orientation == "horizontal":
            line = gray[scan_pos, :]
            line_img = line.reshape(1, -1)

        else:
            line = gray[:, scan_pos]
            line_img = line.reshape(-1, 1)

        edges = cv2.Canny(
            line_img,
            canny_low,
            canny_high
        )

        if orientation == "horizontal":
            positions = np.where(edges[0] > 0)[0]
        else:
            positions = np.where(edges[:, 0] > 0)[0]

        left, right = _get_outer_edges(
            positions,
            line_length
        )

        if left is not None:
            left_samples.append(left)

        if right is not None:
            right_samples.append(right)

        debug_lines.append({
            "position": int(scan_pos),
            "edges": positions.copy(),
            "left": left,
            "right": right
        })

    # --------------------------------------------------------
    # Phải có cạnh ở cả hai phía
    # --------------------------------------------------------

    if not left_samples or not right_samples:
        return None

    # --------------------------------------------------------
    # Chọn cạnh xuất hiện ổn định nhất
    # --------------------------------------------------------

    start = _select_stable_edge(
        left_samples,
        "left"
    )

    end = _select_stable_edge(
        right_samples,
        "right"
    )

    if start is None or end is None:
        return None

    distance_px = end - start

    if distance_px <= 0:
        return None

    return {
        "start": int(start),
        "end": int(end),
        "distance_px": int(distance_px),
        "orientation": orientation,
        "center": int(center),

        # Debug
        "scan_positions": scan_positions.tolist(),
        "left_samples": left_samples,
        "right_samples": right_samples,
        "debug_lines": debug_lines,
    }


# ============================================================
# TƯƠNG THÍCH VỚI CODE CŨ
# ============================================================

def find_horizontal_edges(
    image,
    canny_low=50,
    canny_high=150
):
    """
    Trả về:
        left, right, center_x, center_y, edges

    Giữ để có thể dùng với code cũ.
    """

    result = find_span(
        image,
        "horizontal",
        canny_low,
        canny_high
    )

    if result is None:
        return None, None, None, None

    return (
        result["start"],
        result["end"],
        None,
        result["center"]
    )


def find_vertical_edges(
    image,
    canny_low=50,
    canny_high=150
):
    """
    Trả về:
        top, bottom, center_x, center_y, edges

    Giữ để có thể dùng với code cũ.
    """

    result = find_span(
        image,
        "vertical",
        canny_low,
        canny_high
    )

    if result is None:
        return None, None, None, None

    return (
        result["start"],
        result["end"],
        result["center"],
        None
    )
