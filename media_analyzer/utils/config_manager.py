import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler
import json
import argparse
import socket

# 配置文件的默认路径
DEFAULT_CONFIG_FILENAME = "config-media-analyzer.yaml"

class ConfigManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_config'):
            # 默认配置
            self._config = {
                'database': {
                    'path': 'media_index.db',
                    'postgres': {
                        'host': 'localhost',  # 默认使用localhost
                        'port': 5432,
                        'database': 'media_analyzer',
                        'username': 'postgres',
                        'password': 'postgres'
                    }
                },
                'logging': {
                    'path': 'logs',
                    'level': 'INFO',
                    'max_size': 10485760,
                    'backup_count': 5
                },
                'scan': {
                    'hash_timeout': 10,
                    'progress_interval': 30,
                    'skip_dirs': [
                        "/System", "/Volumes/Recovery", "/private", "/Library",
                        "/bin", "/sbin", "/usr", "/proc", "/sys", "/dev",
                        "/run", "/boot"
                    ]
                },
                'environment': {
                    'is_docker': False  # 默认非Docker环境
                }
            }
            # 检测是否在Docker环境中运行
            self._detect_environment()
            # 加载配置文件（按优先级从低到高）
            self._load_config_files()
    
    def _detect_environment(self):
        """检测运行环境"""
        # 检查是否在Docker环境中运行
        is_docker = False
        try:
            # 检查cgroup文件，这是Docker容器的典型特征
            with open('/proc/self/cgroup', 'r') as f:
                is_docker = 'docker' in f.read()
        except:
            # 尝试访问Docker容器名称
            try:
                socket.gethostbyname('media_analyzer_postgres')
                is_docker = True
            except:
                is_docker = False
        
        self._config['environment']['is_docker'] = is_docker
        print(f"检测到环境: {'Docker' if is_docker else '本地'}")
        
        # 根据环境设置PostgreSQL主机
        if is_docker:
            self._config['database']['postgres']['host'] = 'media_analyzer_postgres'
        else:
            self._config['database']['postgres']['host'] = 'localhost'
    
    def _load_config_files(self):
        """加载所有配置文件，按优先级从低到高"""
        config_paths = []
        
        # 1. 检查当前目录的配置文件
        current_dir_config = os.path.join(os.getcwd(), DEFAULT_CONFIG_FILENAME)
        if os.path.exists(current_dir_config):
            config_paths.append(current_dir_config)
        
        # 2. 检查用户根目录的配置文件 (考虑多个可能位置)
        user_home_configs = [
            os.path.join(str(Path.home()), DEFAULT_CONFIG_FILENAME),
            os.path.join(str(Path.home().joinpath('Documents')), DEFAULT_CONFIG_FILENAME)
        ]
        
        for user_config in user_home_configs:
            if os.path.exists(user_config):
                print(f'找到用户配置: {user_config}')
                config_paths.append(user_config)
                break
        
        # 3. 检查命令行参数中的配置文件路径
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--config', type=str, help='配置文件路径')
        try:
            args, _ = parser.parse_known_args()
            if args.config and os.path.exists(args.config):
                print(f'命令行指定配置: {args.config}')
                config_paths.append(args.config)
        except Exception as e:
            print(f"解析命令行参数时出错: {e}")
        
        # 按优先级顺序加载配置文件
        for config_path in config_paths:
            print(f"加载配置文件: {config_path}")
            self.load_config(config_path)
    
    def load_config(self, config_path: str) -> None:
        """从指定路径加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
                if loaded_config:
                    self._update_config(loaded_config)
                    print(f"成功加载配置文件: {config_path}")
        except Exception as e:
            print(f"加载配置文件失败 {config_path}: {e}")
            print("将使用已有配置")
    
    def _update_config(self, new_config: Dict[str, Any]) -> None:
        """递归更新配置"""
        def update_dict(base: Dict[str, Any], update: Dict[str, Any]) -> None:
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    update_dict(base[key], value)
                else:
                    base[key] = value
        
        update_dict(self._config, new_config)
        
        # 在Docker环境中强制使用容器名称作为主机名
        if self._config['environment']['is_docker']:
            self._config['database']['postgres']['host'] = 'media_analyzer_postgres'
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def setup_logging(self) -> None:
        """设置日志系统"""
        log_path = os.path.expanduser(self.get('logging.path'))
        log_level = self.get('logging.level', 'INFO')
        max_size = self.get('logging.max_size', 10485760)
        backup_count = self.get('logging.backup_count', 5)
        
        # 确保日志目录存在
        os.makedirs(log_path, exist_ok=True)
        
        # 配置日志
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                RotatingFileHandler(
                    os.path.join(log_path, 'media_analyzer.log'),
                    maxBytes=max_size,
                    backupCount=backup_count
                ),
                logging.StreamHandler()
            ]
        )
    
    def __str__(self) -> str:
        """返回格式化的配置字符串"""
        return self._format_config(self._config)
    
    def __repr__(self) -> str:
        """返回配置的JSON表示"""
        return json.dumps(self._config, indent=2, ensure_ascii=False)
    
    def _format_config(self, config: Dict[str, Any], indent: int = 0) -> str:
        """递归格式化配置字典"""
        lines = []
        indent_str = ' ' * indent
        
        for key, value in config.items():
            if isinstance(value, dict):
                lines.append(f"{indent_str}{key}:")
                lines.append(self._format_config(value, indent + 2))
            elif isinstance(value, list):
                lines.append(f"{indent_str}{key}:")
                for item in value:
                    lines.append(f"{indent_str}  - {item}")
            else:
                lines.append(f"{indent_str}{key}: {value}")
        
        return '\n'.join(lines)

# 全局配置管理器实例
config = ConfigManager()

def get_config():
    """获取配置管理器实例"""
    return config 