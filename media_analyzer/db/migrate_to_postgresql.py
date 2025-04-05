import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import logging
from media_analyzer.utils.config_manager import get_config
import time
from datetime import datetime
import platform
import socket

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def get_sqlite_connection():
    """获取 SQLite 连接"""
    config = get_config()
    sqlite_path = os.path.expanduser(config.get('database.path'))
    logger.info(f"连接到 SQLite 数据库: {sqlite_path}")
    return sqlite3.connect(sqlite_path)

def get_postgres_connection():
    """获取 PostgreSQL 连接"""
    config = get_config()
    print(f'config: {config}')
    
    # 获取 PostgreSQL 连接信息
    db_name = config.get('database.postgres.database', 'media_analyzer')
    username = config.get('database.postgres.username', 'postgres')
    password = config.get('database.postgres.password', 'postgres')
    host = config.get('database.postgres.host', 'localhost')
    port = config.get('database.postgres.port', 5432)
    
    # 如果主机名是Docker容器名称，且不在Docker环境中，则切换到localhost
    if host == 'media_analyzer_postgres':
        try:
            socket.gethostbyname(host)
        except socket.gaierror:
            logger.warning(f"无法解析主机名 '{host}'，切换到 'localhost'")
            host = 'localhost'
    
    logger.info(f"连接到 PostgreSQL 数据库: {host}:{port}/{db_name}")
    
    # 尝试连接
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=username,
            password=password,
            host=host,
            port=port
        )
        return conn
    except psycopg2.OperationalError as e:
        if host != 'localhost':
            logger.warning(f"连接到 {host} 失败，尝试连接到 localhost")
            return psycopg2.connect(
                dbname=db_name,
                user=username,
                password=password,
                host='localhost',
                port=port
            )
        else:
            raise

def create_postgres_tables(pg_conn):
    """创建 PostgreSQL 表结构"""
    cursor = pg_conn.cursor()
    
    # 创建设备表
    cursor.execute("""
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
        )
    """)
    
    # 创建文件表
    cursor.execute("""
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
        )
    """)
    
    # 创建扫描进度表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_progress (
            id SERIAL PRIMARY KEY,
            device_uuid VARCHAR(36) UNIQUE NOT NULL,
            total_files INTEGER,
            new_files INTEGER,
            last_updated TIMESTAMP,
            system_id VARCHAR(50) NOT NULL,
            last_sync TIMESTAMP
        )
    """)
    
    # 创建图像分析表
    cursor.execute("""
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
        )
    """)
    
    # 创建同步日志表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_logs (
            id SERIAL PRIMARY KEY,
            table_name VARCHAR(50) NOT NULL,
            record_id INTEGER NOT NULL,
            operation VARCHAR(10) NOT NULL,
            system_id VARCHAR(50) NOT NULL,
            sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    pg_conn.commit()
    logger.info("PostgreSQL 表结构创建完成")

def migrate_devices(sqlite_conn, pg_conn):
    """迁移设备数据"""
    logger.info("开始迁移设备数据...")
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    sqlite_cursor.execute("SELECT * FROM devices")
    devices = sqlite_cursor.fetchall()
    
    # 准备数据
    device_data = []
    for device in devices:
        device_data.append((
            device[1],  # uuid
            device[2],  # mount_path
            device[3],  # label
            device[4],  # first_seen
            device[5],  # last_seen
            'migration',  # system_id
            datetime.now()  # last_sync
        ))
    
    # 批量插入
    execute_values(
        pg_cursor,
        """
        INSERT INTO devices (uuid, mount_path, label, first_seen, last_seen, system_id, last_sync)
        VALUES %s
        ON CONFLICT (uuid) DO UPDATE SET
            mount_path = EXCLUDED.mount_path,
            label = EXCLUDED.label,
            last_seen = EXCLUDED.last_seen,
            last_sync = EXCLUDED.last_sync
        """,
        device_data
    )
    
    pg_conn.commit()
    logger.info(f"完成设备数据迁移，共 {len(devices)} 条记录")

def migrate_files(sqlite_conn, pg_conn):
    """迁移文件数据"""
    logger.info("开始迁移文件数据...")
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    sqlite_cursor.execute("SELECT * FROM files")
    files = sqlite_cursor.fetchall()
    
    # 准备数据
    file_data = []
    for file in files:
        file_data.append((
            file[1],  # device_uuid
            file[2],  # path
            file[3],  # hash
            file[4],  # size
            file[5],  # modified_time
            file[6],  # scanned_time
            'migration',  # system_id
            datetime.now()  # last_sync
        ))
    
    # 批量插入
    execute_values(
        pg_cursor,
        """
        INSERT INTO files (device_uuid, path, hash, size, modified_time, scanned_time, system_id, last_sync)
        VALUES %s
        ON CONFLICT (device_uuid, path) DO UPDATE SET
            hash = EXCLUDED.hash,
            size = EXCLUDED.size,
            modified_time = EXCLUDED.modified_time,
            scanned_time = EXCLUDED.scanned_time,
            last_sync = EXCLUDED.last_sync
        """,
        file_data
    )
    
    pg_conn.commit()
    logger.info(f"完成文件数据迁移，共 {len(files)} 条记录")

def migrate_scan_progress(sqlite_conn, pg_conn):
    """迁移扫描进度数据"""
    logger.info("开始迁移扫描进度数据...")
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    sqlite_cursor.execute("SELECT * FROM scan_progress")
    progresses = sqlite_cursor.fetchall()
    
    # 准备数据
    progress_data = []
    for progress in progresses:
        progress_data.append((
            progress[1],  # device_uuid
            progress[2],  # total_files
            progress[3],  # new_files
            progress[4],  # last_updated
            'migration',  # system_id
            datetime.now()  # last_sync
        ))
    
    # 批量插入
    execute_values(
        pg_cursor,
        """
        INSERT INTO scan_progress (device_uuid, total_files, new_files, last_updated, system_id, last_sync)
        VALUES %s
        ON CONFLICT (device_uuid) DO UPDATE SET
            total_files = EXCLUDED.total_files,
            new_files = EXCLUDED.new_files,
            last_updated = EXCLUDED.last_updated,
            last_sync = EXCLUDED.last_sync
        """,
        progress_data
    )
    
    pg_conn.commit()
    logger.info(f"完成扫描进度数据迁移，共 {len(progresses)} 条记录")

def migrate_image_analysis(sqlite_conn, pg_conn):
    """迁移图像分析数据"""
    logger.info("开始迁移图像分析数据...")
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    sqlite_cursor.execute("SELECT * FROM image_analysis")
    analyses = sqlite_cursor.fetchall()
    
    # 准备数据
    analysis_data = []
    for analysis in analyses:
        analysis_data.append((
            analysis[1],  # file_id
            analysis[2],  # camera_model
            analysis[3],  # taken_time
            analysis[4],  # gps_lat
            analysis[5],  # gps_lon
            bool(analysis[6]),  # has_faces
            analysis[7],  # objects
            analysis[8],  # analyzed_time
            'migration',  # system_id
            datetime.now()  # last_sync
        ))
    
    # 批量插入
    execute_values(
        pg_cursor,
        """
        INSERT INTO image_analysis (file_id, camera_model, taken_time, gps_lat, gps_lon, has_faces, objects, analyzed_time, system_id, last_sync)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            camera_model = EXCLUDED.camera_model,
            taken_time = EXCLUDED.taken_time,
            gps_lat = EXCLUDED.gps_lat,
            gps_lon = EXCLUDED.gps_lon,
            has_faces = EXCLUDED.has_faces,
            objects = EXCLUDED.objects,
            analyzed_time = EXCLUDED.analyzed_time,
            last_sync = EXCLUDED.last_sync
        """,
        analysis_data
    )
    
    pg_conn.commit()
    logger.info(f"完成图像分析数据迁移，共 {len(analyses)} 条记录")

def main():
    """主函数"""
    start_time = time.time()
    logger.info("开始数据迁移...")
    
    # 确保配置已加载
    config = get_config()
    logger.info(f"使用配置: {config}")
    
    # 获取系统ID
    system_id = config.get('system.id', f"{platform.system()}-{platform.node()}")
    logger.info(f"系统ID: {system_id}")
    
    try:
        # 获取连接
        sqlite_conn = get_sqlite_connection()
        pg_conn = get_postgres_connection()
        
        # 创建表结构
        create_postgres_tables(pg_conn)
        
        # 迁移数据
        migrate_devices(sqlite_conn, pg_conn)
        migrate_files(sqlite_conn, pg_conn)
        migrate_scan_progress(sqlite_conn, pg_conn)
        migrate_image_analysis(sqlite_conn, pg_conn)
        
        # 关闭连接
        sqlite_conn.close()
        pg_conn.close()
        
        elapsed = time.time() - start_time
        logger.info(f"数据迁移完成，耗时: {elapsed:.2f} 秒")
        
    except Exception as e:
        logger.error(f"数据迁移失败: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 