import re
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from io import BytesIO

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from PIL import Image

try:
    import barcode
    from barcode.writer import ImageWriter
    HAS_BARCODE = True
except ImportError:
    HAS_BARCODE = False

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    import torch
    from transformers import AutoModel, AutoTokenizer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from backend.database import create_order, get_order, initialize, update_order
from backend.pricing import PricingError, calculate_shipping_fee

try:
    from backend.ocr_processor import extract_from_image_openai
    HAS_OCR_PROCESSOR = True
except ImportError:
    HAS_OCR_PROCESSOR = False

try:
    from backend.volume_detector import detect_dimensions
    HAS_VOLUME_DETECTOR = True
except ImportError:
    HAS_VOLUME_DETECTOR = False

try:
    from backend.document_processor import process_document
    HAS_DOCUMENT_PROCESSOR = True
except ImportError:
    HAS_DOCUMENT_PROCESSOR = False

try:
    from backend.dimension_detector import detect_dimensions, detect_dimensions_dual, detect_dimensions_esp32
    HAS_DIMENSION_DETECTOR = True
except ImportError:
    HAS_DIMENSION_DETECTOR = False

try:
    from backend.multi_camera_detector import measure_multi_camera
    HAS_MULTI_CAMERA_DETECTOR = True
except ImportError:
    HAS_MULTI_CAMERA_DETECTOR = False

try:
    from backend.hybrid_ocr import detect_text_regions, parse_organized_text_to_schema, organize_text_layout
    HAS_HYBRID_OCR = True
except ImportError:
    HAS_HYBRID_OCR = False

app = FastAPI(title="PostFlow API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
# Also initialize on import so command-line tests and ASGI startup behave identically.
initialize()
PROJECT_ROOT = Path(__file__).parent.parent

# In-memory storage for orders in progress (will save to DB on payment confirmation)
_orders_in_progress = {}

# Load regions data for province detection
REGIONS_PATH = PROJECT_ROOT / "backend" / "data" / "regions.json"
with open(REGIONS_PATH, encoding='utf-8') as f:
    REGIONS_DATA = json.load(f)

# Flatten all provinces for easy lookup
ALL_PROVINCES = []
for zone_provinces in [REGIONS_DATA.get("Vùng 1", []), REGIONS_DATA.get("Vùng 2", []), REGIONS_DATA.get("Vùng 3", [])]:
    ALL_PROVINCES.extend(zone_provinces)

# Global model cache for OCR
_ocr_model = None
_ocr_tokenizer = None

def _load_ocr_model():
    global _ocr_model, _ocr_tokenizer
    if _ocr_model is None:
        if not HAS_TRANSFORMERS:
            raise HTTPException(status_code=503, detail="OCR không khả dụng. Cần cài: pip install torch transformers timm pillow")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _ocr_model = AutoModel.from_pretrained(
            "5CD-AI/Vintern-1B-v3_5",
            torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
            low_cpu_mem_usage=True,
            trust_remote_code=True
        ).eval().to(device)
        _ocr_tokenizer = AutoTokenizer.from_pretrained(
            "5CD-AI/Vintern-1B-v3_5",
            trust_remote_code=True,
            use_fast=False
        )
    return _ocr_model, _ocr_tokenizer


@app.on_event("startup")
def startup() -> None:
    initialize()


class QuoteRequest(BaseModel):
    service: str = Field(examples=["ETN011"])
    origin: str = Field(examples=["Hà Nội"])
    destination: str = Field(examples=["Đà Nẵng"])
    actual_weight_kg: float = Field(gt=0, examples=[1.2])
    length_cm: float = Field(gt=0, examples=[40])
    width_cm: float = Field(gt=0, examples=[30])
    height_cm: float = Field(gt=0, examples=[20])


class OrderCreate(BaseModel):
    sender_name: str = Field(min_length=2)
    sender_phone: str = Field(min_length=8)
    sender_province: str = Field(min_length=2)
    sender_ward: str = Field(min_length=2)
    sender_address: str = Field(min_length=5)
    receiver_name: str = Field(min_length=2)
    receiver_phone: str = Field(min_length=8)
    receiver_province: str = Field(min_length=2)
    receiver_ward: str = Field(min_length=2)
    receiver_address: str = Field(min_length=5)
    service: str
    item_description: str = Field(min_length=2)


class MeasurementRequest(BaseModel):
    actual_weight_kg: float = Field(gt=0)
    length_cm: float = Field(gt=0)
    width_cm: float = Field(gt=0)
    height_cm: float = Field(gt=0)


class VolumeDetectRequest(BaseModel):
    cm_per_pixel: float = Field(gt=0, default=0.0525, description="Calibration ratio (cm per pixel)")


class VolumeDetectResult(BaseModel):
    status: str  # "success" | "partial" | "failed"
    length_cm: float | None = None
    width_cm: float | None = None
    height_cm: float | None = None
    volume_cm3: float | None = None
    errors: list[str] = []
    length_image: str | None = None  # base64 data URL
    width_image: str | None = None  # base64 data URL
    height_image: str | None = None  # base64 data URL


class DocumentProcessResult(BaseModel):
    success: bool
    service_type: str | None  # "LETTER" or "GOODS"
    service_confidence: float
    info_bbox: tuple[int, int, int, int] | None  # (x1, y1, x2, y2)
    info_region_base64: str  # Cropped image for OCR input (base64)
    error: str | None = None


class DimensionDetectResult(BaseModel):
    success: bool
    length_cm: float | None
    width_cm: float | None
    height_cm: float | None
    volume_cm3: float | None
    annotated_image_base64: str | None = None  # Visualization (base64)
    error: str | None = None


class DimensionDetectDualResult(BaseModel):
    success: bool
    length_cm: float | None
    width_cm: float | None
    height_cm: float | None
    volume_cm3: float | None
    camera1: dict | None = None  # Camera 1 measurement details
    camera2: dict | None = None  # Camera 2 measurement details
    reference: str | None = None  # "NGANG_1 <-> DỌC_2" or "NGANG_1 <-> NGANG_2"
    annotated_image_base64: str | None = None  # Visualization (base64)
    error: str | None = None


class BoxOCRResult(BaseModel):
    success: bool
    text: str  # Extracted text from box
    lines: list[str]  # Text split by lines
    error: str | None = None


class ProcessDocumentFullResult(BaseModel):
    success: bool
    service_type: str | None  # "LETTER" or "GOODS"
    service_confidence: float
    # Extracted fields from OCR
    sender_name: str = ""
    sender_phone: str = ""
    sender_province: str = ""
    sender_ward: str = ""
    sender_address: str = ""
    receiver_name: str = ""
    receiver_phone: str = ""
    receiver_province: str = ""
    receiver_ward: str = ""
    receiver_address: str = ""
    item_description: str = ""
    missing_fields: list[str] = []
    error: str | None = None


class OCRResult(BaseModel):
    # Người gửi
    sender_name: str = ""
    sender_phone: str = ""
    sender_province: str = ""      # Tỉnh/Thành phố
    sender_ward: str = ""           # Phường/Xã
    sender_address: str = ""        # Địa chỉ cụ thể (số nhà, đường)
    # Người nhận
    receiver_name: str = ""
    receiver_phone: str = ""
    receiver_province: str = ""     # Tỉnh/Thành phố
    receiver_ward: str = ""         # Phường/Xã
    receiver_address: str = ""      # Địa chỉ cụ thể (số nhà, đường)
    # Metadata
    item_description: str = ""
    raw_text: str = ""
    missing_fields: list[str] = []


class ExtractRequest(BaseModel):
    text: str = Field(min_length=5)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_order(tracking_code: str) -> dict:
    order = get_order(tracking_code.upper())
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã vận đơn.")
    order["used_volumetric_weight"] = bool(order["used_volumetric_weight"])
    return order


def _extract_province_from_address(address: str) -> str:
    """Extract province name from address text."""
    if not address:
        return ""

    address_lower = address.lower()

    # Check for exact matches in provinces (case-insensitive)
    for province in ALL_PROVINCES:
        if province.lower() in address_lower:
            return province

    # Check aliases
    aliases = REGIONS_DATA.get("aliases", {})
    for alias, canonical in aliases.items():
        if alias.lower() in address_lower:
            return canonical

    return ""


def _generate_barcode(tracking_code: str) -> BytesIO:
    """Generate barcode image from tracking code."""
    if not HAS_BARCODE:
        raise HTTPException(status_code=503, detail="Barcode library không khả dụng")

    try:
        output = BytesIO()
        barcode_obj = barcode.get('code128', tracking_code, writer=ImageWriter())
        # Write to BytesIO instead of file
        barcode_obj.write(output)
        output.seek(0)
        return output
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo barcode: {str(error)}") from error


def _parse_ocr_result(text: str) -> dict:
    """Parse OCR text: * Tên: / * Địa chỉ: / * SĐT: format (2 blocks)."""
    result = {
        "sender_name": "",
        "sender_phone": "",
        "sender_province": "",
        "sender_ward": "",
        "sender_address": "",
        "receiver_name": "",
        "receiver_phone": "",
        "receiver_province": "",
        "receiver_ward": "",
        "receiver_address": "",
        "item_description": "",
        "missing_fields": [],
    }

    # Handle both real newlines and escaped \n from JSON
    text = text.replace('\\n', '\n').strip()

    # Extract all * Label: Value lines in order
    all_lines = []
    for line in text.split('\n'):
        line = line.strip()
        if line and line.startswith('*'):
            match = re.match(r'\*\s*([^:]+):\s*(.*)', line)
            if match:
                label = match.group(1).strip().lower()
                value = match.group(2).strip()
                all_lines.append((label, value))

    # Assign fields in order: Tên[0], Địa chỉ[0], SĐT[0], Tên[1], Địa chỉ[1], SĐT[1]
    tên_list = [v for k, v in all_lines if k == 'tên']
    dia_chi_list = [v for k, v in all_lines if k == 'địa chỉ']
    sdt_list = [v for k, v in all_lines if k == 'sdt']

    # Sender (first occurrence)
    if len(tên_list) >= 1:
        result["sender_name"] = tên_list[0][:100]
    if len(dia_chi_list) >= 1:
        result["sender_address"] = dia_chi_list[0][:200]
        # Extract province and ward from address
        result["sender_province"] = _extract_province_from_address(dia_chi_list[0])
    if len(sdt_list) >= 1:
        result["sender_phone"] = sdt_list[0]

    # Receiver (second occurrence)
    if len(tên_list) >= 2:
        result["receiver_name"] = tên_list[1][:100]
    if len(dia_chi_list) >= 2:
        result["receiver_address"] = dia_chi_list[1][:200]
        # Extract province and ward from address
        result["receiver_province"] = _extract_province_from_address(dia_chi_list[1])
    if len(sdt_list) >= 2:
        result["receiver_phone"] = sdt_list[1]

    # Detect missing fields - only name, phone, province (bưu cục) required
    required_fields = ["sender_name", "sender_phone", "sender_province",
                      "receiver_name", "receiver_phone", "receiver_province"]
    for field in required_fields:
        if not result[field]:
            result["missing_fields"].append(field)

    return result


@app.post("/extract")
async def extract_from_text(request: ExtractRequest) -> OCRResult:
    """Extract structured information from plain text."""
    try:
        parsed = _parse_ocr_result(request.text)
        return OCRResult(**parsed)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý thông tin: {str(error)}") from error


@app.post("/ocr-image")
async def ocr_image(file: UploadFile = File(...)) -> OCRResult:
    """Extract shipping info from image using Vintern OCR with Vietnamese address normalization."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Tệp phải là ảnh (JPG, PNG, etc.)")

    if not HAS_OCR_PROCESSOR:
        raise HTTPException(status_code=503, detail="OCR không khả dụng. Cần cài dependencies.")

    try:
        contents = await file.read()
        result = extract_from_image(contents)

        # Check for missing fields
        # Required fields: name, phone, province (bưu cục)
        # Ward + address detail are optional
        required_fields = ["sender_name", "sender_phone", "sender_province",
                          "receiver_name", "receiver_phone", "receiver_province"]
        missing = [f for f in required_fields if not result.get(f)]

        return OCRResult(
            sender_name=result.get("sender_name", ""),
            sender_phone=result.get("sender_phone", ""),
            sender_province=result.get("sender_province", ""),
            sender_ward=result.get("sender_ward", ""),
            sender_address=result.get("sender_address", ""),
            receiver_name=result.get("receiver_name", ""),
            receiver_phone=result.get("receiver_phone", ""),
            receiver_province=result.get("receiver_province", ""),
            receiver_ward=result.get("receiver_ward", ""),
            receiver_address=result.get("receiver_address", ""),
            item_description="",
            raw_text=result.get("raw_text", ""),
            missing_fields=missing
        )
    except Exception as error:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý ảnh: {str(error)}") from error


@app.post("/ocr-image-openai-2stage")
async def ocr_image_openai_2stage(file: UploadFile = File(...)) -> OCRResult:
    """Extract using 2-stage OpenAI (extract + normalize) - best accuracy for handwritten text."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Tệp phải là ảnh (JPG, PNG, etc.)")

    if not HAS_OCR_PROCESSOR:
        raise HTTPException(status_code=503, detail="OCR không khả dụng.")

    try:
        contents = await file.read()
        result = extract_from_image_openai_2stage(contents)  # Use 2-stage (extract + normalize)

        # Required fields: name, phone, province (bưu cục)
        # Ward + address detail are optional
        required_fields = ["sender_name", "sender_phone", "sender_province",
                          "receiver_name", "receiver_phone", "receiver_province"]
        missing = [f for f in required_fields if not result.get(f)]

        return OCRResult(
            sender_name=result.get("sender_name", ""),
            sender_phone=result.get("sender_phone", ""),
            sender_province=result.get("sender_province", ""),
            sender_ward=result.get("sender_ward", ""),
            sender_address=result.get("sender_address", ""),
            receiver_name=result.get("receiver_name", ""),
            receiver_phone=result.get("receiver_phone", ""),
            receiver_province=result.get("receiver_province", ""),
            receiver_ward=result.get("receiver_ward", ""),
            receiver_address=result.get("receiver_address", ""),
            item_description="",
            raw_text=result.get("raw_text", ""),
            missing_fields=missing
        )
    except Exception as error:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý ảnh: {str(error)}") from error


def _generate_vietqr(bank_code: str, account: str, amount: int, name: str, description: str = "") -> bytes:
    """Generate VietQR code for banking transfer."""
    # VietQR format - simplified version
    # Real implementation would use vietqr library
    vietqr_data = f"00020101051500340010A000000727{bank_code}0{len(account):02d}{account}520{len(str(amount)):02d}{amount:010d}5802VN62170499{description[:30]}"

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(vietqr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    return output.getvalue()


@app.get("/qrcode")
async def generate_qrcode(amount_vnd: int = 0) -> StreamingResponse:
    """Generate a demo QR; it does not initiate a bank transfer."""
    if not HAS_QRCODE:
        raise HTTPException(status_code=503, detail="Install the base requirements to generate QR codes.")
    if amount_vnd < 0:
        raise HTTPException(status_code=422, detail="Amount must be non-negative.")
    payload = f"POSTFLOW-DEMO|amount_vnd={amount_vnd}|NO_REAL_PAYMENT"
    qr_image = qrcode.make(payload)
    output = BytesIO()
    qr_image.save(output, format="PNG")
    output.seek(0)
    return StreamingResponse(output, media_type="image/png")


@app.post("/detect-dimension")
async def detect_dimension(
    file: UploadFile = File(..., description="Image of box side"),
    cm_per_pixel: float = 0.0525
) -> dict:
    """Detect single dimension from one image (for progressive capture).

    Returns detected dimension in cm.
    """
    if not HAS_VOLUME_DETECTOR:
        raise HTTPException(status_code=503, detail="Volume detector unavailable. Install: pip install opencv-python numpy")

    try:
        from backend.volume_detector import detect_dimension_from_image

        # Read image bytes
        image_bytes = await file.read()

        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        # Detect single dimension
        dimension_cm = detect_dimension_from_image(image_bytes, cm_per_pixel)

        if dimension_cm is None or dimension_cm <= 0:
            return {
                "status": "failed",
                "dimension_cm": None,
                "error": "Could not detect edge in image"
            }

        return {
            "status": "success",
            "dimension_cm": round(dimension_cm, 2),
            "error": None
        }
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Detection error: {str(error)}")


@app.post("/detect-volume")
async def detect_volume(
    file_length: UploadFile = File(..., description="Image of length side"),
    file_width: UploadFile = File(..., description="Image of width side"),
    file_height: UploadFile = File(..., description="Image of height side"),
    cm_per_pixel: float = 0.21
) -> VolumeDetectResult:
    """Auto-detect box dimensions from 3 images with edge visualization.

    Takes 3 box side images (length, width, height) and detects their dimensions
    using edge detection + calibration ratio. Returns annotated images with edges drawn.
    """
    if not HAS_VOLUME_DETECTOR:
        raise HTTPException(status_code=503, detail="Volume detector không khả dụng. Cần cài: pip install opencv-python numpy")

    try:
        # Read image bytes
        length_bytes = await file_length.read()
        width_bytes = await file_width.read()
        height_bytes = await file_height.read()

        # Debug: check file sizes
        print(f"[Volume] File sizes: length={len(length_bytes)}, width={len(width_bytes)}, height={len(height_bytes)}")

        # Validate files not empty
        if not length_bytes or not width_bytes or not height_bytes:
            raise HTTPException(status_code=400, detail="File rỗng - upload ảnh thất bại")

        # Detect dimensions with annotated images
        from backend.volume_detector import detect_dimensions_with_images
        result = detect_dimensions_with_images([length_bytes, width_bytes, height_bytes], cm_per_pixel)

        return VolumeDetectResult(
            status=result["status"],
            length_cm=result.get("length_cm"),
            width_cm=result.get("width_cm"),
            height_cm=result.get("height_cm"),
            volume_cm3=result.get("volume_cm3"),
            errors=result.get("errors", []),
            length_image=result.get("length_image"),
            width_image=result.get("width_image"),
            height_image=result.get("height_image")
        )
    except Exception as error:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Volume detection failed: {str(error)}")


@app.post("/detect-weight")
async def detect_weight(file: UploadFile = File(..., description="Image of scale")) -> dict:
    """Auto-detect weight from scale image using YOLO11s model.

    Takes an image of a scale display and detects the weight value.
    Returns weight in kg.
    """
    try:
        # Read image bytes
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="File rỗng - upload ảnh thất bại")

        print(f"[Weight] File size: {len(image_bytes)} bytes")

        # Import weight detector
        from backend.weight_detector import detect_weight_from_image_with_visual

        # Detect weight with annotated image
        weight, annotated_bytes = detect_weight_from_image_with_visual(image_bytes)

        if weight is None:
            return {
                "status": "failed",
                "weight_kg": None,
                "error": "Không phát hiện được cân",
                "image": None
            }

        # Convert annotated image to base64
        import base64
        image_b64 = "data:image/jpeg;base64," + base64.b64encode(annotated_bytes).decode()

        return {
            "status": "success",
            "weight_kg": round(float(weight), 2),
            "error": None,
            "image": image_b64
        }

    except Exception as error:
        import traceback
        traceback.print_exc()
        return {
            "status": "failed",
            "weight_kg": None,
            "error": f"Weight detection failed: {str(error)}",
            "image": None
        }


@app.post("/ocr-hybrid")
async def ocr_hybrid(file: UploadFile = File(..., description="Postal form image")) -> dict:
    """Hybrid OCR: Claude API + TrOCR Vietnamese.

    Combines Claude's structured OCR with TrOCR's word-level detection
    for maximum accuracy.
    """
    try:
        print("\n" + "🔷"*30)
        print("🔷 HYBRID OCR ENDPOINT CALLED 🔷")
        print("🔷"*30)

        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="File rỗng - upload ảnh thất bại")

        print(f"[Endpoint] Processing image: {file.filename}")
        print(f"[Endpoint] File size: {len(image_bytes)} bytes")

        from backend.hybrid_ocr import hybrid_ocr

        result = hybrid_ocr(image_bytes)

        print(f"[Endpoint] ✅ Hybrid OCR completed successfully")

        # Return structured format
        return {
            "sender_name": result.get("sender_name", ""),
            "sender_phone": result.get("sender_phone", ""),
            "sender_province": result.get("sender_province", ""),
            "sender_ward": result.get("sender_ward", ""),
            "sender_address": result.get("sender_address", ""),
            "receiver_name": result.get("receiver_name", ""),
            "receiver_phone": result.get("receiver_phone", ""),
            "receiver_province": result.get("receiver_province", ""),
            "receiver_ward": result.get("receiver_ward", ""),
            "receiver_address": result.get("receiver_address", ""),
            "item_description": result.get("item_description", ""),
            "missing_fields": result.get("missing_fields", []),
            "trocr_words": result.get("trocr_words", []),
            "layout": result.get("layout", {}),
            "organized_text": result.get("organized_text", "")
        }

    except Exception as error:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Hybrid OCR failed: {str(error)}")


@app.post("/extract-from-text")
async def extract_from_text(req: ExtractRequest) -> dict:
    """Extract shipping info from OCR text by parsing structured format."""
    import re

    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Cần provide text OCR")

    try:
        result = {
            "sender_name": "",
            "sender_phone": "",
            "sender_province": "",
            "sender_ward": "",
            "sender_address": "",
            "receiver_name": "",
            "receiver_phone": "",
            "receiver_province": "",
            "receiver_ward": "",
            "receiver_address": "",
            "item_description": ""
        }

        # Split by person sections (Người gửi / Người nhận)
        lines = text.split('\n')
        current_section = None
        section_prefix = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect section
            if 'Người gửi' in line or 'người gửi' in line:
                current_section = 'sender'
                section_prefix = 'sender_'
                continue
            elif 'Người nhận' in line or 'người nhận' in line:
                current_section = 'receiver'
                section_prefix = 'receiver_'
                continue

            # Parse field lines
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()

                if 'tên' in key and current_section:
                    result[f'{section_prefix}name'] = value
                elif 'điện thoại' in key or 'sđt' in key:
                    result[f'{section_prefix}phone'] = value
                elif 'tỉnh' in key or 'thành phố' in key:
                    result[f'{section_prefix}province'] = value
                elif 'phường' in key or 'xã' in key:
                    result[f'{section_prefix}ward'] = value
                elif 'địa chỉ' in key:
                    result[f'{section_prefix}address'] = value
                elif 'mô tả' in key or 'hàng' in key or 'nội dung' in key:
                    result['item_description'] = value

        # Validate required fields
        required = ['sender_name', 'sender_phone', 'sender_province', 'receiver_name', 'receiver_phone', 'receiver_province']
        missing = [f for f in required if not result.get(f)]

        return {
            **result,
            "missing_fields": missing
        }

    except Exception as error:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Extract error: {str(error)}")


@app.post("/ocr-image-openai")
async def ocr_image_openai(file: UploadFile = File(...)) -> OCRResult:
    """Extract shipping info from image using OpenAI Vision API (faster, ~2-3s)."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Tệp phải là ảnh (JPG, PNG, etc.)")

    if not HAS_OCR_PROCESSOR:
        raise HTTPException(status_code=503, detail="OCR không khả dụng.")

    try:
        contents = await file.read()
        result = extract_from_image_openai(contents)

        # Required fields: name, phone, province (bưu cục)
        # Ward + address detail are optional
        required_fields = ["sender_name", "sender_phone", "sender_province",
                          "receiver_name", "receiver_phone", "receiver_province"]
        missing = [f for f in required_fields if not result.get(f)]

        return OCRResult(
            sender_name=result.get("sender_name", ""),
            sender_phone=result.get("sender_phone", ""),
            sender_province=result.get("sender_province", ""),
            sender_ward=result.get("sender_ward", ""),
            sender_address=result.get("sender_address", ""),
            receiver_name=result.get("receiver_name", ""),
            receiver_phone=result.get("receiver_phone", ""),
            receiver_province=result.get("receiver_province", ""),
            receiver_ward=result.get("receiver_ward", ""),
            receiver_address=result.get("receiver_address", ""),
            item_description="",
            raw_text=result.get("raw_text", ""),
            missing_fields=missing
        )
    except Exception as error:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý ảnh: {str(error)}") from error


@app.post("/ocr")
async def process_ocr(file: UploadFile = File(...)) -> OCRResult:
    """Extract text and information from an image using Vintern-1B-v3_5 OCR model."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Tệp phải là ảnh (JPG, PNG, etc.)")

    try:
        # Load image
        contents = await file.read()
        image = Image.open(BytesIO(contents))

        # Load OCR model
        model, tokenizer = _load_ocr_model()
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Prepare image for model using the model's internal processor
        # The model handles image preprocessing internally via chat
        with torch.no_grad():
            prompt = """Hãy trích xuất thông tin từ ảnh này về một đơn gửi hàng:
        - Tên người gửi (sender_name)
        - Số điện thoại người gửi (sender_phone): định dạng 09xxxxxxxx
        - Tỉnh/thành phố người gửi (origin)
        - Tên người nhận (receiver_name)
        - Số điện thoại người nhận (receiver_phone): định dạng 09xxxxxxxx
        - Tỉnh/thành phố người nhận (destination)
        - Nội dung hàng hóa (item_description)

        Trả về kết quả dưới dạng JSON hoặc danh sách các thông tin tìm được."""

            generation_config = {
                "max_new_tokens": 512,
                "do_sample": False,
            }

            response = model.chat(tokenizer, image, prompt, generation_config)

        # Parse OCR response
        parsed = _parse_ocr_result(response)
        parsed["raw_text"] = response[:200]  # Truncate for response

        return OCRResult(**parsed)

    except Exception as error:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý ảnh: {str(error)}") from error


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/process-document")
async def process_document_endpoint(file: UploadFile) -> DocumentProcessResult:
    """Process document: Classify type + Detect & crop info region.

    Pipeline:
    1. Envelope_box_detection.pt → Classify: Thư từ (LETTER) or Hàng hóa (GOODS)
    2. info.pt → Detect info region
    3. Crop info region from original image
    4. Return cropped image for OCR input

    Args:
        file: Image file (JPEG, PNG, etc.)

    Returns:
        DocumentProcessResult with:
        - success: bool
        - service_type: "LETTER" or "GOODS"
        - service_confidence: float (0.0-1.0)
        - info_bbox: (x1, y1, x2, y2) or None
        - info_region_base64: Cropped image (base64) for OCR
        - error: Error message if failed
    """
    if not HAS_DOCUMENT_PROCESSOR:
        raise HTTPException(status_code=503, detail="Document processor không khả dụng. Cần: pip install ultralytics")

    try:
        # Read image bytes
        image_bytes = await file.read()

        # Process document
        result = process_document(image_bytes, padding=10)

        # Convert info_region_bytes to base64
        import base64
        info_region_base64 = ""
        if result["info_region_bytes"]:
            info_region_base64 = base64.b64encode(result["info_region_bytes"]).decode("utf-8")

        return DocumentProcessResult(
            success=result["success"],
            service_type=result["service_type"],
            service_confidence=result["service_confidence"],
            info_bbox=result["info_bbox"],
            info_region_base64=info_region_base64,
            error=result["error"]
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}") from e


@app.post("/process-document-full")
async def process_document_full_endpoint(file: UploadFile) -> ProcessDocumentFullResult:
    """Full pipeline: Classify + Crop + OCR extract structured fields.

    Pipeline:
    1. /process-document: Classify & crop info region
    2. Claude Vision: OCR the cropped region to extract structured fields
    3. Return all extracted fields + classification result

    Args:
        file: Image file (JPEG, PNG, etc.)

    Returns:
        ProcessDocumentFullResult with:
        - success: bool
        - service_type: "LETTER" or "GOODS"
        - sender_name, sender_phone, sender_province, sender_ward, sender_address
        - receiver_name, receiver_phone, receiver_province, receiver_ward, receiver_address
        - item_description
        - missing_fields: List of required fields that are empty
        - error: Error message if failed
    """
    if not HAS_DOCUMENT_PROCESSOR or not HAS_ANTHROPIC:
        raise HTTPException(status_code=503, detail="Cần cài: pip install ultralytics anthropic")

    try:
        import base64

        # Step 1: Read image bytes
        image_bytes = await file.read()

        # Step 2: Process document (classify + crop)
        result = process_document(image_bytes, padding=10)

        if not result["success"]:
            return ProcessDocumentFullResult(
                success=False,
                service_type=None,
                service_confidence=0.0,
                error=result["error"]
            )

        # Step 3: OCR the cropped info region
        info_region_bytes = result["info_region_bytes"]
        if not info_region_bytes:
            return ProcessDocumentFullResult(
                success=False,
                service_type=result["service_type"],
                service_confidence=result["service_confidence"],
                error="Không thể trích xuất vùng thông tin"
            )

        # Encode cropped region to base64
        crop_b64 = base64.standard_b64encode(info_region_bytes).decode()

        # Call Claude Vision API on cropped region
        client = Anthropic()
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
                            "data": crop_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": """Hãy trích xuất các thông tin vận chuyển từ ảnh này.
Trả về CHỈ một JSON object với các trường sau (để trống "" nếu không tìm thấy):
{
  "sender_name": "tên người gửi",
  "sender_phone": "SĐT người gửi",
  "sender_province": "tỉnh/thành phố người gửi",
  "sender_ward": "quận/huyện/xã người gửi",
  "sender_address": "địa chỉ chi tiết người gửi",
  "receiver_name": "tên người nhận",
  "receiver_phone": "SĐT người nhận",
  "receiver_province": "tỉnh/thành phố người nhận",
  "receiver_ward": "quận/huyện/xã người nhận",
  "receiver_address": "địa chỉ chi tiết người nhận",
  "item_description": "mô tả hàng hóa"
}"""
                    }
                ]
            }]
        )

        # Parse Claude response
        ocr_text = response.content[0].text
        start = ocr_text.find('{')
        end = ocr_text.rfind('}') + 1

        ocr_data = {}
        if start != -1 and end > start:
            try:
                ocr_data = json.loads(ocr_text[start:end])
            except json.JSONDecodeError:
                pass

        # Identify missing fields
        required_fields = ["sender_name", "sender_phone", "sender_province",
                          "receiver_name", "receiver_phone", "receiver_province"]
        missing = [f for f in required_fields if not ocr_data.get(f)]

        return ProcessDocumentFullResult(
            success=True,
            service_type=result["service_type"],
            service_confidence=result["service_confidence"],
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


@app.post("/process-document-trocr")
async def process_document_trocr_endpoint(file: UploadFile) -> ProcessDocumentFullResult:
    """Full pipeline: Classify + Crop + TrOCR + Claude Extract.

    Pipeline:
    1. /process-document: Classify & crop info region
    2. TrOCR: Detect text regions in cropped image
    3. Claude API: Parse OCR text into structured fields

    Args:
        file: Image file (JPEG, PNG, etc.)

    Returns:
        ProcessDocumentFullResult with extracted customer information
    """
    if not HAS_DOCUMENT_PROCESSOR or not HAS_HYBRID_OCR or not HAS_ANTHROPIC:
        raise HTTPException(status_code=503, detail="Cần cài: pip install ultralytics transformers anthropic")

    try:
        import base64

        # Step 1: Read image and process document
        image_bytes = await file.read()
        result = process_document(image_bytes, padding=10)

        # Determine which image to use for TrOCR
        if result["success"] and result["info_region_bytes"]:
            # ✅ Use cropped info region
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

        # Step 2: Detect text regions with TrOCR
        trocr_regions = detect_text_regions(ocr_image_bytes)

        if not trocr_regions:
            return ProcessDocumentFullResult(
                success=False,
                service_type=service_type,
                service_confidence=service_confidence,
                error="Không phát hiện được text"
            )

        # Step 3: Organize text layout and parse with Claude
        layout_dict, organized_raw_text = organize_text_layout(trocr_regions)

        # Parse organized text with Claude
        ocr_data = parse_organized_text_to_schema(organized_raw_text)

        # Identify missing fields
        required_fields = ["sender_name", "sender_phone", "sender_province",
                          "receiver_name", "receiver_phone", "receiver_province"]
        missing = [f for f in required_fields if not ocr_data.get(f)]

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


@app.post("/ocr-box")
async def ocr_box_endpoint(file: UploadFile) -> BoxOCRResult:
    """Extract text from box image using Claude Vision API.

    Args:
        file: Image file (box with printed/handwritten text)

    Returns:
        BoxOCRResult with:
        - success: bool
        - text: Full extracted text
        - lines: Text split by lines
        - error: Error message if failed
    """
    if not HAS_ANTHROPIC:
        raise HTTPException(status_code=503, detail="Claude API không khả dụng. Cần: pip install anthropic")

    try:
        import base64

        # Read image bytes
        image_bytes = await file.read()

        # Encode to base64
        image_b64 = base64.standard_b64encode(image_bytes).decode()

        # Create Claude client
        client = Anthropic()

        # Call Claude Vision API
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
                        "text": """Hãy trích xuất TẤT CẢ văn bản/thông tin có trong ảnh này.
Bao gồm: tên, địa chỉ, SĐT, mã bưu điện, barcode, số đơn, hoặc bất kỳ text nào khác.
Trả về kết quả dưới dạng văn bản thô, từng dòng một."""
                    }
                ]
            }]
        )

        # Extract text
        extracted_text = response.content[0].text.strip()
        lines = [line.strip() for line in extracted_text.split('\n') if line.strip()]

        return BoxOCRResult(
            success=True,
            text=extracted_text,
            lines=lines,
            error=None
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return BoxOCRResult(
            success=False,
            text="",
            lines=[],
            error=f"Lỗi xử lý ảnh: {str(e)}"
        )


@app.post("/detect-dimensions-v2")
async def detect_dimensions_endpoint(file: UploadFile,
                                     reference_mode: str = "VERTICAL") -> DimensionDetectResult:
    """Detect package dimensions (single camera): YOLO + Edge detection.

    Pipeline:
    1. YOLO detect package ROI
    2. Extract horizontal/vertical edges from ROI
    3. Measure dimensions (simple 1-camera)
    4. Calculate volume

    Args:
        file: Image file (cropped info region from /process-document)
        reference_mode: Ignored (kept for backward compatibility)

    Returns:
        DimensionDetectResult with:
        - success: bool
        - length_cm, width_cm, height_cm: Dimensions in cm
        - volume_cm3: Volume in cm³
        - annotated_image_base64: Visualization (base64)
        - error: Error message if failed
    """
    if not HAS_DIMENSION_DETECTOR:
        raise HTTPException(status_code=503, detail="Dimension detector không khả dụng. Cần: pip install ultralytics")

    try:
        # Read image bytes
        image_bytes = await file.read()

        # Detect dimensions
        result = detect_dimensions(image_bytes, reference_mode=reference_mode)

        return DimensionDetectResult(
            success=result["success"],
            length_cm=result["length_cm"],
            width_cm=result["width_cm"],
            height_cm=result["height_cm"],
            volume_cm3=result["volume_cm3"],
            annotated_image_base64=result.get("annotated_image_base64", ""),
            error=result["error"]
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error detecting dimensions: {str(e)}") from e


@app.post("/detect-dimensions-dual")
async def detect_dimensions_dual_endpoint(file_cam1: UploadFile,
                                         file_cam2: UploadFile,
                                         reference_mode: str = "VERTICAL") -> DimensionDetectDualResult:
    """Detect package dimensions (2 cameras) with reference logic: CAM1 + CAM2 → L×W×H.

    Pipeline:
    1. Measure CAM1: NGANG_1 + DỌC_1
    2. Measure CAM2: NGANG_2 + DỌC_2
    3. Apply reference logic: NGANG_1 <-> DỌC_2 (or NGANG_1 <-> NGANG_2)
    4. Calculate final L×W×H + Volume

    Two reference modes:
    - VERTICAL: NGANG_1 (cam1) <-> DỌC_2 (cam2)  → Different orientations
    - HORIZONTAL: NGANG_1 (cam1) <-> NGANG_2 (cam2) → Same orientation

    Args:
        file_cam1: First camera image (Input 1)
        file_cam2: Second camera image (Input 2)
        reference_mode: "VERTICAL" (default) or "HORIZONTAL"

    Returns:
        DimensionDetectDualResult with:
        - success: bool
        - length_cm, width_cm, height_cm: Calculated dimensions in cm
        - volume_cm3: Volume in cm³
        - camera1: Details of Camera 1 measurements (ngang_1_cm, doc_1_cm, etc.)
        - camera2: Details of Camera 2 measurements (ngang_2_cm, doc_2_cm, ratio, etc.)
        - reference: Relationship used ("NGANG_1 <-> DỌC_2" or "NGANG_1 <-> NGANG_2")
        - annotated_image_base64: Visualization on Camera 1 image (base64)
        - error: Error message if failed
    """
    if not HAS_DIMENSION_DETECTOR:
        raise HTTPException(status_code=503, detail="Dimension detector không khả dụng. Cần: pip install ultralytics")

    try:
        # Read image bytes
        image_bytes_cam1 = await file_cam1.read()
        image_bytes_cam2 = await file_cam2.read()

        # Detect dimensions with 2-camera reference logic
        result = detect_dimensions_dual(image_bytes_cam1, image_bytes_cam2,
                                       reference_mode=reference_mode)

        return DimensionDetectDualResult(
            success=result["success"],
            length_cm=result["length_cm"],
            width_cm=result["width_cm"],
            height_cm=result["height_cm"],
            volume_cm3=result["volume_cm3"],
            camera1=result.get("camera1"),
            camera2=result.get("camera2"),
            reference=result.get("reference"),
            annotated_image_base64=result.get("annotated_image_base64", ""),
            error=result["error"]
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error detecting dimensions (dual): {str(e)}") from e


@app.get("/detect-dimensions-esp32")
async def detect_dimensions_esp32_endpoint(esp32_url: str = os.getenv("ESP32_URL", "http://esp32-buudien.local/distance")) -> DimensionDetectResult:
    """Fetch package dimensions from ESP32 ultrasonic sensors.

    Simple sensor-based measurement: fetch 3 distances and return L×W×H directly.

    ESP32 API should return:
    {
        "sensor1": {"success": true, "distance": 30.5},  # Length (cm)
        "sensor2": {"success": true, "distance": 20.3},  # Width (cm)
        "sensor3": {"success": true, "distance": 15.8}   # Height (cm)
    }

    Args:
        esp32_url: ESP32 API endpoint URL (default: http://esp32-buudien.local/distance)

    Returns:
        DimensionDetectResult with:
        - success: bool
        - length_cm, width_cm, height_cm: Dimensions in cm
        - volume_cm3: Volume in cm³
        - error: Error message if failed
    """
    if not HAS_DIMENSION_DETECTOR:
        raise HTTPException(status_code=503, detail="Dimension detector không khả dụng")

    try:
        result = detect_dimensions_esp32(esp32_url=esp32_url)

        return DimensionDetectResult(
            success=result["success"],
            length_cm=result["length_cm"],
            width_cm=result["width_cm"],
            height_cm=result["height_cm"],
            volume_cm3=result["volume_cm3"],
            annotated_image_base64=None,
            error=result["error"]
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching ESP32 dimensions: {str(e)}") from e


@app.post("/detect-dimensions-multi-camera")
async def detect_dimensions_multi_camera_endpoint(file_cam1: UploadFile = File(...),
                                                  file_cam2: UploadFile = File(...)) -> dict:
    """Detect package dimensions using 2 cameras with multi-line edge detection.

    Pipeline:
    1. Camera 1 (reference): Measure NGANG_1 (width) + DOC_1 (height)
    2. Camera 2 (dependent): Measure DOC_2 + NGANG_2 using CAM1 scale
    3. Calculate volume: NGANG_1 × DOC_1 × NGANG_2

    Algorithm: Multi-line edge detection (9 scan lines per direction)
    - Scans multiple lines to find stable edges
    - Avoids logos/text in center using outer edge preference
    - Clusters edge positions for robustness

    Args:
        file_cam1: Image from camera 1 (reference)
        file_cam2: Image from camera 2 (dependent)

    Returns:
        dict with:
        - success: bool
        - ngang_1_cm, doc_1_cm: Camera 1 measurements (reference)
        - doc_2_cm, ngang_2_cm: Camera 2 measurements (using scale from CAM1)
        - volume_cm3: Calculated volume
        - error: Error message if failed
    """
    if not HAS_MULTI_CAMERA_DETECTOR:
        raise HTTPException(status_code=503, detail="Multi-camera detector không khả dụng. Cần: pip install opencv-python numpy")

    try:
        import cv2
        import numpy as np

        # Read image bytes
        frame1_bytes = await file_cam1.read()
        frame2_bytes = await file_cam2.read()

        # Decode images
        nparr1 = np.frombuffer(frame1_bytes, np.uint8)
        frame1 = cv2.imdecode(nparr1, cv2.IMREAD_COLOR)

        nparr2 = np.frombuffer(frame2_bytes, np.uint8)
        frame2 = cv2.imdecode(nparr2, cv2.IMREAD_COLOR)

        if frame1 is None or frame2 is None:
            return {
                "success": False,
                "ngang_1_cm": None,
                "doc_1_cm": None,
                "doc_2_cm": None,
                "ngang_2_cm": None,
                "volume_cm3": None,
                "error": "Invalid image format"
            }

        # Measure both cameras
        result = measure_multi_camera(frame1, frame2)

        return {
            "success": result["success"],
            "ngang_1_cm": result["ngang_1_cm"],
            "doc_1_cm": result["doc_1_cm"],
            "doc_2_cm": result["doc_2_cm"],
            "ngang_2_cm": result["ngang_2_cm"],
            "volume_cm3": result["volume_cm3"],
            "cam1_image": result.get("cam1_image_base64"),
            "cam2_image": result.get("cam2_image_base64"),
            "error": result.get("error")
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "ngang_1_cm": None,
            "doc_1_cm": None,
            "doc_2_cm": None,
            "ngang_2_cm": None,
            "volume_cm3": None,
            "error": f"Error detecting dimensions: {str(e)}"
        }


@app.get("/provinces")
def get_provinces() -> dict:
    """Return list of post offices for dropdown."""
    post_offices_data = REGIONS_DATA.get("post_offices", {})
    # Return list of post office names sorted
    post_office_list = sorted(set(post_offices_data.values())) if post_offices_data else sorted(set(ALL_PROVINCES))
    return {"post_offices": post_office_list}


@app.get("/", include_in_schema=False)
def kiosk_page() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "index.html")


@app.get("/app.js", include_in_schema=False)
def frontend_script() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app.js", media_type="application/javascript")


@app.get("/styles.css", include_in_schema=False)
def frontend_styles() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "styles.css", media_type="text/css")


@app.post("/quotes")
def quote(request: QuoteRequest) -> dict:
    try:
        return calculate_shipping_fee(**request.model_dump()).to_dict()
    except PricingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/orders", status_code=201)
def create_new_order(request: OrderCreate) -> dict:
    try:
        # Validate provinces, service and possible route
        calculate_shipping_fee(
            service=request.service, origin=request.sender_province, destination=request.receiver_province,
            actual_weight_kg=0.1, length_cm=1, width_cm=1, height_cm=1,
        )
    except PricingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    tracking_code = f"PF{uuid4().hex[:10].upper()}"
    now = _now()
    # Generate tracking code and store in memory (will save to DB on payment confirmation)
    order = {"tracking_code": tracking_code, **request.model_dump(), "status": "WAITING_FOR_MEASUREMENT", "created_at": now, "updated_at": now}
    _orders_in_progress[tracking_code] = order
    return order


@app.get("/orders/{tracking_code}")
def read_order(tracking_code: str) -> dict:
    # Check in-memory storage first (order in progress)
    if tracking_code in _orders_in_progress:
        order = _orders_in_progress[tracking_code].copy()
        order["used_volumetric_weight"] = bool(order.get("used_volumetric_weight", 0))
        return order
    # Then check database (completed orders)
    return _require_order(tracking_code)


@app.get("/orders/{tracking_code}/barcode", include_in_schema=False)
async def get_barcode(tracking_code: str):
    """Generate and return barcode image for tracking code."""
    order = _require_order(tracking_code)  # Validate order exists
    barcode_image = _generate_barcode(order["tracking_code"])
    return StreamingResponse(barcode_image, media_type="image/png")


@app.post("/orders/{tracking_code}/measurements")
def save_measurements(tracking_code: str, request: MeasurementRequest) -> dict:
    # Get from in-memory storage (not from DB)
    if tracking_code not in _orders_in_progress:
        raise HTTPException(status_code=404, detail=f"Đơn hàng {tracking_code} không tìm thấy.")

    order = _orders_in_progress[tracking_code]
    if order["status"] == "PAID":
        raise HTTPException(status_code=409, detail="Đơn đã thanh toán, không thể đổi số đo.")

    try:
        quote = calculate_shipping_fee(service=order["service"], origin=order["sender_province"], destination=order["receiver_province"], **request.model_dump())
    except PricingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    # Update in-memory order
    order.update({
        **request.model_dump(),
        "route": quote.route,
        "chargeable_weight_kg": quote.chargeable_weight_kg,
        "used_volumetric_weight": quote.used_volumetric_weight,
        "amount_vnd": quote.amount_vnd,
        "status": "WAITING_FOR_PAYMENT",
        "updated_at": _now()
    })
    _orders_in_progress[tracking_code] = order

    # Return with boolean conversion
    result = order.copy()
    result["used_volumetric_weight"] = bool(result["used_volumetric_weight"])
    return result


@app.post("/orders/{tracking_code}/mock-payment")
def mock_payment(tracking_code: str) -> dict:
    """Confirm payment and SAVE order to database (ONLY time order is persisted)."""
    # Get from in-memory storage
    if tracking_code not in _orders_in_progress:
        raise HTTPException(status_code=404, detail=f"Đơn hàng {tracking_code} không tìm thấy.")

    order = dict(_orders_in_progress[tracking_code])
    if order["status"] != "WAITING_FOR_PAYMENT":
        raise HTTPException(status_code=409, detail="Đơn chưa sẵn sàng để thanh toán.")

    # Set PAID status
    order["status"] = "PAID"
    order["updated_at"] = _now()

    # SAVE to database (first and only time)
    create_order(order)

    # Clean up memory
    del _orders_in_progress[tracking_code]

    result = order.copy()
    result["used_volumetric_weight"] = bool(result.get("used_volumetric_weight", 0))
    return result
