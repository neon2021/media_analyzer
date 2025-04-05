import os
import subprocess
import platform
import hashlib
import logging

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


def list_all_device_ids():
    """列出所有挂载的设备及其UUID"""
    devices = {}
    logger.info("开始获取所有挂载设备列表")
    
    try:
        # 执行mount命令获取挂载信息
        logger.debug("执行mount命令")
        result = subprocess.run(['mount'], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"执行mount命令失败: {result.stderr}")
            return devices

        # 解析mount输出
        logger.debug("解析mount输出")
        for line in result.stdout.splitlines():
            try:
                # macOS格式: /dev/disk2s1 on /Volumes/USB (hfs, local, nodev, nosuid, read-only, noowners, mounted by caesar)
                # macOS autofs格式: map auto_home on /System/Volumes/Data/home (autofs, automounted, nobrowse)
                # Ubuntu格式: /dev/sda1 on /media/username/USB type ext4 (rw,nosuid,nodev,relatime)
                
                # 跳过autofs挂载
                if 'autofs' in line:
                    logger.debug(f"跳过autofs挂载: {line}")
                    continue
                    
                parts = line.split()
                if len(parts) < 3:
                    logger.debug(f"跳过无效的mount行: {line}")
                    continue

                # 提取设备路径和挂载点
                if platform.system() == "Darwin":  # macOS
                    # macOS格式处理
                    parts = line.split(" on ")
                    if len(parts) != 2:
                        logger.debug(f"跳过无效的macOS mount行: {line}")
                        continue
                    device_path = parts[0]
                    mount_point = parts[1].split(" (")[0].strip()
                else:  # Linux
                    # Ubuntu格式处理
                    device_path = parts[0]
                    mount_point = parts[2]

                logger.debug(f"处理设备: {device_path} -> {mount_point}")

                # 跳过系统虚拟文件系统
                if any(mount_point.startswith(sys_path) for sys_path in ['/sys', '/proc', '/dev', '/run', '/boot', '/snap']):
                    logger.debug(f"跳过系统虚拟文件系统: {mount_point}")
                    continue

                # 获取设备UUID
                logger.debug(f"获取设备UUID: {mount_point}")
                uuid = get_device_uuid(mount_point, device_path if platform.system() == "Linux" else None)
                if uuid:
                    logger.info(f"找到设备: {mount_point} -> {uuid}")
                    devices[mount_point] = uuid
                else:
                    logger.warning(f"无法获取设备UUID: {mount_point}")

            except Exception as e:
                logger.error(f"处理mount行时出错: {line}", exc_info=True)
                continue

    except Exception as e:
        logger.error("获取设备列表失败", exc_info=True)

    logger.info(f"完成设备列表获取，共找到 {len(devices)} 个设备")
    return devices
