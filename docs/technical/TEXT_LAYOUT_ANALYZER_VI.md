# TextLayoutAnalyzer - Giải Thích Chi Tiết (Tiếng Việt)

**File:** `backend/text_layout_analyzer.py` (325 dòng)

---

## **🎯 Mục Đích Chính**

TextLayoutAnalyzer **sắp xếp text OCR theo layout 2D**, từ các regions ngẫu nhiên thành **hàng × cột có logic**.

**Input:** List of text regions từ TrOCR
```python
[
  {"box": [10, 20, 100, 50], "text": "Tên"},
  {"box": [200, 20, 350, 50], "text": "John Doe"},
  {"box": [10, 60, 100, 90], "text": "SĐT"},
  {"box": [200, 60, 350, 90], "text": "0987654321"},
  ...
]
```

**Output:** Organized 2D layout + raw text
```python
{
  1: {1: "Tên", 2: "John Doe"},
  2: {1: "SĐT", 2: "0987654321"},
  ...
}
```

---

## **📍 Cơ Chế Hoạt Động: SPLIT → MERGE → PAIR**

### **Bước 1️⃣: SPLIT (Chia trái/phải)**

```
Tìm "Người gửi" marker → x_divider = x_center của nó

LEFT (x < divider)  |  DIVIDER  |  RIGHT (x >= divider)
Tên                 |           |  John Doe
SĐT                 |           |  0987654321
Địa chỉ             |           |  123 Main St
```

**Tại sao:** Postal form là 2 cột - **trái là labels, phải là values**

---

### **Bước 2️⃣: MERGE (Ghép lại)**

**Trong LEFT column:**
```
Blocks: ["Tên", "SĐT", "Địa", "chỉ"]
Lặp 1: "Tên" overlap "SĐT" → ghép ["Tên", "SĐT"]
Lặp 2: ["Tên", "SĐT"] overlap "Địa" → ghép thành ["Tên", "SĐT", "Địa"]
       ["Tên", "SĐT", "Địa"] overlap "chỉ" → ghép thành ["Tên", "SĐT", "Địa", "chỉ"]

Result: 1 merged block = "Tên SĐT Địa chỉ"
```

**Trong RIGHT column:**
```
Blocks: ["John Doe", "0987654321", "123", "Main", "St"]
Lặp 1: "John Doe" overlap "0987654321" → ghép ["John Doe", "0987654321"]
Lặp 2: ["John Doe", "0987654321"] NOT overlap "123" → riêng biệt
       
Result: 2 merged blocks:
  - "John Doe 0987654321"
  - "123 Main St"
```

**Quy tắc overlap:**
```python
def y_overlaps_with(self, other, threshold=0.5):
    overlap_amount = max(0, min(self.y_max, other.y_max) - max(self.y_min, other.y_min))
    overlap_ratio_self = overlap_amount / (self.y_max - self.y_min)
    overlap_ratio_other = overlap_amount / (other.y_max - other.y_min)
    return overlap_ratio_self >= 0.5 AND overlap_ratio_other >= 0.5
```

**Ví dụ:**
```
Block A: y=20-50 (height=30)
Block B: y=40-80 (height=40)

overlap = 50-40 = 10 pixels
ratio_A = 10/30 = 0.33 (33%)
ratio_B = 10/40 = 0.25 (25%)

0.33 < 0.5? YES → NOT overlap
```

---

### **Bước 3️⃣: PAIR (Ghép LEFT ← RIGHT)**

**Duyệt LEFT blocks, tìm RIGHT blocks có y-overlap:**

```
LEFT block: "Tên" (y=20-50)
├─ RIGHT "John Doe" (y=20-50)? overlap >= 0.3? YES → pair!
├─ RIGHT "123 Main St" (y=100-150)? overlap >= 0.3? NO

Row 1: {1: "Tên", 2: "John Doe"}

LEFT block: "SĐT Địa chỉ" (y=60-120)
├─ RIGHT "John Doe 0987654321" (y=40-90)? overlap >= 0.3? YES → pair!
├─ RIGHT "123 Main St" (y=100-150)? overlap >= 0.3? YES → pair!

Row 2: {1: "SĐT Địa chỉ", 2: "John Doe 0987654321", 3: "123 Main St"}
```

---

## **🔌 Các Class & Function**

### **Class 1: Block**

```python
class Block:
    def __init__(self, text: str, x1: int, y1: int, x2: int, y2: int):
        self.text = text
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.x_center = (x1 + x2) // 2  # Dùng để SPLIT LEFT/RIGHT
        self.y_center = (y1 + y2) // 2
        self.y_min, self.y_max = y1, y2
```

**Dùng cho:**
- `x_center`: So sánh với divider
- `y_center`: Sort top-to-bottom
- `y_min, y_max`: Check y-overlap

```python
    def y_overlaps_with(self, other: Block, threshold: float = 0.5) -> bool:
        # Tính overlap pixel
        overlap_start = max(self.y_min, other.y_min)
        overlap_end = min(self.y_max, other.y_max)
        overlap_amount = max(0, overlap_end - overlap_start)
        
        # Tính overlap ratio
        self_height = self.y_max - self.y_min
        other_height = other.y_max - other.y_min
        
        if self_height == 0 or other_height == 0:
            return False
        
        overlap_ratio_self = overlap_amount / self_height
        overlap_ratio_other = overlap_amount / other_height
        
        # **CẢ 2 phải >= threshold**
        return (overlap_ratio_self >= threshold and 
                overlap_ratio_other >= threshold)
```

**Ví dụ threshold:**
- **MERGE threshold = 0.5** (50% - strict) - Chỉ merge nếu thực sự cùng hàng
- **PAIR threshold = 0.3** (30% - relaxed) - Linh hoạt hơn khi pair LEFT-RIGHT

---

### **Class 2: TextLayoutAnalyzer**

```python
class TextLayoutAnalyzer:
    def __init__(self):
        self.blocks = []           # Tất cả detected blocks
        self.layout_dict = {}      # Output: {row: {col: text}}
        self.raw_text = ""         # Output: text string
        self.x_divider = None      # Divider x (từ "Người gửi")
        self.nguoi_gui_idx = None  # Index của "Người gửi"
        self.nguoi_nhan_idx = None # Index của "Người nhận"
```

---

## **🔍 Main Functions**

### **Hàm 1: _find_markers()**

```python
def _find_markers(self):
    """Tìm "Người gửi" và "Người nhận" markers."""
    
    for i, block in enumerate(self.blocks):
        text_lower = block.text.lower().strip()
        
        # Tìm "Người gửi"
        if 'người' in text_lower and 'gửi' in text_lower:
            self.nguoi_gui_idx = i
            self.x_divider = block.x_center  # ← KEY: Divider từ đây!
            print(f"[Divider] 'Người gửi' at x={self.x_divider}")
```

**Tại sao tìm "Người gửi"?**
- Đó là cột labels đầu tiên
- `x_center` của nó = boundary giữa LEFT (labels) và RIGHT (values)

**Ví dụ:**
```
Block "Người gửi": x1=10, x2=100
x_center = (10+100)/2 = 55

Divider = 55
LEFT (x < 55): ["Người gửi", "Tên", "SĐT", ...]
RIGHT (x >= 55): ["John Doe", "0987654321", ...]
```

---

### **Hàm 2: _merge_blocks_within_side()**

```python
def _merge_blocks_within_side(self, side_blocks, side_name):
    """Merge blocks TRONG 1 side (LEFT hoặc RIGHT)."""
    
    merged = []
    used = set()
    
    for i, block in enumerate(side_blocks):
        if i in used:
            continue  # Đã merge rồi
        
        # Bắt đầu group mới
        group = [block]
        used.add(i)
        
        # Tìm tất cả blocks overlap với group (transitive!)
        changed = True
        while changed:
            changed = False
            for j, other in enumerate(side_blocks):
                if j in used:
                    continue
                
                # Check overlap với BẤT KỲ block nào trong group
                for group_block in group:
                    if group_block.y_overlaps_with(other, threshold=0.5):
                        group.append(other)
                        used.add(j)
                        changed = True
                        break
        
        # Merge group: sort by x (left→right), join text
        group.sort(key=lambda b: b.x_center)
        merged_text = " ".join([b.text for b in group])
        
        # Bounding box: min/max of all blocks
        merged_x1 = min(b.x1 for b in group)
        merged_y1 = min(b.y1 for b in group)
        merged_x2 = max(b.x2 for b in group)
        merged_y2 = max(b.y2 for b in group)
        
        merged_block = Block(merged_text, merged_x1, merged_y1, merged_x2, merged_y2)
        merged.append(merged_block)
    
    return merged
```

**Ví dụ transitive merge:**
```
LEFT blocks: ["Người gửi", "Tên", "SĐT", "Địa chỉ"]
             y: 20-50,    20-50,  60-90, 60-90

Lặp 1:
  group = ["Người gửi"]
  "Người gửi" overlap "Tên"? (20-50, 20-50)? YES → group = ["Người gửi", "Tên"]
  ["Người gửi", "Tên"] overlap "SĐT"? NO
  
Lặp 2:
  group = ["SĐT"]
  "SĐT" overlap "Địa chỉ"? (60-90, 60-90)? YES → group = ["SĐT", "Địa chỉ"]

Result:
  ["Người gửi Tên", "SĐT Địa chỉ"] (2 merged blocks)
```

---

### **Hàm 3: organize() - MAIN LOGIC**

```python
def organize(self) -> Dict[int, Dict[int, str]]:
    """SPLIT → MERGE → PAIR"""
    
    # ===== NGƯỜI GỬI SECTION =====
    # Find divider
    self._find_markers()
    if self.x_divider is None:
        return {}
    
    gui_blocks = self.blocks[:self.nguoi_nhan_idx or len(self.blocks)]
    
    # STEP 1: SPLIT
    left_gui = [b for b in gui_blocks if b.x_center < self.x_divider]
    right_gui = [b for b in gui_blocks if b.x_center >= self.x_divider]
    
    # STEP 2: MERGE within each side
    merged_left_gui = self._merge_blocks_within_side(left_gui, "LEFT")
    merged_right_gui = self._merge_blocks_within_side(right_gui, "RIGHT")
    
    # STEP 3: PAIR (LEFT ← RIGHT)
    merged_left_gui.sort(key=lambda b: b.y_center)  # Top to bottom
    
    row_idx = 1
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
        
        row_idx += 1
    
    # ===== NGƯỜI NHẬN SECTION (FLIPPED) =====
    if self.nguoi_nhan_idx:
        nhan_blocks = self.blocks[self.nguoi_nhan_idx+1:]
        
        left_nhan = [b for b in nhan_blocks if b.x_center < self.x_divider]
        right_nhan = [b for b in nhan_blocks if b.x_center >= self.x_divider]
        
        merged_left_nhan = self._merge_blocks_within_side(left_nhan, "LEFT")
        merged_right_nhan = self._merge_blocks_within_side(right_nhan, "RIGHT")
        
        # FLIPPED: Iterate RIGHT first!
        merged_right_nhan.sort(key=lambda b: b.y_center)
        
        used_left = set()
        for right_block in merged_right_nhan:  # ← FLIPPED from NGƯỜI GỬI
            matching_left = []
            
            for i, left_block in enumerate(merged_left_nhan):
                if i in used_left:
                    continue
                
                if right_block.y_overlaps_with(left_block, threshold=0.3):
                    matching_left.append(left_block)
                    used_left.add(i)
            
            self.layout_dict[row_idx] = {}
            col_idx = 1
            
            for left_block in matching_left:
                self.layout_dict[row_idx][col_idx] = left_block.text
                col_idx += 1
            
            self.layout_dict[row_idx][col_idx] = right_block.text
            col_idx += 1
            
            row_idx += 1
    
    return self.layout_dict
```

**Tại sao NGƯỜI NHẬN FLIPPED?**

Trong một số form:
- **NGƯỜI GỬI:** Labels bên trái, Values bên phải
- **NGƯỜI NHẬN:** Layout có thể bị đảo (Values bên trái, Labels bên phải)

**Ví dụ:**
```
NGƯỜI GỬI:
Tên              John Doe      ← LEFT-RIGHT
SĐT              0987654321

NGƯỜI NHẬN:
Mary Smith       Tên           ← RIGHT-LEFT (FLIPPED!)
0912345678       SĐT
```

Nên khi pair NGƯỜI NHẬN, phải iterate RIGHT trước.

---

### **Hàm 4: reconstruct_raw_text()**

```python
def reconstruct_raw_text(self) -> str:
    """Convert layout_dict → text string."""
    
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
```

**Ví dụ:**
```
layout_dict = {
    1: {1: "Tên", 2: "John Doe"},
    2: {1: "SĐT", 2: "0987654321"},
}

raw_text = """Tên John Doe
SĐT 0987654321"""
```

---

### **Hàm 5: print_layout()**

```python
def print_layout(self):
    """Debug output - in layout ra console."""
    print(f"🔷 DIVIDER: x={self.x_divider}")
    print("📊 LAYOUT ARRAY:")
    for row_idx in sorted(self.layout_dict.keys()):
        row_data = self.layout_dict[row_idx]
        print(f"Row {row_idx}: {dict(sorted(row_data.items()))}")
    print("📝 RAW TEXT:")
    print(self.raw_text)
```

---

## **📊 Flow Diagram Đầy Đủ**

```
INPUT: List of regions from TrOCR
[
  {box: [10, 20, 100, 50], text: "Người gửi"},
  {box: [200, 20, 350, 50], text: "John Doe"},
  {box: [10, 60, 100, 90], text: "Tên"},
  {box: [200, 60, 350, 90], text: "Jane Smith"},
  ...
]
        ↓
    add_region() × N
        ↓
    organize()
    ├─ _find_markers()
    │   └─ x_divider = 55 (từ "Người gửi" x_center)
    │
    ├─ NGƯỜI GỬI SECTION:
    │   ├─ SPLIT:
    │   │   LEFT: ["Người gửi", "Tên"]
    │   │   RIGHT: ["John Doe", "Jane Smith"]
    │   │
    │   ├─ MERGE:
    │   │   LEFT → ["Người gửi Tên"]
    │   │   RIGHT → ["John Doe", "Jane Smith"]
    │   │
    │   └─ PAIR:
    │       ["Người gửi Tên"] ← ["John Doe"]
    │       (Jane Smith unpaired → separate row)
    │
    └─ NGƯỜI NHẬN SECTION:
        ├─ SPLIT (cùng divider)
        ├─ MERGE
        └─ PAIR (RIGHT → LEFT FLIPPED)
        ↓
layout_dict = {
    1: {1: "Người gửi Tên", 2: "John Doe"},
    2: {1: "", 2: "Jane Smith"},
    ...
}
        ↓
reconstruct_raw_text()
        ↓
raw_text = """Người gửi Tên John Doe
 Jane Smith
..."""
        ↓
OUTPUT: (layout_dict, raw_text)
```

---

## **🎯 Tại Sao Phải Có TextLayoutAnalyzer?**

**Bài toán:** OCR chỉ trả về danh sách blocks ngẫu nhiên, không biết layout

**Mà:**
- Claude cần organized text (structured) để extract chính xác
- Raw text chỉ có từng dòng lẻ tẻ không logic

**Giải pháp:** TextLayoutAnalyzer
- ✅ Organize text thành 2D layout (rows × cols)
- ✅ Preserve spatial relationships (trái/phải, trên/dưới)
- ✅ Output organized text để Claude parse tốt hơn

**Ví dụ:**

❌ **Không có TextLayoutAnalyzer:**
```
Raw OCR output:
Người gửi
John Doe
Tên
Jane Smith
SĐT
0987654321
Địa chỉ
123 Main St

Claude thấy: list lộn xộn, extract sai!
→ sender_name = "Tên" (SAI!)
```

✅ **Với TextLayoutAnalyzer:**
```
Organized output:
Người gửi John Doe
Tên Jane Smith
SĐT 0987654321
Địa chỉ 123 Main St

Claude thấy: layout logic clear:
→ sender_name = "John Doe" (ĐÚNG!)
```

---

## **⚙️ Threshold Tuning**

### **Khi nào adjust threshold?**

**Merge threshold (default 0.5):**
- ↑ Tăng (0.7): Chỉ merge nếu thực sự cùng hàng (strict)
- ↓ Hạ (0.3): Merge ngay cả lệch nhỏ (relaxed)

**PAIR threshold (default 0.3):**
- ↑ Tăng (0.5): Chỉ pair nếu overlap rõ
- ↓ Hạ (0.1): Pair ngay cả lệch lớn

### **Symptom & Fix:**

| Problem | Symptom | Fix |
|---------|---------|-----|
| **Merge không kịp** | Blocks không được ghép → quá nhiều rows | ↓ Merge threshold |
| **Merge quá nhiều** | Blocks khác hàng bị ghép → rows sai | ↑ Merge threshold |
| **PAIR miss** | LEFT không pair được RIGHT → empty cols | ↓ PAIR threshold |
| **PAIR sai** | LEFT pair với RIGHT khác hàng | ↑ PAIR threshold |

---

## **🧪 Debug Tips**

```python
# In debug info
analyzer.print_layout()

# Sẽ in:
# [Divider] x=55
# [Split] LEFT: 5 blocks | RIGHT: 6 blocks
# [Merge LEFT] Result: 2 merged blocks
# [Merge RIGHT] Result: 3 merged blocks
# [Pairing] Row 1: ["Người gửi Tên"] ← ["John Doe"]
# ...
# [Final] 8 rows
```

---

**Tóm lại:** TextLayoutAnalyzer chuyển chaos thành order! 🎯
