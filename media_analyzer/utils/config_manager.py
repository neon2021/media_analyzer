"""
配置管理模块，统一处理YAML格式的配置文件。

此模块负责:
1. 加载配置文件 (config-media-analyzer.yaml)
2. 提供配置项访问接口
3. 确保配置一致性和默认值
"""

import os
import yaml
import logging
import json
import socket
import platform
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler

# 配置文件的默认路径
DEFAULT_CONFIG_FILENAME = "config-media-analyzer.yaml"

logger = logging.getLogger(__name__)

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
                'system': {
                    'id': 'auto'  # 自动基于主机名生成
                },
                'database': {
                    'type': 'postgresql',  # 明确指定默认使用PostgreSQL
                    'path': 'media_analyzer.db',  # 仅用于SQLite或回退情况
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
            # 处理系统ID
            self._process_system_id()
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
            # 检查Docker环境文件
            is_docker = os.path.exists("/.dockerenv")
            if not is_docker:
                # 尝试访问Docker容器名称
                try:
                    socket.gethostbyname('postgres')
                    is_docker = True
                except:
                    is_docker = False
        
        self._config['environment']['is_docker'] = is_docker
        logger.info(f"检测到环境: {'Docker' if is_docker else '本地'}")
        
        # 根据环境设置PostgreSQL主机
        if is_docker:
            self._config['database']['postgres']['host'] = 'postgres'
    
    def _process_system_id(self):
        """处理系统ID"""
        if self._config['system']['id'] == 'auto':
            system_type = platform.system().lower()
            hostname = socket.gethostname()
            self._config['system']['id'] = f"{system_type}-{hostname}"
            logger.info(f"设置系统ID: {self._config['system']['id']}")
    
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
            os.path.join(str(Path.home().joinpath('Documents')), DEFAULT_CONFIG_FILENAME),
            os.path.expanduser("~/.config/media-analyzer/config.yaml")
        ]
        
        for user_config in user_home_configs:
            if os.path.exists(user_config):
                logger.info(f'找到用户配置: {user_config}')
                config_paths.append(user_config)
        
        # 3. 检查项目配置目录
        project_config = "./config/config-media-analyzer.yaml"
        if os.path.exists(project_config):
            config_paths.append(project_config)
        
        # 4. 检查命令行参数中的配置文件路径
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--config', type=str, help='配置文件路径')
        try:
            args, _ = parser.parse_known_args()
            if args.config and os.path.exists(args.config):
                logger.info(f'命令行指定配置: {args.config}')
                config_paths.append(args.config)
        except Exception as e:
            logger.warning(f"解析命令行参数时出错: {e}")
        
        # 按优先级顺序加载配置文件
        for config_path in config_paths:
            logger.info(f"加载配置文件: {config_path}")
            self.load_config(config_path)
    
    def load_config(self, config_path: str) -> None:
        """从指定路径加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
                if loaded_config:
                    self._update_config(loaded_config)
                    logger.info(f"成功加载配置文件: {config_path}")
        except Exception as e:
            logger.warning(f"加载配置文件失败 {config_path}: {e}")
            logger.info("将使用已有配置")
    
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
            self._config['database']['postgres']['host'] = 'postgres'
        
        # 重新处理系统ID（如果需要）
        self._process_system_id()
    
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
    
    def get_dict(self) -> Dict[str, Any]:
        """获取完整配置字典"""
        return self._config
    
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
_config_manager = ConfigManager()


# 函数接口，与之前的config_manager.py保持兼容
def get_config() -> Dict[str, Any]:
    """获取配置字典"""
    return _config_manager.get_dict()


def get_system_id() -> str:
    """获取系统ID"""
    return _config_manager.get('system.id')


def get_database_config() -> Dict[str, Any]:
    """获取数据库配置"""
    return _config_manager.get('database')


def get_postgres_dsn() -> str:
    """获取PostgreSQL数据库连接字符串"""
    db_config = get_database_config()['postgres']
    return f"postgresql://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"


def get_logging_config() -> Dict[str, Any]:
    """获取日志配置"""
    return _config_manager.get('logging')


def get_scan_config() -> Dict[str, Any]:
    """获取扫描配置"""
    return _config_manager.get('scan')


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """加载配置文件，保持向后兼容"""
    if config_path:
        _config_manager.load_config(config_path)
    return get_config()


def setup_logging() -> None:
    """设置日志系统"""
    _config_manager.setup_logging() 