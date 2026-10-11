# OCR Implementation - Giải Thích Từng Dòng Chi Tiết (Tiếng Việt)

Đây là giải thích kĩ từng dòng code của 4 file OCR chính.

---

## 📄 File 1: `backend/hybrid_ocr.py` (468 dòng)

### **Phần 1: Import & Setup (Dòng 1-46)**

```python
import os
import re
import json
import cv2
import torch
import numpy as np
from pathlib import Path
from PIL import Image
from io import BytesIO
```

**Các thư viện:**
- `os`: Tương tác hệ điều hành
- `re`: Regex - xử lý text
- `json`: Parse dữ liệu JSON
- `cv2`: OpenCV - xử lý ảnh
- `torch`: PyTorch - machine learning framework
- `numpy`: NumPy - xử lý array
- `Path`: Xử lý đường dẫn tệp
- `PIL.Image`: Thư viện ảnh
- `BytesIO`: Xử lý bytes

```python
try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False
```

**Try-except block:**
- Nếu easyocr installed → `HAS_EASYOCR = True`
- Nếu không → `HAS_EASYOCR = False`
- Cho phép chương trình chạy ngay cả khi thiếu thư viện

```python
try:
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    HAS_TROCR = True
except ImportError:
    HAS_TROCR = False
```

**TrOCR model:**
- `TrOCRProcessor`: Tiền xử lý ảnh
- `VisionEncoderDecoderModel`: Model chính (encoder + decoder)

```python
try:
    from anthropic import Anthropic
    HAS_CLAUDE = True
except ImportError:
    HAS_CLAUDE = False
```

**Claude API:**
- `Anthropic`: Client API để gọi Claude

```python
TROCR_MODEL_PATH = Path(__file__).parent.parent / "model" / "trocr-vietnamese-final"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
```

**Model path & device:**
- `TROCR_MODEL_PATH`: Đường dẫn model custom
- `DEVICE`: GPU nếu có, CPU nếu không

```python
_trocr_processor = None
_trocr_model = None
_text_detector = None
```

**Global cache:**
- Lưu model để không load lại nhiều lần
- Ban đầu None (lazy loading)

---

### **Phần 2: Load TrOCR Model (Dòng 48-74)**

```python
def load_trocr_model():
    """Load TrOCR processor and model."""
    global _trocr_processor, _trocr_model
    
    if _trocr_model is not None:
        return  # Đã load rồi
```

**Kiểm tra cache:**
- Nếu đã load → không load lại

```python
    if not HAS_TROCR:
        raise ImportError("transformers not installed. Install with: pip install transformers")
```

**Kiểm tra thư viện:**
- Nếu không install transformers → raise error

```python
    if not TROCR_MODEL_PATH.exists():
        raise FileNotFoundError(f"TrOCR model not found: {TROCR_MODEL_PATH}")
```

**Kiểm tra model file:**
- Nếu model file không tồn tại → raise error

```python
    print(f"[TrOCR] Loading from {TROCR_MODEL_PATH}")
    
    _trocr_processor = TrOCRProcessor.from_pretrained(
        str(TROCR_MODEL_PATH),
        local_files_only=True
    )
```

**Load processor:**
- `from_pretrained()`: Load từ local
- `local_files_only=True`: Không download từ internet

```python
    _trocr_model = VisionEncoderDecoderModel.from_pretrained(
        str(TROCR_MODEL_PATH),
        local_files_only=True
    )
```

**Load model:**
- VisionEncoderDecoderModel = encoder (xử lý vision) + decoder (sinh text)

```python
    _trocr_model.to(DEVICE)
    _trocr_model.eval()
```

**Setup model:**
- `.to(DEVICE)`: Move vào GPU/CPU
- `.eval()`: Chuyển sang mode evaluation (không dùng dropout, deterministic)

---

### **Phần 3: Load Text Detector (Dòng 76-86)**

```python
def load_text_detector():
    """Load EasyOCR text detector."""
    global _text_detector
    
    if not HAS_EASYOCR:
        raise ImportError("easyocr not installed. Install with: pip install easyocr")
    
    print("[TextDetector] Loading EasyOCR...")
    _text_detector = easyocr.Reader(
        ["en", "vi"],  # Support English + Vietnamese
        gpu=torch.cuda.is_available()
    )
    print("[TextDetector] Loaded successfully")
```

**Chi tiết:**
- `easyocr.Reader()`: Tạo reader object
- `["en", "vi"]`: Hỗ trợ 2 ngôn ngữ
- `gpu=True`: Dùng GPU nếu có

---

### **Phần 4: TrOCR Recognize Word (Dòng 88-114)**

```python
def trocr_recognize_word(image_pil) -> str:
    """Use TrOCR to recognize text from a single image crop."""
    
    if _trocr_processor is None or _trocr_model is None:
        load_trocr_model()  # Lazy load nếu chưa load
```

**Lazy loading:**
- Nếu chưa load → load ngay

```python
    try:
        pixel_values = _trocr_processor(
            images=image_pil,
            return_tensors="pt"
        ).pixel_values.to(DEVICE)
```

**Tiền xử lý ảnh:**
- Processor nhận PIL Image
- Return tensor (PyTorch format)
- `.to(DEVICE)`: Move vào GPU/CPU

```python
        with torch.no_grad():
            generated_ids = _trocr_model.generate(
                pixel_values,
                max_new_tokens=128
            )
```

**Generate text:**
- `torch.no_grad()`: Không tính gradient (faster, less memory)
- `.generate()`: Sinh text từ ảnh
- `max_new_tokens=128`: Max 128 tokens (ngăn chặn sinh vô hạn)

```python
        text = _trocr_processor.batch_decode(
            generated_ids,
            skip_special_tokens=True
        )[0].strip()
```

**Decode text:**
- `batch_decode()`: Chuyển token IDs → text
- `skip_special_tokens=True`: Bỏ các token đặc biệt (<PAD>, <EOS>, v.v.)
- `[0]`: Lấy item đầu tiên (batch_size=1)
- `.strip()`: Xóa leading/trailing spaces

```python
        return text if text else ""
        
    except Exception as e:
        print(f"[TrOCR] Recognition error: {e}")
        return ""
```

**Error handling:**
- Nếu error → return empty string

---

### **Phần 5: Detect Text Regions (Dòng 117-198)**

```python
def detect_text_regions(image_bytes: bytes) -> list[dict]:
    """Detect and recognize text regions using TrOCR.
    Returns: [{box: [x1,y1,x2,y2], text: "..."}, ...]
    """
    
    global _text_detector
    
    if _text_detector is None:
        load_text_detector()
```

**Lazy load text detector**

```python
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
```

**Load ảnh từ bytes:**
- `np.frombuffer()`: Bytes → numpy array
- `cv2.imdecode()`: Decode thành ảnh BGR

```python
        if image is None:
            return []
        
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width = image.shape[:2]
```

**Chuyển đổi ảnh:**
- BGR → RGB (OpenCV dùng BGR, PIL dùng RGB)
- Lấy dimensions

```python
        print("[TrOCR] Detecting text regions...")
        horizontal_list, free_list = _text_detector.detect(
            rgb_image,
            min_size=10,          # Bỏ qua regions < 10px
            text_threshold=0.5,   # Confidence text
            low_text=0.3          # Confidence text parts
        )
```

**Detect regions:**
- `horizontal_list`: Vùng text nằm ngang (hầu hết)
- `free_list`: Vùng text tự do (các góc khác)

```python
        horizontal_list = horizontal_list[0] if horizontal_list else []
        free_list = free_list[0] if free_list else []
```

**Extract boxes:**
- EasyOCR return format: [[list_of_boxes]]
- Lấy phần tử đầu tiên

```python
        boxes = []
        for box in horizontal_list:
            x1, x2, y1, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            boxes.append([x1, y1, x2, y2])
```

**Chuyển format boxes:**
- From: [x1, x2, y1, y2] → To: [x1, y1, x2, y2]

```python
        for poly in free_list:
            points = np.array(poly, dtype=np.int32)
            x, y, w, h = cv2.boundingRect(points)
            boxes.append([x, y, x + w, y + h])
```

**Polygon → bounding rectangle:**
- `cv2.boundingRect()`: Lấy bounding box từ polygon

```python
        boxes.sort(key=lambda b: (b[1], b[0]))
```

**Sort boxes:**
- `(y, x)`: Top-to-bottom, left-to-right reading order

```python
        results = []
        print(f"[TrOCR] Recognizing {len(boxes)} regions...")
        
        for idx, (x1, y1, x2, y2) in enumerate(boxes):
            x1 = max(0, x1 - int((x2-x1)*0.05))         # 5% left margin
            y1 = max(0, y1 - int((y2-y1)*0.2))          # 20% top margin
            x2 = min(width, x2 + int((x2-x1)*0.05))     # 5% right margin
            y2 = min(height, y2 + int((y2-y1)*0.2))     # 20% bottom margin
```

**Add margin:**
- Expand box slightly để TrOCR có full text context
- Giới hạn để không exceed image

```python
            if x2 <= x1 or y2 <= y1:
                continue
            
            crop = rgb_image[y1:y2, x1:x2]
            if crop.size == 0:
                continue
```

**Validate crop:**
- Skip nếu box invalid hoặc empty

```python
            pil_crop = Image.fromarray(crop)
            text = trocr_recognize_word(pil_crop)
```

**OCR crop:**
- Chuyển numpy → PIL Image
- Gọi TrOCR

```python
            if text:
                results.append({
                    "box": [x1, y1, x2, y2],
                    "text": text
                })
                print(f"  [{idx+1}] {text}")
        
        return results
```

**Return results:**
- List of {box, text} dicts

---

### **Phần 6: Clean OCR Text (Dòng 290-320)**

```python
def clean_ocr_text(text: str) -> str:
    """Clean OCR artifacts from text."""
    
    text = text.replace("=>", "").replace("->", "").replace("←", "")
```

**Xóa arrow symbols:**
- Những ký tự mà OCR nhầm lẫn

```python
    text = re.sub(r'([A-ZĐ][a-z]+):\s+([A-ZĐ])', r'\1 \2', text)
```

**Fix "Hà: Nội" → "Hà Nội":**
- Regex pattern: (chữ hoa)(chữ thường):space(chữ hoa)
- Replace bằng: (chữ hoa)(chữ thường)space(chữ hoa)
- Xóa đi dấu hai chấm

```python
    text = text.replace(": ", " ").replace(":\n", "\n")
    text = re.sub(r'\s+', ' ', text).strip()
```

**Clean whitespace:**
- Xóa dấu hai chấm thừa
- Consolidate multiple spaces

---

### **Phần 7: Organize Text Layout (Dòng 322-366)**

```python
def organize_text_layout(trocr_regions: list[dict]) -> tuple[dict, str]:
    """Organize detected text regions into 2D layout array."""
    
    from backend.text_layout_analyzer import TextLayoutAnalyzer
    
    analyzer = TextLayoutAnalyzer()
```

**Import TextLayoutAnalyzer:**
- Module riêng để organize layout

```python
    for region in trocr_regions:
        x1, y1, x2, y2 = region['box']
        analyzer.add_region(
            text=region['text'],
            x1=int(x1),
            y1=int(y1),
            x2=int(x2),
            y2=int(y2)
        )
```

**Add regions:**
- TextLayoutAnalyzer nhận tất cả regions

```python
    layout_dict = analyzer.organize()
    raw_text = analyzer.reconstruct_raw_text()
```

**Organize layout:**
- `organize()`: SPLIT → MERGE → PAIR logic
- `reconstruct_raw_text()`: Convert layout dict → text string

```python
    print("\n[Cleanup] Removing OCR artifacts...")
    cleaned_text = clean_ocr_text(raw_text)
    
    for row_idx in layout_dict:
        for col_idx in layout_dict[row_idx]:
            original = layout_dict[row_idx][col_idx]
            cleaned = clean_ocr_text(original)
            if original != cleaned:
                print(f"  Row {row_idx}, Col {col_idx}: '{original}' → '{cleaned}'")
            layout_dict[row_idx][col_idx] = cleaned
```

**Clean artifacts:**
- Xóa OCR artifacts từ text
- Update layout dict

---

### **Phần 8: Parse Text with Claude (Dòng 369-473)**

```python
def parse_organized_text_to_schema(organized_text: str) -> dict:
    """Parse organized OCR text into structured schema using Claude API."""
    
    print("\n[Claude Parse] Starting schema extraction...")
    
    if not HAS_CLAUDE:
        print("[Claude Parse] ❌ Claude not available")
        return {"missing_fields": ["all"]}
```

**Check Claude availability**

```python
    try:
        print("[Claude Parse] Creating Anthropic client...")
        client = Anthropic()
        print("[Claude Parse] ✅ Client created")
```

**Create Claude client:**
- Sẽ dùng API key từ environment

```python
        print("[Claude Parse] Building prompt...")
        prompt = """Parse this Vietnamese postal form text and extract structured information.

TEXT:
"""
        prompt += organized_text
        prompt += """

Extract and return ONLY a JSON object with these exact fields:
{
  "sender_name": "name or empty string",
  "sender_phone": "phone or empty string",
  "sender_province": "province/city or empty string",
  ...
}

Rules:
- Look for "Tên:" labels for names
- Look for "Điện thoại:" for phone numbers
- Look for "Địa chỉ:" for addresses
- Split address into: province, ward, detail
- Return empty string "" if field not found, never null
- Return ONLY the JSON object, nothing else"""
```

**Build prompt:**
- Instructions rõ ràng cho Claude
- Specify format output (JSON)

```python
        print("[Claude Parse] Calling Claude API...")
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        print("[Claude Parse] ✅ API response received")
```

**Call Claude:**
- `claude-sonnet-5`: Model nhanh + accurate
- `max_tokens=500`: Enough cho 11 fields

```python
        result_text = response.content[0].text
        print(f"[Claude Parse] Parsing response... ({len(result_text)} chars)")
        start = result_text.find('{')
        end = result_text.rfind('}') + 1
```

**Extract JSON:**
- Find first `{` và last `}`
- Ignore các text trước/sau

```python
        if start == -1 or end == 0:
            return {"missing_fields": ["all"]}
        
        result = json.loads(result_text[start:end])
```

**Parse JSON:**
- Chuyển JSON string → dict

```python
        required = ['sender_name', 'sender_phone', 'sender_province',
                   'receiver_name', 'receiver_phone', 'receiver_province']
        missing = [f for f in required if not result.get(f)]
        
        result['missing_fields'] = missing
```

**Identify missing fields:**
- Check 6 required fields
- Add missing list to result

```python
        print(f"\n[Claude Parse] ✅ Schema extraction:")
        print(f"  • Sender: {result.get('sender_name')} | {result.get('sender_phone')} | {result.get('sender_province')}")
        print(f"  • Receiver: {result.get('receiver_name')} | {result.get('receiver_phone')} | {result.get('receiver_province')}")
        print(f"  • Missing: {missing}")
        
        return result
        
    except Exception as e:
        print(f"[Claude Parse] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"missing_fields": ["all"]}
```

**Return & error handling**

---

### **Phần 9: Main Hybrid OCR (Dòng 476-568)**

```python
def hybrid_ocr(image_bytes: bytes) -> dict:
    """Hybrid OCR: Claude + TrOCR.
    
    Step 1: Claude API Vision OCR (parallel approach)
    Step 2: TrOCR Word-Level Detection
    Step 2.5: Organize Text Layout
    Step 3: Parse organized text with Claude API
    """
    
    print("\n" + "="*60)
    print("[Hybrid OCR] Starting hybrid OCR processing...")
    print("="*60)
```

**Header:**
- Pretty print để tracking progress

```python
    print("\n[Hybrid OCR] Step 1️⃣: Claude API Vision OCR")
    print("-" * 60)
    claude_result = claude_extract_fields(image_bytes)
```

**Step 1 (optional):**
- Claude Vision OCR (không dùng trong current flow)

```python
    print("\n[Hybrid OCR] Step 2️⃣: TrOCR Word-Level Detection")
    print("-" * 60)
    trocr_regions = detect_text_regions(image_bytes)
    trocr_texts = [r['text'] for r in trocr_regions]
    print(f"[TrOCR Result] Detected {len(trocr_texts)} raw words/phrases")
```

**Step 2:**
- TrOCR detects individual words
- Main OCR engine

```python
    print("\n[Hybrid OCR] Step 2️⃣.5️⃣: Organizing Text Layout")
    print("-" * 60)
    layout_dict, organized_raw_text = organize_text_layout(trocr_regions)
    
    print(f"[Layout] Organized into {len(layout_dict)} rows")
    print(f"[Layout] Reconstructed raw text:")
    print("-" * 60)
    for line in organized_raw_text.split('\n')[:15]:
        print(f"  {line}")
    if organized_raw_text.count('\n') > 15:
        print(f"  ... ({organized_raw_text.count(chr(10)) - 15} more lines)")
```

**Step 2.5:**
- TextLayoutAnalyzer (spatial organization)
- Print first 15 lines

```python
    print("\n[Hybrid OCR] Step 3️⃣: Extracting Schema")
    print("-" * 60)
    schema = parse_organized_text_to_schema(organized_raw_text)
```

**Step 3:**
- Claude text parsing (schema extraction)

```python
    result = {
        'layout': layout_dict,
        'organized_text': organized_raw_text,
        'trocr_words': trocr_regions,
        'missing_fields': []
    }
    
    result['sender_name'] = schema.get('sender_name', '')
    result['sender_phone'] = schema.get('sender_phone', '')
    result['sender_province'] = schema.get('sender_province', '')
    result['sender_ward'] = schema.get('sender_ward', '')
    result['sender_address'] = schema.get('sender_address', '')
    result['receiver_name'] = schema.get('receiver_name', '')
    result['receiver_phone'] = schema.get('receiver_phone', '')
    result['receiver_province'] = schema.get('receiver_province', '')
    result['receiver_ward'] = schema.get('receiver_ward', '')
    result['receiver_address'] = schema.get('receiver_address', '')
    result['item_description'] = schema.get('item_description', '')
    result['missing_fields'] = schema.get('missing_fields', [])
```

**Merge schema:**
- Kết hợp tất cả 11 fields vào result

```python
    print(f"\n[Schema] Sender: {result['sender_name']} | {result['sender_phone']} | {result['sender_province']}")
    print(f"[Schema] Receiver: {result['receiver_name']} | {result['receiver_phone']} | {result['receiver_province']}")
    print(f"[Schema] Missing: {result['missing_fields']}")
    print("="*60 + "\n")
    
    return result
```

**Final output**

---

## 📄 File 2: `backend/text_layout_analyzer.py` (325 dòng)

### **Phần 1: Block Class (Dòng 14-43)**

```python
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
```

**Coordinates:**
- `x_center`: Dùng để so sánh với divider (LEFT/RIGHT)
- `y_center`: Dùng để sort top-to-bottom
- `y_min`, `y_max`: Dùng để check overlap

```python
    def y_overlaps_with(self, other: 'Block', threshold: float = 0.5) -> bool:
        """Check if y-ranges overlap significantly."""
        
        overlap_start = max(self.y_min, other.y_min)
        overlap_end = min(self.y_max, other.y_max)
        overlap_amount = max(0, overlap_end - overlap_start)
```

**Tính overlap amount:**
- `overlap_start`: Y bắt đầu của overlap
- `overlap_end`: Y kết thúc của overlap
- `overlap_amount`: Pixel overlap (có thể 0)

```python
        self_height = self.y_max - self.y_min
        other_height = other.y_max - other.y_min
        
        if self_height == 0 or other_height == 0:
            return False
        
        overlap_ratio_self = overlap_amount / self_height
        overlap_ratio_other = overlap_amount / other_height
        
        return overlap_ratio_self >= threshold and overlap_ratio_other >= threshold
```

**Check overlap ratio:**
- Phần trăm overlap cho mỗi block
- **Cả 2 phải >= threshold** (50% default)
- Ngăn accidental pairing

---

### **Phần 2: Main Organize Function (Dòng 128-256)**

```python
def organize(self) -> Dict[int, Dict[int, str]]:
    """Organize text: SPLIT first → MERGE within sides → PAIR."""
    
    if not self.blocks:
        return {}
    
    print("\n" + "="*80)
    print("TEXT LAYOUT: SPLIT FIRST → MERGE WITHIN SIDES → PAIR")
    print("="*80)
```

**Header**

```python
    print("\n[Step 1] Finding markers...")
    self._find_markers()
```

**Step 1: Tìm markers:**
- Tìm "Người gửi" và "Người nhận"

```python
    if self.x_divider is None or self.nguoi_gui_idx is None:
        print("[ERROR] Could not find 'Người gửi'!")
        return {}
```

**Validate markers:**
- Nếu không tìm → fail

```python
    nguoi_nhan_start = self.nguoi_nhan_idx if self.nguoi_nhan_idx else len(self.blocks)
```

**Determine section boundaries:**
- Nếu có "Người nhận" marker → từ đó chia section
- Nếu không → hết file

```python
    print(f"\n[Step 2] === NGƯỜI GỬI SECTION (blocks 0-{nguoi_nhan_start-1}) ===")
    
    gui_blocks = self.blocks[:nguoi_nhan_start]
    
    # SPLIT by divider FIRST
    left_gui = [b for b in gui_blocks if b.x_center < self.x_divider]
    right_gui = [b for b in gui_blocks if b.x_center >= self.x_divider]
```

**NGƯỜI GỬI section:**
- SPLIT: x_center < divider = LEFT, >= divider = RIGHT

```python
    print(f"[Split] LEFT: {len(left_gui)} blocks | RIGHT: {len(right_gui)} blocks")
    
    merged_left_gui = self._merge_blocks_within_side(left_gui, "LEFT")
    merged_right_gui = self._merge_blocks_within_side(right_gui, "RIGHT")
```

**MERGE within side:**
- Merge LEFT with LEFT
- Merge RIGHT with RIGHT

```python
    merged_left_gui.sort(key=lambda b: b.y_center)
    print(f"\n[Order] LEFT sorted TOP→BOTTOM:")
    for i, b in enumerate(merged_left_gui, 1):
        print(f"  [{i}] y={b.y_center:3d}: {b.text[:50]}")
```

**Sort LEFT by y:**
- Top to bottom reading order

```python
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
```

**PAIR LEFT ← RIGHT:**
- Iterate LEFT blocks
- Find RIGHT blocks với y-overlap (threshold 0.3 - relaxed hơn merge)

```python
        self.layout_dict[row_idx] = {}
        col_idx = 1
        
        self.layout_dict[row_idx][col_idx] = left_block.text
        col_idx += 1
        
        for right_block in matching_right:
            self.layout_dict[row_idx][col_idx] = right_block.text
            col_idx += 1
```

**Create row:**
- layout_dict[row] = {col: text}

```python
    # ===== NGƯỜI NHẬN SECTION (FLIPPED) =====
    if self.nguoi_nhan_idx:
        print(f"\n[Step 3] === NGƯỜI NHẬN SECTION ===")
        
        nhan_blocks = self.blocks[self.nguoi_nhan_idx+1:]
        
        left_nhan = [b for b in nhan_blocks if b.x_center < self.x_divider]
        right_nhan = [b for b in nhan_blocks if b.x_center >= self.x_divider]
        
        merged_left_nhan = self._merge_blocks_within_side(left_nhan, "LEFT")
        merged_right_nhan = self._merge_blocks_within_side(right_nhan, "RIGHT")
        
        merged_right_nhan.sort(key=lambda b: b.y_center)
        print(f"\n[Order] RIGHT sorted TOP→BOTTOM (FLIPPED):")
        
        # PAIR RIGHT → LEFT (FLIPPED)
        print(f"\n[Pairing FLIPPED] RIGHT → LEFT:")
        used_left = set()
        
        for right_block in merged_right_nhan:  # Iterate RIGHT first!
            matching_left = []
            
            for i, left_block in enumerate(merged_left_nhan):
                if i in used_left:
                    continue
                
                if right_block.y_overlaps_with(left_block, threshold=0.3):
                    matching_left.append(left_block)
                    used_left.add(i)
```

**NGƯỜI NHẬN FLIPPED:**
- SPLIT → MERGE như trước
- **NHƯNG** PAIR RIGHT → LEFT (iterate RIGHT first!)
- Khác từ NGƯỜI GỬI (iterate LEFT first)

---

### **Phần 3: Reconstruct & Print (Dòng 258-295)**

```python
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
```

**Convert layout dict → text:**
- Lặp qua rows (sorted)
- Lặp qua cols (sorted)
- Join thành lines

```python
def print_layout(self):
    """Print organized layout for debugging."""
    
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
```

**Debug output**

---

## 📄 File 3: `backend/document_processor.py` (301 dòng)

### **Phần 1: Model Loading (Dòng 32-73)**

```python
def load_classifier_model():
    """Load Envelope_box_detection.pt for document classification."""
    
    if not HAS_YOLO:
        raise ImportError("ultralytics not installed")
    
    if not CLASSIFIER_MODEL_PATH.exists():
        raise FileNotFoundError(f"Classifier model not found: {CLASSIFIER_MODEL_PATH}")
    
    print(f"[DocumentProcessor] Loading classifier from {CLASSIFIER_MODEL_PATH}")
    model = YOLO(str(CLASSIFIER_MODEL_PATH))
    print(f"[DocumentProcessor] Classifier loaded successfully")
    return model
```

**Load YOLO model:**
- Dùng `YOLO()` từ ultralytics
- Local file path

```python
def load_info_detector_model():
    """Load info.pt for info region detection."""
    
    if not HAS_YOLO:
        raise ImportError("ultralytics not installed")
    
    if not INFO_DETECTOR_MODEL_PATH.exists():
        raise FileNotFoundError(f"Info detector model not found: {INFO_DETECTOR_MODEL_PATH}")
    
    print(f"[DocumentProcessor] Loading info detector from {INFO_DETECTOR_MODEL_PATH}")
    model = YOLO(str(INFO_DETECTOR_MODEL_PATH))
    print(f"[DocumentProcessor] Info detector loaded successfully")
    return model
```

**2 YOLO models:**
- Một cho classify (LETTER/GOODS)
- Một cho detect info region

```python
def get_classifier_model():
    """Get or initialize classifier model (lazy loading)."""
    global _classifier_model
    if _classifier_model is None:
        _classifier_model = load_classifier_model()
    return _classifier_model

def get_info_detector_model():
    """Get or initialize info detector model (lazy loading)."""
    global _info_detector_model
    if _info_detector_model is None:
        _info_detector_model = load_info_detector_model()
    return _info_detector_model
```

**Lazy loading:**
- Chỉ load khi gọi lần đầu

---

### **Phần 2: Classify Document (Dòng 102-146)**

```python
def classify_document(image: np.ndarray) -> Tuple[str, float]:
    """Classify document type using Envelope_box_detection.pt."""
    
    try:
        model = get_classifier_model()
        results = model(image, verbose=False)
        
        if not results or len(results) == 0:
            print("[DocumentProcessor] No classification result")
            return "GOODS", 0.0
        
        result = results[0]
        
        if hasattr(result, 'probs') and result.probs is not None:
            class_id = result.probs.top1
            confidence = float(result.probs.top1conf)
            class_name = result.names.get(class_id, "GOODS")
            
            print(f"[DocumentProcessor] Classified as: {class_name} (confidence: {confidence:.2f})")
            return class_name, confidence
```

**Classification model output:**
- `probs`: For classification models
- `top1`: Most confident class
- `top1conf`: Confidence score
- Return (class_name, confidence)

---

### **Phần 3: Detect Info Region (Dòng 149-188)**

```python
def detect_info_region(image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Detect info region bounding box using info.pt."""
    
    try:
        model = get_info_detector_model()
        results = model(image, verbose=False)
        
        if not results or len(results) == 0:
            print("[DocumentProcessor] No info region detected")
            return None
        
        result = results[0]
        
        if hasattr(result, 'boxes') and len(result.boxes) > 0:
            boxes = result.boxes
            box = boxes[0]  # Highest confidence
            
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
```

**Detection model:**
- `boxes[0]`: Most confident detection (YOLO sort by confidence)
- `xyxy[0]`: Coordinates [x1, y1, x2, y2]

---

### **Phần 4: Crop Region (Dòng 191-219)**

```python
def crop_region(image: np.ndarray, bbox: Tuple[int, int, int, int],
                padding: int = 0) -> np.ndarray:
    """Crop region from image based on bounding box."""
    
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
```

**Crop logic:**
- Bounds checking: không âm, không exceed image
- Slicing: [y, x] vì row-major

---

### **Phần 5: Main Process Document (Dòng 222-300)**

```python
def process_document(image_bytes: bytes, padding: int = 10) -> dict:
    """Main pipeline: Classify + Detect info region + Crop."""
    
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
```

**4 steps:**
1. Load ảnh
2. Classify (LETTER/GOODS)
3. Detect info region
4. Crop region

**Error handling:**
- Return error dict thay vì raise exception

---

## 📄 File 4: `backend/app.py` - `/process-document-trocr` Endpoint (Dòng 1049-1137)

```python
@app.post("/process-document-trocr")
async def process_document_trocr_endpoint(file: UploadFile) -> ProcessDocumentFullResult:
    """Full pipeline: Classify + Crop + TrOCR + Claude Extract."""
    
    if not HAS_DOCUMENT_PROCESSOR or not HAS_HYBRID_OCR or not HAS_ANTHROPIC:
        raise HTTPException(status_code=503, detail="Cần cài: pip install ultralytics transformers anthropic")
```

**Check dependencies**

```python
    try:
        import base64
        
        # Step 1: Read image and process document
        image_bytes = await file.read()
        result = process_document(image_bytes, padding=10)
```

**Step 1:**
- Read uploaded file
- Call Document Processor

```python
        # Determine which image to use for TrOCR
        if result["success"] and result["info_region_bytes"]:
            # ✅ Use cropped info region (preferred)
            ocr_image_bytes = result["info_region_bytes"]
            service_type = result["service_type"]
            service_confidence = result["service_confidence"]
            used_cropped = True
        else:
            # ⚠️ Fallback: Use full image if crop failed
            ocr_image_bytes = image_bytes
            service_type = result.get("service_type")
            service_confidence = result.get("service_confidence", 0.0)
            used_cropped = False
```

**2-level fallback:**
- Prefer cropped region
- Fall back to full image nếu crop fail

```python
        # Step 2: Detect text regions with TrOCR
        trocr_regions = detect_text_regions(ocr_image_bytes)
        
        if not trocr_regions:
            return ProcessDocumentFullResult(
                success=False,
                service_type=service_type,
                service_confidence=service_confidence,
                error="Không phát hiện được text"
            )
```

**Step 2:**
- Detect text regions
- Handle empty result

```python
        # Step 3: Organize text layout and parse with Claude
        layout_dict, organized_raw_text = organize_text_layout(trocr_regions)
        
        # Parse organized text with Claude
        ocr_data = parse_organized_text_to_schema(organized_raw_text)
```

**Step 3-4:**
- TextLayoutAnalyzer organize
- Claude parse schema

```python
        # Identify missing fields
        required_fields = ["sender_name", "sender_phone", "sender_province",
                          "receiver_name", "receiver_phone", "receiver_province"]
        missing = [f for f in required_fields if not ocr_data.get(f)]
        
        # Step 4: Return result
        return ProcessDocumentFullResult(
            success=True,
            service_type=service_type,
            service_confidence=service_confidence,
            sender_name=ocr_data.get("sender_name", ""),
            sender_phone=ocr_data.get("sender_phone", ""),
            sender_province=ocr_data.get("sender_province", ""),
            sender_ward=ocr_data.get("sender_ward", ""),
            sender_address=ocr_data.get("sender_address", ""),
            receiver_name=ocr_data.get("receiver_name", ""),
            receiver_phone=ocr_data.get("receiver_phone", ""),
            receiver_province=ocr_data.get("receiver_province", ""),
            receiver_ward=ocr_data.get("receiver_ward", ""),
            receiver_address=ocr_data.get("receiver_address", ""),
            item_description=ocr_data.get("item_description", ""),
            missing_fields=missing,
            error=None
        )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ProcessDocumentFullResult(
            success=False,
            service_type=None,
            service_confidence=0.0,
            error=f"Lỗi xử lý: {str(e)}"
        )
```

**Return ProcessDocumentFullResult:**
- Dataclass với tất cả 11 fields
- Error handling

---

## 📊 Complete Flow Diagram

```
INPUT: Image bytes
  ↓
[Document Processor]
  ├─ Classify: LETTER/GOODS
  ├─ Detect info region bbox
  └─ Crop region (hoặc full image fallback)
  ↓
[Hybrid OCR]
  ├─ EasyOCR: Detect text boxes
  ├─ TrOCR: Recognize each box
  └─ Return: [{box, text}, ...]
  ↓
[TextLayoutAnalyzer]
  ├─ Find divider ("Người gửi")
  ├─ SPLIT LEFT/RIGHT
  ├─ MERGE within side
  ├─ PAIR by y-overlap
  └─ Return: {row → {col → text}}
  ↓
[Claude Parse]
  ├─ Input: organized_raw_text
  ├─ Extract schema (11 fields)
  └─ Return: {sender_name, sender_phone, ...}
  ↓
OUTPUT: ProcessDocumentFullResult
  {
    success, service_type, service_confidence,
    sender_name, sender_phone, sender_province, sender_ward, sender_address,
    receiver_name, receiver_phone, receiver_province, receiver_ward, receiver_address,
    item_description, missing_fields, error
  }
```

---

**Done!** Bạn có file OCR chi tiết bằng tiếng Việt! 🎓🚀
