from media_analyzer.db.db_manager import get_db

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

        # 创建设备挂载点映射表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_mount_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_uuid TEXT NOT NULL,
                system_id TEXT NOT NULL,
                mount_path TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (device_uuid, system_id)
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
                last_accessed TIMESTAMP,
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

        # 创建系统配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 添加索引以提高性能
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_device_uuid ON files(device_uuid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)")
        
        # 自动提交（通过with db.get_cursor()上下文管理器）
        # 不需要显式调用commit，因为get_cursor上下文管理器会自动处理

if __name__ == "__main__":
    init_db()
    print("数据库初始化完成") 