import os
import sqlite3
from PIL import Image
import face_recognition
import exifread
from datetime import datetime

def extract_exif_info(image_path):
    """提取拍摄设备、时间、GPS信息"""
    info = {
        "camera_model": None,
        "taken_time": None,
        "gps_lat": None,
        "gps_lon": None
    }

    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)

        # 相机型号
        if 'Image Model' in tags:
            info["camera_model"] = str(tags['Image Model'])

        # 拍摄时间
        if 'EXIF DateTimeOriginal' in tags:
            info["taken_time"] = str(tags['EXIF DateTimeOriginal'])

        # GPS 信息
        def convert_gps(coord, ref):
            d, m, s = [float(x.num) / float(x.den) for x in coord]
            result = d + (m / 60.0) + (s / 3600.0)
            if ref in ['S', 'W']:
                result *= -1
            return result

        if 'GPS GPSLatitude' in tags and 'GPS GPSLatitudeRef' in tags:
            info["gps_lat"] = convert_gps(tags['GPS GPSLatitude'], str(tags['GPS GPSLatitudeRef']))

        if 'GPS GPSLongitude' in tags and 'GPS GPSLongitudeRef' in tags:
            info["gps_lon"] = convert_gps(tags['GPS GPSLongitude'], str(tags['GPS GPSLongitudeRef']))

    except Exception as e:
        print(f"[EXIF] 错误处理文件 {image_path}: {e}")

    return info

def detect_faces(image_path):
    """检测图像中是否有人脸"""
    try:
        image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(image)
        return len(face_locations) > 0
    except Exception as e:
        print(f"[人脸检测] 错误处理文件 {image_path}: {e}")
        return False

def analyze_image(file_id, image_path, db_path="media_index.db", yolo_model=None):
    exif_info = extract_exif_info(image_path)
    has_face = detect_faces(image_path)
    objects = []

    if yolo_model:
        try:
            objects = detect_objects_in_image(image_path, yolo_model)
        except Exception as e:
            print(f"[物体识别] 失败: {image_path}: {e}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO image_analysis (
            file_id, camera_model, taken_time, gps_lat, gps_lon, has_faces, objects
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        file_id,
        exif_info["camera_model"],
        exif_info["taken_time"],
        exif_info["gps_lat"],
        exif_info["gps_lon"],
        int(has_face),
        ", ".join(objects) if objects else None
    ))
    conn.commit()
    conn.close()


def analyze_all_images(db_path="media_index.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 查找所有 JPG/PNG 文件
    cursor.execute("""
        SELECT id, path FROM files
        WHERE path LIKE '%.jpg' OR path LIKE '%.jpeg' OR path LIKE '%.png'
    """)
    images = cursor.fetchall()
    conn.close()

    from image_analyzer import analyze_image

    for file_id, path in images:
        print(f"分析图像: {path}")
        analyze_image(file_id, path, db_path)

def analyze_all_images_with_yolo(db_path="media_index.db"):
    import sqlite3
    from image_analyzer import analyze_image, load_yolo_model

    model = load_yolo_model()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, path FROM files
        WHERE path LIKE '%.jpg' OR path LIKE '%.jpeg' OR path LIKE '%.png'
    """)
    images = cursor.fetchall()
    conn.close()

    for file_id, path in images:
        print(f"分析图像: {path}")
        analyze_image(file_id, path, db_path, yolo_model=model)


import sys
import torch
from pathlib import Path

# 假设 yolov5 项目已经被 clone 到当前项目根目录
YOLO_PATH = Path(__file__).parent.parent / "yolov5-7.0"
sys.path.insert(0, str(YOLO_PATH))

from models.common import DetectMultiBackend
# from utils.datasets import LoadImages
from utils.general import non_max_suppression, scale_coords
from utils.torch_utils import select_device

# 初始化 YOLO 模型
def load_yolo_model(weights='yolov5s.pt', device='cpu'):
    model = torch.hub.load('ultralytics/yolov5', 'custom', path=weights, force_reload=False)
    model.eval()
    return model

# 检测图片中的物体
def detect_objects_in_image(image_path, model):
    results = model(image_path)
    labels = results.pandas().xyxy[0]['name'].tolist()
    return list(set(labels))  # 去重
