import glob
import os

# 1. Quét tất cả file .txt trong các thư mục labels (train, valid, test)
label_files = glob.glob("dataset/**/labels/*.txt", recursive=True)

for file_path in label_files:
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Chỉ giữ lại các dòng thuộc Class ID 0 và 1 (bỏ Class ID 2)
    new_lines = [
        line for line in lines if line.strip() and line.split()[0] in ["0", "1"]
    ]

    with open(file_path, "w") as f:
        f.writelines(new_lines)

print(f"Đã lọc xong {len(label_files)} file nhãn!")

# 2. BẮT BUỘC: Xóa các file labels.cache để YOLO không đọc lại nhãn cũ
cache_files = glob.glob("dataset/**/labels*.cache", recursive=True)
for cache_path in cache_files:
    os.remove(cache_path)
    print(f"Đã xóa cache: {cache_path}")