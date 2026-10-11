import os
import glob
import cv2
from pathlib import Path

# CẤU HÌNH THEO DATA.YAML CỦA BẠN
DATASET_DIR = "dataset"          # Thư mục dataset gốc
OUTPUT_DIR = "stage2_dataset"    # Thư mục chứa cả ảnh crop + file txt nhãn mới
BOX_CLASS_ID = 0                 # 'Lable-Box'
INFO_CLASS_ID = 2                # 'Lable-info'

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp"]

def crop_image_and_labels():
    splits = ["train", "valid", "test"]
    
    for split in splits:
        split_dir = os.path.join(DATASET_DIR, split)
        if not os.path.exists(split_dir):
            continue
        
        # Tạo thư mục lưu ảnh và nhãn mới cho Stage 2
        out_img_dir = os.path.join(OUTPUT_DIR, split, "images")
        out_lbl_dir = os.path.join(OUTPUT_DIR, split, "labels")
        os.makedirs(out_img_dir, exist_ok=True)
        os.makedirs(out_lbl_dir, exist_ok=True)
        
        images_dir = os.path.join(split_dir, "images") if os.path.exists(os.path.join(split_dir, "images")) else split_dir
        labels_dir = os.path.join(split_dir, "labels") if os.path.exists(os.path.join(split_dir, "labels")) else split_dir
        
        image_files = []
        for ext in IMAGE_EXTENSIONS:
            image_files.extend(glob.glob(os.path.join(images_dir, f"*{ext}")))
            image_files.extend(glob.glob(os.path.join(images_dir, f"*{ext.upper()}")))

        for img_path in image_files:
            base_name = Path(img_path).stem
            label_path = os.path.join(labels_dir, f"{base_name}.txt")
            if not os.path.exists(label_path):
                continue
            
            img = cv2.imread(img_path)
            if img is None:
                continue
            img_h, img_w = img.shape[:2]
            
            with open(label_path, "r") as f:
                lines = [line.strip().split() for line in f.readlines() if line.strip()]
            
            # Phân loại box và info trong file txt
            boxes = []
            infos = []
            for parts in lines:
                cls_id = int(parts[0])
                xc, yc, w, h = map(float, parts[1:5])
                if cls_id == BOX_CLASS_ID:
                    boxes.append((xc, yc, w, h))
                elif cls_id == INFO_CLASS_ID:
                    infos.append((xc, yc, w, h))
            
            # Xử lý từng Lable-Box
            for b_idx, (b_xc, b_yc, b_w, b_h) in enumerate(boxes):
                # Chuyển Lable-Box sang Pixel
                bx1 = int((b_xc - b_w / 2) * img_w)
                by1 = int((b_yc - b_h / 2) * img_h)
                bx2 = int((b_xc + b_w / 2) * img_w)
                by2 = int((b_yc + b_h / 2) * img_h)
                
                bx1, by1 = max(0, bx1), max(0, by1)
                bx2, by2 = min(img_w, bx2), min(img_h, by2)
                
                crop_w = bx2 - bx1
                crop_h = by2 - by1
                if crop_w <= 0 or crop_h <= 0:
                    continue
                
                # Cắt ảnh Lable-Box
                cropped_img = img[by1:by2, bx1:bx2]
                
                # Tìm Lable-info nằm bên trong Lable-Box này và chuyển tọa độ
                new_info_labels = []
                for (i_xc, i_yc, i_w, i_h) in infos:
                    ix1 = int((i_xc - i_w / 2) * img_w)
                    iy1 = int((i_yc - i_h / 2) * img_h)
                    ix2 = int((i_xc + i_w / 2) * img_w)
                    iy2 = int((i_yc + i_h / 2) * img_h)
                    
                    # Kiểm tra tâm nhãn info có nằm trong Box không
                    info_center_x = (ix1 + ix2) / 2
                    info_center_y = (iy1 + iy2) / 2
                    
                    if bx1 <= info_center_x <= bx2 and by1 <= info_center_y <= by2:
                        # Tính tọa độ mới tương đối theo ảnh đã crop
                        new_ix1 = max(0, ix1 - bx1)
                        new_iy1 = max(0, iy1 - by1)
                        new_ix2 = min(crop_w, ix2 - bx1)
                        new_iy2 = min(crop_h, iy2 - by1)
                        
                        # Chuyển về dạng YOLO (0.0 -> 1.0)
                        new_w = (new_ix2 - new_ix1) / crop_w
                        new_h = (new_iy2 - new_iy1) / crop_h
                        new_xc = ((new_ix1 + new_ix2) / 2) / crop_w
                        new_yc = ((new_iy1 + new_iy2) / 2) / crop_h
                        
                        # Class mới trong Stage 2 chỉ có 1 class 'Lable-info' (ID = 0)
                        new_info_labels.append(f"0 {new_xc:.6f} {new_yc:.6f} {new_w:.6f} {new_h:.6f}\n")
                
                # Lưu ảnh và file txt tương ứng
                file_id = f"{base_name}_box_{b_idx}"
                cv2.imwrite(os.path.join(out_img_dir, f"{file_id}.jpg"), cropped_img)
                
                with open(os.path.join(out_lbl_dir, f"{file_id}.txt"), "w") as f_out:
                    f_out.writelines(new_info_labels)

    print("🎉 Hoàn tất! Ảnh crop và file txt nhãn mới đã sẵn sàng trong thư mục 'stage2_dataset'.")

if __name__ == "__main__":
    crop_image_and_labels()