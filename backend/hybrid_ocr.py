"""Hybrid OCR: Claude API + TrOCR Vietnamese

Strategy:
1. Claude extracts structured fields (sender_name, phone, etc.)
2. TrOCR detects individual words/phrases
3. Compare results and merge intelligently
4. Use TrOCR word detection to correct Claude errors
"""

import os
import re
import json
import cv2
import torch
import numpy as np
from pathlib import Path
from PIL import Image
from io import BytesIO

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

try:
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    HAS_TROCR = True
except ImportError:
    HAS_TROCR = False

try:
    from anthropic import Anthropic
    HAS_CLAUDE = True
except ImportError:
    HAS_CLAUDE = False

# Model paths
TROCR_MODEL_PATH = Path(__file__).parent.parent / "model" / "trocr-vietnamese-final"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Global model instances
_trocr_processor = None
_trocr_model = None
_text_detector = None


def load_trocr_model():
    """Load TrOCR processor and model."""
    global _trocr_processor, _trocr_model

    if not HAS_TROCR:
        raise ImportError("transformers not installed. Install with: pip install transformers")

    if not TROCR_MODEL_PATH.exists():
        raise FileNotFoundError(f"TrOCR model not found: {TROCR_MODEL_PATH}")

    print(f"[TrOCR] Loading from {TROCR_MODEL_PATH}")

    _trocr_processor = TrOCRProcessor.from_pretrained(
        str(TROCR_MODEL_PATH),
        local_files_only=True
    )

    _trocr_model = VisionEncoderDecoderModel.from_pretrained(
        str(TROCR_MODEL_PATH),
        local_files_only=True
    )

    _trocr_model.to(DEVICE)
    _trocr_model.eval()

    print(f"[TrOCR] Loaded successfully on {DEVICE}")


def load_text_detector():
    """Load EasyOCR text detector."""
    global _text_detector

    if not HAS_EASYOCR:
        raise ImportError("easyocr not installed. Install with: pip install easyocr")

    print("[TextDetector] Loading EasyOCR...")
    _text_detector = easyocr.Reader(["en", "vi"], gpu=torch.cuda.is_available())
    print("[TextDetector] Loaded successfully")


def trocr_recognize_word(image_pil) -> str:
    """Use TrOCR to recognize text from a single image crop."""
    if _trocr_processor is None or _trocr_model is None:
        load_trocr_model()

    try:
        pixel_values = _trocr_processor(
            images=image_pil,
            return_tensors="pt"
        ).pixel_values.to(DEVICE)

        with torch.no_grad():
            generated_ids = _trocr_model.generate(
                pixel_values,
                max_new_tokens=128
            )

        text = _trocr_processor.batch_decode(
            generated_ids,
            skip_special_tokens=True
        )[0].strip()

        return text if text else ""

    except Exception as e:
        print(f"[TrOCR] Recognition error: {e}")
        return ""


def detect_text_regions(image_bytes: bytes) -> list[dict]:
    """Detect and recognize text regions using TrOCR.

    Returns list of {box: [x1,y1,x2,y2], text: "..."}
    """
    global _text_detector

    if _text_detector is None:
        load_text_detector()

    try:
        # Load image
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return []

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width = image.shape[:2]

        # Detect text regions
        print("[TrOCR] Detecting text regions...")
        horizontal_list, free_list = _text_detector.detect(
            rgb_image,
            min_size=10,
            text_threshold=0.5,
            low_text=0.3
        )

        horizontal_list = horizontal_list[0] if horizontal_list else []
        free_list = free_list[0] if free_list else []

        # Convert to bounding boxes
        boxes = []
        for box in horizontal_list:
            x1, x2, y1, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            boxes.append([x1, y1, x2, y2])

        for poly in free_list:
            points = np.array(poly, dtype=np.int32)
            x, y, w, h = cv2.boundingRect(points)
            boxes.append([x, y, x + w, y + h])

        # Sort top to bottom, left to right
        boxes.sort(key=lambda b: (b[1], b[0]))

        # Recognize text in each box
        results = []
        print(f"[TrOCR] Recognizing {len(boxes)} regions...")

        for idx, (x1, y1, x2, y2) in enumerate(boxes):
            # Clamp and add margin
            x1 = max(0, x1 - int((x2-x1)*0.05))
            y1 = max(0, y1 - int((y2-y1)*0.2))
            x2 = min(width, x2 + int((x2-x1)*0.05))
            y2 = min(height, y2 + int((y2-y1)*0.2))

            if x2 <= x1 or y2 <= y1:
                continue

            crop = rgb_image[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            pil_crop = Image.fromarray(crop)
            text = trocr_recognize_word(pil_crop)

            if text:
                results.append({
                    "box": [x1, y1, x2, y2],
                    "text": text
                })
                print(f"  [{idx+1}] {text}")

        return results

    except Exception as e:
        print(f"[TrOCR] Detection error: {e}")
        import traceback
        traceback.print_exc()
        return []


def claude_extract_fields(image_bytes: bytes) -> dict:
    """Use Claude API to extract structured fields.

    Returns: {sender_name, sender_phone, sender_province, ..., missing_fields}
    """
    if not HAS_CLAUDE:
        raise ImportError("anthropic not installed")

    try:
        import base64
        client = Anthropic()

        image_b64 = base64.standard_b64encode(image_bytes).decode()

        response = client.messages.create(
            model=os.environ["ANTHROPIC_MODEL"],
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": """Extract shipping information from this postal form.
Return ONLY a JSON object with exact fields:
{
  "sender_name": "...",
  "sender_phone": "...",
  "sender_province": "...",
  "sender_ward": "...",
  "sender_address": "...",
  "receiver_name": "...",
  "receiver_phone": "...",
  "receiver_province": "...",
  "receiver_ward": "...",
  "receiver_address": "...",
  "item_description": ""
}"""
                    }
                ]
            }]
        )

        import json
        result_text = response.content[0].text
        start = result_text.find('{')
        end = result_text.rfind('}') + 1

        if start == -1 or end == 0:
            return {}

        result = json.loads(result_text[start:end])

        # Identify missing fields
        required = ['sender_name', 'sender_phone', 'sender_province',
                   'receiver_name', 'receiver_phone', 'receiver_province']
        missing = [f for f in required if not result.get(f)]

        result['missing_fields'] = missing
        return result

    except Exception as e:
        print(f"[Claude] Extraction error: {e}")
        return {"missing_fields": ["all"]}


def compare_and_merge(claude_result: dict, trocr_words: list[dict]) -> dict:
    """Compare Claude and TrOCR results, merge intelligently.

    If Claude result and TrOCR detected different words, prefer TrOCR words
    for individual field values when there's a mismatch.
    """
    # For now, simple approach: use Claude's structured output as primary
    # TrOCR is backup for individual words
    # In future, could do fuzzy matching to detect misread words

    merged = claude_result.copy()
    merged['trocr_words'] = [w['text'] for w in trocr_words]

    return merged


def clean_ocr_text(text: str) -> str:
    """Clean OCR artifacts from text - keep only commas in addresses.

    Removes:
    - Arrows (=>, ->, ←, etc.)
    - Extra colons (except at end of labels like "Tên:")
    - Extra periods (except at end of lines)
    - Double spaces

    Keeps:
    - Commas (important for address separation)
    - Numbers and Vietnamese characters
    """
    # Remove arrow symbols
    text = text.replace("=>", "").replace("->", "").replace("←", "").replace("↑", "").replace("↓", "")

    # Remove extra colons (but be careful with labels)
    # Pattern: if colon appears mid-address, remove it
    # E.g., "Hà: Nội" -> "Hà Nội" but keep "Tên:" at start

    # Fix "Hà: Nội" pattern (colon before city name)
    text = re.sub(r'([A-ZĐ][a-z]+):\s+([A-ZĐ])', r'\1 \2', text)

    # Remove trailing colons before commas
    text = text.replace(": ", " ").replace(":\n", "\n")

    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def organize_text_layout(trocr_regions: list[dict]) -> tuple[dict, str]:
    """Organize detected text regions into 2D layout array.

    Args:
        trocr_regions: List of {box: [x1,y1,x2,y2], text: "..."}

    Returns:
        (layout_dict, raw_text) - organized by spatial position
    """
    from backend.text_layout_analyzer import TextLayoutAnalyzer

    analyzer = TextLayoutAnalyzer()

    for region in trocr_regions:
        x1, y1, x2, y2 = region['box']
        analyzer.add_region(
            text=region['text'],
            x1=int(x1),
            y1=int(y1),
            x2=int(x2),
            y2=int(y2)
        )

    layout_dict = analyzer.organize()
    raw_text = analyzer.reconstruct_raw_text()

    # Clean up OCR artifacts
    print("\n[Cleanup] Removing OCR artifacts...")
    cleaned_text = clean_ocr_text(raw_text)

    # Also clean individual cells in layout_dict
    for row_idx in layout_dict:
        for col_idx in layout_dict[row_idx]:
            original = layout_dict[row_idx][col_idx]
            cleaned = clean_ocr_text(original)
            if original != cleaned:
                print(f"  Row {row_idx}, Col {col_idx}: '{original}' → '{cleaned}'")
            layout_dict[row_idx][col_idx] = cleaned

    print("[Cleanup] ✅ Done")

    # Print for debugging
    analyzer.print_layout()

    return layout_dict, cleaned_text


def parse_organized_text_to_schema(organized_text: str) -> dict:
    """Parse organized OCR text into structured schema using Claude API.

    Args:
        organized_text: Cleaned, organized text from layout analyzer

    Returns:
        {
            "sender_name": "...",
            "sender_phone": "...",
            "sender_province": "...",
            "sender_ward": "...",
            "sender_address": "...",
            "receiver_name": "...",
            "receiver_phone": "...",
            "receiver_province": "...",
            "receiver_ward": "...",
            "receiver_address": "...",
            "item_description": "...",
            "missing_fields": [...]
        }
    """
    print("\n[Claude Parse] Starting schema extraction...")

    if not HAS_CLAUDE:
        print("[Claude Parse] ❌ Claude not available")
        return {"missing_fields": ["all"]}

    try:
        print("[Claude Parse] Creating Anthropic client...")
        client = Anthropic()
        print("[Claude Parse] ✅ Client created")

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
- Use exact field names - no variations
- Return empty string "" if field not found, never null
- Return ONLY the JSON object, nothing else"""

        print("[Claude Parse] Calling Claude API...")
        response = client.messages.create(
            model=os.environ["ANTHROPIC_MODEL"],
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        print("[Claude Parse] ✅ API response received")

        result_text = response.content[0].text
        print(f"[Claude Parse] Parsing response... ({len(result_text)} chars)")
        start = result_text.find('{')
        end = result_text.rfind('}') + 1

        if start == -1 or end == 0:
            return {"missing_fields": ["all"]}

        result = json.loads(result_text[start:end])

        # Validate required fields
        required = ['sender_name', 'sender_phone', 'sender_province',
                   'receiver_name', 'receiver_phone', 'receiver_province']
        missing = [f for f in required if not result.get(f)]

        result['missing_fields'] = missing

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


def hybrid_ocr(image_bytes: bytes) -> dict:
    """Hybrid OCR: Claude + TrOCR.

    Args:
        image_bytes: Image file bytes

    Returns:
        {
            "sender_name": "...",
            "sender_phone": "...",
            ...,
            "trocr_words": ["word1", "word2", ...],
            "missing_fields": [...]
        }
    """
    print("\n" + "="*60)
    print("[Hybrid OCR] Starting hybrid OCR processing...")
    print("="*60)

    # Step 1: Claude API extracts structured fields
    print("\n[Hybrid OCR] Step 1️⃣: Claude API Vision OCR")
    print("-" * 60)
    claude_result = claude_extract_fields(image_bytes)
    print(f"[Claude Result] Extracted fields:")
    print(f"  • Sender: {claude_result.get('sender_name')} ({claude_result.get('sender_phone')})")
    print(f"  • Receiver: {claude_result.get('receiver_name')} ({claude_result.get('receiver_phone')})")
    print(f"  • Missing: {claude_result.get('missing_fields', [])}")

    # Step 2: TrOCR detects individual words
    print("\n[Hybrid OCR] Step 2️⃣: TrOCR Word-Level Detection")
    print("-" * 60)
    trocr_regions = detect_text_regions(image_bytes)
    trocr_texts = [r['text'] for r in trocr_regions]
    print(f"[TrOCR Result] Detected {len(trocr_texts)} raw words/phrases")

    # Step 2.5: Organize text by spatial layout
    print("\n[Hybrid OCR] Step 2️⃣.5️⃣: Organizing Text Layout (Left→Right, Top→Bottom)")
    print("-" * 60)
    layout_dict, organized_raw_text = organize_text_layout(trocr_regions)

    print(f"[Layout] Organized into {len(layout_dict)} rows")
    print(f"[Layout] Reconstructed raw text:")
    print("-" * 60)
    for line in organized_raw_text.split('\n')[:15]:  # Show first 15 lines
        print(f"  {line}")
    if organized_raw_text.count('\n') > 15:
        print(f"  ... ({organized_raw_text.count(chr(10)) - 15} more lines)")

    # Step 3: Return organized text + layout
    print("\n[Hybrid OCR] Step 3️⃣: Final Organized Output")
    print("-" * 60)

    result = {
        'layout': layout_dict,
        'organized_text': organized_raw_text,
        'trocr_words': [r['text'] for r in trocr_regions],
        'missing_fields': []
    }

    print(f"[Organized] Text lines: {len(organized_raw_text.split(chr(10)))}")
    print(f"[Organized] Layout rows: {len(layout_dict)}")
    print("\n[Organized] Raw text:")
    print("-" * 60)
    for line in organized_raw_text.split('\n'):
        print(f"  {line}")
    print("="*60 + "\n")

    # Step 3: Extract schema from organized text using Claude API
    print("\n[Hybrid OCR] Step 3️⃣: Extracting Schema")
    print("-" * 60)
    schema = parse_organized_text_to_schema(organized_raw_text)

    # Merge schema into result
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

    print(f"\n[Schema] Sender: {result['sender_name']} | {result['sender_phone']} | {result['sender_province']}")
    print(f"[Schema] Receiver: {result['receiver_name']} | {result['receiver_phone']} | {result['receiver_province']}")
    print(f"[Schema] Missing: {result['missing_fields']}")
    print("="*60 + "\n")

    return result
