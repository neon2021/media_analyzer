from media_analyzer.db.db_manager import get_db

def init_db():
    """初始化数据库表结构"""
    db = get_db()
    
    # 创建设备表
    db.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id SERIAL PRIMARY KEY,
            uuid VARCHAR(36) NOT NULL,
            mount_path TEXT NOT NULL,
            label TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            system_id VARCHAR(50) NOT NULL,
            last_sync TIMESTAMP,
            is_active BOOLEAN DEFAULT true,
            UNIQUE (uuid, system_id)
        )
    """)

    # 创建设备挂载点映射表
    db.execute("""
        CREATE TABLE IF NOT EXISTS device_mount_points (
            id SERIAL PRIMARY KEY,
            device_uuid VARCHAR(36) NOT NULL,
            system_id VARCHAR(50) NOT NULL,
            mount_path TEXT NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (device_uuid, system_id)
        )
    """)

    # 创建文件表
    db.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id SERIAL PRIMARY KEY,
            device_uuid VARCHAR(36) NOT NULL,
            path TEXT NOT NULL,
            hash VARCHAR(64),
            size BIGINT,
            modified_time TIMESTAMP,
            scanned_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            system_id VARCHAR(50) NOT NULL,
            last_sync TIMESTAMP,
            UNIQUE(device_uuid, path, system_id)
        )
    """)

    # 创建扫描进度表
    db.execute("""
        CREATE TABLE IF NOT EXISTS scan_progress (
            id SERIAL PRIMARY KEY,
            device_uuid VARCHAR(36) NOT NULL,
            total_files INTEGER,
            new_files INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(device_uuid) REFERENCES devices(uuid)
        )
    """)

    # 创建图像分析表
    db.execute("""
        CREATE TABLE IF NOT EXISTS image_analysis (
            id SERIAL PRIMARY KEY,
            file_id INTEGER NOT NULL,
            camera_model TEXT,
            taken_time TIMESTAMP,
            gps_lat REAL,
            gps_lon REAL,
            has_faces BOOLEAN DEFAULT FALSE,
            objects TEXT,
            analyzed_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(file_id) REFERENCES files(id)
        )
    """)

    # 创建系统配置表
    db.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 添加索引以提高性能
    db.execute("CREATE INDEX IF NOT EXISTS idx_files_device_uuid ON files(device_uuid)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)")
    
    # 提交事务
    db.commit()

if __name__ == "__main__":
    init_db()
    print("数据库初始化完成") 