import os
import sqlite3
from PIL import Image
import face_recognition
import exifread
from datetime import datetime
import logging
from typing import Dict, Any, List, Optional
from media_analyzer.db.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

def extract_exif_info(image_path: str) -> Dict[str, Any]:
    """
    提取图片的EXIF信息
    
    Args:
        image_path: 图片文件路径
        
    Returns:
        EXIF信息字典
    """
    info = {
        "camera_model": None,
        "taken_time": None,
        "gps_lat": None,
        "gps_lon": None,
        "width": None,
        "height": None
    }

    try:
        # 使用PIL获取图片尺寸
        with Image.open(image_path) as img:
            info["width"] = img.width
            info["height"] = img.height

        # 使用exifread获取EXIF信息
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)

            # 相机型号
            if 'Image Model' in tags:
                info["camera_model"] = str(tags['Image Model'])

            # 拍摄时间
            if 'EXIF DateTimeOriginal' in tags:
                info["taken_time"] = str(tags['EXIF DateTimeOriginal'])

            # GPS信息
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
        logger.error(f"提取EXIF信息出错: {image_path}, 错误: {e}")

    return info

def detect_faces(image_path: str) -> bool:
    """
    检测图片中是否包含人脸
    
    Args:
        image_path: 图片文件路径
        
    Returns:
        是否包含人脸
    """
    try:
        image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(image)
        return len(face_locations) > 0
    except Exception as e:
        logger.error(f"人脸检测出错: {image_path}, 错误: {e}")
        return False

def analyze_image(file_id: int, image_path: str, db_manager: DatabaseManager) -> None:
    """
    分析图片文件并将结果存入数据库
    
    Args:
        file_id: 文件ID
        image_path: 图片文件路径
        db_manager: 数据库管理器
    """
    try:
        # 提取EXIF信息
        exif_info = extract_exif_info(image_path)
        
        # 检测人脸
        has_face = detect_faces(image_path)
        
        # 插入或更新图片分析结果
        db_manager.execute("""
            INSERT OR REPLACE INTO image_analysis (
                file_id, camera_model, taken_time, gps_lat, gps_lon, 
                width, height, has_faces
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_id,
            exif_info["camera_model"],
            exif_info["taken_time"],
            exif_info["gps_lat"],
            exif_info["gps_lon"],
            exif_info["width"],
            exif_info["height"],
            int(has_face)
        ))
        
        logger.info(f"图片分析完成: {image_path}")
        
    except Exception as e:
        logger.error(f"分析图片出错: {image_path}, 错误: {e}")

def analyze_all_images(db_manager: DatabaseManager) -> None:
    """
    分析数据库中所有图片文件
    
    Args:
        db_manager: 数据库管理器
    """
    try:
        # 查找所有图片文件
        images = db_manager.query_all("""
            SELECT id, path FROM files
            WHERE path LIKE '%.jpg' 
            OR path LIKE '%.jpeg' 
            OR path LIKE '%.png'
        """)
        
        total = len(images)
        logger.info(f"找到 {total} 个图片文件需要分析")
        
        for i, (file_id, path) in enumerate(images, 1):
            logger.info(f"正在分析图片 [{i}/{total}]: {path}")
            analyze_image(file_id, path, db_manager)
            
    except Exception as e:
        logger.error(f"分析图片文件出错: {e}")

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
