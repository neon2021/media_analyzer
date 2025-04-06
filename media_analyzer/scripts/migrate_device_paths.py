#!/usr/bin/env python3
"""
迁移脚本：将旧的绝对路径格式的文件数据更新为新的相对路径格式，并添加system_id

此脚本用于处理从SQLite迁移到PostgreSQL但尚未适配多系统支持的数据。
主要功能：
1. 为每个设备记录添加system_id
2. 将system_id为'migration'的记录更新为当前系统ID
3. 将文件表中的绝对路径转换为相对路径
4. 为文件记录添加system_id
"""

"""
## 数据迁移

如果你有从旧版本迁移的数据需要适配多系统环境，可以使用迁移脚本将旧的绝对路径格式转换为新的相对路径格式，并添加system_id。

### 迁移从SQLite导入的数据

对于从SQLite迁移到PostgreSQL但尚未适配多系统支持的数据，使用以下命令：

```bash
# 先检查将要执行的更改，不实际修改数据库
python media_analyzer/scripts/migrate_device_paths.py --dry-run

# 确认无误后，执行实际迁移
python media_analyzer/scripts/migrate_device_paths.py

# 指定系统ID和配置文件（可选）
python media_analyzer/scripts/migrate_device_paths.py --system-id="macos-mycomputer" --config=config/my-config.yaml

# 非交互模式，自动处理所有设备
python media_analyzer/scripts/migrate_device_paths.py --non-interactive
```

迁移脚本将执行以下操作：
1. 为设备表添加system_id字段并更新现有记录
2. 将system_id为NULL或'migration'的设备记录更新为当前系统ID
3. 将文件表中的system_id为NULL或'migration'的记录更新为当前系统ID
4. 将文件表中的绝对路径转换为相对路径（如果当前是绝对路径）
5. 更新唯一约束，从单一uuid约束改为(uuid, system_id)联合约束
6. 更新文件表约束，从(device_uuid, path)改为(device_uuid, path, system_id)

迁移脚本会在执行实际更改前先显示样本文件的转换预览，包括：
- 当前路径（绝对或相对）
- 转换后的相对路径
- 系统ID的变化（从'migration'或NULL到当前系统ID）
- 转换状态（可转换、已是相对路径或错误）

迁移完成后，可以使用show_db_tables.py脚本查看结果：

```bash
python media_analyzer/scripts/show_db_tables.py --system your-system-id
```

## 注意事项

- 确保你的外接设备在每次连接时挂载到相同的路径
- 数据库迁移前建议先备份现有数据
- 对于多系统环境，每个系统应使用唯一的system_id
- 从SQLite迁移的数据通常会有system_id为'migration'的记录，迁移脚本会将其更新为当前系统ID
"""

import os
import sys
import argparse
import logging
import psycopg2
from datetime import datetime
from pathlib import Path
from tabulate import tabulate

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from media_analyzer.utils.config_manager import get_config
from media_analyzer.utils.path_converter import PathConverter

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

def update_device_table(conn, system_id):
    """更新设备表，添加system_id，并将'migration'记录更新为当前系统ID"""
    cursor = conn.cursor()
    
    # 检查是否已有system_id字段
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='devices' AND column_name='system_id';
    """)
    has_system_id = cursor.fetchone() is not None
    
    if not has_system_id:
        logger.info("添加system_id字段到devices表...")
        cursor.execute("ALTER TABLE devices ADD COLUMN system_id VARCHAR(50)")
        logger.info("成功添加system_id字段到devices表")
    
    # 更新system_id为NULL或空的记录
    cursor.execute("""
        UPDATE devices
        SET system_id = %s
        WHERE system_id IS NULL OR system_id = '';
    """, (system_id,))
    
    null_updated_rows = cursor.rowcount
    logger.info(f"更新了 {null_updated_rows} 个system_id为NULL的设备记录")
    
    # 更新system_id为'migration'的记录
    cursor.execute("""
        UPDATE devices
        SET system_id = %s
        WHERE system_id = 'migration';
    """, (system_id,))
    
    migration_updated_rows = cursor.rowcount
    logger.info(f"更新了 {migration_updated_rows} 个system_id为'migration'的设备记录")
    
    total_updated = null_updated_rows + migration_updated_rows
    logger.info(f"总计更新了 {total_updated} 个设备记录的system_id为 {system_id}")
    
    # 添加唯一约束（如果需要）
    cursor.execute("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name='devices' AND constraint_type='UNIQUE' 
            AND constraint_name LIKE '%uuid%system_id%';
    """)
    has_unique_constraint = cursor.fetchone() is not None
    
    if not has_unique_constraint:
        # 首先删除之前的uuid唯一约束（如果存在）
        cursor.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name='devices' AND constraint_type='UNIQUE' 
                AND constraint_name LIKE '%uuid%';
        """)
        old_constraint = cursor.fetchone()
        if old_constraint:
            constraint_name = old_constraint[0]
            logger.info(f"删除旧的唯一约束: {constraint_name}")
            cursor.execute(f"ALTER TABLE devices DROP CONSTRAINT {constraint_name}")
        
        logger.info("添加(uuid, system_id)联合唯一约束到devices表...")
        # 检查是否有重复记录
        cursor.execute("""
            SELECT uuid, system_id, COUNT(*)
            FROM devices
            GROUP BY uuid, system_id
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        if duplicates:
            logger.warning(f"发现 {len(duplicates)} 组重复的(uuid, system_id)记录，需要手动处理")
            for uuid, sid, count in duplicates:
                logger.warning(f"UUID: {uuid}, system_id: {sid}, 数量: {count}")
        else:
            try:
                cursor.execute("ALTER TABLE devices ADD CONSTRAINT devices_uuid_system_id_key UNIQUE (uuid, system_id)")
                logger.info("成功添加(uuid, system_id)联合唯一约束")
            except psycopg2.Error as e:
                logger.error(f"添加唯一约束失败: {e}")
    
    conn.commit()
    cursor.close()

def update_files_table(conn, system_id, interactive=True, dry_run=False):
    """更新文件表，转换绝对路径为相对路径，并添加system_id"""
    cursor = conn.cursor()
    
    # 检查是否已有system_id字段
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='files' AND column_name='system_id';
    """)
    has_system_id = cursor.fetchone() is not None
    
    if not has_system_id:
        logger.info("添加system_id字段到files表...")
        cursor.execute("ALTER TABLE files ADD COLUMN system_id VARCHAR(50)")
        logger.info("成功添加system_id字段到files表")
    
    # 更新system_id为'migration'的记录
    if not dry_run:
        cursor.execute("""
            UPDATE files
            SET system_id = %s
            WHERE system_id = 'migration';
        """, (system_id,))
        
        migration_updated = cursor.rowcount
        logger.info(f"更新了 {migration_updated} 个system_id为'migration'的文件记录")
    
    # 查询所有设备记录
    cursor.execute("""
        SELECT id, uuid, mount_path 
        FROM devices 
        WHERE system_id = %s
    """, (system_id,))
    devices = cursor.fetchall()
    logger.info(f"找到 {len(devices)} 个设备记录")
    
    total_files = 0
    updated_files = 0
    skipped_files = 0
    
    # 处理每个设备
    for device_id, device_uuid, mount_path in devices:
        # 查询该设备的所有文件，包括system_id为NULL或空的，以及等于'migration'的
        cursor.execute("""
            SELECT id, path, system_id 
            FROM files 
            WHERE device_uuid = %s AND (
                system_id IS NULL OR 
                system_id = '' OR 
                system_id = 'migration'
            )
        """, (device_uuid,))
        files = cursor.fetchall()
        total_files += len(files)
        
        if not files:
            logger.info(f"设备 {device_uuid} 没有需要更新的文件记录")
            continue
        
        logger.info(f"设备 {device_uuid} 有 {len(files)} 个文件记录需要处理")
        
        # 仅显示前10个文件（用于确认）
        sample_files = files[:10]
        formatted_samples = []
        for file_id, file_path, file_system_id in sample_files:
            try:
                # 判断是否是绝对路径
                is_absolute = os.path.isabs(file_path)
                
                if is_absolute:
                    # 尝试从绝对路径提取相对路径
                    rel_path = PathConverter.get_relative_path(file_path, mount_path)
                    status = "可转换 (绝对->相对)"
                else:
                    # 已经是相对路径，不需要转换
                    rel_path = file_path
                    status = "已是相对路径"
                
                # 显示system_id的变化
                system_id_change = f"{file_system_id or 'NULL'} -> {system_id}" if file_system_id != system_id else file_system_id
                
            except Exception as e:
                rel_path = "无法转换"
                status = f"错误: {str(e)}"
                system_id_change = f"{file_system_id or 'NULL'} -> {system_id}" if file_system_id != system_id else file_system_id
            
            formatted_samples.append([file_id, file_path, mount_path, rel_path, system_id_change, status])
        
        print("\n样本文件路径转换结果:")
        headers = ["文件ID", "当前路径", "设备挂载点", "转换后相对路径", "系统ID变化", "状态"]
        print(tabulate(formatted_samples, headers=headers, tablefmt="pretty"))
        
        if interactive:
            confirm = input(f"\n是否处理设备 {device_uuid} 的 {len(files)} 个文件? (y/n): ")
            if confirm.lower() != 'y':
                logger.info(f"跳过设备 {device_uuid} 的文件处理")
                skipped_files += len(files)
                continue
        
        # 处理文件路径
        device_updated = 0
        device_errors = 0
        
        for file_id, file_path, file_system_id in files:
            try:
                # 判断是否是绝对路径
                is_absolute = os.path.isabs(file_path)
                
                if is_absolute:
                    # 从绝对路径提取相对路径
                    rel_path = PathConverter.get_relative_path(file_path, mount_path)
                else:
                    # 已经是相对路径，不需要转换
                    rel_path = file_path
                
                # 更新文件记录
                if not dry_run:
                    cursor.execute("""
                        UPDATE files
                        SET path = %s, system_id = %s
                        WHERE id = %s
                    """, (rel_path, system_id, file_id))
                
                device_updated += 1
            except Exception as e:
                logger.error(f"处理文件ID {file_id} 失败: {e}")
                device_errors += 1
        
        if device_errors > 0:
            logger.warning(f"设备 {device_uuid} 有 {device_errors} 个文件处理失败")
        
        logger.info(f"设备 {device_uuid} 更新了 {device_updated} 个文件记录" + (" (dry run)" if dry_run else ""))
        updated_files += device_updated
    
    # 添加唯一约束（如果需要）
    if not dry_run:
        cursor.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name='files' AND constraint_type='UNIQUE' 
                AND constraint_name LIKE '%device_uuid%path%system_id%';
        """)
        has_unique_constraint = cursor.fetchone() is not None
        
        if not has_unique_constraint:
            # 首先删除之前的唯一约束（如果存在）
            cursor.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name='files' AND constraint_type='UNIQUE' 
                    AND constraint_name LIKE '%device_uuid%path%';
            """)
            old_constraint = cursor.fetchone()
            if old_constraint:
                constraint_name = old_constraint[0]
                logger.info(f"删除旧的唯一约束: {constraint_name}")
                cursor.execute(f"ALTER TABLE files DROP CONSTRAINT {constraint_name}")
            
            logger.info("添加(device_uuid, path, system_id)联合唯一约束到files表...")
            # 检查是否有重复记录
            cursor.execute("""
                SELECT device_uuid, path, system_id, COUNT(*)
                FROM files
                GROUP BY device_uuid, path, system_id
                HAVING COUNT(*) > 1
            """)
            duplicates = cursor.fetchall()
            if duplicates:
                logger.warning(f"发现 {len(duplicates)} 组重复的(device_uuid, path, system_id)记录，需要手动处理")
                for duuid, path, sid, count in duplicates:
                    logger.warning(f"设备UUID: {duuid}, 路径: {path}, 系统ID: {sid}, 数量: {count}")
            else:
                try:
                    cursor.execute("ALTER TABLE files ADD CONSTRAINT files_device_uuid_path_system_id_key UNIQUE (device_uuid, path, system_id)")
                    logger.info("成功添加(device_uuid, path, system_id)联合唯一约束")
                except psycopg2.Error as e:
                    logger.error(f"添加唯一约束失败: {e}")
    
    # 更新system_id为NULL的记录
    if not dry_run:
        cursor.execute("""
            UPDATE files
            SET system_id = %s
            WHERE system_id IS NULL OR system_id = '';
        """, (system_id,))
        
        null_updated = cursor.rowcount
        logger.info(f"更新了 {null_updated} 个system_id为NULL的文件记录")
    
    if not dry_run:
        conn.commit()
    cursor.close()
    
    logger.info(f"总计: {total_files} 个文件记录")
    logger.info(f"已更新: {updated_files} 个文件记录" + (" (dry run)" if dry_run else ""))
    logger.info(f"已跳过: {skipped_files} 个文件记录")
    
    return updated_files

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="迁移旧数据到新的数据库结构")
    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--system-id', type=str, help='系统ID，默认使用配置中的system.id或主机名')
    parser.add_argument('--non-interactive', action='store_true', help='非交互模式，自动处理所有设备')
    parser.add_argument('--dry-run', action='store_true', help='仅显示将要执行的操作，不实际修改数据库')
    args = parser.parse_args()
    
    # 加载配置
    config = get_config()
    if args.config:
        config.load_config(args.config)
    
    # 获取系统ID
    system_id = args.system_id
    if not system_id:
        system_id = config.get('system.id')
    
    if not system_id:
        # 使用主机名作为默认系统ID
        import platform
        system_name = platform.system().lower()
        hostname = platform.node()
        system_id = f"{system_name}-{hostname}"
    
    logger.info(f"使用系统ID: {system_id}")
    
    interactive = not args.non_interactive
    dry_run = args.dry_run
    
    if dry_run:
        logger.info("运行在dry-run模式，不会实际修改数据库")
    
    try:
        # 连接到数据库
        conn = get_postgres_connection(config)
        
        # 更新设备表
        if not dry_run:
            update_device_table(conn, system_id)
        else:
            logger.info("[DRY RUN] 将更新设备表，添加system_id并更新'migration'记录")
        
        # 更新文件表
        updated_files = update_files_table(conn, system_id, interactive, dry_run)
        
        # 输出结果统计
        if updated_files > 0 and not dry_run:
            logger.info(f"成功更新了 {updated_files} 个文件记录")
            logger.info("您可以使用以下命令检查数据库更新结果:")
            logger.info(f"python media_analyzer/scripts/show_db_tables.py --system {system_id}")
        
        # 关闭连接
        conn.close()
        
    except Exception as e:
        logger.error(f"错误: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main()) 