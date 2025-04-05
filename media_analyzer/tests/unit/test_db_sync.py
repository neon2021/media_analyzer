import unittest
import sys
import os
import psycopg2
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import platform
import argparse

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from media_analyzer.db.db_sync_manager import DatabaseSyncManager
from media_analyzer.utils.config_manager import get_config, ConfigManager

# 在测试开始前解析参数并加载测试配置
def setup_test_environment():
    parser = argparse.ArgumentParser(description="数据库同步测试")
    parser.add_argument('--config', type=str, help='配置文件路径', default='config/config-media-analyzer-test.yaml')
    args, unknown = parser.parse_known_args()
    
    # 将未知参数还给sys.argv
    sys.argv = [sys.argv[0]] + unknown
    
    if args.config and os.path.exists(args.config):
        print(f"使用测试配置文件: {args.config}")
        config = get_config()
        config.load_config(args.config)
    else:
        print(f"警告: 找不到测试配置文件 {args.config}")

# 在导入模块时设置测试环境
setup_test_environment()

class TestDatabaseSyncManager(unittest.TestCase):
    def setUp(self):
        """测试前的准备工作"""
        # 从配置获取系统ID，而不是自动生成
        config = get_config()
        self.sync_manager = DatabaseSyncManager()
        self.test_system_id = config.get('system.id', 'test-system')
        print(f"Using system ID for tests: {self.test_system_id}")
        
        # 从配置管理器获取PostgreSQL连接设置
        db_name = config.get('database.postgres.database', 'media_analyzer')
        username = config.get('database.postgres.username', 'postgres')
        password = config.get('database.postgres.password', 'postgres')
        host = config.get('database.postgres.host', 'localhost')
        port = config.get('database.postgres.port', 5432)
        
        # 创建测试数据库连接
        try:
            self.test_conn = psycopg2.connect(
                dbname=db_name,
                user=username,
                password=password,
                host=host,
                port=port
            )
            self.test_cursor = self.test_conn.cursor()
            
            # 创建测试表
            self._create_test_tables()
        except Exception as e:
            print(f"连接到测试数据库失败: {e}")
            self.skipTest(f"无法连接到测试数据库: {e}")
        
    def tearDown(self):
        """测试后的清理工作"""
        if hasattr(self, 'test_conn') and self.test_conn:
            try:
                self._drop_test_tables()
                self.test_cursor.close()
                self.test_conn.close()
            except Exception as e:
                print(f"清理测试环境失败: {e}")
        
    def _create_test_tables(self):
        """创建测试表"""
        self.test_cursor.execute("""
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
        
        self.test_cursor.execute("""
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
        
        self.test_conn.commit()
        
    def _drop_test_tables(self):
        """删除测试表"""
        self.test_cursor.execute("DROP TABLE IF EXISTS devices CASCADE")
        self.test_cursor.execute("DROP TABLE IF EXISTS files CASCADE")
        self.test_conn.commit()
        
    @patch('media_analyzer.db.db_sync_manager.psycopg2.connect')
    def test_connect(self, mock_connect):
        """测试数据库连接"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        self.sync_manager.connect()
        
        mock_connect.assert_called_once()
        self.assertEqual(self.sync_manager.conn, mock_conn)
        self.assertEqual(self.sync_manager.cursor, mock_conn.cursor())
        
    def test_sync_devices(self):
        """测试设备数据同步"""
        # 检查是否有可用的连接
        if not hasattr(self, 'test_conn') or not self.test_conn:
            self.skipTest("数据库连接不可用")
            
        # 插入测试数据
        test_device = (
            'test-uuid',
            '/test/mount/path',
            'Test Device',
            datetime.now(),
            datetime.now(),
            'other-system',
            datetime.now() - timedelta(minutes=10),
            True
        )
        
        self.test_cursor.execute("""
            INSERT INTO devices (uuid, mount_path, label, first_seen, last_seen, system_id, last_sync, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, test_device)
        self.test_conn.commit()
        
        # 模拟数据库连接
        self.sync_manager.conn = self.test_conn
        self.sync_manager.cursor = self.test_cursor
        self.sync_manager.last_sync_time = datetime.now() - timedelta(minutes=5)
        
        # 模拟设备检查
        with patch.object(self.sync_manager, '_check_device_exists', return_value=True):
            self.sync_manager.sync_devices()
            
        # 验证结果
        self.test_cursor.execute("SELECT system_id, last_sync FROM devices WHERE uuid = %s", ('test-uuid',))
        result = self.test_cursor.fetchone()
        self.assertEqual(result[0], self.test_system_id)
        self.assertGreater(result[1], self.sync_manager.last_sync_time)
        
    def test_sync_files(self):
        """测试文件数据同步"""
        # 检查是否有可用的连接
        if not hasattr(self, 'test_conn') or not self.test_conn:
            self.skipTest("数据库连接不可用")
            
        # 插入测试数据
        test_file = (
            'test-uuid',
            '/test/file/path',
            'test-hash',
            1024,
            datetime.now(),
            datetime.now(),
            'other-system',
            datetime.now() - timedelta(minutes=10)
        )
        
        self.test_cursor.execute("""
            INSERT INTO files (device_uuid, path, hash, size, modified_time, scanned_time, system_id, last_sync)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, test_file)
        self.test_conn.commit()
        
        # 模拟数据库连接
        self.sync_manager.conn = self.test_conn
        self.sync_manager.cursor = self.test_cursor
        self.sync_manager.last_sync_time = datetime.now() - timedelta(minutes=5)
        
        # 模拟文件检查
        with patch.object(self.sync_manager, '_check_file_exists', return_value=True):
            self.sync_manager.sync_files()
            
        # 验证结果
        self.test_cursor.execute("""
            SELECT system_id, last_sync 
            FROM files 
            WHERE device_uuid = %s AND path = %s
        """, ('test-uuid', '/test/file/path'))
        result = self.test_cursor.fetchone()
        self.assertEqual(result[0], self.test_system_id)
        self.assertGreater(result[1], self.sync_manager.last_sync_time)
        
    def test_device_conflict_resolution(self):
        """测试设备冲突解决"""
        # 检查是否有可用的连接
        if not hasattr(self, 'test_conn') or not self.test_conn:
            self.skipTest("数据库连接不可用")
            
        # 插入两个系统的设备数据
        device1 = (
            'test-uuid',
            '/test/mount/path1',
            'Test Device 1',
            datetime.now(),
            datetime.now(),
            'system1',
            datetime.now() - timedelta(minutes=10),
            True
        )
        
        device2 = (
            'test-uuid',
            '/test/mount/path2',
            'Test Device 2',
            datetime.now(),
            datetime.now(),
            'system2',
            datetime.now() - timedelta(minutes=5),
            True
        )
        
        self.test_cursor.execute("""
            INSERT INTO devices (uuid, mount_path, label, first_seen, last_seen, system_id, last_sync, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, device1)
        
        self.test_cursor.execute("""
            INSERT INTO devices (uuid, mount_path, label, first_seen, last_seen, system_id, last_sync, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (uuid) DO UPDATE SET
                mount_path = EXCLUDED.mount_path,
                label = EXCLUDED.label,
                last_seen = EXCLUDED.last_seen,
                system_id = EXCLUDED.system_id,
                last_sync = EXCLUDED.last_sync
        """, device2)
        
        self.test_conn.commit()
        
        # 模拟数据库连接
        self.sync_manager.conn = self.test_conn
        self.sync_manager.cursor = self.test_cursor
        self.sync_manager.last_sync_time = datetime.now() - timedelta(minutes=5)
        
        # 模拟设备检查
        with patch.object(self.sync_manager, '_check_device_exists', return_value=True):
            self.sync_manager.sync_devices()
            
        # 验证结果
        self.test_cursor.execute("SELECT system_id, mount_path FROM devices WHERE uuid = %s", ('test-uuid',))
        result = self.test_cursor.fetchone()
        self.assertEqual(result[0], self.test_system_id)
        
    def test_file_conflict_resolution(self):
        """测试文件冲突解决"""
        # 检查是否有可用的连接
        if not hasattr(self, 'test_conn') or not self.test_conn:
            self.skipTest("数据库连接不可用")
            
        # 插入两个系统的文件数据
        file1 = (
            'test-uuid',
            '/test/file/path',
            'hash1',
            1024,
            datetime.now(),
            datetime.now(),
            'system1',
            datetime.now() - timedelta(minutes=10)
        )
        
        file2 = (
            'test-uuid',
            '/test/file/path',
            'hash2',
            2048,
            datetime.now(),
            datetime.now(),
            'system2',
            datetime.now() - timedelta(minutes=5)
        )
        
        self.test_cursor.execute("""
            INSERT INTO files (device_uuid, path, hash, size, modified_time, scanned_time, system_id, last_sync)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, file1)
        
        self.test_cursor.execute("""
            INSERT INTO files (device_uuid, path, hash, size, modified_time, scanned_time, system_id, last_sync)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (device_uuid, path) DO UPDATE SET
                hash = EXCLUDED.hash,
                size = EXCLUDED.size,
                modified_time = EXCLUDED.modified_time,
                scanned_time = EXCLUDED.scanned_time,
                system_id = EXCLUDED.system_id,
                last_sync = EXCLUDED.last_sync
        """, file2)
        
        self.test_conn.commit()
        
        # 模拟数据库连接
        self.sync_manager.conn = self.test_conn
        self.sync_manager.cursor = self.test_cursor
        self.sync_manager.last_sync_time = datetime.now() - timedelta(minutes=5)
        
        # 模拟文件检查
        with patch.object(self.sync_manager, '_check_file_exists', return_value=True):
            self.sync_manager.sync_files()
            
        # 验证结果
        self.test_cursor.execute("""
            SELECT system_id, hash, size 
            FROM files 
            WHERE device_uuid = %s AND path = %s
        """, ('test-uuid', '/test/file/path'))
        result = self.test_cursor.fetchone()
        self.assertEqual(result[0], self.test_system_id)
        
    def test_sync_loop(self):
        """测试同步循环"""
        with patch.object(self.sync_manager, 'sync_all') as mock_sync:
            with patch('time.sleep') as mock_sleep:
                # 模拟 KeyboardInterrupt
                mock_sleep.side_effect = KeyboardInterrupt()
                
                self.sync_manager.start_sync_loop(interval=1)
                
                mock_sync.assert_called()
                mock_sleep.assert_called_with(1)
                
if __name__ == '__main__':
    unittest.main() 