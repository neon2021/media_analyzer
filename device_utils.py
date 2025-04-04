import os
import subprocess
import platform
import hashlib

def get_device_uuid(mount_path: str) -> str:
    """
    获取挂载设备的唯一ID（分区UUID或设备指纹），兼容 macOS 和 Linux。
    
    参数:
        mount_path: 设备的挂载路径，例如 "/Volumes/MyDisk" 或 "/media/user/USB"
        
    返回:
        唯一设备ID（字符串）
    """
    system = platform.system()

    if not os.path.exists(mount_path):
        raise FileNotFoundError(f"路径不存在: {mount_path}")

    try:
        if system == "Darwin":  # macOS
            # 获取挂载设备信息
            result = subprocess.check_output(["diskutil", "info", mount_path]).decode()
            uuid = None
            for line in result.splitlines():
                if "Volume UUID" in line:
                    uuid = line.split(":")[1].strip()
                    break
            if uuid:
                return uuid

        elif system == "Linux":
            # 使用 mount 查看设备路径
            mount_output = subprocess.check_output(["mount"]).decode()
            device_path = None
            for line in mount_output.splitlines():
                if mount_path in line:
                    device_path = line.split()[0]
                    break

            if device_path:
                # 尝试用 blkid 获取 UUID
                blkid_output = subprocess.check_output(["blkid", device_path]).decode()
                for item in blkid_output.split():
                    if item.startswith("UUID="):
                        return item.split("=")[1].strip('"')

    except Exception as e:
        print(f"获取 UUID 时出错：{e}")

    # 如果无法获取UUID，退而求其次：使用设备路径生成指纹
    try:
        stat = os.stat(mount_path)
        fingerprint = f"{mount_path}:{stat.st_dev}:{stat.st_ino}:{stat.st_ctime}"
        return "fp_" + hashlib.md5(fingerprint.encode()).hexdigest()
    except Exception as e:
        raise RuntimeError(f"无法生成设备指纹：{e}")


def list_all_device_ids() -> dict:
    """
    获取当前系统中所有挂载设备（包括本地系统盘和外接设备）及其唯一ID。
    """
    system = platform.system()
    device_ids = {}

    try:
        mounts = subprocess.check_output(["mount"]).decode().splitlines()

        for line in mounts:
            parts = line.split(" on ")
            if len(parts) >= 2:
                # 提取挂载路径（去除挂载参数括号）
                mount_info = parts[1]
                mount_path = mount_info.split(" (")[0].strip()

                # macOS
                if system == "Darwin":
                    if mount_path.startswith("/Volumes/") or mount_path == "/":
                        try:
                            device_id = get_device_uuid(mount_path)
                            device_ids[mount_path] = device_id
                        except Exception as e:
                            print(f"跳过 {mount_path}: {e}")

                # Linux
                elif system == "Linux":
                    if mount_path.startswith(("/media/", "/mnt/", "/home/", "/")):
                        try:
                            device_id = get_device_uuid(mount_path)
                            device_ids[mount_path] = device_id
                        except Exception as e:
                            print(f"跳过 {mount_path}: {e}")

    except Exception as e:
        print(f"获取挂载设备列表失败：{e}")

    return device_ids
