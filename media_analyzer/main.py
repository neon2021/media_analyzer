#!/usr/bin/env python3
import os
import sys
import argparse
import logging
import platform
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'media_analyzer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger(__name__)

from media_analyzer.db.db_init import init_db
from media_analyzer.utils.device_utils import list_all_devices, get_device_info
from media_analyzer.core.update_device_registry import update_device_registry
from media_analyzer.core.file_scanner import scan_files_on_device
from media_analyzer.core.file_retriever import get_file_path, search_files
from media_analyzer.config import load_config, get_config

def init_command(args):
    """初始化数据库"""
    logger.info("初始化数据库")
    init_db()
    logger.info("数据库初始化完成")

def devices_command(args):
    """列出所有设备"""
    logger.info("列出所有设备")
    devices = list_all_devices()
    
    if not devices:
        logger.info("没有找到设备")
        return
    
    print("\n发现以下设备:")
    print("=" * 80)
    print(f"{'UUID':<36} | {'标签':<20} | {'挂载点'}")
    print("-" * 80)
    
    for device in devices:
        print(f"{device['uuid']:<36} | {device['label']:<20} | {device['mount_path']}")
    
    print("=" * 80)
    
    # 更新设备注册表
    if not args.no_update:
        logger.info("更新设备注册表")
        update_device_registry(devices)

def scan_command(args):
    """扫描指定设备上的文件"""
    mount_path = args.path
    
    # 获取设备信息
    device_info = get_device_info(mount_path)
    
    if not device_info:
        # 尝试使用命令行指定的UUID
        if args.uuid:
            device_info = {
                'uuid': args.uuid,
                'mount_path': mount_path,
                'label': os.path.basename(mount_path)
            }
            logger.info(f"使用命令行指定的UUID: {args.uuid}")
        else:
            logger.error(f"无法获取挂载点 {mount_path} 的设备信息，请使用 --uuid 参数指定设备UUID")
            return
    
    # 更新设备注册表
    update_device_registry([device_info])
    
    print(f"\n开始扫描设备: {device_info['label']} (UUID: {device_info['uuid']})")
    print(f"挂载点: {device_info['mount_path']}")
    print("=" * 80)
    
    # 开始扫描
    scan_files_on_device(device_info['mount_path'], device_info['uuid'])
    
    print("=" * 80)
    print("扫描完成")

def search_command(args):
    """搜索文件"""
    # 构建搜索参数
    params = {
        'keyword': args.keyword,
        'device_uuid': args.device,
        'file_type': args.type,
        'limit': args.limit,
        'offset': args.offset
    }
    
    if args.min_size:
        params['min_size'] = args.min_size
    
    if args.max_size:
        params['max_size'] = args.max_size
    
    # 执行搜索
    results = search_files(**params)
    
    if not results:
        print("未找到匹配的文件")
        return
    
    print(f"\n找到 {len(results)} 个匹配的文件:")
    print("=" * 120)
    print(f"{'ID':<6} | {'设备':<15} | {'大小':>10} | {'修改时间':<19} | {'路径'}")
    print("-" * 120)
    
    for result in results:
        size_str = format_size(result['size'])
        modified_time = result['modified_time'].strftime('%Y-%m-%d %H:%M:%S') if result['modified_time'] else 'N/A'
        print(f"{result['id']:<6} | {result['device_label']:<15} | {size_str:>10} | {modified_time:<19} | {result['path']}")
    
    print("=" * 120)

def get_command(args):
    """获取文件路径"""
    file_id = args.id
    system_id = args.system_id
    
    # 获取文件路径
    file_path = get_file_path(file_id, system_id)
    
    if not file_path:
        print(f"无法获取ID为 {file_id} 的文件路径")
        return
    
    print(f"文件路径: {file_path}")
    
    # 如果指定了打开文件
    if args.open:
        open_file(file_path)

def open_file(path):
    """打开文件"""
    system = platform.system()
    
    try:
        if system == 'Darwin':  # macOS
            os.system(f'open "{path}"')
        elif system == 'Linux':
            os.system(f'xdg-open "{path}"')
        elif system == 'Windows':
            os.system(f'start "" "{path}"')
        else:
            logger.warning(f"不支持的操作系统: {system}")
    except Exception as e:
        logger.error(f"打开文件失败: {e}")

def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.1f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.1f} GB"

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="媒体文件分析工具")
    
    # 加载配置
    config = load_config()
    
    # 创建子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # init 命令
    init_parser = subparsers.add_parser('init', help='初始化数据库')
    init_parser.set_defaults(func=init_command)
    
    # devices 命令
    devices_parser = subparsers.add_parser('devices', help='列出所有设备')
    devices_parser.add_argument('--no-update', action='store_true', help='不更新设备注册表')
    devices_parser.set_defaults(func=devices_command)
    
    # scan 命令
    scan_parser = subparsers.add_parser('scan', help='扫描设备上的文件')
    scan_parser.add_argument('path', help='设备挂载路径')
    scan_parser.add_argument('--uuid', help='设备UUID（如果无法自动获取）')
    scan_parser.set_defaults(func=scan_command)
    
    # search 命令
    search_parser = subparsers.add_parser('search', help='搜索文件')
    search_parser.add_argument('--keyword', help='搜索关键词')
    search_parser.add_argument('--device', help='设备UUID')
    search_parser.add_argument('--type', help='文件类型')
    search_parser.add_argument('--min-size', type=int, help='最小文件大小（字节）')
    search_parser.add_argument('--max-size', type=int, help='最大文件大小（字节）')
    search_parser.add_argument('--limit', type=int, default=100, help='结果数量限制')
    search_parser.add_argument('--offset', type=int, default=0, help='结果偏移量')
    search_parser.set_defaults(func=search_command)
    
    # get 命令
    get_parser = subparsers.add_parser('get', help='获取文件路径')
    get_parser.add_argument('id', type=int, help='文件ID')
    get_parser.add_argument('--system-id', help='系统ID')
    get_parser.add_argument('--open', action='store_true', help='打开文件')
    get_parser.set_defaults(func=get_command)
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 如果没有指定命令，显示帮助信息
    if not args.command:
        parser.print_help()
        return
    
    # 执行相应的命令
    args.func(args)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        sys.exit(0)
    except Exception as e:
        logger.exception("程序出错")
        sys.exit(1) 