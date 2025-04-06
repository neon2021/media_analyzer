#!/usr/bin/env python3
"""
媒体文件扫描脚本
扫描设备中的媒体文件并将信息存入数据库
"""

import os
import sys
import time
import hashlib
import logging
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple

# 将项目根目录添加到导入路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from media_analyzer.utils.path_converter import get_relative_path
from media_analyzer.utils.device_utils import get_device_by_path, get_mount_point
from media_analyzer.core.update_device_registry import update_device_registry
from media_analyzer.utils.config_manager import get_scan_config, get_system_id

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scan.log')
    ]
)

logger = logging.getLogger(__name__)

# 全局变量
MEDIA_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',
    '.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm',
    '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
}

# 统计信息
stats = {
    'total_files': 0,
    'processed_files': 0,
    'skipped_files': 0,
    'error_files': 0,
    'total_size': 0,
    'start_time': None,
    'last_progress_time': None
}

# 要扫描的目录列表
scan_dirs = []


def calculate_file_hash(file_path: str, block_size: int = 8192, timeout: int = 10) -> Optional[str]:
    """
    计算文件的SHA-256哈希值，带超时
    
    Args:
        file_path: 文件路径
        block_size: 读取块大小
        timeout: 超时时间（秒）
        
    Returns:
        哈希值字符串，超时或出错时返回None
    """
    try:
        start_time = time.time()
        hasher = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            while True:
                # 检查是否超时
                if time.time() - start_time > timeout:
                    logger.warning(f"计算哈希超时: {file_path}")
                    return None
                
                data = f.read(block_size)
                if not data:
                    break
                hasher.update(data)
        
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"计算哈希出错: {file_path}, 错误: {e}")
        return None


def get_file_info(file_path: str, timeout: int = 10) -> Dict[str, Any]:
    """
    获取文件信息
    
    Args:
        file_path: 文件路径
        timeout: 哈希计算超时时间（秒）
        
    Returns:
        文件信息字典
    """
    try:
        stat_info = os.stat(file_path)
        
        file_info = {
            'path': file_path,
            'rel_path': get_relative_path(file_path),
            'size': stat_info.st_size,
            'created_at': datetime.fromtimestamp(stat_info.st_ctime),
            'modified_at': datetime.fromtimestamp(stat_info.st_mtime),
            'hash': calculate_file_hash(file_path, timeout=timeout)
        }
        
        # 获取设备信息
        device = get_device_by_path(file_path)
        if device:
            file_info['device_uuid'] = device.get('uuid')
            file_info['device_path'] = device.get('path')
            file_info['mount_point'] = get_mount_point(file_path)
        
        return file_info
    except Exception as e:
        logger.error(f"获取文件信息出错: {file_path}, 错误: {e}")
        return {'path': file_path, 'error': str(e)}


def should_scan_file(file_path: str) -> bool:
    """
    判断是否应该扫描该文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        是否应该扫描
    """
    # 检查扩展名
    _, ext = os.path.splitext(file_path.lower())
    if ext not in MEDIA_EXTENSIONS:
        return False
    
    # 跳过隐藏文件
    if os.path.basename(file_path).startswith('.'):
        return False
    
    return True


def should_scan_dir(dir_path: str) -> bool:
    """
    判断是否应该扫描该目录
    
    Args:
        dir_path: 目录路径
        
    Returns:
        是否应该扫描
    """
    # 跳过隐藏目录
    if os.path.basename(dir_path).startswith('.'):
        return False
    
    # 从配置中获取要跳过的目录
    config = get_scan_config()
    skip_dirs = config.get('skip_dirs', [])
    
    # 检查是否在跳过列表中
    for skip_dir in skip_dirs:
        if dir_path.startswith(skip_dir):
            return False
    
    return True


def print_progress():
    """打印进度信息"""
    if stats['total_files'] == 0:
        percent = 0
    else:
        percent = (stats['processed_files'] / stats['total_files']) * 100
        
    elapsed = time.time() - stats['start_time']
    files_per_sec = stats['processed_files'] / elapsed if elapsed > 0 else 0
    
    logger.info(
        f"进度: {stats['processed_files']}/{stats['total_files']} "
        f"({percent:.1f}%), "
        f"已处理: {stats['processed_files']}, "
        f"已跳过: {stats['skipped_files']}, "
        f"错误: {stats['error_files']}, "
        f"总大小: {stats['total_size'] / (1024*1024*1024):.2f} GB, "
        f"速度: {files_per_sec:.1f} 文件/秒"
    )


def scan_directory(dir_path: str, db_manager, system_id: str, timeout: int = 10, progress_interval: int = 30) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    扫描目录中的所有媒体文件
    
    Args:
        dir_path: 目录路径
        db_manager: 数据库管理器
        system_id: 系统ID
        timeout: 哈希计算超时时间（秒）
        progress_interval: 进度报告间隔（秒）
        
    Returns:
        (扫描到的文件信息列表, 错误文件路径列表)
    """
    logger.info(f"开始扫描目录: {dir_path}")
    
    file_infos = []
    error_files = []
    
    # 获取设备信息
    device = get_device_by_path(dir_path)
    if not device:
        logger.warning(f"无法获取设备信息: {dir_path}")
        return [], [dir_path]
    
    device_uuid = device.get('uuid')
    if not device_uuid:
        logger.warning(f"无法获取设备UUID: {dir_path}")
        return [], [dir_path]
    
    # 添加设备到设备注册表
    update_device_registry(device_uuid, system_id=system_id)
    
    # 统计文件总数
    stats['total_files'] = 0
    stats['processed_files'] = 0
    stats['skipped_files'] = 0
    stats['error_files'] = 0
    stats['total_size'] = 0
    stats['start_time'] = time.time()
    stats['last_progress_time'] = time.time()
    
    # 先统计文件总数
    for root, dirs, files in os.walk(dir_path):
        if not should_scan_dir(root):
            dirs[:] = []  # 跳过此目录的子目录
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            if should_scan_file(file_path):
                stats['total_files'] += 1
                try:
                    stats['total_size'] += os.path.getsize(file_path)
                except:
                    pass
    
    logger.info(f"总共找到 {stats['total_files']} 个媒体文件，总大小约 {stats['total_size'] / (1024*1024*1024):.2f} GB")
    
    # 记录已处理文件的路径集合
    processed_paths = set()
    
    # 扫描文件
    for root, dirs, files in os.walk(dir_path):
        if not should_scan_dir(root):
            dirs[:] = []  # 跳过此目录的子目录
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            if file_path in processed_paths:
                continue
                
            if should_scan_file(file_path):
                try:
                    file_info = get_file_info(file_path, timeout=timeout)
                    
                    # 添加系统ID和设备UUID
                    file_info['system_id'] = system_id
                    if 'device_uuid' not in file_info and device_uuid:
                        file_info['device_uuid'] = device_uuid
                    
                    file_infos.append(file_info)
                    processed_paths.add(file_path)
                    stats['processed_files'] += 1
                    
                    # 每批次文件入库
                    if len(file_infos) >= 100:
                        save_file_infos_to_db(file_infos, db_manager)
                        file_infos = []
                except Exception as e:
                    logger.error(f"处理文件出错: {file_path}, 错误: {e}")
                    error_files.append(file_path)
                    stats['error_files'] += 1
            else:
                stats['skipped_files'] += 1
            
            # 定期报告进度
            current_time = time.time()
            if current_time - stats['last_progress_time'] >= progress_interval:
                print_progress()
                stats['last_progress_time'] = current_time
    
    # 处理剩余文件
    if file_infos:
        save_file_infos_to_db(file_infos, db_manager)
    
    print_progress()
    logger.info(f"目录扫描完成: {dir_path}")
    return file_infos, error_files


def save_file_infos_to_db(file_infos: List[Dict[str, Any]], db_manager) -> int:
    """
    将文件信息保存到数据库
    
    Args:
        file_infos: 文件信息列表
        db_manager: 数据库管理器
        
    Returns:
        成功保存的文件数量
    """
    if not file_infos:
        return 0
        
    try:
        # 准备SQL
        if db_manager.db_type == "sqlite":
            query = """
            INSERT OR REPLACE INTO files 
            (device_uuid, path, rel_path, size, hash, created_at, modified_at, system_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
        else:  # postgres
            query = """
            INSERT INTO files 
            (device_uuid, path, rel_path, size, hash, created_at, modified_at, system_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (device_uuid, path, system_id) 
            DO UPDATE SET
                rel_path = EXCLUDED.rel_path,
                size = EXCLUDED.size,
                hash = EXCLUDED.hash,
                created_at = EXCLUDED.created_at,
                modified_at = EXCLUDED.modified_at
            """
        
        # 准备参数
        params_list = []
        for file_info in file_infos:
            if 'error' in file_info:
                continue
                
            params = (
                file_info.get('device_uuid'),
                file_info.get('path'),
                file_info.get('rel_path'),
                file_info.get('size'),
                file_info.get('hash'),
                file_info.get('created_at'),
                file_info.get('modified_at'),
                file_info.get('system_id')
            )
            params_list.append(params)
        
        # 执行批量插入
        if params_list:
            count = db_manager.executemany(query, params_list)
            db_manager.commit()
            return count
            
        return 0
    except Exception as e:
        logger.error(f"保存文件信息到数据库出错: {e}")
        db_manager.rollback()
        return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='扫描媒体文件并将信息存入数据库')
    parser.add_argument('-d', '--dir', action='append', help='要扫描的目录')
    parser.add_argument('--db-type', default='postgres', choices=['sqlite', 'postgres'], help='数据库类型')
    args = parser.parse_args()
    
    # 如果没有指定目录，使用当前目录
    if not args.dir:
        args.dir = [os.getcwd()]
    
    # 获取配置
    config = get_scan_config()
    hash_timeout = config.get('hash_timeout', 10)
    progress_interval = config.get('progress_interval', 30)
    
    # 获取系统ID
    system_id = get_system_id()
    logger.info(f"系统ID: {system_id}")
    
    try:
        # 初始化数据库连接
        from media_analyzer.db.db_manager import DBManager
        db_manager = DBManager(db_type=args.db_type)
        
        # 确保表存在
        if not db_manager.table_exists('files'):
            logger.info("创建files表")
            if db_manager.db_type == "sqlite":
                db_manager.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_uuid TEXT NOT NULL,
                    path TEXT NOT NULL,
                    rel_path TEXT,
                    size INTEGER,
                    hash TEXT,
                    created_at TIMESTAMP,
                    modified_at TIMESTAMP,
                    system_id TEXT NOT NULL,
                    UNIQUE(device_uuid, path, system_id)
                )
                """)
            else:  # postgres
                db_manager.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id SERIAL PRIMARY KEY,
                    device_uuid VARCHAR(36) NOT NULL,
                    path TEXT NOT NULL,
                    rel_path TEXT,
                    size BIGINT,
                    hash VARCHAR(64),
                    created_at TIMESTAMP,
                    modified_at TIMESTAMP,
                    system_id VARCHAR(50) NOT NULL,
                    UNIQUE(device_uuid, path, system_id)
                )
                """)
            db_manager.commit()
            
        # 扫描目录
        total_files = 0
        total_errors = 0
        
        for dir_path in args.dir:
            dir_path = os.path.abspath(dir_path)
            logger.info(f"开始处理目录: {dir_path}")
            
            # 更新设备注册表
            device = get_device_by_path(dir_path)
            if device:
                device_uuid = device.get('uuid')
                if device_uuid:
                    update_device_registry(device_uuid, system_id=system_id)
            
            # 扫描目录
            file_infos, error_files = scan_directory(
                dir_path, 
                db_manager, 
                system_id,
                timeout=hash_timeout,
                progress_interval=progress_interval
            )
            
            total_files += len(file_infos)
            total_errors += len(error_files)
        
        logger.info(f"所有扫描完成. 共处理 {total_files} 个文件, {total_errors} 个错误.")
        
    except Exception as e:
        logger.error(f"扫描过程中出错: {e}")
        return 1
    finally:
        try:
            db_manager.close()
        except:
            pass
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 