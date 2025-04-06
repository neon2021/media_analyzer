#!/usr/bin/env python3
"""
测试设备工具函数
"""

import sys
import os
import logging

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_list_all_device_ids():
    """测试获取所有设备ID"""
    from media_analyzer.utils.device_utils import list_all_device_ids
    
    logger.info("测试 list_all_device_ids 函数...")
    device_ids = list_all_device_ids()
    
    if device_ids:
        logger.info(f"找到 {len(device_ids)} 个设备:")
        for mount_path, uuid in device_ids.items():
            logger.info(f"  - 挂载点: {mount_path}, UUID: {uuid}")
    else:
        logger.warning("未找到任何设备")
    
    return device_ids

if __name__ == "__main__":
    test_list_all_device_ids() 