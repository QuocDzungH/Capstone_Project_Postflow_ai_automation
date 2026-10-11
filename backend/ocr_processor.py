"""OCR processor - Claude Vision API with preprocessing."""
import os
import json
import re
from pathlib import Path
from io import BytesIO
from dotenv import load_dotenv
from unidecode import unidecode
from fuzzywuzzy import process
import cv2
import numpy as np
from PIL import Image, ImageEnhance

# Load .env with explicit path
ENV_PATH = Path(__file__).parent.parent / ".env"
print(f"[Debug] Loading .env from: {ENV_PATH}")
print(f"[Debug] .env exists: {ENV_PATH.exists()}")
load_dotenv(ENV_PATH)
print(f"[Debug] After load_dotenv - ANTHROPIC_API_KEY: {bool(os.getenv('ANTHROPIC_API_KEY'))}")

# Load VN provinces
DATA_DIR = Path(__file__).parent / "data"
VN_UNITS_PATH = DATA_DIR / "simplified_json_generated_data_vn_units.json"
try:
    with open(VN_UNITS_PATH, "r", encoding="utf-8") as f:
        VN_UNITS = json.load(f)
except:
    VN_UNITS = []

# Global model cache
_model = None
_tokenizer = None

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def _load_model():
    """Load Vintern model (cached)."""
    global _model, _tokenizer
    if _model is None:
        model_name = "5CD-AI/Vintern-1B-v3_5"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = AutoModel.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
            use_flash_attn=False,
        ).eval().to(device)
        _tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, use_fast=False)
    return _model, _tokenizer


def _build_transform(input_size=448):
    """Build image transform."""
    transform = T.Compose([
        T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])
    return transform


def _find_closest_aspect_ratio(aspect_ratio, target_ratios, width, height, image_size):
    """Find best aspect ratio."""
    best_ratio_diff = float('inf')
    best_ratio = (1, 1)
    area = width * height
    for ratio in target_ratios:
        target_aspect_ratio = ratio[0] / ratio[1]
        ratio_diff = abs(aspect_ratio - target_aspect_ratio)
        if ratio_diff < best_ratio_diff:
            best_ratio_diff = ratio_diff
            best_ratio = ratio
        elif ratio_diff == best_ratio_diff:
            if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                best_ratio = ratio
    return best_ratio


def _dynamic_preprocess(image, min_num=1, max_num=12, image_size=448, use_thumbnail=False):
    """Preprocess image with dynamic aspect ratio."""
    orig_width, orig_height = image.size
    aspect_ratio = orig_width / orig_height
    target_ratios = set(
        (i, j) for n in range(min_num, max_num + 1) for i in range(1, n + 1) for j in range(1, n + 1) if
        i * j <= max_num and i * j >= min_num)
    target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])
    target_aspect_ratio = _find_closest_aspect_ratio(aspect_ratio, target_ratios, orig_width, orig_height, image_size)
    target_width = image_size * target_aspect_ratio[0]
    target_height = image_size * target_aspect_ratio[1]
    blocks = target_aspect_ratio[0] * target_aspect_ratio[1]
    resized_img = image.resize((target_width, target_height))
    processed_images = []
    for i in range(blocks):
        box = (
            (i % (target_width // image_size)) * image_size,
            (i // (target_width // image_size)) * image_size,
            ((i % (target_width // image_size)) + 1) * image_size,
            ((i // (target_width // image_size)) + 1) * image_size
        )
        split_img = resized_img.crop(box)
        processed_images.append(split_img)
    if use_thumbnail and len(processed_images) != 1:
        thumbnail_img = image.resize((image_size, image_size))
        processed_images.append(thumbnail_img)
    return processed_images


def _load_image(image_bytes, input_size=448, max_num=6):
    """Load and preprocess image from bytes."""
    image = Image.open(BytesIO(image_bytes)).convert('RGB')
    transform = _build_transform(input_size=input_size)
    images = _dynamic_preprocess(image, image_size=input_size, use_thumbnail=True, max_num=max_num)
    pixel_values = [transform(img) for img in images]
    pixel_values = torch.stack(pixel_values)
    return pixel_values


def _normalize_text(text):
    """Normalize for fuzzy matching."""
    return unidecode(text.lower().strip())


def _best_match(part_norm, items, vn_field="FullName"):
    """Fuzzy match province (list of dict)."""
    vn_names = [_normalize_text(i.get(vn_field, "")) for i in items]
    vn_match = process.extractOne(part_norm, vn_names)
    if vn_match and vn_match[1] >= 85:
        for i in items:
            if _normalize_text(i.get(vn_field, "")) == vn_match[0]:
                return i.get(vn_field, ""), vn_match[1], i.get("Code", "")
    return None, None, None


def _best_match_ward(part_norm, ward_names):
    """Fuzzy match ward from list of strings.

    Args:
        part_norm: Normalized ward name to search
        ward_names: List of ward name strings (not dicts)

    Returns:
        (matched_ward_name, confidence_score) or (None, None)
    """
    if not ward_names:
        return None, None

    # Normalize all ward names
    norm_names = [_normalize_text(name) for name in ward_names]

    # Fuzzy match
    match = process.extractOne(part_norm, norm_names)
    if match and match[1] >= 85:
        # Find original ward name with best match
        matched_idx = norm_names.index(match[0])
        return ward_names[matched_idx], match[1]

    return None, None


def _normalize_prefix(last_part):
    """Normalize Tỉnh/Thành phố abbreviations."""
    lp = last_part.strip()
    if re.match(r"^(T\.?\s|t\.?\s)", lp):
        return re.sub(r"^(T\.?\s|t\.?\s)", "Tỉnh ", lp), True
    elif re.match(r"^(Tp\.?\s|TP\.?\s|tp\.?\s)", lp):
        return re.sub(r"^(Tp\.?\s|TP\.?\s|tp\.?\s)", "Thành phố ", lp), True
    return lp, False


def _normalize_address(address, vn_units):
    """Extract province/ward/detail_address from full address string.

    Returns: (province, ward, detail_address)
    - province: Tỉnh/Thành phố (cleaned prefix)
    - ward: Phường/Xã/Huyện (cleaned prefix)
    - detail_address: Địa chỉ cụ thể (số nhà, đường) sau khi loại bỏ tỉnh + phường
    """
    if not address:
        return "", "", ""

    parts = re.split(r"[,-]", address)
    parts = [p.strip() for p in parts if p.strip()]

    province, ward = None, None
    province_idx = -1  # Track which index is province
    ward_idx = -1      # Track which index is ward

    if parts:
        # Find province (usually last part)
        last_part, prefix_added = _normalize_prefix(parts[-1].strip())
        if prefix_added:
            candidates = [last_part]
        else:
            candidates = [f"Tỉnh {last_part}", f"Thành phố {last_part}"]

        best_province, best_score, best_code = None, 0, None
        for cand in candidates:
            prov, score, code = _best_match(_normalize_text(cand), vn_units)
            if prov and score > best_score:
                best_province, best_score, best_code = prov, score, code

        province = best_province
        if province:
            province_idx = len(parts) - 1
            wards = []
            for p in vn_units:
                if p["Code"] == best_code:
                    wards = p.get("Wards", [])
                    break

            # Find ward (usually 2nd-last part)
            for i in range(len(parts)-2, -1, -1):
                w, w_score = _best_match_ward(_normalize_text(parts[i]), wards)
                if w:
                    ward = w
                    ward_idx = i
                    break

    # Strip prefix from results
    if province:
        province = re.sub(r'^(Tỉnh|Thành phố)\s+', '', province).strip()
    if ward:
        ward = re.sub(r'^(Phường|Huyện|Xã)\s+', '', ward).strip()

    # Build detail_address: remove province and ward parts
    detail_parts = []
    for i, p in enumerate(parts):
        if i != province_idx and i != ward_idx:
            detail_parts.append(p)
    detail_address = ", ".join(detail_parts).strip()

    return province or "", ward or "", detail_address


def _clean_text(text):
    """Remove special chars."""
    return re.sub(r"[*#]", "", text).strip()


def _extract_addresses(text):
    """Extract sender/receiver blocks + phones.

    Fuzzy match to handle OCR errors (GỬI ≈ GỜI, NHẬN ≈ NHÀN)
    """
    text = _clean_text(text)

    # Fuzzy: match NGƯỜI GỬI/GỜI/similar + NGƯỜI NHẬN/NHÀN/similar
    # Handles OCR character errors
    sender_match = re.search(r"NGƯỜI\s*[GỬỜ][ỊI]?\s*:?(.*?)(?=NGƯỜI\s*[NNTX][HPFB])", text, re.S | re.I)
    receiver_match = re.search(r"NGƯỜI\s*[NNTX][HPFB]\s*:?(.*)", text, re.S | re.I)

    sender = sender_match.group(1).strip() if sender_match else ""
    receiver = receiver_match.group(1).strip() if receiver_match else ""

    sender_phone = None
    receiver_phone = None

    if sender:
        phone_match = re.search(r'Điện thoại["\s:]*"?(\d{9,11})"?', sender)
        if phone_match:
            sender_phone = phone_match.group(1)
            sender = re.sub(r'Điện thoại["\s:]*"?\d{9,11}"?', "", sender).strip()

    if receiver:
        phone_match = re.search(r'Điện thoại["\s:]*"?(\d{9,11})"?', receiver)
        if phone_match:
            receiver_phone = phone_match.group(1)
            receiver = re.sub(r'Điện thoại["\s:]*"?\d{9,11}"?', "", receiver).strip()

    return sender, receiver, sender_phone, receiver_phone


def _parse_addresses_json(sender_text, receiver_text):
    """Parse JSON-like address blocks."""
    sender_name = re.search(r'"Tên"\s*:\s*"([^"]*)"', sender_text, re.I)
    sender_addr = re.search(r'"Địa chỉ"\s*:\s*"([^"]*)"', sender_text, re.I)

    receiver_name = re.search(r'"Tên"\s*:\s*"([^"]*)"', receiver_text, re.I)
    receiver_addr = re.search(r'"Địa chỉ"\s*:\s*"([^"]*)"', receiver_text, re.I)

    return (
        sender_name.group(1) if sender_name else "",
        sender_addr.group(1) if sender_addr else "",
        receiver_name.group(1) if receiver_name else "",
        receiver_addr.group(1) if receiver_addr else ""
    )


def _extract_with_vintern(image_bytes):
    """Extract using local Vintern model (GPU only)."""
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if device == "cpu":
        raise RuntimeError("GPU not available - fallback to OpenAI API")

    # Load model
    model, tokenizer = _load_model()

    # Stage 1: OCR image
    pixel_values = _load_image(image_bytes, max_num=6).to(torch.bfloat16).cuda()

    generation_config = dict(max_new_tokens=512, do_sample=False, num_beams=3, repetition_penalty=3.5)
    question = """<image>
Hãy nhận diện và trích xuất toàn bộ chữ viết tay trong ảnh.
Trả lời theo định dạng:
**NGƯỜI GỬI:**
"Tên": "..."
"Địa chỉ": "..."
"Điện thoại": "..."
**NGƯỜI NHẬN:**
"Tên": "..."
"Địa chỉ": "..."
"Điện thoại": "..."
"""

    ocr_text = model.chat(tokenizer, pixel_values, question, generation_config)

    # Stage 2: Parse + extract
    sender_block, receiver_block, sender_phone, receiver_phone = _extract_addresses(ocr_text)

    sender_name, sender_addr, receiver_name, receiver_addr = _parse_addresses_json(sender_block, receiver_block)

    # Extract provinces + wards + detail addresses
    sender_prov, sender_ward, sender_detail = _normalize_address(sender_addr, VN_UNITS)
    receiver_prov, receiver_ward, receiver_detail = _normalize_address(receiver_addr, VN_UNITS)

    return {
        "sender_name": sender_name,
        "sender_phone": sender_phone or "",
        "sender_province": sender_prov,
        "sender_ward": sender_ward,
        "sender_address": sender_detail,
        "receiver_name": receiver_name,
        "receiver_phone": receiver_phone or "",
        "receiver_province": receiver_prov,
        "receiver_ward": receiver_ward,
        "receiver_address": receiver_detail,
        "raw_text": ocr_text[:500],
    }


def _preprocess_image(image_bytes):
    """Preprocess image for OCR: preserve resolution, crop form, enhance, deskew.

    Strategy:
    - Keep resolution high (1568-2000px ideal for Claude)
    - Crop to form boundaries (remove background)
    - Enhance contrast (mực nổi hơn nền)
    - Deskew (text straight)
    - Preserve color (don't binarize)
    - High quality JPEG (>=85)
    """
    # Load image - keep original size
    img_pil = Image.open(BytesIO(image_bytes)).convert('RGB')
    img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    # 1. Enhance contrast (mực nổi bật) + brightness
    img_pil = ImageEnhance.Contrast(img_pil).enhance(1.3)
    img_pil = ImageEnhance.Brightness(img_pil).enhance(1.05)

    # 2. Deskew if rotated
    img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

    # Detect angle from text contours
    coords = np.column_stack(np.where(gray > 150))
    if len(coords) > 100:  # Only if enough text detected
        angle = cv2.minAreaRect(cv2.convexHull(coords.astype(np.float32)))[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) > 0.5:  # Rotate if noticeably tilted
            h, w = gray.shape
            center = (w // 2, h // 2)
            rot_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            img_cv = cv2.warpAffine(img_cv, rot_matrix, (w, h), borderMode=cv2.BORDER_REFLECT)

    # 3. Gentle denoise (preserve detail)
    img_cv = cv2.bilateralFilter(img_cv, 9, 75, 75)

    # 4. Crop form boundaries (remove background)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
        # Crop with small margin
        margin = 10
        x_start = max(0, x - margin)
        y_start = max(0, y - margin)
        x_end = min(img_cv.shape[1], x + w + margin)
        y_end = min(img_cv.shape[0], y + h + margin)
        img_cv = img_cv[y_start:y_end, x_start:x_end]

    # 5. Convert back to RGB and save
    img_pil = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))

    # Preserve resolution (keep original or scale only if too large)
    max_side = max(img_pil.size)
    if max_side > 2000:  # Only downscale if > 2000px
        scale = 2000 / max_side
        new_size = (int(img_pil.size[0] * scale), int(img_pil.size[1] * scale))
        img_pil = img_pil.resize(new_size, Image.Resampling.LANCZOS)

    output = BytesIO()
    img_pil.save(output, format='JPEG', quality=90)  # High quality, no artifacts
    output.seek(0)
    return output.getvalue()


def _extract_with_claude(image_bytes):
    """Extract using Claude Vision API (Anthropic)."""
    import base64
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError("Anthropic SDK not installed")

    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    print(f"[Debug] ANTHROPIC_API_KEY: {bool(os.getenv('ANTHROPIC_API_KEY'))}")
    print(f"[Debug] CLAUDE_API_KEY: {bool(os.getenv('CLAUDE_API_KEY'))}")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY or CLAUDE_API_KEY not set")

    # Preprocess image - DISABLED: testing if preprocessing hurts accuracy
    # Hypothesis: crop/denoise might degrade handwritten text quality
    # print("[Preprocess] Enhancing, deskewing, denoising...")
    # image_bytes = _preprocess_image(image_bytes)
    print("[Preprocess] SKIPPED - sending raw image to match Claude web behavior")

    client = Anthropic(api_key=api_key)
    img_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    # The optional cloud model is selected in the user's private .env.
    models = [os.environ["ANTHROPIC_MODEL"]]
    response = None

    for model in models:
        try:
            print(f"[Model] Trying {model}...")
            response = client.messages.create(
                model=model,
                max_tokens=2000,
                temperature=0,  # OCR needs accuracy, no hallucination
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": """Đây là phiếu gửi hàng EMS Việt Nam.
Vui lòng đọc và trích xuất thông tin theo EXACT format dưới đây:

NGƯỜI GỬI
Tên: [chính xác như ảnh]
Địa chỉ: [chính xác như ảnh]
Điện thoại: [số điện thoại 10-11 chữ số]

NGƯỜI NHẬN
Tên: [chính xác như ảnh]
Địa chỉ: [chính xác như ảnh]
Điện thoại: [số điện thoại 10-11 chữ số]

Yêu cầu QUAN TRỌNG:
- Giữ ĐÚNG format trên (từng dòng riêng, "Tên:", "Địa chỉ:", "Điện thoại:")
- Nếu chữ khó đọc, ghi chú [?] hoặc thêm "(chữ hơi khó đọc)"
- Đọc cẩn thận từng ký tự
- Không thêm ghi chú khác ngoài các dòng trên"""
                        }
                    ],
                }],
            )
            print(f"[Model] ✓ {model} success!")
            break
        except Exception as e:
            print(f"[Model] ✗ {model} failed: {str(e)}")
            continue

    if not response:
        raise RuntimeError("All models failed!")

    ocr_text = response.content[0].text if response.content else ""
    print(f"[Claude OCR] Raw text:\n{ocr_text}\n")

    # Stage 2: Parse + Extract using our logic
    sender_block, receiver_block, sender_phone, receiver_phone = _extract_addresses(ocr_text)

    def clean_value(val):
        """Clean extracted value."""
        if not val:
            return ""
        val = val.replace('"', '')
        val = re.sub(r'\.+', '', val)
        val = re.sub(r'\s+', ' ', val).strip()
        return val

    def extract_after_keyword(block, keyword):
        """Extract value after keyword (same line or next line)."""
        lines = block.split('\n')
        for i, line in enumerate(lines):
            if keyword.lower() in line.lower() and ':' in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    value = parts[1].strip()
                    if value and not value.startswith(('Sender', 'Recipient', 'Phone', 'Address')):
                        return value

                for j in range(i+1, len(lines)):
                    next_val = lines[j].strip()
                    if next_val and not next_val.startswith(('(', '_', 'Sender', 'Recipient', 'Phone', 'Address', 'Tên', 'Địa')):
                        return next_val
        return ""

    sender_name = clean_value(extract_after_keyword(sender_block, "Tên"))
    sender_full_addr = clean_value(extract_after_keyword(sender_block, "Địa chỉ"))
    receiver_name = clean_value(extract_after_keyword(receiver_block, "Tên"))
    receiver_full_addr = clean_value(extract_after_keyword(receiver_block, "Địa chỉ"))

    # Extract provinces + wards + detail addresses
    sender_prov, sender_ward, sender_addr = _normalize_address(sender_full_addr, VN_UNITS)
    receiver_prov, receiver_ward, receiver_addr = _normalize_address(receiver_full_addr, VN_UNITS)

    result = {
        "sender_name": sender_name,
        "sender_phone": sender_phone or "",
        "sender_province": sender_prov,
        "sender_ward": sender_ward,
        "sender_address": sender_addr,
        "receiver_name": receiver_name,
        "receiver_phone": receiver_phone or "",
        "receiver_province": receiver_prov,
        "receiver_ward": receiver_ward,
        "receiver_address": receiver_addr,
        "raw_text": ocr_text[:500],
    }
    print(f"[Claude Result] {json.dumps(result, ensure_ascii=False, indent=2)}")
    return result


def extract_from_image_openai(image_bytes):
    """Extract using Claude Vision API only."""
    print("[Strategy] Using Claude Vision API")
    return _extract_with_claude(image_bytes)
