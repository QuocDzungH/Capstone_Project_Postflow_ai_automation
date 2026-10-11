# PostFlow Model & Pricing Architecture Explanation

## 🎯 **PHẦN 1: MODEL TrOCR - Cách Hoạt Động**

### **Pipeline TrOCR (trong `hybrid_ocr.py`)**

```
Input Image (ảnh form)
    ↓
[Step 1] Claude API Vision → Extract fields trực tiếp
    ↓
[Step 2] EasyOCR Text Detector → Phát hiện regions (từng từ/câu)
    ↓
[Step 2.5] TrOCR Recognize → OCR từng region với model Transformers
    ↓
[Step 2.5] TextLayoutAnalyzer → Sắp xếp theo vị trí (Top→Bottom, Left→Right)
    ↓
[Step 3] Claude API Text → Parse organized text thành schema
    ↓
Output: Customer fields + organized layout
```

### **Chi tiết từng bước:**

#### **Step 1: EasyOCR Text Detector (`detect_text_regions`)**
- Dùng `easyocr.Reader(["en", "vi"])` để scan ảnh
- Trả về 2 loại boxes:
  - `horizontal_list` - vùng text nằm ngang (hầu hết trong form)
  - `free_list` - vùng text tự do (các góc khác)
- Convert tất cả thành format `[x1, y1, x2, y2]`
- **Sort** theo vị trí: `(y: từ trên xuống) → (x: từ trái sang phải)`

**Code:**
```python
def detect_text_regions(image_bytes: bytes) -> list[dict]:
    """Detect and recognize text regions using TrOCR."""
    
    # Load image từ bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Detect regions bằng EasyOCR
    horizontal_list, free_list = _text_detector.detect(
        rgb_image,
        min_size=10,
        text_threshold=0.5,
        low_text=0.3
    )
    
    # Convert to bounding boxes [x1, y1, x2, y2]
    boxes = []
    for box in horizontal_list:
        boxes.append([x1, y1, x2, y2])
    
    # Sort top to bottom, left to right
    boxes.sort(key=lambda b: (b[1], b[0]))
    
    # Recognize text in each box (bước 2.5)
    results = []
    for idx, (x1, y1, x2, y2) in enumerate(boxes):
        crop = rgb_image[y1:y2, x1:x2]
        pil_crop = Image.fromarray(crop)
        text = trocr_recognize_word(pil_crop)
        
        if text:
            results.append({
                "box": [x1, y1, x2, y2],
                "text": text
            })
    
    return results
```

#### **Step 2: TrOCR Recognize Model (`trocr_recognize_word`)**
- Load model từ: `model/trocr-vietnamese-final/`
- Model này là `VisionEncoderDecoderModel` (từ Hugging Face Transformers)
- Đầu vào: PIL Image crop
- Đầu ra: Text string
- Chạy trên GPU nếu có, CPU nếu không

**Code:**
```python
def trocr_recognize_word(image_pil) -> str:
    """Use TrOCR to recognize text from a single image crop."""
    
    # Preprocess image
    pixel_values = _trocr_processor(
        images=image_pil,
        return_tensors="pt"
    ).pixel_values.to(DEVICE)
    
    # Generate text
    with torch.no_grad():
        generated_ids = _trocr_model.generate(
            pixel_values,
            max_new_tokens=128
        )
    
    # Decode result
    text = _trocr_processor.batch_decode(
        generated_ids,
        skip_special_tokens=True
    )[0].strip()
    
    return text if text else ""
```

#### **Step 3: TextLayoutAnalyzer - Sắp xếp theo Layout (`organize_text_layout`)**

Đây là phần **thông minh nhất**! Nó tổ chức lại text theo 2D grid:

```
Algorithm:
1. Find divider line (tìm "Người gửi" để biết cột trái/phải)
2. Split blocks thành LEFT/RIGHT (x < divider = LEFT, x >= divider = RIGHT)
3. MERGE blocks trong cùng 1 side (LEFT với LEFT, RIGHT với RIGHT)
4. PAIR LEFT ← RIGHT bằng y-overlap (if height overlap >= 50%)

Kết quả: Layout Dict = {
    row_1: {col_1: "Tên", col_2: "John Doe"},
    row_2: {col_1: "SĐT", col_2: "0987654321"},
    ...
}
```

**Ví dụ cụ thể:**
```
EasyOCR detects 5 regions:
  [0]   x=10,  y=20   → "Người gửi"
  [1]   x=200, y=20   → "John Doe"    (RIGHT)
  [2]   x=10,  y=50   → "SĐT"
  [3]   x=200, y=50   → "0987654321"  (RIGHT)

TextLayoutAnalyzer organizes:
  LEFT: ["Người gửi", "SĐT"]
  RIGHT: ["John Doe", "0987654321"]
  
Pairing by y-overlap:
  Row 1: "Người gửi" ← "John Doe"        (y20 overlaps)
  Row 2: "SĐT" ← "0987654321"            (y50 overlaps)
  
Reconstructed raw text:
  Người gửi John Doe
  SĐT 0987654321
```

**Code:**
```python
def organize(self) -> Dict[int, Dict[int, str]]:
    """Organize text: SPLIT first → MERGE within sides → PAIR."""
    
    # Step 1: Find divider (x_center của "Người gửi")
    self._find_markers()
    x_divider = self.x_divider
    
    # Step 2: SPLIT by divider
    left_gui = [b for b in blocks if b.x_center < x_divider]
    right_gui = [b for b in blocks if b.x_center >= x_divider]
    
    # Step 3: MERGE within each side
    merged_left = self._merge_blocks_within_side(left_gui, "LEFT")
    merged_right = self._merge_blocks_within_side(right_gui, "RIGHT")
    
    # Step 4: PAIR by y-overlap
    for left_block in merged_left:
        matching_right = []
        for right_block in merged_right:
            if left_block.y_overlaps_with(right_block, threshold=0.3):
                matching_right.append(right_block)
        
        # Create row
        row_data = {
            1: left_block.text,
            2: " ".join([b.text for b in matching_right])
        }
```

**Key Methods:**

- `y_overlaps_with(other, threshold=0.5)` - Check if 2 blocks overlap vertically
  ```python
  overlap_amount = max(overlap_end - overlap_start)
  overlap_ratio = overlap_amount / self_height
  return overlap_ratio >= threshold
  ```

- `_merge_blocks_within_side()` - Merge adjacent blocks on same side
  ```python
  # Transitively merge: if A overlaps B and B overlaps C, merge all 3
  for i, block in enumerate(blocks):
      group = [block]
      # Find all overlapping blocks
      for other in remaining_blocks:
          if any(b.y_overlaps_with(other) for b in group):
              group.append(other)
      
      # Merge group: sort by x, combine text
      merged_text = " ".join([b.text for b in group])
  ```

#### **Step 4: Claude API Text Parse (`parse_organized_text_to_schema`)**
- Input: Organized text từ step trước
- Prompt: "Extract sender_name, sender_phone, ..., receiver_name, ..."
- Output: JSON schema với 11 fields

**Code:**
```python
def parse_organized_text_to_schema(organized_text: str) -> dict:
    """Parse organized OCR text into structured schema using Claude API."""
    
    client = Anthropic()
    
    prompt = """Parse this Vietnamese postal form text and extract structured information.

TEXT:
""" + organized_text + """

Extract and return ONLY a JSON object with these exact fields:
{
  "sender_name": "name or empty string",
  "sender_phone": "phone or empty string",
  "sender_province": "province/city or empty string",
  "sender_ward": "ward/district or empty string",
  "sender_address": "detailed address or empty string",
  "receiver_name": "name or empty string",
  "receiver_phone": "phone or empty string",
  "receiver_province": "province/city or empty string",
  "receiver_ward": "ward/district or empty string",
  "receiver_address": "detailed address or empty string",
  "item_description": "item description or empty string"
}

Rules:
- Look for "Tên:" labels for names (first is sender, second is receiver)
- Look for "Điện thoại:" for phone numbers
- Look for "Địa chỉ:" for addresses
- Split address into: province (tỉnh), ward (quận/huyện/xã), and detailed address
- Return empty string "" if field not found, never null
- Return ONLY the JSON object, nothing else"""
    
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse JSON from response
    result_text = response.content[0].text
    result = json.loads(result_text[start:end])
    
    return result
```

---

## 🎯 **PHẦN 2: REGION DETECTION - Document Processor**

Cái này độc lập với TrOCR! Nó được gọi **TRƯỚC** khi chạy TrOCR.

### **Pipeline Document Processor (`document_processor.py`)**

```
Input Image
    ↓
[Step 1] Envelope_box_detection.pt → Classify: LETTER or GOODS?
    ↓
[Step 2] info.pt (YOLO detection) → Detect info region bbox
    ↓
[Step 3] Crop info region (với padding)
    ↓
Output: {
    service_type: "LETTER" | "GOODS",
    info_bbox: (x1, y1, x2, y2),
    info_region_bytes: cropped_image_for_OCR
}
```

### **Chi tiết:**

#### **Model 1: `Envelope_box_detection.pt` (Classification)**
- Input: Full image
- Output: Class + confidence
- 2 classes:
  - `LETTER` (Thư từ) - regular mail
  - `GOODS` (Hàng hóa) - parcels
- Dùng `result.probs.top1` để lấy class ID
- In console: `"Classified as: LETTER (confidence: 0.95)"`

**Code:**
```python
def classify_document(image: np.ndarray) -> Tuple[str, float]:
    """Classify document type using Envelope_box_detection.pt."""
    
    model = get_classifier_model()
    results = model(image, verbose=False)
    
    result = results[0]
    
    # Classification model output
    class_id = result.probs.top1
    confidence = float(result.probs.top1conf)
    class_name = result.names.get(class_id, "GOODS")
    
    print(f"[DocumentProcessor] Classified as: {class_name} (confidence: {confidence:.2f})")
    return class_name, confidence
```

#### **Model 2: `info.pt` (Detection)**
- Input: Full image
- Output: Multiple bounding boxes (nhưng chỉ lấy **first box** - highest confidence)
- Bounding box format: `(x1, y1, x2, y2)`
- Cái bbox này chính là **khu vực chứa customer info** (sender/receiver data)
- In console: `"Info region detected at (50, 100, 400, 600), confidence: 0.92"`

**Code:**
```python
def detect_info_region(image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Detect info region bounding box using info.pt."""
    
    model = get_info_detector_model()
    results = model(image, verbose=False)
    
    result = results[0]
    
    # Get first detected box (highest confidence)
    if hasattr(result, 'boxes') and len(result.boxes) > 0:
        box = result.boxes[0]
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
        confidence = float(box.conf[0])
        
        print(f"[DocumentProcessor] Info region detected at ({x1}, {y1}, {x2}, {y2}), confidence: {confidence:.2f}")
        return (int(x1), int(y1), int(x2), int(y2))
    
    return None
```

#### **Step 3: Crop Region**

```python
def crop_region(image: np.ndarray, bbox: Tuple[int, int, int, int], padding: int = 0) -> np.ndarray:
    """Crop region from image based on bounding box."""
    
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
```

Kết quả: Một ảnh nhỏ hơn, chỉ chứa vùng customer info. Cái ảnh này được gửi tới **TrOCR** để OCR.

#### **Lợi ích:**
- ✅ Giảm noise (background, logos, barcodes)
- ✅ Tăng accuracy vì TrOCR chỉ focus vào info region
- ✅ Tăng speed (xử lý ảnh nhỏ hơn)

#### **Main Pipeline:**
```python
def process_document(image_bytes: bytes, padding: int = 10) -> dict:
    """Main pipeline: Classify + Detect info region + Crop."""
    
    # Step 1: Load image
    image = image_bytes_to_cv2(image_bytes)
    
    # Step 2: Classify document type
    service_type, service_confidence = classify_document(image)
    
    # Step 3: Detect info region
    info_bbox = detect_info_region(image)
    
    if info_bbox is None:
        return {
            "success": False,
            "service_type": service_type,
            "error": "Failed to detect info region"
        }
    
    # Step 4: Crop info region
    cropped_image = crop_region(image, info_bbox, padding=padding)
    cropped_bytes = cv2_to_image_bytes(cropped_image)
    
    return {
        "success": True,
        "service_type": service_type,
        "service_confidence": float(service_confidence),
        "info_bbox": info_bbox,
        "info_region_bytes": cropped_bytes,
        "original_image_bytes": image_bytes,
        "error": None
    }
```

---

## 🎯 **PHẦN 3: PRICING ENGINE - Tính Giá Cước**

Phần này **tùy hoàn toàn vào regions.json + pricing.json**!

### **Flow Pricing (`pricing.py`)**

```
Input: {
    service: "ETN011",
    origin: "Hà Nội",
    destination: "TP. Hồ Chí Minh",
    actual_weight_kg: 2.5,
    length_cm: 30, width_cm: 20, height_cm: 15
}
    ↓
[Step 1] normalize_province() → "Hà Nội", "TP. Hồ Chí Minh"
    ↓
[Step 2] determine_route() → Tìm "Hà Nội đi TP.HCM và ngược lại"
    ↓
[Step 3] chargeable_weight_kg() → Tính khối lượng tính cước
    ↓
[Step 4] Look up pricing table → Calculate amount
    ↓
Output: PriceQuote {
    service, route, actual_weight, chargeable_weight,
    used_volumetric, amount_vnd
}
```

### **Chi tiết từng step:**

#### **Step 1: Normalize Province**

```python
def normalize_province(province: str) -> str:
    """Return the canonical province name, accepting configured spelling aliases."""
    
    # Input: "TP HCM", "hà nội" (người dùng có thể viết tắt/khác dạu)
    # Process:
    #  - Normalize accents (TP HCM → "tp hcm")
    #  - Remove non-alpha (chỉ lấy a-z, 0-9)
    #  - Lookup alias dict (regions.json)
    
    def _key(value: str) -> str:
        normalized = unicodedata.normalize("NFD", value.strip().lower())
        without_marks = "".join(char for char in normalized 
                               if unicodedata.category(char) != "Mn")
        return re.sub(r"[^a-z0-9]", "", without_marks.replace("đ", "d"))
    
    # Load alias map from regions.json
    alias_map = {
        "tphcm": "TP. Hồ Chí Minh",
        "tphochiminh": "TP. Hồ Chí Minh",
        "hanoi": "Hà Nội",
        "danang": "Đà Nẵng",
    }
    
    canonical = alias_map.get(_key(province), province.strip())
    match = _province_map.get(_key(canonical))
    
    if not match:
        raise PricingError(f"Chưa có vùng cước cho tỉnh/thành: {province!r}.")
    
    # Output: "TP. Hồ Chí Minh", "Hà Nội" (canonical names)
    return match[0]
```

**regions.json structure:**
```json
{
  "Vùng 1": [
    "Hà Nội", "Hải Phòng", "Quảng Ninh", "Cao Bằng", 
    "Lạng Sơn", "Bắc Ninh", "Ninh Bình", ...
  ],
  "Vùng 2": [
    "TP. Hồ Chí Minh", "Bình Dương", "Long An", 
    "Đồng Nai", "Bà Rịa - Vũng Tàu", ...
  ],
  "Vùng 3": [
    "Đà Nẵng", "Hue", "Quảng Nam", "Đắk Lắk", ...
  ],
  "aliases": {
    "Hồ Chí Minh": "TP. Hồ Chí Minh",
    "TP HCM": "TP. Hồ Chí Minh",
    "Da Nang": "Đà Nẵng"
  }
}
```

#### **Step 2: Determine Route**

```python
def determine_route(origin: str, destination: str, service: str) -> str:
    """Determine the tariff route from origin/destination and service code."""
    
    # Normalize both provinces
    origin = normalize_province(origin)              # "Hà Nội"
    destination = normalize_province(destination)    # "TP. Hồ Chí Minh"
    
    # Rule 1: Same province
    if origin == destination:
        return "Nội tỉnh"
    
    # Tìm zone của mỗi tỉnh từ regions.json:
    origin_zone = "Vùng 1"           # Hà Nội → Vùng 1
    dest_zone = "Vùng 2"             # TP.HCM → Vùng 2
    
    # Rule 2: Same zone
    if origin_zone == dest_zone:
        return "Nội vùng"
    
    # Rule 3: Special routes (ETN services only)
    hanoi, hcm, danang = "Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng"
    pair = {origin, destination}
    
    if service.startswith("ETN"):
        if pair == {hanoi, hcm}:
            return "Hà Nội đi TP.HCM và ngược lại"   # Special route
        if danang in pair and (hanoi in pair or hcm in pair):
            return "Đà Nẵng đi Hà Nội, TP.HCM và ngược lại"
        return "Liên vùng"  # Different zones
    
    # Rule 4: CTN services
    return "Cận vùng" if "Vùng 3" in {origin_zone, dest_zone} else "Cách vùng"
```

**Routes for ETN services:**
| Route | Condition |
|-------|-----------|
| Nội tỉnh | origin == destination |
| Nội vùng | same zone |
| Hà Nội ↔ TP.HCM | special route |
| Đà Nẵng ↔ HN/HCM | special route |
| Liên vùng | different zones |

#### **Step 3: Chargeable Weight**

```python
def chargeable_weight_kg(actual_weight_kg: float, length_cm: float, 
                         width_cm: float, height_cm: float) -> tuple[float, bool]:
    """Use real weight unless at least one package side is over 50 cm."""
    
    actual_weight = 2.5 kg
    length, width, height = 30, 20, 15 cm
    
    # Rule: If any dimension > 50cm, use volumetric weight
    has_large_dimension = any(side > 50 for side in [length, width, height])
    # = False (không có cạnh > 50cm)
    
    if has_large_dimension:
        volumetric_weight = (length * width * height) / 6000
        # = (30 * 20 * 15) / 6000 = 9000 / 6000 = 1.5 kg
        
        chargeable_weight = max(actual_weight, volumetric_weight)
        # = max(2.5, 1.5) = 2.5 kg
        
        return chargeable_weight, True  # used volumetric
    else:
        return actual_weight, False     # used actual weight
    
    # Result: (2.5 kg, False)
```

**Key Rule:**
- If **any dimension > 50cm**: Calculate volumetric weight = L×W×H/6000
- Use: **max(actual_weight, volumetric_weight)**
- Otherwise: Use actual weight

#### **Step 4: Lookup Pricing Table**

**Structure của pricing.json:**
```json
{
  "ETN011": {
    "name": "Hàng hoá",
    "unit_grams": 500,
    "base_tiers": [
      [50,   [8000, 9500, 10500, 10500, 11000]],     // 0-50g
      [100,  [8000, 13500, 14500, 14500, 15000]],    // 51-100g
      [250,  [10000, 17500, 23000, 23500, 24500]],   // 101-250g
      [500,  [12500, 25000, 29500, 30500, 31500]],   // 251-500g
      [1000, [15000, 35000, 43000, 44000, 46000]],   // 501-1000g
      [1500, [18000, 42000, 55500, 57000, 59500]],   // 1001-1500g
      [2000, [21000, 51000, 62500, 67000, 71000]]    // 1501-2000g
    ],
    "extra_after_grams": 2000,
    "extra_per_unit": [1600, 4000, 9500, 10500, 12000]
  }
}
```

**Tier Structure:**
- **upper_bound**: Max grams for this tier (inclusive)
- **prices**: Array of 5 prices (one per route)

**Route Index Mapping:**
```
Route                                          Index (ETN)
─────────────────────────────────────────────────────────
Nội tỉnh (same province)                        0
Nội vùng (same zone)                            1
Đà Nẵng ↔ Hà Nội/TP.HCM                         2
Hà Nội ↔ TP.HCM                                 3
Liên vùng (different zones)                     4
```

**Lookup Logic:**

```python
def calculate_shipping_fee(*, service: str, origin: str, destination: str, 
                          actual_weight_kg: float, length_cm: float, 
                          width_cm: float, height_cm: float) -> PriceQuote:
    """Calculate a tariff quote."""
    
    # Step 1: Normalize & determine route
    route = determine_route(origin, destination, service)
    # = "Hà Nội đi TP.HCM và ngược lại"
    
    # Step 2: Calculate chargeable weight
    chargeable_kg, used_volume = chargeable_weight_kg(
        actual_weight_kg, length_cm, width_cm, height_cm)
    # = (2.5, False)
    
    grams = chargeable_kg * 1000  # = 2500g
    config = PRICING[service]      # Get ETN011 config
    
    # Step 3: Find route index
    etn_routes = ["Nội tỉnh", "Nội vùng", "Đà Nẵng đi Hà Nội, TP.HCM và ngược lại", 
                  "Hà Nội đi TP.HCM và ngược lại", "Liên vùng"]
    route_index = etn_routes.index(route)
    # = 3 (Hà Nội ↔ TP.HCM)
    
    # Step 4: Find price tier (2500g falls into which tier?)
    base_price = None
    base_limit = None
    
    for upper_bound, prices in config["base_tiers"]:
        if grams <= upper_bound:
            base_price = prices[route_index]
            base_limit = upper_bound
            break
    
    # grams=2500, checking:
    # [2000, [21000, 51000, 62500, 67000, 71000]]
    # 2500 > 2000? YES → Not in base_tiers
    
    # So we use the LAST tier as base
    base_price = config["base_tiers"][-1][1][route_index]
    # = [21000, 51000, 62500, 67000, 71000][3] = 67000 VND (for 2000g)
    
    base_limit = 2000
    
    # Step 5: Calculate extra charge (for weight > 2000g)
    if grams > base_limit:
        extra_grams = grams - base_limit
        # = 2500 - 2000 = 500g
        
        extra_unit_size = config["unit_grams"]  # 500g
        extra_units = ceil(extra_grams / extra_unit_size)
        # = ceil(500 / 500) = 1 unit
        
        extra_per_unit = config["extra_per_unit"][route_index]
        # = [1600, 4000, 9500, 10500, 12000][3] = 10500 VND
        
        amount = base_price + extra_units * extra_per_unit
        # = 67000 + 1 * 10500 = 77500 VND
    else:
        amount = base_price
    
    return PriceQuote(
        service=service,
        route=route,
        actual_weight_kg=actual_weight_kg,
        chargeable_weight_kg=chargeable_kg,
        used_volumetric=used_volume,
        amount_vnd=round(amount, 2)
    )
```

**Final Result:**
```json
{
  "service": "ETN011",
  "route": "Hà Nội đi TP.HCM và ngược lại",
  "actual_weight_kg": 2.5,
  "chargeable_weight_kg": 2.5,
  "used_volumetric": false,
  "amount_vnd": 77500
}
```

---

## 📊 **TÓM TẮT ARCHITECTURE**

```
┌─────────────────────────────────────┐
│       User Upload Form Image        │
└──────────────┬──────────────────────┘
               ↓
┌──────────────────────────────────────┐
│   Document Processor                 │
│   ├─ Classify: LETTER/GOODS         │
│   └─ Detect & Crop info region      │
└──────────┬───────────────────────────┘
           ↓
┌──────────────────────────────────────┐
│   Hybrid OCR Pipeline                │
│   ├─ Step 1: Claude API Vision       │
│   ├─ Step 2: EasyOCR + TrOCR        │
│   ├─ Step 2.5: TextLayoutAnalyzer   │
│   └─ Step 3: Claude API Text Parse   │
└──────────┬───────────────────────────┘
           ↓
┌──────────────────────────────────────┐
│   Extracted Customer Data            │
│   ├─ sender_name, sender_phone, ...  │
│   └─ receiver_name, receiver_phone   │
└──────────┬───────────────────────────┘
           ↓
┌──────────────────────────────────────┐
│   Pricing Engine                     │
│   ├─ Normalize provinces             │
│   ├─ Determine route                 │
│   ├─ Calculate chargeable weight    │
│   └─ Lookup pricing table           │
└──────────┬───────────────────────────┘
           ↓
┌──────────────────────────────────────┐
│   Payment → Tracking Code → Save DB  │
└──────────────────────────────────────┘
```

---

## ⚡ **KỲ LẠI / KEY POINTS**

| Component | Purpose | Key File |
|-----------|---------|----------|
| **EasyOCR** | Detect text regions | `hybrid_ocr.py:detect_text_regions()` |
| **TrOCR Model** | Recognize text in each region | `hybrid_ocr.py:trocr_recognize_word()` |
| **TextLayoutAnalyzer** | Organize regions into 2D grid | `text_layout_analyzer.py` |
| **Document Processor** | Classify + detect info region | `document_processor.py` |
| **Pricing Engine** | Calculate shipping fee | `pricing.py` |
| **Data Tables** | Region zones & pricing tiers | `data/regions.json`, `pricing.json` |

---

## 📝 **WORKFLOW SUMMARY**

### **Full User Journey:**

1. **User uploads postal form image**
   - → Document Processor classifies (LETTER/GOODS)
   - → Detects info region bounding box
   - → Crops info region

2. **Info region sent to Hybrid OCR**
   - → EasyOCR detects text regions (boxes)
   - → TrOCR recognizes text in each box
   - → TextLayoutAnalyzer organizes into 2D layout
   - → Claude API parses organized text into schema

3. **Customer fields auto-filled in form**
   - User can edit/correct fields
   - User moves to Step 2 (measurements)

4. **User inputs weight + dimensions**
   - length_cm, width_cm, height_cm, actual_weight_kg

5. **Pricing Engine calculates fee**
   - Normalize provinces
   - Determine route (Hà Nội ↔ TP.HCM, Nội tỉnh, etc.)
   - Calculate chargeable weight (volumetric check)
   - Lookup pricing table
   - Return total amount in VND

6. **User selects payment method**
   - Bank transfer (generate VietQR)
   - Cash payment

7. **Order created + saved to SQLite**
   - Tracking code generated
   - Barcode generated
   - User prints or saves tracking info

---

## 🔧 **DEBUGGING TIPS**

### **If OCR accuracy is low:**
1. Check if info region detection works (crop might be wrong)
2. Verify TrOCR model is loaded correctly
3. Check text layout analyzer output (printed in console)
4. Fallback: Claude API Vision might need re-prompt

### **If region detection fails:**
1. Check if `Envelope_box_detection.pt` exists
2. Check if `info.pt` exists
3. Try full image OCR fallback (if info.pt fails)
4. Verify model confidence thresholds

### **If pricing is incorrect:**
1. Check province normalization (should match regions.json)
2. Verify route determination (check console output)
3. Check if weight/dimension tier is correct
4. Verify pricing.json has all required services/routes

---

## 💾 **DATA FILES REFERENCE**

### **regions.json**
- Vùng 1, 2, 3 → list of provinces
- aliases → province name variations
- post_offices → mapping province → post office name

### **pricing.json**
- LETTER, ETN001, ETN011, ETN013, CTN001
- base_tiers: [upper_gram_limit, [prices_for_5_routes]]
- progressive_tiers (CTN001 only): [upper_limit, [prices]]
- extra_after_grams, extra_per_unit: for weight > base tier

---

**Model architecture designed for accuracy, modularity, and scalability!** ✨
