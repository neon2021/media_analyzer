import os
import logging
from datetime import datetime
from media_analyzer.db.db_manager import get_db
from media_analyzer.utils.path_converter import PathConverter
from media_analyzer.core.update_device_registry import get_device_mount_point

logger = logging.getLogger(__name__)

def get_file_path(file_id, system_id=None):
    """
    获取文件的完整路径，适用于当前系统
    
    Args:
        file_id (int): 文件ID
        system_id (str, optional): 系统ID，用于确定当前运行的操作系统
    
    Returns:
        str: 文件的完整路径，如果找不到则返回None
    """
    db = get_db()
    
    with db.get_cursor() as cursor:
        # 获取文件和设备信息
        cursor.execute('''
        SELECT f.device_uuid, f.path, d.label
        FROM files f
        JOIN devices d ON f.device_uuid = d.uuid
        WHERE f.id = ?
        ''', (file_id,))
        
        result = cursor.fetchone()
        if not result:
            logger.error(f"找不到ID为 {file_id} 的文件")
            return None
            
        device_uuid, rel_path, device_label = result
        
        # 获取设备在当前系统上的挂载点
        mount_point = get_device_mount_point(device_uuid, system_id)
        
        if not mount_point:
            logger.warning(f"设备 {device_label} (UUID: {device_uuid}) 未挂载在当前系统")
            return None
            
        # 构建完整路径
        full_path = os.path.join(mount_point, rel_path)
        
        # 检查文件是否存在
        if not os.path.exists(full_path):
            logger.warning(f"文件 {full_path} 不存在")
            return None
            
        return full_path

def update_file_access(file_id):
    """
    更新文件的访问记录
    
    Args:
        file_id (int): 文件ID
    """
    db = get_db()
    
    with db.get_cursor() as cursor:
        cursor.execute('''
        UPDATE files
        SET last_accessed = ?
        WHERE id = ?
        ''', (datetime.now(), file_id))
        
        if cursor.rowcount == 0:
            logger.warning(f"更新文件访问记录失败，ID: {file_id}")

def search_files(keyword=None, device_uuid=None, file_type=None, min_size=None, max_size=None, limit=100, offset=0):
    """
    搜索文件
    
    Args:
        keyword (str, optional): 搜索关键词
        device_uuid (str, optional): 设备UUID
        file_type (str, optional): 文件类型
        min_size (int, optional): 最小文件大小
        max_size (int, optional): 最大文件大小
        limit (int, optional): 返回结果限制
        offset (int, optional): 分页偏移量
        
    Returns:
        list: 文件列表
    """
    db = get_db()
    params = []
    conditions = []
    
    # 构建查询条件
    if keyword:
        conditions.append("path LIKE ?")
        params.append(f"%{keyword}%")
        
    if device_uuid:
        conditions.append("device_uuid = ?")
        params.append(device_uuid)
        
    if file_type:
        conditions.append("path LIKE ?")
        params.append(f"%.{file_type}")
        
    if min_size is not None:
        conditions.append("size >= ?")
        params.append(min_size)
        
    if max_size is not None:
        conditions.append("size <= ?")
        params.append(max_size)
        
    # 构建查询SQL
    sql = '''
    SELECT 
        f.id, f.device_uuid, f.path, f.hash, f.size, 
        f.modified_time, f.scanned_time, f.last_accessed,
        d.label as device_label
    FROM files f
    JOIN devices d ON f.device_uuid = d.uuid
    '''
    
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
        
    sql += " ORDER BY f.modified_time DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    with db.get_cursor() as cursor:
        cursor.execute(sql, params)
        results = cursor.fetchall()
        
    return results 