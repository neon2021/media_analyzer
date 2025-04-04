from device_utils import get_device_uuid, list_all_device_ids


# 列出所有挂载的外接设备
devices = list_all_device_ids()
for path, device_id in devices.items():
    print(f"{path} -> {device_id}")

    # 获取特定设备的 UUID
    uuid = get_device_uuid(f"{path}")  # 或 "/media/username/USB"
    print(f"设备UUID: {uuid}")