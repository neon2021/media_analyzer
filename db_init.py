from db_manager import get_db

def init_db():
    """初始化数据库表结构"""
    db = get_db()
    
    with db.get_cursor() as cursor:
        # 创建设备表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                mount_path TEXT,
                label TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP
            )
        """)

        # 创建文件表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_uuid TEXT NOT NULL,
                path TEXT NOT NULL,
                hash TEXT,
                size INTEGER,
                modified_time TEXT,
                scanned_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (device_uuid, path)
            )
        """)

        # 创建扫描进度表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_uuid TEXT NOT NULL,
                total_files INTEGER,
                new_files INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(device_uuid) REFERENCES devices(uuid)
            )
        """)

        # 创建图像分析表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                camera_model TEXT,
                taken_time TEXT,
                gps_lat REAL,
                gps_lon REAL,
                has_faces INTEGER DEFAULT 0,
                objects TEXT,
                analyzed_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(file_id) REFERENCES files(id)
            )
        """) 