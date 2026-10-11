from person_detector import PersonDetector
from hand_detector import HandDetector
from package_detector import PackageDetector
from package_roi import extract_roi


class FrameProcessor:

    def __init__(
        self,
        person_model,
        hand_model,
        package_model,
        person_conf=0.4,
        hand_conf=0.3,
        package_conf=0.4,
        roi_expand=0.10
    ):
        self.person_detector = PersonDetector(
            person_model,
            person_conf
        )

        self.hand_detector = HandDetector(
            hand_model,
            hand_conf
        )

        self.package_detector = PackageDetector(
            package_model,
            package_conf
        )

        self.roi_expand = roi_expand

    def process(self, frame):

        # ==========================================
        # 1. DETECT NGƯỜI
        # ==========================================

        persons = self.person_detector.detect(frame)

        # ==========================================
        # 2. LOẠI NGƯỜI
        # ==========================================

        person_removed = self.person_detector.remove_person(
            frame,
            persons
        )

        # ==========================================
        # 3. DETECT TAY
        # ==========================================

        hands = self.hand_detector.detect(
            person_removed
        )

        # ==========================================
        # 4. LOẠI TAY
        # ==========================================

        hand_removed = self.hand_detector.remove_hands(
            person_removed,
            hands
        )

        # ==========================================
        # 5. DETECT PACKAGE
        # ==========================================

        packages = self.package_detector.detect(
            hand_removed
        )

        # ==========================================
        # 6. CHỌN PACKAGE LỚN NHẤT
        # ==========================================

        package = self.package_detector.get_largest_package(
            packages
        )

        # ==========================================
        # 7. LẤY ROI + MỞ RỘNG 10%
        # ==========================================

        roi, roi_box = extract_roi(
            hand_removed,
            package,
            self.roi_expand
        )

        return {
            "persons": persons,
            "hands": hands,
            "packages": packages,
            "package": package,

            "person_removed": person_removed,
            "hand_removed": hand_removed,

            "roi": roi,
            "roi_box": roi_box
        }