-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 创建设备表
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE NOT NULL,
    mount_path TEXT NOT NULL,
    label TEXT,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    system_id VARCHAR(50) NOT NULL,
    last_sync TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- 创建文件表
CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    device_uuid VARCHAR(36) NOT NULL,
    path TEXT NOT NULL,
    hash VARCHAR(64),
    size BIGINT,
    modified_time TIMESTAMP,
    scanned_time TIMESTAMP,
    system_id VARCHAR(50) NOT NULL,
    last_sync TIMESTAMP,
    UNIQUE(device_uuid, path)
);

-- 创建扫描进度表
CREATE TABLE IF NOT EXISTS scan_progress (
    id SERIAL PRIMARY KEY,
    device_uuid VARCHAR(36) UNIQUE NOT NULL,
    total_files INTEGER,
    new_files INTEGER,
    last_updated TIMESTAMP,
    system_id VARCHAR(50) NOT NULL,
    last_sync TIMESTAMP
);

-- 创建图像分析表
CREATE TABLE IF NOT EXISTS image_analysis (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL,
    camera_model TEXT,
    taken_time TIMESTAMP,
    gps_lat FLOAT,
    gps_lon FLOAT,
    has_faces BOOLEAN,
    objects JSONB,
    analyzed_time TIMESTAMP,
    system_id VARCHAR(50) NOT NULL,
    last_sync TIMESTAMP
);

-- 创建同步日志表
CREATE TABLE IF NOT EXISTS sync_logs (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    record_id INTEGER NOT NULL,
    operation VARCHAR(10) NOT NULL,
    system_id VARCHAR(50) NOT NULL,
    sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_devices_uuid ON devices(uuid);
CREATE INDEX IF NOT EXISTS idx_devices_system_id ON devices(system_id);
CREATE INDEX IF NOT EXISTS idx_files_device_uuid ON files(device_uuid);
CREATE INDEX IF NOT EXISTS idx_files_system_id ON files(system_id);
CREATE INDEX IF NOT EXISTS idx_scan_progress_device_uuid ON scan_progress(device_uuid);
CREATE INDEX IF NOT EXISTS idx_scan_progress_system_id ON scan_progress(system_id);
CREATE INDEX IF NOT EXISTS idx_image_analysis_file_id ON image_analysis(file_id);
CREATE INDEX IF NOT EXISTS idx_image_analysis_system_id ON image_analysis(system_id);
CREATE INDEX IF NOT EXISTS idx_sync_logs_table_name ON sync_logs(table_name);
CREATE INDEX IF NOT EXISTS idx_sync_logs_system_id ON sync_logs(system_id);

-- 创建函数
CREATE OR REPLACE FUNCTION update_last_sync()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_sync = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器
CREATE TRIGGER update_devices_last_sync
    BEFORE UPDATE ON devices
    FOR EACH ROW
    EXECUTE FUNCTION update_last_sync();

CREATE TRIGGER update_files_last_sync
    BEFORE UPDATE ON files
    FOR EACH ROW
    EXECUTE FUNCTION update_last_sync();

CREATE TRIGGER update_scan_progress_last_sync
    BEFORE UPDATE ON scan_progress
    FOR EACH ROW
    EXECUTE FUNCTION update_last_sync();

CREATE TRIGGER update_image_analysis_last_sync
    BEFORE UPDATE ON image_analysis
    FOR EACH ROW
    EXECUTE FUNCTION update_last_sync(); 