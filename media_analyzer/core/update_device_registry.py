"""
设备注册表管理模块，负责更新和维护设备注册信息

此模块包含用于更新设备注册表的函数，支持添加、更新和标记设备状态。
设备注册表存储在数据库中，记录所有曾经连接过的设备及其当前状态。
"""

import os
import logging
import socket
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from media_analyzer.utils.device_utils import get_device_by_uuid, list_all_device_ids
from media_analyzer.utils.config_manager import get_config
from media_analyzer.db.db_manager import get_db

logger = logging.getLogger(__name__)


def update_device_registry(devices: Union[str, List[Dict[str, Any]], Dict[str, Any]], system_id: Optional[str] = None) -> bool:
    """
    更新设备注册表，添加或更新设备信息
    
    Args:
        devices: 设备UUID字符串、设备信息字典、或设备信息字典列表
        system_id: 系统ID，如果为None则从配置中获取
        
    Returns:
        操作是否成功
    """
    try:
        # 获取系统ID
        if system_id is None:
            system_id = get_config().get('system.id', socket.gethostname())
            
        # 获取数据库连接
        db = get_db()
        
        # 转换设备参数为标准格式
        device_list = []
        if isinstance(devices, str):
            # 单个设备UUID
            device_info = get_device_by_uuid(devices)
            if device_info:
                device_list.append(device_info)
            else:
                device_list.append({'uuid': devices})
        elif isinstance(devices, dict):
            # 单个设备信息字典
            device_list.append(devices)
        else:
            # 设备信息字典列表
            device_list = devices
        
        # 确保表存在
        _ensure_devices_table_exists(db)
        
        # 批量更新设备
        for device_info in device_list:
            device_uuid = device_info.get('uuid')
            if not device_uuid:
                logger.warning(f"设备信息缺少UUID: {device_info}")
                continue
                
            # 准备设备数据
            device_data = {
                'uuid': device_uuid,
                'mount_path': device_info.get('mount_path', ''),
                'label': device_info.get('label', ''),
                'last_seen': datetime.now(),
                'system_id': system_id,
                'is_active': True
            }
            
            # 查询是否已存在
            if db.db_type == 'sqlite':
                result = db.query_one(
                    "SELECT id FROM devices WHERE uuid = ? AND system_id = ?", 
                    (device_uuid, system_id)
                )
            else:  # PostgreSQL
                result = db.query_one(
                    "SELECT id FROM devices WHERE uuid = %s AND system_id = %s", 
                    (device_uuid, system_id)
                )
                
            if result:
                # 更新现有设备
                if db.db_type == 'sqlite':
                    db.execute("""
                    UPDATE devices 
                    SET mount_path = ?, label = ?, last_seen = ?, is_active = ?
                    WHERE uuid = ? AND system_id = ?
                    """, (
                        device_data['mount_path'],
                        device_data['label'],
                        device_data['last_seen'],
                        device_data['is_active'],
                        device_data['uuid'],
                        device_data['system_id']
                    ))
                else:  # PostgreSQL
                    db.execute("""
                    UPDATE devices 
                    SET mount_path = %s, label = %s, last_seen = %s, is_active = %s
                    WHERE uuid = %s AND system_id = %s
                    """, (
                        device_data['mount_path'],
                        device_data['label'],
                        device_data['last_seen'],
                        device_data['is_active'],
                        device_data['uuid'],
                        device_data['system_id']
                    ))
                logger.info(f"更新设备记录: {device_uuid} (系统: {system_id})")
            else:
                # 添加新设备
                if db.db_type == 'sqlite':
                    db.execute("""
                    INSERT INTO devices 
                    (uuid, mount_path, label, first_seen, last_seen, system_id, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        device_data['uuid'],
                        device_data['mount_path'],
                        device_data['label'],
                        device_data['last_seen'],  # first_seen = last_seen for new records
                        device_data['last_seen'],
                        device_data['system_id'],
                        device_data['is_active']
                    ))
                else:  # PostgreSQL
                    db.execute("""
                    INSERT INTO devices 
                    (uuid, mount_path, label, first_seen, last_seen, system_id, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        device_data['uuid'],
                        device_data['mount_path'],
                        device_data['label'],
                        device_data['last_seen'],  # first_seen = last_seen for new records
                        device_data['last_seen'],
                        device_data['system_id'],
                        device_data['is_active']
                    ))
                logger.info(f"添加新设备记录: {device_uuid} (系统: {system_id})")
        
        # 提交事务
        db.commit()
        
        # 标记非活动设备
        active_uuids = [device.get('uuid') for device in device_list]
        mark_inactive_devices(active_uuids, system_id)
        
        return True
        
    except Exception as e:
        logger.error(f"更新设备注册表失败: {e}")
        return False


def mark_inactive_devices(active_uuids: List[str], system_id: Optional[str] = None) -> int:
    """
    标记当前系统中不存在的设备为非活动状态
    
    Args:
        active_uuids: 当前活动的设备UUID列表
        system_id: 系统ID，如果为None则从配置中获取
        
    Returns:
        标记为非活动的设备数量
    """
    try:
        # 获取系统ID
        if system_id is None:
            system_id = get_config().get('system.id', socket.gethostname())
            
        if not active_uuids:
            logger.warning(f"当前系统 {system_id} 未提供任何活动设备")
            return 0
        
        # 获取数据库连接
        db = get_db()
        
        # 更新不在当前设备列表中的设备状态
        count = 0
        if db.db_type == 'sqlite':
            placeholders = ','.join(['?'] * len(active_uuids))
            query = f"""
            UPDATE devices
            SET is_active = 0
            WHERE system_id = ? AND uuid NOT IN ({placeholders}) AND is_active = 1
            """
            params = [system_id] + active_uuids
            result = db.execute(query, tuple(params))
        else:  # PostgreSQL
            placeholders = ','.join(['%s'] * len(active_uuids))
            query = f"""
            UPDATE devices
            SET is_active = FALSE
            WHERE system_id = %s AND uuid NOT IN ({placeholders}) AND is_active = TRUE
            """
            params = [system_id] + active_uuids
            result = db.execute(query, tuple(params))
        
        db.commit()
        
        count = result if isinstance(result, int) else 0
        if count > 0:
            logger.info(f"已将 {count} 个设备标记为非活动状态 (系统: {system_id})")
        
        return count
        
    except Exception as e:
        logger.error(f"标记非活动设备失败: {e}")
        return 0


def _ensure_devices_table_exists(db) -> bool:
    """
    确保设备表存在
    
    Args:
        db: 数据库连接
        
    Returns:
        表是否存在或创建成功
    """
    try:
        if not db.table_exists('devices'):
            logger.info("创建devices表")
            if db.db_type == "sqlite":
                db.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT NOT NULL,
                    mount_path TEXT,
                    label TEXT,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    system_id TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    UNIQUE(uuid, system_id)
                )
                """)
            else:  # postgres
                db.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id SERIAL PRIMARY KEY,
                    uuid VARCHAR(36) NOT NULL,
                    mount_path TEXT,
                    label VARCHAR(255),
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    system_id VARCHAR(50) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    UNIQUE(uuid, system_id)
                )
                """)
            db.commit()
        return True
    except Exception as e:
        logger.error(f"创建devices表失败: {e}")
        return False
