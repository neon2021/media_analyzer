#!/usr/bin/env python3
"""
文件扫描入口脚本
"""

import os
import sys
import argparse
import logging
from media_analyzer.utils.config_manager import get_config
from media_analyzer.utils.device_utils import list_all_device_ids
from media_analyzer.core.file_scanner import scan_files_on_device
from media_analyzer.db.db_init import init_db
from media_analyzer.core.update_device_registry import update_device_registry

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="媒体文件扫描程序")
    parser.add_argument('--config', type=str, help='配置文件路径')
    args = parser.parse_args()
    
    # 加载配置
    config = get_config()
    if args.config:
        config.load_config(args.config)
    
    # 设置日志
    config.setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # 确保配置已加载后再初始化数据库
        from media_analyzer.db.db_manager import get_db
        db = get_db()  # 这会使用最新的配置初始化数据库
        
        # 初始化数据库（仅首次）
        logger.info("初始化数据库...")
        init_db()

        # 获取所有设备
        logger.info("获取设备列表...")
        devices = list_all_device_ids()
        
        if not devices:
            logger.warning("未找到任何设备")
            return 0

        # 更新设备注册表
        logger.info("更新设备注册表...")
        device_list = [{'uuid': uuid, 'mount_path': mount_path, 'label': os.path.basename(mount_path)} 
                     for mount_path, uuid in devices.items()]
        update_device_registry(device_list)

        # 扫描每个设备
        for mount_path, uuid in devices.items():
            logger.info(f"开始扫描设备: {mount_path} (UUID: {uuid})")
            scan_files_on_device(mount_path, uuid)
            
        return 0
            
    except Exception as e:
        logger.error(f"程序执行出错: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 