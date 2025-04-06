import unittest
import platform
import os
import logging
from media_analyzer.utils.path_converter import PathConverter

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class TestPathConverter(unittest.TestCase):
    """测试路径转换器类"""
    
    def test_normalize_path(self):
        """测试路径标准化"""
        # Windows风格路径
        win_path = "C:\\Users\\test\\Documents"
        self.assertEqual(PathConverter.normalize_path(win_path), "C:/Users/test/Documents")
        
        # Unix风格路径
        unix_path = "/home/user/documents"
        self.assertEqual(PathConverter.normalize_path(unix_path), unix_path)
        
        # None值处理
        self.assertIsNone(PathConverter.normalize_path(None))
    
    def test_get_relative_path(self):
        """测试获取相对路径"""
        # macOS路径
        mac_full_path = "/Volumes/External/Photos/image.jpg"
        mac_mount = "/Volumes/External"
        print(f"测试macOS路径: {mac_full_path}, 挂载点: {mac_mount}")
        self.assertEqual(PathConverter.get_relative_path(mac_full_path, mac_mount), "Photos/image.jpg")
        
        # Ubuntu路径
        ubuntu_full_path = "/media/user/External/Photos/image.jpg"
        ubuntu_mount = "/media/user/External"
        print(f"测试Ubuntu路径: {ubuntu_full_path}, 挂载点: {ubuntu_mount}")
        self.assertEqual(PathConverter.get_relative_path(ubuntu_full_path, ubuntu_mount), "Photos/image.jpg")
        
        # 确保挂载点有斜杠结尾
        print(f"测试挂载点无斜杠结尾: {mac_full_path}, 挂载点: {mac_mount[:-1]}")
        self.assertEqual(PathConverter.get_relative_path(mac_full_path, mac_mount[:-1]), "Photos/image.jpg")
        
        # 路径不是以挂载点开头的情况
        invalid_path = "/some/other/path/image.jpg"
        print(f"测试非挂载点开头的路径: {invalid_path}, 挂载点: {mac_mount}")
        self.assertEqual(PathConverter.get_relative_path(invalid_path, mac_mount), invalid_path)
    
    def test_to_platform_path(self):
        """测试转换为平台路径"""
        rel_path = "Photos/image.jpg"
        mount_point = "/Volumes/External"
        
        # 测试结果应该是平台正确的路径
        expected = os.path.join(mount_point, rel_path)
        if platform.system() == 'Windows':
            expected = expected.replace('/', '\\')
            
        self.assertEqual(PathConverter.to_platform_path(rel_path, mount_point), expected)
        
        # 测试相对路径有开头斜杠的情况
        rel_path_with_slash = "/Photos/image.jpg"
        self.assertEqual(
            PathConverter.to_platform_path(rel_path_with_slash, mount_point),
            expected
        )
        
        # 测试挂载点有结尾斜杠的情况
        mount_with_slash = mount_point + "/"
        self.assertEqual(
            PathConverter.to_platform_path(rel_path, mount_with_slash),
            expected
        )
    
    def test_get_mount_point_pattern(self):
        """测试获取挂载点模式"""
        # macOS模式
        self.assertEqual(
            PathConverter.get_mount_point_pattern('Darwin'),
            r'^/Volumes/([^/]+)'
        )
        
        # Ubuntu模式
        self.assertEqual(
            PathConverter.get_mount_point_pattern('Linux'),
            r'^/media/([^/]+)/([^/]+)'
        )
        
        # Windows模式
        self.assertEqual(
            PathConverter.get_mount_point_pattern('Windows'),
            r'^([A-Z]:)'
        )
        
        # 未知系统默认使用Linux模式
        self.assertEqual(
            PathConverter.get_mount_point_pattern('Unknown'),
            r'^/media/([^/]+)/([^/]+)'
        )
    
    def test_extract_mount_point(self):
        """测试提取挂载点"""
        # macOS路径
        mac_path = "/Volumes/External/Photos/image.jpg"
        self.assertEqual(
            PathConverter.extract_mount_point(mac_path, 'Darwin'),
            "/Volumes/External"
        )
        
        # Ubuntu路径
        ubuntu_path = "/media/user/External/Photos/image.jpg"
        self.assertEqual(
            PathConverter.extract_mount_point(ubuntu_path, 'Linux'),
            "/media/user/External"
        )
        
        # Windows路径
        win_path = "C:/Users/test/Documents"
        self.assertEqual(
            PathConverter.extract_mount_point(win_path, 'Windows'),
            "C:"
        )
        
        # 不匹配的路径
        invalid_path = "/some/other/path"
        self.assertIsNone(
            PathConverter.extract_mount_point(invalid_path, 'Darwin')
        )
        
        # None值处理
        self.assertIsNone(PathConverter.extract_mount_point(None))

if __name__ == '__main__':
    unittest.main() 