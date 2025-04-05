from device_utils import list_all_device_ids
from file_scanner import scan_files_on_device
from db_init import init_db
from update_device_registry import update_device_registry
from config_manager import get_config
import argparse
import logging

if __name__=="__main__":
    # 获取配置（配置管理器会自动按优先级从多个位置加载配置）
    config = get_config()
    
    # 设置日志
    config.setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # 确保配置已加载后再初始化数据库
        from db_manager import get_db
        db = get_db()  # 这会使用最新的配置初始化数据库
        
        # 初始化数据库（仅首次）
        logger.info("初始化数据库...")
        init_db()

        # 更新设备注册表
        logger.info("更新设备注册表...")
        update_device_registry()

        # 获取所有设备
        logger.info("获取设备列表...")
        devices = list_all_device_ids()
        
        if not devices:
            logger.warning("未找到任何设备")
            exit(0)

        # 扫描每个设备
        for mount_path, uuid in devices.items():
            logger.info(f"开始扫描设备: {mount_path} (UUID: {uuid})")
            scan_files_on_device(mount_path, uuid)
            
    except Exception as e:
        logger.error(f"程序执行出错: {e}", exc_info=True)
        exit(1)
