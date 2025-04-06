import unittest
from unittest.mock import patch, MagicMock
import os
import io
import logging
from datetime import datetime
from contextlib import redirect_stdout
from media_analyzer.core.update_device_registry import update_device_registry, get_device_mount_point
from media_analyzer.db.db_manager import get_db

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class TestDeviceRegistry(unittest.TestCase):
    """设备注册表更新功能测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 配置日志处理
        self.logger = logging.getLogger('media_analyzer.core.update_device_registry')
        # 保存原始处理器
        self.original_handlers = self.logger.handlers.copy()
        # 清除现有处理器
        self.logger.handlers = []
        # 创建捕获处理器
        self.log_output = io.StringIO()
        handler = logging.StreamHandler(self.log_output)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # 创建测试数据库连接
        self.db_patcher = patch('media_analyzer.core.update_device_registry.get_db')
        self.mock_get_db = self.db_patcher.start()
        
        # 模拟数据库和游标
        self.mock_db = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_db.get_cursor.return_value.__enter__.return_value = self.mock_cursor
        self.mock_get_db.return_value = self.mock_db
        
        # 模拟配置
        self.config_patcher = patch('media_analyzer.core.update_device_registry.get_config')
        self.mock_get_config = self.config_patcher.start()
        self.mock_get_config.return_value = {'system': {'id': 'test-system'}}
        
        # 测试设备数据
        self.test_devices = [
            {
                'uuid': 'test-uuid-1',
                'mount_path': '/Volumes/TestDrive1',
                'label': 'TestDrive1'
            },
            {
                'uuid': 'test-uuid-2',
                'mount_path': '/Volumes/TestDrive2',
                'label': 'TestDrive2'
            }
        ]
    
    def tearDown(self):
        """测试后清理"""
        # 恢复原始日志处理器
        self.logger.handlers = self.original_handlers
        
        self.db_patcher.stop()
        self.config_patcher.stop()
    
    def test_update_device_registry_empty_devices(self):
        """测试空设备列表时的更新行为"""
        result = update_device_registry([])
        
        self.assertEqual(result, 0)
        # 确认数据库操作没有执行
        self.mock_cursor.execute.assert_not_called()
        
        # 检查日志输出
        log_content = self.log_output.getvalue()
        print(f"日志输出: {log_content}")
        self.assertIn("WARNING - 没有检测到设备", log_content)
    
    def test_update_device_registry_new_devices(self):
        """测试添加新设备"""
        # 模拟查询结果为空（设备不存在）
        self.mock_cursor.fetchone.return_value = None
        
        # 执行更新
        result = update_device_registry(self.test_devices)
        
        # 验证结果
        self.assertEqual(result, 2)
        
        # 检查日志输出
        log_content = self.log_output.getvalue()
        print(f"日志输出: {log_content}")
        self.assertIn(f"INFO - 发现 {len(self.test_devices)} 个设备", log_content)
        self.assertIn("INFO - 添加新设备", log_content)
        
        # 验证设备表操作
        # self.assertEqual(self.mock_cursor.execute.call_count, 6)  # 1次创建表 + 2次查询 + 2次插入 + 1次标记不活跃
        
        # 验证创建表调用
        create_table_call = self.mock_cursor.execute.call_args_list[0]
        self.assertIn('CREATE TABLE IF NOT EXISTS device_mount_points', create_table_call[0][0])
        
        # 验证查询调用
        for i, device in enumerate(self.test_devices):
            select_call = self.mock_cursor.execute.call_args_list[i*2+1]
            self.assertIn('SELECT id, mount_path FROM devices WHERE uuid', select_call[0][0])
            self.assertEqual(select_call[0][1][0], device['uuid'])
            
            # 验证插入调用
            insert_call = self.mock_cursor.execute.call_args_list[i*2+2]
            self.assertIn('INSERT INTO devices', insert_call[0][0])
            self.assertEqual(insert_call[0][1][0], device['uuid'])
            self.assertEqual(insert_call[0][1][1], device['mount_path'])
            self.assertEqual(insert_call[0][1][2], device['label'])
    
    def test_update_device_registry_existing_devices(self):
        """测试更新现有设备"""
        # 模拟查询结果（设备存在）
        self.mock_cursor.fetchone.return_value = (1, '/old/path')
        
        # 执行更新
        result = update_device_registry(self.test_devices)
        
        # 验证结果
        self.assertEqual(result, 2)
        
        # 检查日志输出
        log_content = self.log_output.getvalue()
        print(f"日志输出: {log_content}")
        self.assertIn(f"INFO - 发现 {len(self.test_devices)} 个设备", log_content)
        self.assertIn("INFO - 更新设备", log_content)
        
        # 验证设备表操作
        self.assertEqual(self.mock_cursor.execute.call_count, 6)  # 1次创建表 + 2次查询 + 2次更新 + 1次标记不活跃
        
        # 验证更新调用
        for i, device in enumerate(self.test_devices):
            update_call = self.mock_cursor.execute.call_args_list[i*2+2]
            self.assertIn('UPDATE devices', update_call[0][0])
            self.assertEqual(update_call[0][1][0], device['mount_path'])
            self.assertEqual(update_call[0][1][2], device['uuid'])
    
    def test_get_device_mount_point(self):
        """测试获取设备挂载点"""
        # 模拟配置
        config_patcher = patch('media_analyzer.core.update_device_registry.get_config')
        mock_get_config = config_patcher.start()
        mock_get_config.return_value = {'system': {'id': 'test-system'}}
        
        # 模拟数据库连接
        db_patcher = patch('media_analyzer.core.update_device_registry.get_db')
        mock_get_db = db_patcher.start()
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_db.get_cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_db.return_value = mock_db
        
        try:
            # 测试1：从映射表中找到挂载点
            mock_cursor.fetchone.return_value = ('/mount/path',)
            mount_point = get_device_mount_point('test-uuid')
            self.assertEqual(mount_point, '/mount/path')
            
            # 验证调用
            mock_cursor.execute.assert_called_with('''
            SELECT mount_path FROM device_mount_points
            WHERE device_uuid = ? AND system_id = ?
            ORDER BY last_updated DESC
            LIMIT 1
            ''', ('test-uuid', 'test-system'))
            
            # 测试2：从映射表中找不到，但在devices表中找到
            mock_cursor.reset_mock()
            mock_cursor.fetchone.side_effect = [None, ('/devices/path',)]
            mount_point = get_device_mount_point('test-uuid')
            self.assertEqual(mount_point, '/devices/path')
            
            # 验证调用设备表
            self.assertEqual(mock_cursor.execute.call_count, 2)
            second_call = mock_cursor.execute.call_args_list[1]
            self.assertIn('SELECT mount_path FROM devices', second_call[0][0])
            
            # 测试3：完全找不到挂载点
            mock_cursor.reset_mock()
            mock_cursor.fetchone.side_effect = [None, None]
            mount_point = get_device_mount_point('test-uuid')
            self.assertIsNone(mount_point)
            
            # 检查日志输出
            log_content = self.log_output.getvalue()
            print(f"日志输出: {log_content}")
            self.assertIn("WARNING - 设备 (UUID: test-uuid) 在系统 test-system 上未找到有效的挂载点", log_content)
            
        finally:
            config_patcher.stop()
            db_patcher.stop()

if __name__ == '__main__':
    unittest.main() 