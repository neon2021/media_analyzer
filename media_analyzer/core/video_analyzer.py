import os
import cv2
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
from media_analyzer.db.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

def extract_video_metadata(video_path: str) -> Dict[str, Any]:
    """
    提取视频元数据信息
    
    Args:
        video_path: 视频文件路径
        
    Returns:
        视频元数据信息字典
    """
    info = {
        "duration": None,
        "width": None,
        "height": None,
        "fps": None,
        "codec": None,
        "format": None,
        "created_time": None
    }

    try:
        # 使用OpenCV获取视频信息
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            info["fps"] = cap.get(cv2.CAP_PROP_FPS)
            info["duration"] = cap.get(cv2.CAP_PROP_FRAME_COUNT) / info["fps"] if info["fps"] > 0 else None
            cap.release()

        # 获取文件创建时间
        stat_info = os.stat(video_path)
        info["created_time"] = datetime.fromtimestamp(stat_info.st_ctime)

    except Exception as e:
        logger.error(f"提取视频元数据出错: {video_path}, 错误: {e}")

    return info

def analyze_video(file_id: int, video_path: str, db_manager: DatabaseManager) -> None:
    """
    分析视频文件并将结果存入数据库
    
    Args:
        file_id: 文件ID
        video_path: 视频文件路径
        db_manager: 数据库管理器
    """
    try:
        # 提取视频元数据
        metadata = extract_video_metadata(video_path)
        
        # 插入或更新视频分析结果
        db_manager.execute("""
            INSERT OR REPLACE INTO video_analysis (
                file_id, duration, width, height, fps, created_time
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            file_id,
            metadata["duration"],
            metadata["width"],
            metadata["height"],
            metadata["fps"],
            metadata["created_time"]
        ))
        
        logger.info(f"视频分析完成: {video_path}")
        
    except Exception as e:
        logger.error(f"分析视频出错: {video_path}, 错误: {e}")

def analyze_all_videos(db_manager: DatabaseManager) -> None:
    """
    分析数据库中所有视频文件
    
    Args:
        db_manager: 数据库管理器
    """
    try:
        # 查找所有视频文件
        videos = db_manager.query_all("""
            SELECT id, path FROM files
            WHERE path LIKE '%.mp4' 
            OR path LIKE '%.avi' 
            OR path LIKE '%.mov' 
            OR path LIKE '%.mkv'
        """)
        
        total = len(videos)
        logger.info(f"找到 {total} 个视频文件需要分析")
        
        for i, (file_id, path) in enumerate(videos, 1):
            logger.info(f"正在分析视频 [{i}/{total}]: {path}")
            analyze_video(file_id, path, db_manager)
            
    except Exception as e:
        logger.error(f"分析视频文件出错: {e}") 