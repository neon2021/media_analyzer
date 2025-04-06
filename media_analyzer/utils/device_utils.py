import os
import re
import subprocess
import platform
import hashlib
import logging
from media_analyzer.utils.path_converter import PathConverter

# 获取当前模块的logger
logger = logging.getLogger(__name__)

def get_device_uuid(mount_path: str, device_path: str = None) -> str:
    """
    获取挂载设备的唯一ID（分区UUID或设备指纹），兼容 macOS 和 Linux。
    
    参数:
        mount_path: 设备的挂载路径，例如 "/Volumes/MyDisk" 或 "/media/user/USB"
        device_path: 设备路径，例如 "/dev/sda1"（仅Linux需要）
        
    返回:
        唯一设备ID（字符串）
    """
    system = platform.system()
    logger.debug(f"获取设备UUID - 系统类型: {system}, 挂载路径: {mount_path}, 设备路径: {device_path}")

    if not os.path.exists(mount_path):
        logger.error(f"路径不存在: {mount_path}")
        raise FileNotFoundError(f"路径不存在: {mount_path}")

    try:
        if system == "Darwin":  # macOS
            logger.debug("使用diskutil获取设备信息")
            # 获取挂载设备信息
            result = subprocess.check_output(["diskutil", "info", mount_path]).decode()
            uuid = None
            for line in result.splitlines():
                if "Volume UUID" in line:
                    uuid = line.split(":")[1].strip()
                    break
            if uuid:
                logger.debug(f"成功获取UUID: {uuid}")
                return uuid

        elif system == "Linux":
            logger.debug("使用blkid获取设备信息")
            if device_path:
                # 跳过虚拟文件系统
                try:
                    # 尝试用 blkid 获取 UUID
                    blkid_output = subprocess.check_output(["blkid", device_path]).decode()
                    for item in blkid_output.split():
                        if item.startswith("UUID="):
                            uuid = item.split("=")[1].strip('"')
                            logger.debug(f"成功获取UUID: {uuid}")
                            return uuid
                except subprocess.CalledProcessError as e:
                    logger.warning(f"blkid命令执行失败: {e}")
                    return None

    except Exception as e:
        logger.error(f"获取 UUID 时出错：{e}", exc_info=True)

    # 如果无法获取UUID，退而求其次：使用设备路径生成指纹
    try:
        logger.debug("无法获取UUID，尝试生成设备指纹")
        stat = os.stat(mount_path)
        fingerprint = f"{mount_path}:{stat.st_dev}:{stat.st_ino}:{stat.st_ctime}"
        device_fingerprint = "fp_" + hashlib.md5(fingerprint.encode()).hexdigest()
        logger.debug(f"生成设备指纹: {device_fingerprint}")
        return device_fingerprint
    except Exception as e:
        logger.error(f"无法生成设备指纹：{e}", exc_info=True)
        raise RuntimeError(f"无法生成设备指纹：{e}")


def list_all_devices():
    """
    列出系统中的所有存储设备
    
    Returns:
        list: 设备列表，每个设备包含uuid、mount_path和label
    """
    system = platform.system()
    
    if system == 'Darwin':  # macOS
        return _list_macos_devices()
    elif system == 'Linux':  # Linux
        return _list_linux_devices()
    elif system == 'Windows':  # Windows
        return _list_windows_devices()
    else:
        logger.warning(f"未知的操作系统: {system}")
        return []

def list_all_device_ids():
    """
    获取所有设备的挂载路径和UUID的映射字典
    
    Returns:
        dict: 挂载路径到UUID的映射 {mount_path: uuid}
    """
    devices = list_all_devices()
    device_ids = {}
    
    for device in devices:
        mount_path = device.get('mount_path')
        uuid = device.get('uuid')
        
        if mount_path and uuid:
            # 标准化路径，确保路径格式一致
            mount_path = PathConverter.normalize_path(mount_path)
            device_ids[mount_path] = uuid
            logger.info(f"添加设备映射: {mount_path} -> {uuid}")
    
    if not device_ids:
        logger.warning("未找到任何设备")
    else:
        logger.info(f"找到 {len(device_ids)} 个设备")
    
    return device_ids

def _list_macos_devices():
    """
    列出macOS系统中的所有设备
    
    Returns:
        list: 设备列表
    """
    devices = []
    
    try:
        # 获取所有卷的信息
        result = subprocess.run(['diskutil', 'list', '-plist'], 
                               capture_output=True, text=True, check=True)
        
        # 解析plist输出
        import plistlib
        disk_list = plistlib.loads(result.stdout.encode('utf-8'))
        
        # 获取所有磁盘
        for disk in disk_list.get('AllDisksAndPartitions', []):
            # 检查是否有分区
            partitions = disk.get('Partitions', [])
            
            for partition in partitions:
                # 忽略没有挂载点的分区
                mount_point = partition.get('MountPoint')
                if not mount_point:
                    continue
                
                # 获取UUID
                volume_name = partition.get('VolumeName', '')
                if not volume_name:
                    volume_name = os.path.basename(mount_point)
                
                # 获取设备UUID
                uuid_result = subprocess.run(
                    ['diskutil', 'info', '-plist', mount_point],
                    capture_output=True, text=True, check=False
                )
                
                if uuid_result.returncode == 0:
                    volume_info = plistlib.loads(uuid_result.stdout.encode('utf-8'))
                    uuid = volume_info.get('VolumeUUID')
                    
                    if uuid:
                        devices.append({
                            'uuid': uuid,
                            'mount_path': mount_point,
                            'label': volume_name
                        })
                        logger.info(f"发现设备: {volume_name} (UUID: {uuid}), 挂载点: {mount_point}")
    
    except Exception as e:
        logger.error(f"获取macOS设备列表失败: {e}")
    
    return devices

def _list_linux_devices():
    """
    列出Linux系统中的所有设备
    
    Returns:
        list: 设备列表
    """
    devices = []
    
    try:
        # 执行lsblk命令获取所有块设备信息
        result = subprocess.run(
            ['lsblk', '-o', 'UUID,MOUNTPOINT,LABEL', '-n', '-p'],
            capture_output=True, text=True, check=True
        )
        
        # 解析输出
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            
            # 跳过没有UUID或挂载点的设备
            if len(parts) < 2 or not parts[0] or not parts[1]:
                continue
                
            uuid = parts[0].strip()
            mount_path = parts[1].strip()
            
            # 获取卷标（如果有）
            label = parts[2].strip() if len(parts) >= 3 else os.path.basename(mount_path)
            
            # 不再忽略系统目录
            devices.append({
                'uuid': uuid,
                'mount_path': mount_path,
                'label': label
            })
            
            logger.info(f"发现设备: {label} (UUID: {uuid}), 挂载点: {mount_path}")
    
    except Exception as e:
        logger.error(f"获取Linux设备列表失败: {e}")
    
    # 如果没有找到任何设备或者发生错误，添加一些调试用的默认设备
    if not devices:
        logger.info("添加基本系统目录用于测试")
        # 添加根目录
        root_dir = "/"
        root_stat = os.stat(root_dir)
        root_uuid = f"debug_root_{root_stat.st_dev}_{root_stat.st_ino}"
        
        devices.append({
            'uuid': root_uuid,
            'mount_path': root_dir,
            'label': 'Root'
        })
        
        # 添加用户主目录
        home_dir = os.path.expanduser("~")
        home_stat = os.stat(home_dir)
        home_uuid = f"debug_home_{home_stat.st_dev}_{home_stat.st_ino}"
        
        devices.append({
            'uuid': home_uuid,
            'mount_path': home_dir,
            'label': 'Home'
        })
        
        # 添加当前工作目录（如果与主目录不同）
        cwd = os.getcwd()
        if cwd != home_dir:
            cwd_stat = os.stat(cwd)
            cwd_uuid = f"debug_cwd_{cwd_stat.st_dev}_{cwd_stat.st_ino}"
            
            devices.append({
                'uuid': cwd_uuid,
                'mount_path': cwd,
                'label': 'Current Directory'
            })
        
        logger.info(f"已添加 {len(devices)} 个调试设备")
    
    return devices

def _list_windows_devices():
    """
    列出Windows系统中的所有设备
    
    Returns:
        list: 设备列表
    """
    devices = []
    
    try:
        # 使用wmic获取所有卷的信息
        result = subprocess.run(
            ['wmic', 'volume', 'get', 'DeviceID,DriveLetter,Label,DriveType'],
            capture_output=True, text=True, check=True
        )
        
        # 解析输出（跳过标题行）
        lines = result.stdout.strip().split('\n')[1:]
        for line in lines:
            parts = re.split(r'\s{2,}', line.strip())
            
            # 跳过格式不正确的行
            if len(parts) < 4:
                continue
                
            drive_letter = parts[1].strip()
            label = parts[2].strip()
            device_id = parts[0].strip()
            drive_type = parts[3].strip()
            
            # 只处理可移动设备和固定硬盘（类型2和3）
            if drive_type not in ['2', '3'] or not drive_letter:
                continue
                
            # 使用卷序列号作为UUID
            uuid = device_id.replace('\\', '_').replace('?', '_')
            mount_path = f"{drive_letter}\\"
            
            if not label:
                label = drive_letter
                
            devices.append({
                'uuid': uuid,
                'mount_path': mount_path,
                'label': label
            })
            
            logger.info(f"发现设备: {label} (UUID: {uuid}), 挂载点: {mount_path}")
    
    except Exception as e:
        logger.error(f"获取Windows设备列表失败: {e}")
    
    return devices

def get_device_info(mount_path):
    """
    获取指定挂载点的设备信息
    
    Args:
        mount_path (str): 挂载点路径
        
    Returns:
        dict: 设备信息，包含uuid、mount_path和label，如果未找到则返回None
    """
    # 标准化路径
    mount_path = PathConverter.normalize_path(mount_path)
    
    # 获取所有设备
    devices = list_all_devices()
    
    # 查找匹配的设备
    for device in devices:
        device_mount = PathConverter.normalize_path(device['mount_path'])
        
        # 检查路径是否匹配
        if mount_path == device_mount or mount_path.startswith(device_mount + '/'):
            return device
    
    logger.warning(f"未找到挂载点 {mount_path} 对应的设备")
    return None
