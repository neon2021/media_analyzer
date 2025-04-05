#!/usr/bin/env python3
"""
图像分析入口脚本
"""

import os
import sys
import argparse
import logging
from media_analyzer.utils.config_manager import get_config
from media_analyzer.core.image_analyzer import analyze_images

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="媒体文件分析程序")
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--limit', type=int, default=100, help='处理的最大图像数量')
    args = parser.parse_args()
    
    # 加载配置
    config = get_config()
    if args.config:
        config.load_config(args.config)
    
    # 设置日志
    config.setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # 分析图像
        logger.info(f"开始分析图像，最大数量: {args.limit}")
        analyze_images(limit=args.limit)
        return 0
    except Exception as e:
        logger.error(f"程序执行出错: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 