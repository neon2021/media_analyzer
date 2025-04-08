"""
File type detection module for media files.
This module provides functionality to detect and categorize different types of media files.
"""

import os
import logging
import mimetypes
from typing import Dict, Optional, List
from pathlib import Path

# 获取日志记录器
logger = logging.getLogger('media_analyzer.file_type_detector')

# 支持的媒体文件类型及其扩展名
MEDIA_TYPES = {
    'image': {
        'extensions': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'],
        'mime_types': ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/tiff', 'image/webp']
    },
    'video': {
        'extensions': ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'],
        'mime_types': ['video/mp4', 'video/x-msvideo', 'video/quicktime', 'video/x-matroska', 
                      'video/x-ms-wmv', 'video/x-flv', 'video/webm']
    },
    'audio': {
        'extensions': ['.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'],
        'mime_types': ['audio/mpeg', 'audio/wav', 'audio/aac', 'audio/flac', 'audio/ogg', 
                      'audio/mp4', 'audio/x-ms-wma']
    }
}

def detect_file_type(file_path: str) -> Optional[str]:
    """
    Detect the type of a media file based on its extension and MIME type.
    
    Args:
        file_path: Path to the file to be analyzed
        
    Returns:
        str: The detected media type ('image', 'video', 'audio') or None if not a supported media file
        
    Raises:
        FileNotFoundError: If the file does not exist
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        # 获取文件扩展名
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # 获取文件的MIME类型
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # 检查扩展名和MIME类型是否匹配任何支持的媒体类型
        for media_type, type_info in MEDIA_TYPES.items():
            if (file_ext in type_info['extensions'] or 
                (mime_type and mime_type in type_info['mime_types'])):
                logger.debug(f"Detected {media_type} file: {file_path}")
                return media_type
                
        logger.warning(f"Unsupported file type: {file_path} (MIME: {mime_type})")
        return None
        
    except Exception as e:
        logger.error(f"Error detecting file type for {file_path}: {e}")
        return None

def get_supported_extensions(media_type: str) -> List[str]:
    """
    Get the list of supported file extensions for a specific media type.
    
    Args:
        media_type: The type of media ('image', 'video', 'audio')
        
    Returns:
        List[str]: List of supported file extensions for the specified media type
    """
    return MEDIA_TYPES.get(media_type, {}).get('extensions', [])

def is_media_file(file_path: str) -> bool:
    """
    Check if a file is a supported media file.
    
    Args:
        file_path: Path to the file to be checked
        
    Returns:
        bool: True if the file is a supported media file, False otherwise
    """
    return detect_file_type(file_path) is not None 