#!/usr/bin/env python3
"""
媒体文件分析脚本
分析数据库中的媒体文件并将结果存入数据库
"""

import os
import sys
import logging
import argparse
from typing import List, Optional

# 将项目根目录添加到导入路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from media_analyzer.core.image_analyzer import analyze_all_images
from media_analyzer.core.video_analyzer import analyze_all_videos
from media_analyzer.utils.config_manager import ConfigManager
from media_analyzer.db.db_manager import DatabaseManager

def setup_environment():
    """设置环境（日志、数据库等）"""
    # 初始化配置管理器
    config_manager = ConfigManager()
    
    # 设置日志
    config_manager.setup_logging()
    logger = logging.getLogger(__name__)
    
    # 初始化数据库连接
    db_config = config_manager.get_config().get('database', {})
    db_manager = DatabaseManager(
        db_type=db_config.get('type', 'sqlite'),
        db_path=db_config.get('path', 'media_index.db'),
        host=db_config.get('host', 'localhost'),
        port=db_config.get('port', 5432),
        user=db_config.get('user', 'postgres'),
        password=db_config.get('password', 'postgres'),
        db_name=db_config.get('name', 'media_analyzer')
    )
    
    return logger, db_manager

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='分析媒体文件并将结果存入数据库')
    parser.add_argument('--analyze-images', action='store_true', help='分析图片文件')
    parser.add_argument('--analyze-videos', action='store_true', help='分析视频文件')
    args = parser.parse_args()
    
    logger, db_manager = setup_environment()
    
    try:
        # 如果没有指定分析类型，则分析所有类型
        if not args.analyze_images and not args.analyze_videos:
            args.analyze_images = True
            args.analyze_videos = True
        
        if args.analyze_images:
            logger.info("开始分析图片文件...")
            analyze_all_images(db_manager)
            logger.info("图片文件分析完成")
        
        if args.analyze_videos:
            logger.info("开始分析视频文件...")
            analyze_all_videos(db_manager)
            logger.info("视频文件分析完成")
            
    except Exception as e:
        logger.error(f"分析过程中出错: {e}")
        return 1
    finally:
        # 关闭数据库连接
        db_manager.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 