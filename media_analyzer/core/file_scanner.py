import os
import hashlib
import time
import multiprocessing
from datetime import datetime
from db_manager import get_db

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

def save_progress_to_db(device_uuid, total_files, new_files):
    """每 N 秒保存一次进度到数据库"""
    db = get_db()
    with db.get_cursor() as cursor:
        cursor.execute("""
            INSERT OR REPLACE INTO scan_progress (device_uuid, total_files, new_files, last_updated)
            VALUES (?, ?, ?, ?)
        """, (device_uuid, total_files, new_files, now()))
    
def scan_files_on_device(mount_path, device_uuid, progress_interval=30):
    """递归扫描指定设备上的文件并写入数据库"""
    db = get_db()
    total = 0
    new_files = 0
    start_time = time.time()

    for root, dirs, files in os.walk(mount_path):
        # 在目录阶段剪枝
        # 系统目录跳过
        if should_skip_path(root):
            dirs[:] = []  # 清空子目录，阻止继续深入
            continue      # 跳过该 root 下的所有文件
        
        for name in files:
            file_path = os.path.join(root, name)
            
            # ✅ 每个文件实时检查数据库中是否已存在
            with db.get_cursor(commit=False) as cursor:
                cursor.execute("""
                    SELECT 1 FROM files WHERE device_uuid = ? AND path = ? LIMIT 1
                """, (device_uuid, file_path))
                if cursor.fetchone():
                    continue  # 文件已存在，跳过
            
            try:
                stat = os.stat(file_path)
                size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()
                file_hash = compute_file_hash(file_path)
                total += 1

                if file_hash:
                    with db.get_cursor() as cursor:
                        cursor.execute("""
                            INSERT OR IGNORE INTO files (
                                device_uuid, path, hash, size, modified_time
                            ) VALUES (?, ?, ?, ?, ?)
                        """, (device_uuid, file_path, file_hash, size, mtime))

                        if cursor.rowcount > 0:
                            new_files += 1

            except Exception as e:
                print(f"[{now()}] [跳过] 无法处理文件: {file_path}, 错误: {e}")

            # 每 N 秒保存进度到数据库
            if time.time() - start_time >= progress_interval:
                save_progress_to_db(device_uuid, total, new_files)
                print(f"[{now()}] 保存进度: 已扫描 {total} 文件, 新增 {new_files} 文件, 耗时: {time.time() - start_time:.1f} 秒")
                start_time = time.time()  # 重置计时器

            if total % 1000 == 0:
                elapsed = time.time() - start_time
                print(f"[{now()}] [进度] 已处理: {total} 文件，新增: {new_files}，耗时: {elapsed:.1f} 秒")

    # 最后保存一次进度
    save_progress_to_db(device_uuid, total, new_files)
    elapsed = time.time() - start_time
    print(f"[{now()}] [完成] 总计扫描: {total} 文件，新增: {new_files}，总耗时: {elapsed:.1f} 秒")