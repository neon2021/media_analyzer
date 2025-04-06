"""
设备工具模块，提供设备信息获取和管理功能

此模块包含用于获取设备信息、路径转换和设备挂载点管理的各种工具函数
"""

import os
import re
import logging
import platform
import subprocess
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def get_current_system_info() -> Dict[str, str]:
    """
    获取当前系统信息
    
    Returns:
        系统信息字典，包含系统类型和主机名
    """
    return {
        'system': platform.system().lower(),
        'hostname': platform.node()
    }


def list_all_device_ids() -> Dict[str, str]:
    """
    列出系统中所有设备的ID，包括系统分区和外接设备
    
    Returns:
        字典，键为挂载路径，值为设备UUID
    """
    system = platform.system()
    devices = {}
    
    # 首先获取外接设备
    if system == 'Darwin':  # macOS
        devices = _list_macos_devices()
    elif system == 'Linux':
        devices = _list_linux_devices()
    elif system == 'Windows':
        devices = _list_windows_devices()
    else:
        logger.warning(f"不支持的操作系统: {system}")
    
    # 添加本地主目录
    home_dir = os.path.expanduser("~")
    if os.path.exists(home_dir) and home_dir not in devices:
        # 为主目录生成一个固定的UUID (根据主机名和用户目录)
        system_name = platform.node().replace('.', '-')
        user_name = os.path.basename(home_dir)
        home_uuid = f"HOME-{system_name}-{user_name}"
        
        devices[home_dir] = home_uuid
        logger.info(f"已添加主目录到设备列表: {home_dir} (UUID: {home_uuid})")
    
    return devices


def _list_macos_devices() -> Dict[str, str]:
    """
    列出 macOS 系统中的所有设备
    
    Returns:
        字典，键为挂载路径，值为设备UUID
    """
    devices = {}
    
    try:
        # 获取磁盘列表
        result = subprocess.run(['diskutil', 'list', '-plist'], 
                               capture_output=True, text=True, check=True)
        
        # 解析输出，查找每个磁盘的UUID和挂载点
        # macOS diskutil 信息比较复杂，需要额外处理
        
        # 使用命令获取所有卷信息
        result = subprocess.run(['diskutil', 'info', '-all'], 
                               capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"获取设备信息失败: {result.stderr}")
            return devices
            
        # 解析输出
        current_volume = None
        current_data = {}
        
        for line in result.stdout.splitlines():
            line = line.strip()
            
            # 新卷的开始
            if line.startswith('Device Identifier:'):
                # 保存之前的卷信息
                if current_volume and 'UUID' in current_data and 'Mount Point' in current_data:
                    devices[current_data['Mount Point']] = current_data['UUID']
                
                current_volume = line.split(':')[1].strip()
                current_data = {}
            
            # 获取UUID
            elif 'Volume UUID:' in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current_data['UUID'] = parts[1].strip()
            
            # 获取挂载点
            elif 'Mount Point:' in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    mount_point = parts[1].strip()
                    if mount_point and mount_point != '(not mounted)':
                        current_data['Mount Point'] = mount_point
        
        # 保存最后一个卷的信息
        if current_volume and 'UUID' in current_data and 'Mount Point' in current_data:
            devices[current_data['Mount Point']] = current_data['UUID']
            
        # 过滤掉系统挂载点，但保留用户根目录所在卷
        filtered_devices = {}
        for path, uuid in devices.items():
            # 保留/Volumes下的卷，过滤掉Recovery和VM
            if ((path.startswith('/Volumes/') and 
                not path.startswith('/Volumes/Recovery') and 
                not path.startswith('/Volumes/VM')) or
                # 保留根目录所在卷
                path == '/'):
                filtered_devices[path] = uuid
            
        return filtered_devices
        
    except Exception as e:
        logger.error(f"获取macOS设备列表失败: {e}")
        return {}


def _list_linux_devices() -> Dict[str, str]:
    """
    列出 Linux 系统中的所有设备
    
    Returns:
        字典，键为挂载路径，值为设备UUID
    """
    devices = {}
    
    try:
        # 获取块设备列表
        result = subprocess.run(['lsblk', '-o', 'NAME,UUID,MOUNTPOINT', '-n', '-p'], 
                                capture_output=True, text=True, check=True)
        
        # 解析输出
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 3:
                device_path = parts[0]
                uuid = parts[1]
                mount_point = ' '.join(parts[2:])
                
                if uuid and mount_point and mount_point not in ['/boot', '/']:
                    devices[mount_point] = uuid
        
        return devices
        
    except Exception as e:
        logger.error(f"获取Linux设备列表失败: {e}")
        return {}


def _list_windows_devices() -> Dict[str, str]:
    """
    列出 Windows 系统中的所有设备
    
    Returns:
        字典，键为挂载路径，值为设备UUID
    """
    devices = {}
    
    try:
        # 使用 wmic 命令获取卷信息
        result = subprocess.run(['wmic', 'volume', 'get', 'DeviceID,DriveLetter'], 
                               capture_output=True, text=True, check=True)
        
        # 解析输出
        for line in result.stdout.splitlines()[1:]:  # 跳过标题行
            parts = line.strip().split()
            if len(parts) >= 2:
                drive_letter = parts[0]
                device_id = parts[1]
                
                if drive_letter and device_id and drive_letter != 'C:':
                    devices[drive_letter] = device_id
        
        return devices
        
    except Exception as e:
        logger.error(f"获取Windows设备列表失败: {e}")
        return {}


def get_device_by_path(path: str) -> Optional[Dict[str, Any]]:
    """
    根据路径获取设备信息
    
    Args:
        path: 文件或目录路径
        
    Returns:
        设备信息字典，包含uuid、path和label字段，如果未找到设备则返回None
    """
    if not path:
        return None
        
    # 获取所有设备
    all_devices = list_all_device_ids()
    if not all_devices:
        logger.warning("未找到任何设备")
        return None
    
    # 规范化路径
    abs_path = os.path.abspath(path)
    
    # 找到最匹配的挂载点
    best_match = None
    best_length = 0
    
    for mount_path, uuid in all_devices.items():
        if abs_path.startswith(mount_path) and len(mount_path) > best_length:
            best_match = mount_path
            best_length = len(mount_path)
    
    if best_match:
        return {
            'uuid': all_devices[best_match],
            'path': best_match,
            'label': os.path.basename(best_match)
        }
    
    return None


def get_device_by_uuid(uuid: str) -> Optional[Dict[str, Any]]:
    """
    根据UUID获取设备信息
    
    Args:
        uuid: 设备UUID
        
    Returns:
        设备信息字典，包含uuid、path和label字段，如果未找到设备则返回None
    """
    if not uuid:
        return None
        
    # 获取所有设备
    all_devices = list_all_device_ids()
    
    # 查找匹配的UUID
    for mount_path, device_uuid in all_devices.items():
        if device_uuid == uuid:
            return {
                'uuid': uuid,
                'path': mount_path,
                'label': os.path.basename(mount_path)
            }
    
    return None


def get_mount_point(path: str) -> Optional[str]:
    """
    获取路径所在的挂载点
    
    Args:
        path: 文件或目录路径
        
    Returns:
        挂载点路径，如果未找到则返回None
    """
    device = get_device_by_path(path)
    if device:
        return device['path']
    return None
