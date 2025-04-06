#!/usr/bin/env python3
"""
显示PostgreSQL数据库中的设备和文件表内容
"""

import os
import sys
import argparse
import logging
import psycopg2
from tabulate import tabulate

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from media_analyzer.utils.config_manager import get_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def get_postgres_connection(config):
    """获取PostgreSQL连接"""
    # 获取 PostgreSQL 连接信息
    db_name = config.get('database.postgres.database', 'media_analyzer')
    username = config.get('database.postgres.username', 'postgres')
    password = config.get('database.postgres.password', 'postgres')
    host = config.get('database.postgres.host', 'localhost')
    port = config.get('database.postgres.port', 5432)
    
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

def print_devices_table(conn, limit=None, system_id=None):
    """打印设备表"""
    cursor = conn.cursor()
    
    # 构建查询语句
    if system_id:
        query = """
            SELECT id, uuid, mount_path, label, first_seen, last_seen, system_id, is_active
            FROM devices
            WHERE system_id = %s
            ORDER BY id
        """
        # 添加限制条件
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query, (system_id,))
    else:
        query = """
            SELECT id, uuid, mount_path, label, first_seen, last_seen, system_id, is_active
            FROM devices
            ORDER BY id
        """
        # 添加限制条件
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query)
    
    rows = cursor.fetchall()
    
    if not rows:
        if system_id:
            print(f"设备表中没有系统ID为 {system_id} 的记录")
        else:
            print("设备表中没有记录")
        return
    
    headers = ["ID", "UUID", "挂载路径", "标签", "首次发现", "最后发现", "系统ID", "活跃状态"]
    if system_id:
        print(f"\n===== 设备表 (系统ID: {system_id}) =====")
    else:
        print("\n===== 设备表 =====")
    print(tabulate(rows, headers=headers, tablefmt="pretty"))
    print("")
    
    cursor.close()

def print_files_table(conn, device_uuid=None, system_id=None, limit=10):
    """打印文件表"""
    cursor = conn.cursor()
    
    # 构建查询语句
    if device_uuid and system_id:
        query = """
            SELECT id, device_uuid, path, hash, size, modified_time, scanned_time, system_id
            FROM files
            WHERE device_uuid = %s AND system_id = %s
            ORDER BY id
        """
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query, (device_uuid, system_id))
    elif device_uuid:
        query = """
            SELECT id, device_uuid, path, hash, size, modified_time, scanned_time, system_id
            FROM files
            WHERE device_uuid = %s
            ORDER BY id
        """
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query, (device_uuid,))
    elif system_id:
        query = """
            SELECT id, device_uuid, path, hash, size, modified_time, scanned_time, system_id
            FROM files
            WHERE system_id = %s
            ORDER BY id
        """
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query, (system_id,))
    else:
        query = """
            SELECT id, device_uuid, path, hash, size, modified_time, scanned_time, system_id
            FROM files
            ORDER BY id
        """
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query)
    
    rows = cursor.fetchall()
    
    if not rows:
        if device_uuid and system_id:
            print(f"文件表中没有设备UUID为 {device_uuid} 且系统ID为 {system_id} 的记录")
        elif device_uuid:
            print(f"文件表中没有设备UUID为 {device_uuid} 的记录")
        elif system_id:
            print(f"文件表中没有系统ID为 {system_id} 的记录")
        else:
            print("文件表中没有记录")
        return
    
    # 处理长字段的显示
    formatted_rows = []
    for row in rows:
        id, device_uuid, path, hash_value, size, modified_time, scanned_time, system_id = row
        # 截断哈希值以适合表格显示
        if hash_value and len(hash_value) > 10:
            hash_value = hash_value[:10] + "..."
        
        # 如果路径太长，截断
        if path and len(path) > 40:
            path = path[:37] + "..."
            
        formatted_rows.append([id, device_uuid, path, hash_value, size, modified_time, scanned_time, system_id])
    
    headers = ["ID", "设备UUID", "文件路径", "哈希值", "大小(字节)", "修改时间", "扫描时间", "系统ID"]
    title = "\n===== 文件表"
    if device_uuid:
        title += f" (设备UUID: {device_uuid}"
        if system_id:
            title += f", 系统ID: {system_id}"
        title += ")"
    elif system_id:
        title += f" (系统ID: {system_id})"
    title += " ====="
    print(title)
    print(tabulate(formatted_rows, headers=headers, tablefmt="pretty"))
    print("")
    
    cursor.close()

def print_device_summary(conn, system_id=None):
    """打印设备概要信息"""
    cursor = conn.cursor()
    
    # 查询每个设备的文件数量
    if system_id:
        cursor.execute("""
            SELECT d.id, d.uuid, d.label, d.mount_path, COUNT(f.id) AS file_count, 
                   SUM(f.size) AS total_size, MAX(f.scanned_time) AS last_scan, d.system_id
            FROM devices d
            LEFT JOIN files f ON d.uuid = f.device_uuid AND d.system_id = f.system_id
            WHERE d.system_id = %s
            GROUP BY d.id, d.uuid, d.label, d.mount_path, d.system_id
            ORDER BY d.id
        """, (system_id,))
    else:
        cursor.execute("""
            SELECT d.id, d.uuid, d.label, d.mount_path, COUNT(f.id) AS file_count, 
                   SUM(f.size) AS total_size, MAX(f.scanned_time) AS last_scan, d.system_id
            FROM devices d
            LEFT JOIN files f ON d.uuid = f.device_uuid AND d.system_id = f.system_id
            GROUP BY d.id, d.uuid, d.label, d.mount_path, d.system_id
            ORDER BY d.id
        """)
    
    rows = cursor.fetchall()
    
    if not rows:
        if system_id:
            print(f"设备表中没有系统ID为 {system_id} 的记录")
        else:
            print("设备表中没有记录")
        return
    
    # 格式化数据
    formatted_rows = []
    for row in rows:
        id, uuid, label, mount_path, file_count, total_size, last_scan, device_system_id = row
        
        # 格式化挂载路径
        if mount_path and len(mount_path) > 25:
            mount_path = mount_path[:22] + "..."
        
        # 格式化总大小（转换为MB、GB等）
        if total_size:
            if total_size > 1024 * 1024 * 1024:  # GB
                formatted_size = f"{total_size / (1024 * 1024 * 1024):.2f} GB"
            elif total_size > 1024 * 1024:  # MB
                formatted_size = f"{total_size / (1024 * 1024):.2f} MB"
            elif total_size > 1024:  # KB
                formatted_size = f"{total_size / 1024:.2f} KB"
            else:
                formatted_size = f"{total_size} B"
        else:
            formatted_size = "0 B"
            
        formatted_rows.append([id, uuid, label or "无标签", mount_path, file_count or 0, formatted_size, last_scan or "未扫描", device_system_id])
    
    headers = ["ID", "UUID", "标签", "挂载路径", "文件数量", "总大小", "最后扫描时间", "系统ID"]
    if system_id:
        print(f"\n===== 设备概要 (系统ID: {system_id}) =====")
    else:
        print("\n===== 设备概要 =====")
    print(tabulate(formatted_rows, headers=headers, tablefmt="pretty"))
    print("")
    
    cursor.close()

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="显示PostgreSQL数据库中的设备和文件表内容")
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--device', type=str, help='指定设备UUID查看其文件')
    parser.add_argument('--system', type=str, help='指定系统ID查看其设备和文件')
    parser.add_argument('--limit', type=int, default=10, help='显示记录的最大数量（默认10条）')
    parser.add_argument('--all', action='store_true', help='显示所有记录，不限制数量')
    parser.add_argument('--summary', action='store_true', help='仅显示设备概要信息')
    args = parser.parse_args()
    
    # 加载配置
    config = get_config()
    if args.config:
        config.load_config(args.config)
    
    try:
        # 连接到数据库
        conn = get_postgres_connection(config)
        
        # 显示设备概要或详细信息
        if args.summary:
            print_device_summary(conn, args.system)
        else:
            # 显示设备表
            limit = None if args.all else args.limit
            print_devices_table(conn, limit, args.system)
            
            # 显示文件表
            limit = None if args.all else args.limit
            print_files_table(conn, args.device, args.system, limit)
        
        # 关闭连接
        conn.close()
        
    except Exception as e:
        logger.error(f"错误: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main()) 