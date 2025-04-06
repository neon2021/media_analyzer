import os
import logging
import platform
from datetime import datetime
from media_analyzer.db.db_manager import get_db
from media_analyzer.config import get_config

logger = logging.getLogger(__name__)

def update_device_registry(devices):
    """
    更新设备注册表，记录设备的UUID和挂载点，以及系统ID
    
    Args:
        devices (list): 设备列表，每个设备包含uuid、mount_path和label
        
    Returns:
        int: 更新的设备数量
    """
    if not devices:
        logger.warning("没有检测到设备")
        return 0
        
    logger.info(f"发现 {len(devices)} 个设备")
    
    db = get_db()
    config = get_config()
    
    # 获取系统标识
    system_id = config.get('system.id', f"{platform.system().lower()}-{platform.node()}")
    
    # 当前活跃设备的UUID
    active_uuids = [device['uuid'] for device in devices]
    
    with db.get_cursor() as cursor:
        # 创建设备挂载点映射表（如果不存在）
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_mount_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_uuid TEXT NOT NULL,
            system_id TEXT NOT NULL,
            mount_path TEXT NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (device_uuid, system_id)
        )
        ''')
        
        # 检查并更新现有设备
        updated_count = 0
        for device in devices:
            # 检查设备是否已存在
            cursor.execute('''
            SELECT id, mount_path FROM devices WHERE uuid = ?
            ''', (device['uuid'],))
            
            result = cursor.fetchone()
            current_time = datetime.now()
            
            if result:
                # 更新现有设备的挂载点和最后检测时间
                cursor.execute('''
                UPDATE devices 
                SET mount_path = ?, last_seen = ?
                WHERE uuid = ?
                ''', (device['mount_path'], current_time, device['uuid']))
                
                logger.info(f"更新设备: {device['label']} (UUID: {device['uuid']}), 挂载点: {device['mount_path']}")
            else:
                # 添加新设备
                cursor.execute('''
                INSERT INTO devices (uuid, mount_path, label, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ''', (device['uuid'], device['mount_path'], device['label'], current_time, current_time))
                
                logger.info(f"添加新设备: {device['label']} (UUID: {device['uuid']}), 挂载点: {device['mount_path']}")
            
            # 存储设备挂载点映射
            store_mount_point_mapping(cursor, device['uuid'], system_id, device['mount_path'])
            
            updated_count += 1
        
        # 标记不活跃的设备
        cursor.execute('''
        UPDATE devices
        SET mount_path = NULL
        WHERE uuid NOT IN ({}) AND mount_path IS NOT NULL
        '''.format(','.join(['?'] * len(active_uuids))), active_uuids if active_uuids else [""])
        
        db.conn.commit()
    
    return updated_count

def store_mount_point_mapping(cursor, device_uuid, system_id, mount_path):
    """
    存储设备挂载点映射
    
    Args:
        cursor: 数据库游标
        device_uuid (str): 设备UUID
        system_id (str): 系统标识
        mount_path (str): 挂载路径
    """
    cursor.execute('''
    INSERT INTO device_mount_points (device_uuid, system_id, mount_path, last_updated)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(device_uuid, system_id) DO UPDATE SET
        mount_path = excluded.mount_path,
        last_updated = excluded.last_updated
    ''', (device_uuid, system_id, mount_path, datetime.now()))

def get_device_mount_point(device_uuid, system_id=None):
    """
    获取设备在指定系统上的挂载点
    
    Args:
        device_uuid (str): 设备UUID
        system_id (str, optional): 系统标识，如果未指定则使用当前系统
        
    Returns:
        str: 设备挂载点路径，如果未找到则返回None
    """
    db = get_db()
    
    if not system_id:
        config = get_config()
        system_id = config.get('system.id', f"{platform.system().lower()}-{platform.node()}")
    
    with db.get_cursor() as cursor:
        # 先检查设备挂载点映射
        cursor.execute('''
        SELECT mount_path FROM device_mount_points
        WHERE device_uuid = ? AND system_id = ?
        ORDER BY last_updated DESC
        LIMIT 1
        ''', (device_uuid, system_id))
        
        result = cursor.fetchone()
        if result:
            return result[0]
        
        # 如果没有找到映射，检查设备表
        cursor.execute('''
        SELECT mount_path FROM devices
        WHERE uuid = ? AND mount_path IS NOT NULL
        ''', (device_uuid,))
        
        result = cursor.fetchone()
        if result:
            return result[0]
    
    logger.warning(f"设备 (UUID: {device_uuid}) 在系统 {system_id} 上未找到有效的挂载点")
    return None
