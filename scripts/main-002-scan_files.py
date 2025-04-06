from media_analyzer.utils.device_utils import list_all_device_ids
from media_analyzer.core.file_scanner import scan_files_on_device
from media_analyzer.db.db_init import init_db
from media_analyzer.core.update_device_registry import update_device_registry
from media_analyzer.utils.config_manager import ConfigManager, get_config
import argparse
import logging
import os
import sys

if __name__=="__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="扫描设备中的媒体文件")
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--no-fallback', action='store_true', help='禁用数据库连接失败时回退到SQLite')
    args = parser.parse_args()
    
    # 设置环境变量控制数据库回退行为
    if args.no_fallback:
        os.environ['ALLOW_DB_FALLBACK'] = 'false'
    
    # 获取配置管理器（会自动按优先级从多个位置加载配置）
    config_manager = ConfigManager()
    
    # 如果指定了配置文件，加载它
    if args.config:
        config_manager.load_config(args.config)
        
    config = get_config()
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
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
            exit(0)
        
        # 构建设备列表，用于设备注册表更新
        device_list = []
        for mount_path, uuid in devices.items():
            device_list.append({
                'uuid': uuid,
                'mount_path': mount_path,
                'label': os.path.basename(mount_path) or 'Root'
            })
            
        # 更新设备注册表
        logger.info("更新设备注册表...")
        update_device_registry(device_list)

        # 扫描每个设备
        for mount_path, uuid in devices.items():
            logger.info(f"开始扫描设备: {mount_path} (UUID: {uuid})")
            # 复用同一个数据库连接
            scan_files_on_device(mount_path, uuid, db=db)
            
    except Exception as e:
        logger.error(f"程序执行出错: {e}", exc_info=True)
        sys.exit(1)
