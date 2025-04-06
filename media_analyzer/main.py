#!/usr/bin/env python3
"""
Media Analyzer 主程序

负责启动主界面，处理命令行参数，并调用相应的功能模块
"""

import os
import sys
import logging
import argparse
from typing import Dict, Any, List, Optional

# 将项目根目录添加到导入路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from media_analyzer.utils.device_utils import list_all_device_ids
from media_analyzer.core.update_device_registry import update_device_registry, mark_inactive_devices
from media_analyzer.utils.config_manager import get_config, get_system_id

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('media_analyzer.log')
    ]
)

logger = logging.getLogger(__name__)


def list_devices() -> List[Dict[str, Any]]:
    """
    列出当前系统中的所有设备
    
    Returns:
        设备信息列表
    """
    devices = list_all_device_ids()
    system_id = get_system_id()
    
    device_list = []
    for mount_path, uuid in devices.items():
        label = os.path.basename(mount_path)
        device_list.append({
            'uuid': uuid,
            'path': mount_path,
            'label': label,
            'system_id': system_id
        })
        
        # 更新设备注册表
        update_device_registry(uuid, device_info={
            'uuid': uuid,
            'path': mount_path,
            'label': label
        }, system_id=system_id)
    
    return device_list


def update_all_devices() -> int:
    """
    更新所有设备的注册信息
    
    Returns:
        更新的设备数量
    """
    system_id = get_system_id()
    devices = list_all_device_ids()
    
    count = 0
    for mount_path, uuid in devices.items():
        label = os.path.basename(mount_path)
        success = update_device_registry(uuid, device_info={
            'uuid': uuid,
            'path': mount_path,
            'label': label
        }, system_id=system_id)
        
        if success:
            count += 1
    
    # 标记不再存在的设备为非活动状态
    mark_inactive_devices(system_id)
    
    return count


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Media Analyzer - 媒体文件分析工具")
    
    # 命令行参数
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--list-devices', action='store_true', help='列出所有连接的设备')
    parser.add_argument('--update-registry', action='store_true', help='更新设备注册表')
    parser.add_argument('--scan', type=str, help='扫描指定目录')
    parser.add_argument('--db-type', default='postgres', choices=['sqlite', 'postgres'], help='数据库类型')
    
    args = parser.parse_args()
    
    # 加载配置
    config = get_config()
    system_id = get_system_id()
    logger.info(f"系统ID: {system_id}")
    
    # 处理命令行选项
    if args.list_devices:
        devices = list_devices()
        print("\n连接的设备列表:")
        if devices:
            for device in devices:
                print(f"  - UUID: {device['uuid']}")
                print(f"    挂载点: {device['path']}")
                print(f"    标签: {device['label']}")
                print(f"    系统: {device['system_id']}")
                print("")
        else:
            print("  未找到设备\n")
        return 0
        
    elif args.update_registry:
        count = update_all_devices()
        print(f"\n已更新 {count} 个设备的注册信息\n")
        return 0
        
    elif args.scan:
        # 导入并执行扫描模块
        scan_dir = os.path.abspath(args.scan)
        
        # 检查目录是否存在
        if not os.path.exists(scan_dir):
            logger.error(f"目录不存在: {scan_dir}")
            return 1
            
        logger.info(f"开始扫描目录: {scan_dir}")
        
        # 导入扫描模块并执行
        from media_analyzer.scripts.scan import scan_directory
        from media_analyzer.db.db_manager import DBManager
        
        db_manager = DBManager(db_type=args.db_type)
        file_infos, error_files = scan_directory(scan_dir, db_manager, system_id)
        
        logger.info(f"扫描完成，发现 {len(file_infos)} 个文件，{len(error_files)} 个错误")
        return 0
        
    else:
        # 默认行为：打印帮助信息
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main()) 