import unittest
import os
import sys
import tempfile
import psycopg2
import argparse
import logging
import hashlib
from datetime import datetime
from pathlib import Path
import shutil
from tabulate import tabulate

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from media_analyzer.utils.config_manager import get_config
from media_analyzer.utils.path_converter import PathConverter
from media_analyzer.core.file_scanner import calculate_file_hash

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 在测试开始前解析参数并加载测试配置
def setup_test_environment():
    parser = argparse.ArgumentParser(description="文件扫描与PostgreSQL存储测试")
    parser.add_argument('--config', type=str, help='配置文件路径', default='config/config-media-analyzer-test.yaml')
    parser.add_argument('--real_scan_dir', type=str, help='真实扫描目录（可选）')
    parser.add_argument('--keep_tables', action='store_true', help='保留测试表（不删除）')
    args, unknown = parser.parse_known_args()
    
    # 将未知参数还给sys.argv
    sys.argv = [sys.argv[0]] + unknown
    
    # 加载配置
    if args.config and os.path.exists(args.config):
        print(f"使用测试配置文件: {args.config}")
        config = get_config()
        config.load_config(args.config)
    else:
        print(f"警告: 找不到测试配置文件 {args.config}")
    
    return args.real_scan_dir, args.keep_tables

# 在导入模块时设置测试环境并获取命令行参数
REAL_SCAN_DIR, KEEP_TABLES = setup_test_environment()

class TestFileScanPostgres(unittest.TestCase):
    """测试文件扫描并存储到PostgreSQL"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 获取配置
        self.config = get_config()
        
        # 使用真实扫描目录或创建临时目录
        if REAL_SCAN_DIR and os.path.isdir(REAL_SCAN_DIR):
            self.temp_dir = REAL_SCAN_DIR
            self.using_real_dir = True
            logger.info(f"使用真实目录进行扫描: {self.temp_dir}")
            
            # 查找真实目录中的不超过3个媒体文件
            self.test_files = []
            supported_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.mp4', '.mov', '.avi']
            
            for root, _, files in os.walk(self.temp_dir):
                if len(self.test_files) >= 3:
                    break
                    
                for file in files:
                    if len(self.test_files) >= 3:
                        break
                        
                    _, ext = os.path.splitext(file)
                    if ext.lower() in supported_extensions:
                        file_path = os.path.join(root, file)
                        self.test_files.append(file_path)
                        logger.info(f"添加真实测试文件: {file_path}")
            
            if not self.test_files:
                logger.warning(f"在{self.temp_dir}中未找到媒体文件，将使用临时文件")
                self.using_real_dir = False
                self._create_temp_dir_and_files()
        else:
            self.using_real_dir = False
            self._create_temp_dir_and_files()
        
        # 生成设备UUID（使用目录路径的哈希）
        self.device_uuid = "test_" + hashlib.md5(self.temp_dir.encode()).hexdigest()[:12]
        logger.info(f"测试设备UUID: {self.device_uuid}")
        
        # 从配置管理器获取PostgreSQL连接设置
        db_name = self.config.get('database.postgres.database', 'media_analyzer_test')
        username = self.config.get('database.postgres.username', 'postgres')
        password = self.config.get('database.postgres.password', 'postgres')
        host = self.config.get('database.postgres.host', 'localhost')
        port = self.config.get('database.postgres.port', 5432)
        
        self.system_id = self.config.get('system.id', 'test-system')
        logger.info(f"使用系统ID: {self.system_id}")
        
        # 创建测试数据库连接
        try:
            self.conn = psycopg2.connect(
                dbname=db_name,
                user=username,
                password=password,
                host=host,
                port=port
            )
            self.cursor = self.conn.cursor()
            
            # 创建测试表
            self._create_test_tables()
            
            # 创建设备记录
            self._create_device_record()
            
        except Exception as e:
            logger.error(f"连接到测试数据库失败: {e}")
            self.skipTest(f"无法连接到测试数据库: {e}")
    
    def _create_temp_dir_and_files(self):
        """创建临时目录和测试文件"""
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"创建临时目录作为模拟设备: {self.temp_dir}")
        
        # 创建测试文件
        self.test_files = []
        for i in range(3):
            # 创建子目录
            subdir = os.path.join(self.temp_dir, f"subdir_{i}")
            os.makedirs(subdir, exist_ok=True)
            
            # 在子目录中创建测试文件
            file_path = os.path.join(subdir, f"test_file_{i}.jpg")
            with open(file_path, 'w') as f:
                f.write(f"This is test file {i}")
            self.test_files.append(file_path)
            logger.info(f"创建测试文件: {file_path}")
    
    def tearDown(self):
        """测试后的清理工作"""
        # 清理临时目录（如果使用的是临时目录）
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir) and not self.using_real_dir:
            shutil.rmtree(self.temp_dir)
            logger.info(f"清理临时目录: {self.temp_dir}")
        
        # 清理数据库记录（除非指定了保留）
        if hasattr(self, 'conn') and self.conn:
            try:
                # 如果指定了保留表，则不删除表
                if not KEEP_TABLES:
                    self._drop_test_tables()
                else:
                    logger.info("保留测试表供后续使用")
                    
                self.cursor.close()
                self.conn.close()
                logger.info("关闭数据库连接")
            except Exception as e:
                logger.error(f"清理测试环境失败: {e}")
    
    def _create_test_tables(self):
        """创建测试表"""
        # 1. 创建devices表，添加(uuid, system_id)联合唯一约束
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id SERIAL PRIMARY KEY,
                uuid VARCHAR(36) NOT NULL,
                mount_path TEXT NOT NULL,
                label TEXT,
                first_seen TIMESTAMP,
                last_seen TIMESTAMP,
                system_id VARCHAR(50) NOT NULL,
                last_sync TIMESTAMP,
                is_active BOOLEAN DEFAULT true,
                UNIQUE (uuid, system_id)
            )
        """)
        
        self.cursor.execute("""
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
                UNIQUE(device_uuid, path, system_id)
            )
        """)
        
        self.conn.commit()
        logger.info("创建测试表完成")
    
    def _drop_test_tables(self):
        """删除测试表"""
        self.cursor.execute("DROP TABLE IF EXISTS files CASCADE")
        self.cursor.execute("DROP TABLE IF EXISTS devices CASCADE")
        self.conn.commit()
        logger.info("删除测试表完成")
    
    def _create_device_record(self):
        """创建设备记录"""
        self.cursor.execute("""
            INSERT INTO devices (uuid, mount_path, label, first_seen, last_seen, system_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (uuid, system_id) DO UPDATE SET
                mount_path = EXCLUDED.mount_path,
                last_seen = EXCLUDED.last_seen
        """, (
            self.device_uuid,
            self.temp_dir,
            "Test Device",
            datetime.now(),
            datetime.now(),
            self.system_id
        ))
        self.conn.commit()
        logger.info(f"创建设备记录: UUID={self.device_uuid}, 挂载点={self.temp_dir}, 系统ID={self.system_id}")
    
    def _print_device_table(self):
        """以表格形式打印设备记录"""
        self.cursor.execute("""
            SELECT id, uuid, mount_path, label, first_seen, last_seen, system_id
            FROM devices
        """)
        rows = self.cursor.fetchall()
        
        headers = ["ID", "UUID", "挂载路径", "标签", "首次发现", "最后发现", "系统ID"]
        print("\n===== 设备表 =====")
        print(tabulate(rows, headers=headers, tablefmt="pretty"))
        print("")
    
    def _print_files_table(self):
        """以表格形式打印文件记录"""
        self.cursor.execute("""
            SELECT id, device_uuid, path, hash, size, modified_time, scanned_time, system_id
            FROM files
            ORDER BY id
        """)
        rows = self.cursor.fetchall()
        
        # 处理长字段的显示
        formatted_rows = []
        for row in rows:
            id, device_uuid, path, hash_value, size, modified_time, scanned_time, system_id = row
            # 截断哈希值以适合表格显示
            if hash_value and len(hash_value) > 10:
                hash_value = hash_value[:10] + "..."
            
            formatted_rows.append([id, device_uuid, path, hash_value, size, modified_time, scanned_time, system_id])
        
        headers = ["ID", "设备UUID", "文件路径", "哈希值", "大小", "修改时间", "扫描时间", "系统ID"]
        print("\n===== 文件表 =====")
        print(tabulate(formatted_rows, headers=headers, tablefmt="pretty"))
        print("")
    
    def test_scan_and_restore_files(self):
        """测试扫描文件、存储到PostgreSQL并还原"""
        logger.info("开始测试扫描文件并还原路径")
        
        # 步骤1: 扫描文件并存储到数据库
        self._scan_files_to_db()
        
        # 步骤2: 打印数据库表内容
        self._print_device_table()
        self._print_files_table()
        
        # 步骤3: 从数据库读取文件路径
        file_records = self._get_files_from_db()
        
        # 步骤4: 验证文件数量
        self.assertEqual(len(file_records), len(self.test_files),
                         f"期望找到{len(self.test_files)}个文件，实际找到{len(file_records)}个")
        logger.info(f"验证文件数量: {len(file_records)}")
        
        # 步骤5: 还原文件路径并验证文件可以打开
        restored_files = []
        for record in file_records:
            file_id, device_uuid, rel_path = record
            
            # 获取挂载点
            mount_point = self._get_device_mount_point(device_uuid)
            self.assertIsNotNone(mount_point, f"设备 {device_uuid} 的挂载点不存在")
            
            # 还原完整路径
            full_path = PathConverter.to_platform_path(rel_path, mount_point)
            logger.info(f"还原文件路径: {full_path}")
            
            # 验证文件存在并可以打开
            self.assertTrue(os.path.exists(full_path), f"文件 {full_path} 不存在")
            
            try:
                with open(full_path, 'rb') as f:
                    # 读取前100字节即可，不必读取整个文件
                    content = f.read(100)
                    content_preview = str(content[:20]) if content else "空文件"
                    logger.info(f"成功打开文件 {full_path}，内容预览: {content_preview}...")
                    
                    # 添加到已还原文件列表
                    file_size = os.path.getsize(full_path)
                    restored_files.append([file_id, rel_path, full_path, file_size, "可打开"])
            except Exception as e:
                self.fail(f"无法打开文件 {full_path}: {e}")
        
        # 打印还原的文件信息表
        headers = ["文件ID", "相对路径", "完整路径", "文件大小", "状态"]
        print("\n===== 已还原文件 =====")
        print(tabulate(restored_files, headers=headers, tablefmt="pretty"))
        print("")
        
        # 如果保留表，输出提示
        if KEEP_TABLES:
            print(f"\n数据库表已保留，可以使用以下命令查看表内容:")
            print(f"python media_analyzer/scripts/show_db_tables.py --config {self.config.get('current_config_file', 'config/config-media-analyzer-test.yaml')}")
            print("")
        
        # 步骤6 (可选): 测试相同设备在不同系统上的情况
        if KEEP_TABLES:
            logger.info("测试相同设备在不同系统上的情况")
            # 使用相同的device_uuid，但不同的system_id
            different_system_id = f"{self.system_id}-different"
            self._test_same_device_different_system(different_system_id)
    
    def _test_same_device_different_system(self, different_system_id):
        """测试相同设备在不同系统上的情况"""
        logger.info(f"创建相同设备在不同系统({different_system_id})上的记录")
        
        # 创建相同设备在不同系统上的记录
        different_mount_path = f"{self.temp_dir}-on-{different_system_id}"
        
        self.cursor.execute("""
            INSERT INTO devices (uuid, mount_path, label, first_seen, last_seen, system_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (uuid, system_id) DO UPDATE SET
                mount_path = EXCLUDED.mount_path,
                last_seen = EXCLUDED.last_seen
        """, (
            self.device_uuid,
            different_mount_path,
            "Test Device on Different System",
            datetime.now(),
            datetime.now(),
            different_system_id
        ))
        self.conn.commit()
        
        # 打印更新后的设备表
        self.cursor.execute("""
            SELECT id, uuid, mount_path, label, first_seen, last_seen, system_id
            FROM devices
            WHERE uuid = %s
            ORDER BY system_id
        """, (self.device_uuid,))
        
        rows = self.cursor.fetchall()
        
        headers = ["ID", "UUID", "挂载路径", "标签", "首次发现", "最后发现", "系统ID"]
        print("\n===== 设备表 (相同设备在不同系统上) =====")
        print(tabulate(rows, headers=headers, tablefmt="pretty"))
        print("")
        
        # 说明结果
        print("可以看到相同UUID的设备在不同system_id上有不同的挂载路径记录")
        print("这使得系统能够正确处理同一设备在不同机器上的情况")
        print("")
    
    def _scan_files_to_db(self):
        """扫描文件并存储到数据库"""
        for file_path in self.test_files:
            # 获取文件相对路径
            rel_path = PathConverter.get_relative_path(file_path, self.temp_dir)
            
            # 获取文件信息
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size
            modified_time = datetime.fromtimestamp(file_stat.st_mtime)
            
            # 计算文件哈希
            file_hash = calculate_file_hash(file_path)
            
            # 存储到数据库
            self.cursor.execute("""
                INSERT INTO files 
                (device_uuid, path, hash, size, modified_time, scanned_time, system_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (device_uuid, path, system_id) DO UPDATE SET
                    hash = EXCLUDED.hash,
                    size = EXCLUDED.size,
                    modified_time = EXCLUDED.modified_time,
                    scanned_time = EXCLUDED.scanned_time
            """, (
                self.device_uuid,
                rel_path,
                file_hash,
                file_size,
                modified_time,
                datetime.now(),
                self.system_id
            ))
            
            logger.info(f"存储文件记录: device_uuid={self.device_uuid}, path={rel_path}, system_id={self.system_id}")
        
        self.conn.commit()
    
    def _get_files_from_db(self):
        """从数据库获取文件记录"""
        self.cursor.execute("""
            SELECT id, device_uuid, path
            FROM files
            WHERE device_uuid = %s AND system_id = %s
        """, (self.device_uuid, self.system_id))
        
        return self.cursor.fetchall()
    
    def _get_device_mount_point(self, device_uuid):
        """获取设备挂载点"""
        self.cursor.execute("""
            SELECT mount_path
            FROM devices
            WHERE uuid = %s AND system_id = %s
        """, (device_uuid, self.system_id))
        
        result = self.cursor.fetchone()
        return result[0] if result else None

if __name__ == '__main__':
    unittest.main() 