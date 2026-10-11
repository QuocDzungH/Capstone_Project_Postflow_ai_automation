import argparse
import os
import time
from datetime import datetime

import requests


parser = argparse.ArgumentParser(description="Read parcel dimensions from the ESP32 HTTP endpoint.")
parser.add_argument("--url", default=os.getenv("ESP32_URL", "http://esp32-buudien.local/distance"))
parser.add_argument("--interval", type=float, default=0.8)
args = parser.parse_args()
if args.interval <= 0:
    parser.error("--interval must be positive")
URL = args.url


def get_sensor_text(sensor):
    if sensor.get("success"):
        return f'{sensor["distance"]:.1f} cm'

    return "Không có Echo"


print("Đang đọc dữ liệu từ ESP32...")
print("Nhấn Ctrl + C để dừng.\n")

try:
    while True:
        try:
            response = requests.get(URL, timeout=3)
            response.raise_for_status()

            data = response.json()

            cb1 = get_sensor_text(data["sensor1"])
            cb2 = get_sensor_text(data["sensor2"])
            cb3 = get_sensor_text(data["sensor3"])

            current_time = datetime.now().strftime("%H:%M:%S")

            print(
                f"{current_time} | "
                f"CB1: {cb1} | "
                f"CB2: {cb2} | "
                f"CB3: {cb3}"
            )

        except requests.RequestException as error:
            print(f"Lỗi kết nối ESP32: {error}")

        except (KeyError, TypeError, ValueError) as error:
            print(f"Dữ liệu ESP32 không đúng cấu trúc: {error}")

        time.sleep(args.interval)

except KeyboardInterrupt:
    print("\nĐã dừng chương trình.")
