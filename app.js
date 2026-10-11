const API = location.protocol === 'file:' ? 'http://127.0.0.1:8000' : '';
const $ = id => document.getElementById(id);
const money = v => new Intl.NumberFormat('vi-VN', {minimumFractionDigits: 0, maximumFractionDigits: 2}).format(v) + ' ₫';

let data = {};
let quote = null;

function fillFormFromExtraction(result) {
  const fields = ['sender_name', 'sender_phone', 'sender_province', 'sender_ward', 'sender_address',
                  'receiver_name', 'receiver_phone', 'receiver_province', 'receiver_ward', 'receiver_address',
                  'item_description'];
  const form = $('form1');
  fields.forEach(field => {
    const input = form.elements[field] || form.querySelector('[name="' + field + '"]');
    if (input && result[field]) {
      input.value = result[field];
    }
  });
}

function show(step) {
  document.querySelectorAll('.step').forEach(el => el.classList.add('hidden'));
  $(step).classList.remove('hidden');
}

async function api(path, opts = {}) {
  const r = await fetch(API + path, {headers: {'Content-Type': 'application/json'}, ...opts});
  const b = await r.json();
  if (!r.ok) throw new Error(b.detail || 'Lỗi');
  return b;
}

async function checkApi() {
  try {
    await api('/health');
    $('apiStatus').textContent = '● API đã kết nối';
    $('apiStatus').classList.add('online');
  } catch {
    $('apiStatus').textContent = '● API chưa chạy';
  }
}


// ========== STEP 1: Camera + OCR ==========

async function initCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}});
    const video = $('videoStream');
    video.srcObject = stream;
    $('cameraContainer').style.display = 'block';
    $('noCameraMessage').style.display = 'none';
    $('captureBtn').style.display = 'block';
  } catch (err) {
    $('noCameraMessage').textContent = '❌ Không thể kết nối camera. Kiểm tra DroidCam.';
  }
}

async function captureAndUpload() {
  const video = $('videoStream');
  const canvas = $('captureCanvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);

  $('ocrLoading').classList.remove('hidden');
  $('ocrResult').classList.add('hidden');

  try {
    canvas.toBlob(async blob => {
      const formData = new FormData();
      formData.append('file', blob, 'capture.jpg');
      // Use hybrid OCR (Claude + TrOCR) instead of Claude only
      const endpoint = API + '/ocr-hybrid';
      console.log('[OCR] Using hybrid OCR endpoint:', endpoint);
      const response = await fetch(endpoint, {method: 'POST', body: formData});
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Lỗi OCR');
      }
      const result = await response.json();
      fillFormFromExtraction(result);

      const box = $('ocrResult');
      if (result.missing_fields.length === 0) {
        box.textContent = '✓ Thông tin đầy đủ!';
        box.style.background = '#d4edda';
        box.style.color = '#155724';
      } else {
        const labels = {'sender_name':'Tên gửi','sender_phone':'SĐT gửi','sender_province':'Bưu cục gửi','sender_ward':'Phường gửi','sender_address':'Địa chỉ gửi','receiver_name':'Tên nhận','receiver_phone':'SĐT nhận','receiver_province':'Bưu cục nhận','receiver_ward':'Phường nhận','receiver_address':'Địa chỉ nhận'};
        box.textContent = '⚠️ Thiếu: ' + result.missing_fields.map(f => labels[f] || f).join(', ');
        box.style.background = '#fff3cd';
        box.style.color = '#856404';
      }
      box.classList.remove('hidden');
      $('ocrLoading').classList.add('hidden');
    }, 'image/jpeg', 0.95);
  } catch (err) {
    const box = $('ocrResult');
    box.textContent = '✗ ' + err.message;
    box.style.background = '#f8d7da';
    box.style.color = '#721c24';
    box.classList.remove('hidden');
    $('ocrLoading').classList.add('hidden');
  }
}

$('captureBtn').addEventListener('click', captureAndUpload);

$('imageInput').addEventListener('change', async e => {
  const f = e.target.files[0];
  if (!f) return;

  $('ocrLoading').classList.remove('hidden');
  $('ocrResult').classList.add('hidden');

  try {
    const formData = new FormData();
    formData.append('file', f);
    // Use hybrid OCR (Claude + TrOCR)
    const endpoint = API + '/ocr-hybrid';
    console.log('[OCR] Using hybrid OCR endpoint:', endpoint);
    const response = await fetch(endpoint, {method: 'POST', body: formData});
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Lỗi OCR');
    }
    const result = await response.json();
    fillFormFromExtraction(result);

    const box = $('ocrResult');
    if (result.missing_fields.length === 0) {
      box.textContent = '✓ Thông tin đầy đủ!';
      box.style.background = '#d4edda';
      box.style.color = '#155724';
    } else {
      const labels = {'sender_name':'Tên gửi','sender_phone':'SĐT gửi','sender_province':'Bưu cục gửi','sender_ward':'Phường gửi','sender_address':'Địa chỉ gửi','receiver_name':'Tên nhận','receiver_phone':'SĐT nhận','receiver_province':'Bưu cục nhận','receiver_ward':'Phường nhận','receiver_address':'Địa chỉ nhận'};
      box.textContent = '⚠️ Thiếu: ' + result.missing_fields.map(f => labels[f] || f).join(', ');
      box.style.background = '#fff3cd';
      box.style.color = '#856404';
    }
    box.classList.remove('hidden');
    $('ocrLoading').classList.add('hidden');
  } catch (err) {
    const box = $('ocrResult');
    box.textContent = '✗ ' + err.message;
    box.style.background = '#f8d7da';
    box.style.color = '#721c24';
    box.classList.remove('hidden');
    $('ocrLoading').classList.add('hidden');
  }
});

// Extract from OCR text
$('extractFromTextBtn').addEventListener('click', async e => {
  const text = $('ocrTextInput').value.trim();
  if (!text) {
    alert('Vui lòng dán text OCR');
    return;
  }

  $('ocrLoading').classList.remove('hidden');
  $('ocrResult').classList.add('hidden');

  try {
    const response = await fetch(API + '/extract-from-text', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text})
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Lỗi extract');
    }

    const result = await response.json();
    fillFormFromExtraction(result);

    const box = $('ocrResult');
    if (result.missing_fields.length === 0) {
      box.textContent = '✓ Thông tin đầy đủ!';
      box.style.background = '#d4edda';
      box.style.color = '#155724';
    } else {
      const labels = {'sender_name':'Tên gửi','sender_phone':'SĐT gửi','sender_province':'Bưu cục gửi','sender_ward':'Phường gửi','sender_address':'Địa chỉ gửi','receiver_name':'Tên nhận','receiver_phone':'SĐT nhận','receiver_province':'Bưu cục nhận','receiver_ward':'Phường nhận','receiver_address':'Địa chỉ nhận'};
      box.textContent = '⚠️ Thiếu: ' + result.missing_fields.map(f => labels[f] || f).join(', ');
      box.style.background = '#fff3cd';
      box.style.color = '#856404';
    }
    box.classList.remove('hidden');
    $('ocrLoading').classList.add('hidden');
  } catch (err) {
    const box = $('ocrResult');
    box.textContent = '✗ ' + err.message;
    box.style.background = '#f8d7da';
    box.style.color = '#721c24';
    box.classList.remove('hidden');
    $('ocrLoading').classList.add('hidden');
  }
});

initCamera();

// ========== STEP 2: Measure ==========

async function initVolumeCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}});
    const video = $('volumeVideoStream');
    video.srcObject = stream;
    $('volumeCameraContainer').style.display = 'block';
    $('volumeNoCameraMsg').style.display = 'none';
  } catch (err) {
    $('volumeNoCameraMsg').textContent = '❌ Không thể kết nối camera. Kiểm tra DroidCam.';
  }
}

function captureVolumeFrame(side) {
  const video = $('volumeVideoStream');
  if (!video || !video.srcObject) {
    $('volumeCaptureStatus').textContent = '❌ Camera chưa kết nối';
    return;
  }

  const canvas = $('volumeCanvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);

  canvas.toBlob(blob => {
    // Store blob in file input via DataTransfer
    const dt = new DataTransfer();
    const file = new File([blob], `${side}.jpg`, {type: 'image/jpeg'});
    dt.items.add(file);

    const inputId = side === 'length' ? 'imgLength' : side === 'width' ? 'imgWidth' : 'imgHeight';
    $(inputId).files = dt.files;

    const sideLabel = {length: 'dài', width: 'rộng', height: 'cao'}[side];
    $('volumeCaptureStatus').textContent = `✓ Đã capture cạnh ${sideLabel}`;
  }, 'image/jpeg', 0.95);
}

$('captureLengthBtn')?.addEventListener('click', () => captureVolumeFrame('length'));
$('captureWidthBtn')?.addEventListener('click', () => captureVolumeFrame('width'));
$('captureHeightBtn')?.addEventListener('click', () => captureVolumeFrame('height'));

// Apply calibration button - recalculate with new cm_per_pixel
$('applyCalibrationBtn')?.addEventListener('click', async () => {
  const imgLength = $('imgLength').files[0];
  const imgWidth = $('imgWidth').files[0];
  const imgHeight = $('imgHeight').files[0];
  const cmPerPixel = parseFloat($('cmPerPixelCapture').value) || 0.21;
  console.log('[Calibration] cm_per_pixel:', cmPerPixel, 'from input:', $('cmPerPixelCapture').value);

  if (!imgLength || !imgWidth || !imgHeight) {
    $('volumeDetectResult').textContent = '⚠️ Cần chụp hoặc upload 3 ảnh trước';
    $('volumeDetectResult').style.background = '#fff3cd';
    $('volumeDetectResult').style.color = '#856404';
    $('volumeDetectResult').classList.remove('hidden');
    return;
  }

  $('volumeDetectLoading').classList.remove('hidden');
  $('volumeDetectResult').classList.add('hidden');

  try {
    const formData = new FormData();
    formData.append('file_length', imgLength);
    formData.append('file_width', imgWidth);
    formData.append('file_height', imgHeight);
    formData.append('cm_per_pixel', cmPerPixel);
    console.log('[Calibration] Sending cm_per_pixel:', cmPerPixel);

    const response = await fetch(API + '/detect-volume', {method: 'POST', body: formData});
    if (!response.ok) throw new Error((await response.json()).detail || 'Lỗi detect');

    const result = await response.json();
    const form = $('form2');
    if (result.length_cm) form.elements['length_cm'].value = result.length_cm;
    if (result.width_cm) form.elements['width_cm'].value = result.width_cm;
    if (result.height_cm) form.elements['height_cm'].value = result.height_cm;

    const box = $('volumeDetectResult');
    if (result.status === 'success') {
      box.textContent = `✓ Dài: ${result.length_cm}cm, Rộng: ${result.width_cm}cm, Cao: ${result.height_cm}cm`;
      box.style.background = '#d4edda';
      box.style.color = '#155724';
    } else if (result.status === 'partial') {
      const dims = [];
      if (result.length_cm) dims.push(`Dài: ${result.length_cm}cm`);
      if (result.width_cm) dims.push(`Rộng: ${result.width_cm}cm`);
      if (result.height_cm) dims.push(`Cao: ${result.height_cm}cm`);
      box.textContent = `⚠️ ${dims.join(', ')}`;
      box.style.background = '#fff3cd';
      box.style.color = '#856404';
    } else {
      box.textContent = `❌ ${result.errors?.join(', ') || 'Không detect được'}`;
      box.style.background = '#f8d7da';
      box.style.color = '#721c24';
    }
    box.classList.remove('hidden');

    if (result.length_image || result.width_image || result.height_image) {
      if (result.length_image) $('lengthPreview').src = result.length_image;
      if (result.width_image) $('widthPreview').src = result.width_image;
      if (result.height_image) $('heightPreview').src = result.height_image;
      $('previewImages').style.display = 'block';
    }
  } catch (err) {
    $('volumeDetectResult').textContent = '❌ ' + err.message;
    $('volumeDetectResult').style.background = '#f8d7da';
    $('volumeDetectResult').style.color = '#721c24';
    $('volumeDetectResult').classList.remove('hidden');
  } finally {
    $('volumeDetectLoading').classList.add('hidden');
  }
});

// File upload support
$('imgLength')?.addEventListener('change', () => $('volumeCaptureStatus').textContent = '✓ Đã chọn ảnh Dài');
$('imgWidth')?.addEventListener('change', () => $('volumeCaptureStatus').textContent = '✓ Đã chọn ảnh Rộng');
$('imgHeight')?.addEventListener('change', () => $('volumeCaptureStatus').textContent = '✓ Đã chọn ảnh Cao');

// Detect button
$('detectBtn')?.addEventListener('click', async () => {
  const imgLength = $('imgLength').files[0];
  const imgWidth = $('imgWidth').files[0];
  const imgHeight = $('imgHeight').files[0];
  const cmPerPixel = parseFloat($('cmPerPixelCapture').value) || 0.21;

  if (!imgLength || !imgWidth || !imgHeight) {
    $('volumeDetectResult').textContent = '⚠️ Cần chụp hoặc upload 3 ảnh (dài, rộng, cao)';
    $('volumeDetectResult').style.background = '#fff3cd';
    $('volumeDetectResult').style.color = '#856404';
    $('volumeDetectResult').classList.remove('hidden');
    return;
  }

  $('volumeDetectLoading').classList.remove('hidden');
  $('volumeDetectResult').classList.add('hidden');

  try {
    const formData = new FormData();
    formData.append('file_length', imgLength);
    formData.append('file_width', imgWidth);
    formData.append('file_height', imgHeight);
    formData.append('cm_per_pixel', cmPerPixel);

    const response = await fetch(API + '/detect-volume', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Lỗi detect');
    }

    const result = await response.json();

    // Auto-fill form fields
    const form = $('form2');
    if (result.length_cm) form.elements['length_cm'].value = result.length_cm;
    if (result.width_cm) form.elements['width_cm'].value = result.width_cm;
    if (result.height_cm) form.elements['height_cm'].value = result.height_cm;

    const box = $('volumeDetectResult');
    if (result.status === 'success') {
      box.textContent = `✓ Detect xong! Dài: ${result.length_cm}cm, Rộng: ${result.width_cm}cm, Cao: ${result.height_cm}cm (Thể tích: ${result.volume_cm3}cm³)`;
      box.style.background = '#d4edda';
      box.style.color = '#155724';
    } else if (result.status === 'partial') {
      const dims = [];
      if (result.length_cm) dims.push(`Dài: ${result.length_cm}cm`);
      if (result.width_cm) dims.push(`Rộng: ${result.width_cm}cm`);
      if (result.height_cm) dims.push(`Cao: ${result.height_cm}cm`);
      box.textContent = `⚠️ Detect 1 phần: ${dims.join(', ')}`;
      box.style.background = '#fff3cd';
      box.style.color = '#856404';
    } else {
      box.textContent = `❌ Không detect được. Lỗi: ${result.errors?.join(', ') || 'unknown'}`;
      box.style.background = '#f8d7da';
      box.style.color = '#721c24';
    }
    box.classList.remove('hidden');

    // Show preview images with edges
    if (result.length_image || result.width_image || result.height_image) {
      const previewDiv = $('previewImages');
      if (result.length_image) $('lengthPreview').src = result.length_image;
      if (result.width_image) $('widthPreview').src = result.width_image;
      if (result.height_image) $('heightPreview').src = result.height_image;
      previewDiv.style.display = 'block';
    }
  } catch (err) {
    const box = $('volumeDetectResult');
    box.textContent = '❌ ' + err.message;
    box.style.background = '#f8d7da';
    box.style.color = '#721c24';
    box.classList.remove('hidden');
  } finally {
    $('volumeDetectLoading').classList.add('hidden');
  }
});

// ========== WEIGHT DETECTION (reuse volume camera) ==========

function captureWeightFrame() {
  console.log('[Weight] Button clicked');

  // Use the same volume camera stream
  const video = $('volumeVideoStream');

  // Check if video element exists
  if (!video) {
    console.error('[Weight] Video element not found');
    showWeightError('❌ Lỗi: Không tìm thấy video element');
    return;
  }

  console.log('[Weight] Video element found, srcObject:', !!video.srcObject);

  // Check if camera stream is ready
  if (!video.srcObject) {
    console.error('[Weight] No camera stream');
    showWeightError('❌ Camera chưa kết nối. Vui lòng chụp chiều dài/rộng/cao trước.');
    return;
  }

  // Check video dimensions
  console.log('[Weight] Video dimensions:', video.videoWidth, 'x', video.videoHeight);
  if (video.videoWidth === 0 || video.videoHeight === 0) {
    console.error('[Weight] Video not loaded yet');
    showWeightError('❌ Camera chưa sẵn sàng. Thử lại sau 1 giây.');
    return;
  }

  console.log('[Weight] Capturing from volume camera...');
  const canvas = $('weightCanvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  console.log('[Weight] Canvas:', canvas.width, 'x', canvas.height);

  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);

  canvas.toBlob(blob => {
    if (!blob) {
      console.error('[Weight] Canvas toBlob failed');
      showWeightError('❌ Lỗi: Không thể capture ảnh');
      return;
    }

    console.log('[Weight] Blob created, size:', blob.size);

    // Store blob in file input via DataTransfer
    const dt = new DataTransfer();
    const file = new File([blob], 'weight.jpg', {type: 'image/jpeg'});
    dt.items.add(file);
    $('imgWeight').files = dt.files;

    console.log('[Weight] File added to input, calling detectWeight...');

    // Immediately send to backend for detection
    detectWeight();
  }, 'image/jpeg', 0.95);
}

function showWeightError(message) {
  const result = $('weightDetectResult');
  result.textContent = message;
  result.style.background = '#f8d7da';
  result.style.color = '#721c24';
  result.classList.remove('hidden');
}

async function detectWeight() {
  console.log('[Weight Detect] Starting...');
  const imgWeight = $('imgWeight').files[0];

  if (!imgWeight) {
    console.error('[Weight Detect] No file selected');
    const result = $('weightDetectResult');
    result.textContent = '⚠️ Cần chụp hoặc upload ảnh cân';
    result.style.background = '#fff3cd';
    result.style.color = '#856404';
    result.classList.remove('hidden');
    return;
  }

  console.log('[Weight Detect] File size:', imgWeight.size, 'bytes');

  $('weightDetectLoading').classList.remove('hidden');
  $('weightDetectResult').classList.add('hidden');

  try {
    const formData = new FormData();
    formData.append('file', imgWeight);

    console.log('[Weight Detect] Sending to backend:', API + '/detect-weight');
    const response = await fetch(API + '/detect-weight', {method: 'POST', body: formData});

    console.log('[Weight Detect] Response status:', response.status);

    if (!response.ok) {
      const error = await response.json();
      console.error('[Weight Detect] Error response:', error);
      throw new Error(error.detail || 'Lỗi detect cân');
    }

    const result = await response.json();
    console.log('[Weight Detect] Result:', result);

    // Auto-fill weight field
    if (result.status === 'success' && result.weight_kg) {
      const form = $('form2');
      form.elements['actual_weight_kg'].value = result.weight_kg;

      const box = $('weightDetectResult');
      box.textContent = `✓ Đọc cân: ${result.weight_kg} kg`;
      box.style.background = '#d4edda';
      box.style.color = '#155724';
      box.classList.remove('hidden');

      // Show preview
      if (result.image) {
        $('weightPreview').src = result.image;
        $('weightPreviewContainer').style.display = 'block';
      }
    } else {
      const box = $('weightDetectResult');
      box.textContent = `❌ ${result.error || 'Không detect được cân'}`;
      box.style.background = '#f8d7da';
      box.style.color = '#721c24';
      box.classList.remove('hidden');
    }
  } catch (err) {
    const box = $('weightDetectResult');
    box.textContent = '❌ ' + err.message;
    box.style.background = '#f8d7da';
    box.style.color = '#721c24';
    box.classList.remove('hidden');
  } finally {
    $('weightDetectLoading').classList.add('hidden');
  }
}

// Attach weight capture listeners
try {
  const btn = $('captureWeightBtn');
  if (btn) {
    btn.addEventListener('click', captureWeightFrame);
    console.log('[Init] captureWeightBtn listener attached');
  } else {
    console.error('[Init] captureWeightBtn not found!');
  }

  const input = $('imgWeight');
  if (input) {
    input.addEventListener('change', () => detectWeight());
    console.log('[Init] imgWeight listener attached');
  } else {
    console.error('[Init] imgWeight not found!');
  }
} catch (e) {
  console.error('[Init] Error attaching weight listeners:', e);
}

// ========== STEP 1-5: Form Navigation ==========

$('form1').addEventListener('submit', e => {
  e.preventDefault();
  data = Object.fromEntries(new FormData(e.target));
  $('step2Summary').textContent = data.sender_name + ' → ' + data.receiver_name + ' | ' + data.item_description;

  // If service = "LETTER" (thư từ), skip Step 2 and auto-fill minimal values
  if (data.service === 'LETTER') {
    console.log('[LETTER] Processing letter service...');
    // Auto-fill Step 2 with minimal values for letter
    $('form2').elements['actual_weight_kg'].value = 0.01; // 10g
    $('form2').elements['length_cm'].value = 10;
    $('form2').elements['width_cm'].value = 10;
    $('form2').elements['height_cm'].value = 1;

    // Auto-calculate price and jump to Step 3
    const measure = {
      actual_weight_kg: 0.01,
      length_cm: 10,
      width_cm: 10,
      height_cm: 1
    };

    (async () => {
      try {
        console.log('[LETTER] Calling /quotes with:', {service: data.service, origin: data.sender_province, destination: data.receiver_province, ...measure});
        quote = await api('/quotes', {
          method: 'POST',
          body: JSON.stringify({
            service: data.service,
            origin: data.sender_province,
            destination: data.receiver_province,
            ...measure
          })
        });
        console.log('[LETTER] Quote received:', quote);
        $('step3Route').textContent = 'Tuyến: ' + quote.route;
        $('step3Weight').textContent = 'Khối lượng: ' + quote.chargeable_weight_kg + ' kg';
        $('step3Amount').textContent = money(quote.amount_vnd);
        show('step3');
      } catch (err) {
        console.error('[LETTER] Error:', err);
        alert('Lỗi tính cước thư từ: ' + err.message);
        show('step2');
      }
    })();
  } else {
    // Normal flow: show Step 2 for measuring
    show('step2');
    // Don't init camera here - old UI removed
  }
});

$('form2').addEventListener('submit', async e => {
  e.preventDefault();
  const measure = Object.fromEntries(new FormData(e.target));
  try {
    quote = await api('/quotes', {
      method: 'POST',
      body: JSON.stringify({
        service: data.service,
        origin: data.sender_province,
        destination: data.receiver_province,
        ...measure
      })
    });
    $('step3Route').textContent = 'Tuyến: ' + quote.route;
    $('step3Weight').textContent = 'Khối lượng: ' + quote.chargeable_weight_kg + ' kg';
    $('step3Amount').textContent = money(quote.amount_vnd);
    show('step3');
  } catch (err) {
    alert('Lỗi: ' + err.message);
  }
});

$('back2').addEventListener('click', () => show('step1'));
$('back3').addEventListener('click', () => show('step2'));
$('back4a').addEventListener('click', () => show('step3'));
$('back4b').addEventListener('click', () => show('step3'));

$('payCK').addEventListener('click', () => {
  $('step4aAmount').textContent = money(quote.amount_vnd);
  const qrUrl = API + `/qrcode?amount_vnd=${quote.amount_vnd}`;
  $('qrImage').src = qrUrl;
  show('step4a');
});

$('payCash').addEventListener('click', () => {
  $('step4bAmount').textContent = money(quote.amount_vnd);
  show('step4b');
});

async function finish() {
  try {
    const order = await api('/orders', {method: 'POST', body: JSON.stringify(data)});
    const tracking = order.tracking_code;

    await api('/orders/' + tracking + '/measurements', {
      method: 'POST',
      body: JSON.stringify(Object.fromEntries(new FormData($('form2'))))
    });

    await api('/orders/' + tracking + '/mock-payment', {method: 'POST'});

    $('step5Code').textContent = tracking;
    $('step5Barcode').src = API + '/orders/' + tracking + '/barcode?t=' + Date.now();
    show('step5');
  } catch (e) {
    alert('Lỗi: ' + e.message);
  }
}

$('confirmCK').addEventListener('click', finish);
$('confirmCash').addEventListener('click', finish);

$('print').addEventListener('click', () => {
  const w = window.open();
  w.document.write('<img src="' + $('step5Barcode').src + '" style="max-width:100%;"/>');
  w.document.close();
  w.print();
});

$('newOrder').addEventListener('click', () => {
  data = {};
  quote = null;
  $('form1').reset();
  $('form2').reset();
  $('imageInput').value = '';
  $('uploadLabel').textContent = '📁 Chọn ảnh';
  $('ocrResult').classList.add('hidden');
  show('step1');
});

checkApi();
