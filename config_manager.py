import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler
import json

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
                    'path': 'media_index.db'
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
                }
            }
    
    def load_config(self, config_path: str) -> None:
        """从指定路径加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
                self._update_config(loaded_config)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            print("将使用默认配置")
    
    def _update_config(self, new_config: Dict[str, Any]) -> None:
        """递归更新配置"""
        def update_dict(base: Dict[str, Any], update: Dict[str, Any]) -> None:
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    update_dict(base[key], value)
                else:
                    base[key] = value
        
        update_dict(self._config, new_config)
    
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