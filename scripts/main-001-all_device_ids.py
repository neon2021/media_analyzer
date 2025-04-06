from media_analyzer.utils.device_utils import list_all_device_ids, get_device_by_path


# 列出所有挂载的外接设备
devices = list_all_device_ids()
for path, device_id in devices.items():
    print(f"{path} -> {device_id}")

    # 获取特定设备的信息
    device_info = get_device_by_path(path)
    if device_info:
        print(f"设备UUID: {device_info['uuid']}")