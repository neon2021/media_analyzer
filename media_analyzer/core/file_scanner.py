import os
import logging
import time
import hashlib
import multiprocessing
from datetime import datetime
from typing import Optional

from media_analyzer.utils.path_converter import PathConverter
from media_analyzer.utils.config_manager import get_config

logger = logging.getLogger(__name__)

# ========== 配置项 ==========
HASH_TIMEOUT = 10             # 单个文件最大哈希耗时（秒）
PROGRESS_INTERVAL = 30        # 每 N 秒保存一次扫描进度
# ============================

def hash_worker(path, block_size, queue):
    """计算文件的 SHA256 哈希值"""
    try:
        hasher = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(block_size):
                hasher.update(chunk)
        queue.put(hasher.hexdigest())
    except Exception as e:
        print(f"[跳过] 无法读取文件: {path}, 错误: {e}")
        queue.put(e)

def compute_file_hash(path, block_size=65536, timeout=HASH_TIMEOUT):
    queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=hash_worker, args=(path, block_size, queue))
    p.start()
    p.join(timeout)
    
    if p.is_alive():
        p.terminate()
        p.join()
        print(f"[{now()}] [跳过] 文件读取超时（{timeout}s）: {path}")
        return None

    result = queue.get()
    if isinstance(result, Exception):
        print(f"[{now()}] [跳过] 无法读取文件: {path}, 错误: {result}")
        return None

    return result
    
def now():
    """返回当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# macOS 和 Linux 常见系统路径
SKIP_DIRS = [
    "/System", "/Volumes/Recovery", "/private", "/Library", "/bin", "/sbin", "/usr", # macOS
    "/proc", "/sys", "/dev", "/run", "/boot",    # Linux
]

def should_skip_path(path):
    for skip in SKIP_DIRS:
        if path.startswith(skip):
            return True
    return False

def save_progress_to_db(db, device_uuid, total_files, new_files):
    """每 N 秒保存一次进度到数据库"""
    current_time = datetime.now()
    
    if db.db_type == "sqlite":
        db.execute("""
            INSERT OR REPLACE INTO scan_progress (device_uuid, total_files, new_files, last_updated)
            VALUES (?, ?, ?, ?)
        """, (device_uuid, total_files, new_files, current_time))
    else:  # PostgreSQL
        db.execute("""
            INSERT INTO scan_progress (device_uuid, total_files, new_files, last_updated)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (device_uuid) DO UPDATE SET
            total_files = EXCLUDED.total_files,
            new_files = EXCLUDED.new_files,
            last_updated = EXCLUDED.last_updated
        """, (device_uuid, total_files, new_files, current_time))
    
    db.commit()

def calculate_file_hash(file_path, block_size=8192, max_size=10*1024*1024):
    """
    计算文件的哈希值 (仅计算前10MB内容)
    
    Args:
        file_path (str): 文件路径
        block_size (int): 每次读取的块大小
        max_size (int): 最大处理的文件大小
        
    Returns:
        str: 文件SHA256哈希值的16进制表示
    """
    sha256 = hashlib.sha256()
    size = 0
    
    try:
        with open(file_path, 'rb') as f:
            while size < max_size:
                data = f.read(block_size)
                if not data:
                    break
                size += len(data)
                sha256.update(data)
        return sha256.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希时出错: {file_path}, 错误: {e}")
        return None

# 检查配置文件中的值
def check_db_config():
    """检查数据库配置并返回数据库类型，推断为 'sqlite' 或 'postgresql'"""
    config = get_config()
    return config.get('database.type', 'sqlite').lower()

# 在文件开始时就确定数据库类型
def scan_files_on_device(mount_path, device_uuid, db=None):
    """
    扫描设备上的所有媒体文件
    
    Args:
        mount_path (str): 设备挂载路径
        device_uuid (str): 设备UUID
        db (DBManager, optional): 数据库连接，如果为None则自动获取
    """
    logger.info(f"开始扫描设备: {mount_path} (UUID: {device_uuid})")
    
    # 如果没有提供数据库连接，则获取一个
    if db is None:
        from media_analyzer.db.db_manager import get_db
        db = get_db()
    
    # 获取数据库类型，用于后续SQL语法
    db_type = db.db_type
    logger.info(f"使用数据库类型: {db_type}")
    
    # 标准化挂载路径
    mount_path = PathConverter.normalize_path(mount_path)
    
    # 获取媒体文件扩展名列表
    media_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.mp4', '.mov', '.avi', '.mkv']
    
    # 获取系统ID
    system_id = get_config().get('system.id', 'default-system')
    
    # 创建临时表来跟踪已扫描的文件
    if db_type == 'sqlite':
        db.execute('''
        CREATE TEMPORARY TABLE IF NOT EXISTS scanned_files (
            path TEXT PRIMARY KEY
        )
        ''')
    else:  # PostgreSQL
        db.execute('''
        CREATE TEMPORARY TABLE IF NOT EXISTS scanned_files (
            path TEXT PRIMARY KEY
        )
        ''')
    
    # 开始计时
    start_time = time.time()
    scanned_count = 0
    new_files_count = 0
    
    # 定期更新进度
    last_progress_update = start_time
    progress_interval = 30  # 每30秒更新一次进度
    
    # 遍历目录
    for root, dirs, files in os.walk(mount_path):
        # 排除系统目录
        if any(hidden in root for hidden in ['/System', '/Volumes/Recovery', '/private', '/Library', '.Trashes']):
            continue
            
        for file in files:
            # 检查文件扩展名
            ext = os.path.splitext(file)[1].lower()
            if ext not in media_extensions:
                continue
            
            # 构建文件路径
            file_path = os.path.join(root, file)
            
            # 转换为相对路径存储
            rel_path = PathConverter.get_relative_path(file_path, mount_path)
            logger.debug(f"原始路径: {file_path}, 挂载点: {mount_path}, 相对路径: {rel_path}")
            
            # 获取文件信息
            try:
                file_stat = os.stat(file_path)
                file_size = file_stat.st_size
                modified_time = datetime.fromtimestamp(file_stat.st_mtime)
                
                # 计算文件哈希
                file_hash = calculate_file_hash(file_path)
                
                # 首先检查文件是否已存在
                if db_type == 'sqlite':
                    result = db.query_one(
                        "SELECT id FROM files WHERE device_uuid = ? AND path = ?", 
                        (device_uuid, rel_path)
                    )
                else:  # PostgreSQL
                    result = db.query_one(
                        "SELECT id FROM files WHERE device_uuid = %s AND path = %s", 
                        (device_uuid, rel_path)
                    )
                
                exists = result is not None
                
                if exists:
                    # 更新现有记录
                    if db_type == 'sqlite':
                        db.execute('''
                        UPDATE files SET 
                            hash = ?,
                            size = ?, 
                            modified_time = ?,
                            scanned_time = ?,
                            system_id = ?
                        WHERE device_uuid = ? AND path = ?
                        ''', (file_hash, file_size, modified_time, datetime.now(), system_id, device_uuid, rel_path))
                    else:  # PostgreSQL
                        db.execute('''
                        UPDATE files SET 
                            hash = %s,
                            size = %s, 
                            modified_time = %s,
                            scanned_time = %s,
                            system_id = %s
                        WHERE device_uuid = %s AND path = %s
                        ''', (file_hash, file_size, modified_time, datetime.now(), system_id, device_uuid, rel_path))
                else:
                    # 插入新记录
                    if db_type == 'sqlite':
                        db.execute('''
                        INSERT INTO files 
                        (device_uuid, path, hash, size, modified_time, scanned_time, system_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (device_uuid, rel_path, file_hash, file_size, modified_time, datetime.now(), system_id))
                    else:  # PostgreSQL
                        db.execute('''
                        INSERT INTO files 
                        (device_uuid, path, hash, size, modified_time, scanned_time, system_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ''', (device_uuid, rel_path, file_hash, file_size, modified_time, datetime.now(), system_id))
                    
                    new_files_count += 1
                
                # 更新已扫描文件表
                if db_type == 'sqlite':
                    db.execute('INSERT OR REPLACE INTO scanned_files (path) VALUES (?)', (rel_path,))
                else:  # PostgreSQL
                    db.execute('''
                    INSERT INTO scanned_files (path) VALUES (%s)
                    ON CONFLICT (path) DO NOTHING
                    ''', (rel_path,))
                
                # 更新计数
                scanned_count += 1
                
                # 定期更新进度
                now = time.time()
                if now - last_progress_update > progress_interval:
                    elapsed = now - start_time
                    rate = scanned_count / elapsed if elapsed > 0 else 0
                    logger.info(f"已扫描 {scanned_count} 个文件，发现 {new_files_count} 个新文件，耗时: {elapsed:.2f}秒，速率: {rate:.2f}文件/秒")
                    
                    # 检查进度记录是否存在
                    if db_type == 'sqlite':
                        result = db.query_one(
                            "SELECT 1 FROM scan_progress WHERE device_uuid = ?", 
                            (device_uuid,)
                        )
                    else:  # PostgreSQL
                        result = db.query_one(
                            "SELECT 1 FROM scan_progress WHERE device_uuid = %s", 
                            (device_uuid,)
                        )
                    
                    progress_exists = result is not None
                    
                    if progress_exists:
                        # 更新现有进度
                        if db_type == 'sqlite':
                            db.execute('''
                            UPDATE scan_progress SET 
                                total_files = ?,
                                new_files = ?,
                                last_updated = ?
                            WHERE device_uuid = ?
                            ''', (scanned_count, new_files_count, datetime.now(), device_uuid))
                        else:  # PostgreSQL
                            db.execute('''
                            UPDATE scan_progress SET 
                                total_files = %s,
                                new_files = %s,
                                last_updated = %s
                            WHERE device_uuid = %s
                            ''', (scanned_count, new_files_count, datetime.now(), device_uuid))
                    else:
                        # 插入新进度
                        if db_type == 'sqlite':
                            db.execute('''
                            INSERT INTO scan_progress 
                            (device_uuid, total_files, new_files, last_updated)
                            VALUES (?, ?, ?, ?)
                            ''', (device_uuid, scanned_count, new_files_count, datetime.now()))
                        else:  # PostgreSQL
                            db.execute('''
                            INSERT INTO scan_progress 
                            (device_uuid, total_files, new_files, last_updated)
                            VALUES (%s, %s, %s, %s)
                            ''', (device_uuid, scanned_count, new_files_count, datetime.now()))
                    
                    db.commit()
                    last_progress_update = now
            
            except Exception as e:
                logger.error(f"处理文件时出错: {file_path}, 错误: {e}")
    
    # 删除不再存在的文件记录
    if db_type == 'sqlite':
        db.execute('''
        DELETE FROM files 
        WHERE device_uuid = ? AND path NOT IN (SELECT path FROM scanned_files)
        ''', (device_uuid,))
    else:  # PostgreSQL
        db.execute('''
        DELETE FROM files 
        WHERE device_uuid = %s AND path NOT IN (SELECT path FROM scanned_files)
        ''', (device_uuid,))
    
    # 更新最终进度
    elapsed = time.time() - start_time
    logger.info(f"扫描完成。处理了 {scanned_count} 个文件，新增 {new_files_count} 个文件，耗时: {elapsed:.2f}秒")
    
    if db_type == 'sqlite':
        db.execute('''
        UPDATE scan_progress SET 
            total_files = ?,
            new_files = ?,
            last_updated = ?
        WHERE device_uuid = ?
        ''', (scanned_count, new_files_count, datetime.now(), device_uuid))
    else:  # PostgreSQL
        db.execute('''
        UPDATE scan_progress SET 
            total_files = %s,
            new_files = %s,
            last_updated = %s
        WHERE device_uuid = %s
        ''', (scanned_count, new_files_count, datetime.now(), device_uuid))
    
    db.commit()