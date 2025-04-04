from datetime import datetime
from device_utils import list_all_device_ids
from db_manager import get_db

def update_device_registry():
    """更新设备注册表"""
    db = get_db()
    devices = list_all_device_ids()
    now = datetime.now().isoformat()

    with db.get_cursor() as cursor:
        for mount_path, uuid in devices.items():
            cursor.execute("""
                INSERT INTO devices (uuid, mount_path, first_seen, last_seen)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET
                    mount_path=excluded.mount_path,
                    last_seen=excluded.last_seen
            """, (uuid, mount_path, now, now))
