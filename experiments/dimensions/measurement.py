# ==========================================
# HỆ SỐ CAMERA 1
# ==========================================

CM_PER_PIXEL_CAM1 = 29 / 150


# ==========================================
# PIXEL -> CM
# ==========================================

def pixel_to_cm(
    pixel_distance,
    cm_per_pixel
):

    if pixel_distance is None:
        return None

    return (
        pixel_distance
        * cm_per_pixel
    )


# ==========================================
# CAMERA 1
# ==========================================

def measure_camera1(
    horizontal_result,
    vertical_result
):
    """
    Camera 1:

        Đường ngang giữa ROI
            -> NGANG_1

        Đường dọc giữa ROI
            -> DỌC_1

    Camera 1 dùng hệ số:

        29 / 150 cm/pixel
    """


    # ======================================
    # NGANG 1
    # ======================================

    if horizontal_result is not None:

        ngang_1_px = (
            horizontal_result[
                "distance_px"
            ]
        )

        ngang_1_cm = pixel_to_cm(

            ngang_1_px,

            CM_PER_PIXEL_CAM1
        )

    else:

        ngang_1_px = None

        ngang_1_cm = None


    # ======================================
    # DỌC 1
    # ======================================

    if vertical_result is not None:

        doc_1_px = (
            vertical_result[
                "distance_px"
            ]
        )

        doc_1_cm = pixel_to_cm(

            doc_1_px,

            CM_PER_PIXEL_CAM1
        )

    else:

        doc_1_px = None

        doc_1_cm = None


    # ======================================
    # TRẢ KẾT QUẢ
    # ======================================

    return {

        "ngang_1_px": ngang_1_px,

        "ngang_1_cm": ngang_1_cm,

        "doc_1_px": doc_1_px,

        "doc_1_cm": doc_1_cm
    }


# ==========================================
# CAMERA 2
# ==========================================

def measure_camera2(
    horizontal_result,
    vertical_result,
    ngang_1_cm,
    reference_mode="VERTICAL"
):
    """
    Camera 2 có 2 cách setup.

    ========================================================
    CASE 1: VERTICAL
    ========================================================

        NGANG_1 <-> DỌC_2

    Hai đoạn này là cùng một cạnh thực tế.

        DỌC_2_cm = NGANG_1_cm

    Sau đó:

        ratio =
            NGANG_2_pixel
            ----------------
             DỌC_2_pixel

    và:

        NGANG_2_cm =
            ratio * DỌC_2_cm


    ========================================================
    CASE 2: HORIZONTAL
    ========================================================

        NGANG_1 <-> NGANG_2

    Hai đoạn này là cùng một cạnh thực tế.

        NGANG_2_cm = NGANG_1_cm

    Sau đó:

        ratio =
            DỌC_2_pixel
            ----------------
            NGANG_2_pixel

    và:

        DỌC_2_cm =
            ratio * NGANG_2_cm


    ========================================================
    reference_mode
    ========================================================

        "VERTICAL"

            NGANG_1 <-> DỌC_2


        "HORIZONTAL"

            NGANG_1 <-> NGANG_2
    """


    # ======================================
    # KIỂM TRA INPUT
    # ======================================

    if (
        horizontal_result is None
        or vertical_result is None
        or ngang_1_cm is None
    ):

        return {

            "ngang_2_px": None,

            "doc_2_px": None,

            "ngang_2_cm": None,

            "doc_2_cm": None,

            "reference": None,

            "ratio": None
        }


    # ======================================
    # KIỂM TRA REFERENCE
    # ======================================

    if reference_mode not in [
        "VERTICAL",
        "HORIZONTAL"
    ]:

        raise ValueError(
            "reference_mode phải là "
            "'VERTICAL' hoặc 'HORIZONTAL'"
        )


    # ======================================
    # LẤY PIXEL CAMERA 2
    # ======================================

    ngang_2_px = (
        horizontal_result[
            "distance_px"
        ]
    )

    doc_2_px = (
        vertical_result[
            "distance_px"
        ]
    )


    # ======================================
    # KIỂM TRA PIXEL
    # ======================================

    if (
        ngang_2_px is None
        or doc_2_px is None
        or ngang_2_px <= 0
        or doc_2_px <= 0
    ):

        return {

            "ngang_2_px": ngang_2_px,

            "doc_2_px": doc_2_px,

            "ngang_2_cm": None,

            "doc_2_cm": None,

            "reference": None,

            "ratio": None
        }


    # ========================================================
    # CASE 1
    #
    # NGANG_1 <-> DỌC_2
    # ========================================================

    if reference_mode == "VERTICAL":

        # --------------------------------------
        # DỌC 2 THỰC TẾ
        #
        # Đây là cùng một cạnh với NGANG 1
        # --------------------------------------

        doc_2_cm = ngang_1_cm


        # --------------------------------------
        # TỶ LỆ TRÊN ẢNH CAMERA 2
        #
        # NGANG_2_pixel / DỌC_2_pixel
        # --------------------------------------

        ratio = (
            ngang_2_px
            / doc_2_px
        )


        # --------------------------------------
        # TÍNH NGANG 2
        # --------------------------------------

        ngang_2_cm = (
            ratio
            * doc_2_cm
        )


        # --------------------------------------
        # GHI NHẬN QUAN HỆ
        # --------------------------------------

        reference = (
            "NGANG_1 <-> DỌC_2"
        )


    # ========================================================
    # CASE 2
    #
    # NGANG_1 <-> NGANG_2
    # ========================================================

    else:

        # --------------------------------------
        # NGANG 2 THỰC TẾ
        #
        # Đây là cùng một cạnh với NGANG 1
        # --------------------------------------

        ngang_2_cm = ngang_1_cm


        # --------------------------------------
        # TỶ LỆ TRÊN ẢNH CAMERA 2
        #
        # DỌC_2_pixel / NGANG_2_pixel
        # --------------------------------------

        ratio = (
            doc_2_px
            / ngang_2_px
        )


        # --------------------------------------
        # TÍNH DỌC 2
        # --------------------------------------

        doc_2_cm = (
            ratio
            * ngang_2_cm
        )


        # --------------------------------------
        # GHI NHẬN QUAN HỆ
        # --------------------------------------

        reference = (
            "NGANG_1 <-> NGANG_2"
        )


    # ==========================================
    # TRẢ KẾT QUẢ
    # ==========================================

    return {

        # Pixel Camera 2

        "ngang_2_px": ngang_2_px,

        "doc_2_px": doc_2_px,


        # Kích thước thực tế

        "ngang_2_cm": ngang_2_cm,

        "doc_2_cm": doc_2_cm,


        # Thông tin tính toán

        "reference": reference,

        "ratio": ratio
    }


# ==========================================
# TÍNH THỂ TÍCH
# ==========================================

def calculate_volume(
    ngang_1_cm,
    doc_1_cm,
    ngang_2_cm
):
    """
    Thể tích:

        V =
            NGANG_1
            × DỌC_1
            × NGANG_2
    """


    # ======================================
    # KIỂM TRA
    # ======================================

    if (
        ngang_1_cm is None
        or doc_1_cm is None
        or ngang_2_cm is None
    ):

        return None


    # ======================================
    # TÍNH
    # ======================================

    volume = (
        ngang_1_cm
        * doc_1_cm
        * ngang_2_cm
    )


    return volume