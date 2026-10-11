import cv2
import numpy as np

from frame_processor import FrameProcessor

# QUAN TRỌNG:
# File này dùng edge_detector_multi.py riêng,
# KHÔNG sửa edge_detector.py cũ.
from edge_detector_multi import find_span


# ============================================================
# CẤU HÌNH
# ============================================================

CAM1_INDEX = 2
CAM2_INDEX = 1

# Camera 1:
# 150 pixel = 29 cm
CM_PER_PIXEL_CAM1 = 9.5 / 150

ROI_EXPAND_RATIO = 0.10

CANNY_LOW = 50
CANNY_HIGH = 150


# ============================================================
# KHỞI TẠO PIPELINE
# ============================================================

processor_cam1 = FrameProcessor(
    person_model="models/person/yolo26n.pt",
    hand_model="models/hand/best.pt",
    package_model="models/package/best.pt"
)

processor_cam2 = FrameProcessor(
    person_model="models/person/yolo26n.pt",
    hand_model="models/hand/best.pt",
    package_model="models/package/best.pt"
)


# ============================================================
# ROI
# ============================================================

def expand_roi(
    image,
    package_box,
    ratio=0.10
):
    h, w = image.shape[:2]

    x1, y1, x2, y2 = map(
        int,
        package_box
    )

    bw = x2 - x1
    bh = y2 - y1

    expand_x = int(bw * ratio)
    expand_y = int(bh * ratio)

    rx1 = max(
        0,
        x1 - expand_x
    )

    ry1 = max(
        0,
        y1 - expand_y
    )

    rx2 = min(
        w,
        x2 + expand_x
    )

    ry2 = min(
        h,
        y2 + expand_y
    )

    roi = image[
        ry1:ry2,
        rx1:rx2
    ].copy()

    return roi, (
        rx1,
        ry1,
        rx2,
        ry2
    )


# ============================================================
# CAMERA 1
# ============================================================

def measure_camera1(frame):

    results = processor_cam1.process(
        frame
    )

    package = results["package"]

    if package is None:
        return None

    package_box = package["box"]

    roi, roi_box = expand_roi(
        frame,
        package_box,
        ROI_EXPAND_RATIO
    )

    rx1, ry1, rx2, ry2 = roi_box

    if roi.size == 0:
        return None

    # --------------------------------------------------------
    # MULTI-LINE EDGE
    # --------------------------------------------------------

    horizontal = find_span(
        roi,
        "horizontal",
        CANNY_LOW,
        CANNY_HIGH
    )

    vertical = find_span(
        roi,
        "vertical",
        CANNY_LOW,
        CANNY_HIGH
    )

    result = {
        "frame": frame.copy(),
        "roi": roi.copy(),
        "roi_box": roi_box,
        "package_box": package_box,

        "ngang_1_px": None,
        "ngang_1_cm": None,

        "doc_1_px": None,
        "doc_1_cm": None,

        "ngang_points_global": None,
        "doc_points_global": None,

        "horizontal_debug": horizontal,
        "vertical_debug": vertical,

        "center_global": (
            rx1 + roi.shape[1] // 2,
            ry1 + roi.shape[0] // 2
        )
    }

    # --------------------------------------------------------
    # NGANG 1
    # --------------------------------------------------------

    if horizontal is not None:

        left = horizontal["start"]
        right = horizontal["end"]
        center_y = horizontal["center"]

        left_global = (
            rx1 + left,
            ry1 + center_y
        )

        right_global = (
            rx1 + right,
            ry1 + center_y
        )

        px = right - left
        cm = px * CM_PER_PIXEL_CAM1

        result["ngang_1_px"] = px
        result["ngang_1_cm"] = cm

        result["ngang_points_global"] = (
            left_global,
            right_global
        )

    # --------------------------------------------------------
    # DỌC 1
    # --------------------------------------------------------

    if vertical is not None:

        top = vertical["start"]
        bottom = vertical["end"]
        center_x = vertical["center"]

        top_global = (
            rx1 + center_x,
            ry1 + top
        )

        bottom_global = (
            rx1 + center_x,
            ry1 + bottom
        )

        px = bottom - top
        cm = px * CM_PER_PIXEL_CAM1

        result["doc_1_px"] = px
        result["doc_1_cm"] = cm

        result["doc_points_global"] = (
            top_global,
            bottom_global
        )

    return result


# ============================================================
# CAMERA 2
# ============================================================

def measure_camera2(
    frame,
    ngang_1_cm
):

    results = processor_cam2.process(
        frame
    )

    package = results["package"]

    if package is None:
        return None

    package_box = package["box"]

    roi, roi_box = expand_roi(
        frame,
        package_box,
        ROI_EXPAND_RATIO
    )

    rx1, ry1, rx2, ry2 = roi_box

    if roi.size == 0:
        return None

    horizontal = find_span(
        roi,
        "horizontal",
        CANNY_LOW,
        CANNY_HIGH
    )

    vertical = find_span(
        roi,
        "vertical",
        CANNY_LOW,
        CANNY_HIGH
    )

    result = {
        "frame": frame.copy(),
        "roi": roi.copy(),
        "roi_box": roi_box,
        "package_box": package_box,

        "doc_2_px": None,
        "doc_2_cm": None,

        "ngang_2_px": None,
        "ngang_2_cm": None,

        "doc_points_global": None,
        "ngang_points_global": None,

        "scale_cam2": None,

        "horizontal_debug": horizontal,
        "vertical_debug": vertical
    }

    # --------------------------------------------------------
    # DỌC 2
    # --------------------------------------------------------

    if vertical is not None:

        top = vertical["start"]
        bottom = vertical["end"]
        center_x = vertical["center"]

        doc_2_px = bottom - top

        result["doc_2_px"] = doc_2_px

        result["doc_points_global"] = (
            (
                rx1 + center_x,
                ry1 + top
            ),
            (
                rx1 + center_x,
                ry1 + bottom
            )
        )

        if (
            ngang_1_cm is not None
            and doc_2_px > 0
        ):

            scale = (
                ngang_1_cm
                / doc_2_px
            )

            result["scale_cam2"] = scale

            result["doc_2_cm"] = (
                doc_2_px * scale
            )

            # ------------------------------------------------
            # NGANG 2
            # ------------------------------------------------

            if horizontal is not None:

                left = horizontal["start"]
                right = horizontal["end"]
                center_y = horizontal["center"]

                ngang_2_px = right - left

                result["ngang_2_px"] = (
                    ngang_2_px
                )

                result["ngang_2_cm"] = (
                    ngang_2_px * scale
                )

                result["ngang_points_global"] = (
                    (
                        rx1 + left,
                        ry1 + center_y
                    ),
                    (
                        rx1 + right,
                        ry1 + center_y
                    )
                )

    return result


# ============================================================
# THỂ TÍCH
# ============================================================

def calculate_volume(
    ngang_1,
    doc_1,
    ngang_2
):

    if (
        ngang_1 is None
        or doc_1 is None
        or ngang_2 is None
    ):
        return None

    return (
        ngang_1
        * doc_1
        * ngang_2
    )


# ============================================================
# VẼ KẾT QUẢ
# ============================================================

def draw_result(
    image,
    data,
    title
):

    result = image.copy()

    rx1, ry1, rx2, ry2 = (
        data["roi_box"]
    )

    # Package bbox
    px1, py1, px2, py2 = (
        data["package_box"]
    )

    cv2.rectangle(
        result,
        (px1, py1),
        (px2, py2),
        (0, 255, 0),
        2
    )

    # ROI
    cv2.rectangle(
        result,
        (rx1, ry1),
        (rx2, ry2),
        (255, 255, 0),
        2
    )

    # --------------------------------------------------------
    # NGANG
    # --------------------------------------------------------

    points = data.get(
        "ngang_points_global"
    )

    if points is not None:

        p1, p2 = points

        cv2.line(
            result,
            p1,
            p2,
            (0, 255, 0),
            3
        )

        cv2.circle(
            result,
            p1,
            6,
            (0, 0, 255),
            -1
        )

        cv2.circle(
            result,
            p2,
            6,
            (255, 0, 0),
            -1
        )

    # --------------------------------------------------------
    # DỌC
    # --------------------------------------------------------

    points = data.get(
        "doc_points_global"
    )

    if points is not None:

        p1, p2 = points

        cv2.line(
            result,
            p1,
            p2,
            (255, 0, 0),
            3
        )

        cv2.circle(
            result,
            p1,
            6,
            (0, 0, 255),
            -1
        )

        cv2.circle(
            result,
            p2,
            6,
            (255, 0, 0),
            -1
        )

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    cv2.putText(
        result,
        title,
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2
    )

    if data.get("ngang_1_cm") is not None:
        cv2.putText(
            result,
            f"NGANG_1 = {data['ngang_1_cm']:.2f} cm",
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

    if data.get("doc_1_cm") is not None:
        cv2.putText(
            result,
            f"DOC_1 = {data['doc_1_cm']:.2f} cm",
            (20, 105),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 0, 0),
            2
        )


    if data.get("doc_2_cm") is not None:
        cv2.putText(
            result,
            f"DOC_2 = {data['doc_2_cm']:.2f} cm",
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 0, 0),
            2
        )

    if data.get("ngang_2_cm") is not None:
        cv2.putText(
            result,
            f"NGANG_2 = {data['ngang_2_cm']:.2f} cm",
            (20, 105),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

    return result


# ============================================================
# DEBUG: IN CÁC MẪU CẠNH
# ============================================================

def print_edge_debug(
    name,
    data
):

    edge = data.get(
        "horizontal_debug"
        if name == "horizontal"
        else "vertical"
    )

    if edge is None:
        print(
            f"{name}: KHÔNG TÌM THẤY"
        )
        return

    print(
        f"{name}: "
        f"{edge['start']} -> "
        f"{edge['end']} "
        f"({edge['distance_px']} px)"
    )

    print(
        "  samples start:",
        edge["left_samples"]
    )

    print(
        "  samples end  :",
        edge["right_samples"]
    )


# ============================================================
# MỞ CAMERA
# ============================================================

cap1 = cv2.VideoCapture(
    CAM1_INDEX
)

cap2 = cv2.VideoCapture(
    CAM2_INDEX
)

if not cap1.isOpened():
    print(
        f"Không mở được Camera 1 "
        f"(index={CAM1_INDEX})"
    )
    raise SystemExit

if not cap2.isOpened():
    print(
        f"Không mở được Camera 2 "
        f"(index={CAM2_INDEX})"
    )

    cap1.release()
    raise SystemExit


print(
    "======================================"
)

print(
    "MULTI-LINE EDGE TEST"
)

print(
    "SPACE : Chụp 2 camera và đo"
)

print(
    "Q     : Thoát"
)

print(
    "======================================"
)


# ============================================================
# VÒNG LẶP
# ============================================================

while True:

    ret1, frame1 = cap1.read()
    ret2, frame2 = cap2.read()

    if not ret1 or not ret2:
        print(
            "Không đọc được frame!"
        )
        break

    cv2.imshow(
        "Camera 1 - Live",
        frame1
    )

    cv2.imshow(
        "Camera 2 - Live",
        frame2
    )

    key = cv2.waitKey(1) & 0xFF

    # ========================================================
    # SPACE
    # ========================================================

    if key == 32:

        print(
            "\n======================================"
        )

        print(
            "CHUP VA DO - MULTI LINE"
        )

        print(
            "======================================"
        )

        # ----------------------------------------------------
        # CAMERA 1
        # ----------------------------------------------------

        cam1 = measure_camera1(
            frame1
        )

        if cam1 is None:

            print(
                "CAM 1: "
                "Không tìm thấy package/ROI"
            )

            continue

        print(
            "\n--- CAMERA 1 ---"
        )

        if cam1["ngang_1_px"] is not None:

            print(
                f"NGANG_1: "
                f"{cam1['ngang_1_px']:.1f} px "
                f"-> "
                f"{cam1['ngang_1_cm']:.2f} cm"
            )

        else:

            print(
                "NGANG_1: Không tìm thấy cạnh"
            )

        if cam1["doc_1_px"] is not None:

            print(
                f"DOC_1: "
                f"{cam1['doc_1_px']:.1f} px "
                f"-> "
                f"{cam1['doc_1_cm']:.2f} cm"
            )

        else:

            print(
                "DOC_1: Không tìm thấy cạnh"
            )

        print_edge_debug(
            "horizontal",
            cam1
        )

        print_edge_debug(
            "vertical",
            cam1
        )

        # ----------------------------------------------------
        # CAMERA 2
        # ----------------------------------------------------

        cam2 = measure_camera2(
            frame2,
            cam1["ngang_1_cm"]
        )

        if cam2 is None:

            print(
                "CAM 2: "
                "Không tìm thấy package/ROI"
            )

            continue

        print(
            "\n--- CAMERA 2 ---"
        )

        if cam2["doc_2_px"] is not None:

            print(
                f"DOC_2: "
                f"{cam2['doc_2_px']:.1f} px "
                f"-> "
                f"{cam2['doc_2_cm']:.2f} cm"
            )

        else:

            print(
                "DOC_2: Không tìm thấy cạnh"
            )

        if cam2["ngang_2_px"] is not None:

            print(
                f"NGANG_2: "
                f"{cam2['ngang_2_px']:.1f} px "
                f"-> "
                f"{cam2['ngang_2_cm']:.2f} cm"
            )

        else:

            print(
                "NGANG_2: Không tính được"
            )

        # ----------------------------------------------------
        # VẼ
        # ----------------------------------------------------
        doc_1 = cam1["doc_1_cm"] * (
            1 + 0.1 * (
                cam1["doc_1_cm"] - cam1["ngang_1_cm"]
        ) / min(
            cam1["doc_1_cm"],
            cam1["ngang_1_cm"]
            )
        )

        cam1["doc_1_cm"] = doc_1

        result1 = draw_result(
            frame1,
            cam1,
            "CAM 1 - MULTI LINE"
        )

        result2 = draw_result(
            frame2,
            cam2,
            "CAM 2 - MULTI LINE"
        )

        cv2.imshow(
            "CAM 1 - Multi Line Result",
            result1
        )

        cv2.imshow(
            "CAM 2 - Multi Line Result",
            result2
        )

        # ----------------------------------------------------
        # THỂ TÍCH
        # ----------------------------------------------------

        ngang_1 = cam1[
            "ngang_1_cm"
        ]
        
        doc_1 = cam1[
            "doc_1_cm"
        ] * (1 + 0.1 * (cam1["doc_1_cm"] - cam1["ngang_1_cm"]) / min(cam1["doc_1_cm"], cam1["ngang_1_cm"]))
        cam1["doc_1"] = doc_1 

        ngang_2 = cam2[
            "ngang_2_cm"
        ]

        volume = calculate_volume(
            ngang_1,
            doc_1,
            ngang_2
        )

        print(
            "\n======================================"
        )

        print(
            "KẾT QUẢ"
        )

        print(
            "======================================"
        )

        print(
            f"NGANG_1 = "
            f"{ngang_1:.2f} cm"
            if ngang_1 is not None
            else "NGANG_1 = --"
        )

        print(
            f"DOC_1 = "
            f"{doc_1:.2f} cm"
            if doc_1 is not None
            else "DOC_1 = --"
        )

        print(
            f"NGANG_2 = "
            f"{ngang_2:.2f} cm"
            if ngang_2 is not None
            else "NGANG_2 = --"
        )

        print(
            f"VOLUME = "
            f"{volume:.2f} cm3"
            if volume is not None
            else "VOLUME = --"
        )

        print(
            "======================================"
        )

    elif key == ord("q"):
        break


cap1.release()
cap2.release()

cv2.destroyAllWindows()
