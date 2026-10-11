"""Smart Text Layout Analyzer - SPLIT FIRST, then merge within sides, then pair.

Correct Algorithm:
1. Split blocks by divider LINE (x < divider = LEFT, x >= divider = RIGHT)
2. Merge WITHIN each side separately (preserve LEFT/RIGHT distinction)
3. Pair LEFT ← RIGHT by y-overlap

This maintains proper left/right classification throughout!
"""

from typing import List, Dict, Tuple, Optional


class Block:
    """Represents a text block."""

    def __init__(self, text: str, x1: int, y1: int, x2: int, y2: int):
        self.text = text
        self.x1 = int(x1)
        self.y1 = int(y1)
        self.x2 = int(x2)
        self.y2 = int(y2)
        self.x_center = (x1 + x2) // 2
        self.y_center = (y1 + y2) // 2
        self.y_min = int(y1)
        self.y_max = int(y2)

    def y_overlaps_with(self, other: 'Block', threshold: float = 0.5) -> bool:
        """Check if y-ranges overlap significantly."""
        overlap_start = max(self.y_min, other.y_min)
        overlap_end = min(self.y_max, other.y_max)
        overlap_amount = max(0, overlap_end - overlap_start)

        self_height = self.y_max - self.y_min
        other_height = other.y_max - other.y_min

        if self_height == 0 or other_height == 0:
            return False

        overlap_ratio_self = overlap_amount / self_height
        overlap_ratio_other = overlap_amount / other_height

        return overlap_ratio_self >= threshold and overlap_ratio_other >= threshold


class TextLayoutAnalyzer:
    """Analyze text: SPLIT → MERGE within sides → PAIR"""

    def __init__(self):
        self.blocks = []
        self.layout_dict = {}
        self.raw_text = ""
        self.x_divider = None
        self.nguoi_gui_idx = None
        self.nguoi_nhan_idx = None

    def add_region(self, text: str, x1: int, y1: int, x2: int, y2: int):
        """Add detected text region (remove periods)."""
        text_cleaned = text.replace(".", "").strip()
        if text_cleaned:
            self.blocks.append(Block(text_cleaned, x1, y1, x2, y2))

    def _find_markers(self):
        """Find 'Người gửi' and 'Người nhận' markers."""
        for i, block in enumerate(self.blocks):
            text_lower = block.text.lower().strip()

            if 'người' in text_lower and 'gửi' in text_lower:
                self.nguoi_gui_idx = i
                self.x_divider = block.x_center
                print(f"\n[Divider] 'Người gửi' at index {i}, x={self.x_divider}")
                print(f"[Split] LEFT: x < {self.x_divider} | RIGHT: x >= {self.x_divider}")

            if 'người' in text_lower and 'nhận' in text_lower:
                self.nguoi_nhan_idx = i
                print(f"[Marker] 'Người nhận' at index {i}")

    def _merge_blocks_within_side(self, side_blocks: List[Block], side_name: str) -> List[Block]:
        """Merge blocks WITHIN one side (LEFT or RIGHT only)."""
        if not side_blocks:
            return []

        print(f"\n[Merge {side_name}] Merging {len(side_blocks)} blocks in {side_name} side...")

        merged = []
        used = set()

        for i, block in enumerate(side_blocks):
            if i in used:
                continue

            # Start new merged group
            group = [block]
            used.add(i)

            # Find all blocks that overlap with this one (transitively)
            changed = True
            while changed:
                changed = False
                for j, other in enumerate(side_blocks):
                    if j in used:
                        continue

                    # Check overlap with any block in group
                    for group_block in group:
                        if group_block.y_overlaps_with(other, threshold=0.5):
                            group.append(other)
                            used.add(j)
                            changed = True
                            break

            # Merge group: sort by x, combine text
            group.sort(key=lambda b: b.x_center)
            merged_text = " ".join([b.text for b in group])
            merged_x1 = min(b.x1 for b in group)
            merged_y1 = min(b.y1 for b in group)
            merged_x2 = max(b.x2 for b in group)
            merged_y2 = max(b.y2 for b in group)

            merged_block = Block(merged_text, merged_x1, merged_y1, merged_x2, merged_y2)
            merged.append(merged_block)

            print(f"  [{len(merged)}] {merged_text[:50]:50s} (x={merged_block.x_center})")

        print(f"[Merge {side_name}] Result: {len(merged)} merged blocks")
        return merged

    def organize(self) -> Dict[int, Dict[int, str]]:
        """Organize text: SPLIT first → MERGE within sides → PAIR."""
        if not self.blocks:
            return {}

        print("\n" + "="*80)
        print("TEXT LAYOUT: SPLIT FIRST → MERGE WITHIN SIDES → PAIR")
        print("="*80)

        # Step 1: Find markers
        print("\n[Step 1] Finding markers...")
        self._find_markers()

        if self.x_divider is None or self.nguoi_gui_idx is None:
            print("[ERROR] Could not find 'Người gửi'!")
            return {}

        # Determine section boundaries
        nguoi_nhan_start = self.nguoi_nhan_idx if self.nguoi_nhan_idx else len(self.blocks)

        self.layout_dict = {}
        row_idx = 1

        # ===== NGƯỜI GỬI SECTION =====
        print(f"\n[Step 2] === NGƯỜI GỬI SECTION (blocks 0-{nguoi_nhan_start-1}) ===")

        gui_blocks = self.blocks[:nguoi_nhan_start]

        # SPLIT by divider FIRST
        left_gui = [b for b in gui_blocks if b.x_center < self.x_divider]
        right_gui = [b for b in gui_blocks if b.x_center >= self.x_divider]

        print(f"[Split] LEFT: {len(left_gui)} blocks | RIGHT: {len(right_gui)} blocks")

        # MERGE within each side separately
        merged_left_gui = self._merge_blocks_within_side(left_gui, "LEFT")
        merged_right_gui = self._merge_blocks_within_side(right_gui, "RIGHT")

        # Sort LEFT by y (top to bottom)
        merged_left_gui.sort(key=lambda b: b.y_center)
        print(f"\n[Order] LEFT sorted TOP→BOTTOM:")
        for i, b in enumerate(merged_left_gui, 1):
            print(f"  [{i}] y={b.y_center:3d}: {b.text[:50]}")

        # PAIR LEFT ← RIGHT by y-overlap
        print(f"\n[Pairing] LEFT ← RIGHT:")
        used_right = set()

        for left_block in merged_left_gui:
            matching_right = []

            for i, right_block in enumerate(merged_right_gui):
                if i in used_right:
                    continue

                if left_block.y_overlaps_with(right_block, threshold=0.3):
                    matching_right.append(right_block)
                    used_right.add(i)

            # Create row
            self.layout_dict[row_idx] = {}
            col_idx = 1

            self.layout_dict[row_idx][col_idx] = left_block.text
            col_idx += 1

            for right_block in matching_right:
                self.layout_dict[row_idx][col_idx] = right_block.text
                col_idx += 1

            right_text = " ".join([b.text for b in matching_right])
            print(f"  Row {row_idx}: [{left_block.text:30s}] ← [{right_text}]")

            row_idx += 1

        # ===== NGƯỜI NHẬN SECTION =====
        if self.nguoi_nhan_idx:
            print(f"\n[Step 3] === NGƯỜI NHẬN SECTION (blocks {self.nguoi_nhan_idx+1}-end) ===")

            nhan_blocks = self.blocks[self.nguoi_nhan_idx+1:]

            # SPLIT by divider FIRST
            left_nhan = [b for b in nhan_blocks if b.x_center < self.x_divider]
            right_nhan = [b for b in nhan_blocks if b.x_center >= self.x_divider]

            print(f"[Split] LEFT: {len(left_nhan)} blocks | RIGHT: {len(right_nhan)} blocks")

            # MERGE within each side separately
            merged_left_nhan = self._merge_blocks_within_side(left_nhan, "LEFT")
            merged_right_nhan = self._merge_blocks_within_side(right_nhan, "RIGHT")

            # Sort RIGHT by y (FLIPPED)
            merged_right_nhan.sort(key=lambda b: b.y_center)
            print(f"\n[Order] RIGHT sorted TOP→BOTTOM (FLIPPED):")
            for i, b in enumerate(merged_right_nhan, 1):
                print(f"  [{i}] y={b.y_center:3d}: {b.text[:50]}")

            # PAIR RIGHT → LEFT (FLIPPED)
            print(f"\n[Pairing FLIPPED] RIGHT → LEFT:")
            used_left = set()

            for right_block in merged_right_nhan:
                matching_left = []

                for i, left_block in enumerate(merged_left_nhan):
                    if i in used_left:
                        continue

                    if right_block.y_overlaps_with(left_block, threshold=0.3):
                        matching_left.append(left_block)
                        used_left.add(i)

                # Create row
                self.layout_dict[row_idx] = {}
                col_idx = 1

                for left_block in matching_left:
                    self.layout_dict[row_idx][col_idx] = left_block.text
                    col_idx += 1

                self.layout_dict[row_idx][col_idx] = right_block.text
                col_idx += 1

                left_text = " ".join([b.text for b in matching_left])
                print(f"  Row {row_idx}: [{left_text:30s}] → [{right_block.text}]")

                row_idx += 1

        return self.layout_dict

    def reconstruct_raw_text(self) -> str:
        """Reconstruct raw text from organized layout."""
        if not self.layout_dict:
            return ""

        lines = []
        for row_idx in sorted(self.layout_dict.keys()):
            row_data = self.layout_dict[row_idx]
            words = []
            for col_idx in sorted(row_data.keys()):
                words.append(row_data[col_idx])
            line = " ".join(words)
            lines.append(line)

        self.raw_text = "\n".join(lines)
        return self.raw_text

    def print_layout(self):
        """Print organized layout."""
        print("\n" + "="*80)
        print("FINAL ORGANIZED LAYOUT")
        print("="*80)

        print(f"\n🔷 DIVIDER: x={self.x_divider}")

        print("\n📊 LAYOUT ARRAY:")
        print("-"*80)
        for row_idx in sorted(self.layout_dict.keys()):
            row_data = self.layout_dict[row_idx]
            row_str = " | ".join(f"[{col}]={text}"
                                for col, text in sorted(row_data.items()))
            print(f"Row {row_idx}: {row_str}")

        print("\n" + "="*80)
        print("📝 RAW TEXT:")
        print("="*80)
        print(self.raw_text)
        print("="*80 + "\n")

    def to_dict(self) -> dict:
        """Export as dict."""
        return {
            "layout": self.layout_dict,
            "raw_text": self.raw_text,
            "x_divider": self.x_divider,
            "total_rows": len(self.layout_dict),
            "total_blocks": len(self.blocks)
        }


def analyze_detected_regions(regions: List[Dict]) -> Tuple[Dict, str]:
    """Analyze detected regions."""
    analyzer = TextLayoutAnalyzer()

    for region in regions:
        analyzer.add_region(
            text=region['text'],
            x1=region['x1'],
            y1=region['y1'],
            x2=region['x2'],
            y2=region['y2']
        )

    analyzer.organize()
    analyzer.reconstruct_raw_text()

    return analyzer.layout_dict, analyzer.raw_text
