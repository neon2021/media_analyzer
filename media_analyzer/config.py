import os
import json
import logging
import platform
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 加载.env文件
load_dotenv()

# 默认配置
DEFAULT_CONFIG = {
    'system': {
        'id': f"{platform.system().lower()}-{platform.node()}",
        'platform': platform.system()
    },
    'database': {
        'type': 'sqlite',
        'sqlite': {
            'path': 'media_analyzer.db'
        },
        'postgresql': {
            'host': 'localhost',
            'port': 5432,
            'database': 'media_analyzer',
            'user': 'postgres',
            'password': 'postgres'
        }
    },
    'media': {
        'extensions': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.mp4', '.mov', '.avi', '.mkv']
    },
    'scan': {
        'progress_interval': 30,  # 每30秒更新一次进度
        'hash_timeout': 10        # 单个文件最大哈希耗时（秒）
    }
}

# 全局配置对象
_config = None

def load_config(config_path=None):
    """
    加载配置文件
    
    Args:
        config_path (str, optional): 配置文件路径，如果不指定则使用默认路径
        
    Returns:
        dict: 配置字典
    """
    global _config
    
    # 如果未指定配置文件路径，使用默认路径
    if not config_path:
        config_path = os.getenv('CONFIG_PATH', 'config.json')
    
    # 使用深拷贝防止修改默认配置
    config = DEFAULT_CONFIG.copy()
    
    # 尝试加载配置文件
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                
            # 递归合并配置
            config = _merge_configs(config, file_config)
            logger.info(f"已加载配置文件: {config_path}")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
    else:
        logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
        
        # 保存默认配置
        save_config(config, config_path)
    
    # 处理环境变量覆盖
    # 系统ID
    if os.getenv('SYSTEM_ID'):
        config['system']['id'] = os.getenv('SYSTEM_ID')
    
    # 数据库配置
    if os.getenv('POSTGRES_HOST'):
        config['database']['postgresql']['host'] = os.getenv('POSTGRES_HOST')
    if os.getenv('POSTGRES_PORT'):
        config['database']['postgresql']['port'] = int(os.getenv('POSTGRES_PORT'))
    if os.getenv('POSTGRES_DB'):
        config['database']['postgresql']['database'] = os.getenv('POSTGRES_DB')
    if os.getenv('POSTGRES_USER'):
        config['database']['postgresql']['user'] = os.getenv('POSTGRES_USER')
    if os.getenv('POSTGRES_PASSWORD'):
        config['database']['postgresql']['password'] = os.getenv('POSTGRES_PASSWORD')
    
    # 数据库类型选择
    if os.getenv('DATABASE_TYPE'):
        config['database']['type'] = os.getenv('DATABASE_TYPE')
    
    # 保存配置到全局变量
    _config = config
    
    return config

def save_config(config, config_path=None):
    """
    保存配置到文件
    
    Args:
        config (dict): 配置字典
        config_path (str, optional): 配置文件路径，如果不指定则使用默认路径
    """
    if not config_path:
        config_path = os.getenv('CONFIG_PATH', 'config.json')
    
    # 确保目录存在
    os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        logger.info(f"配置已保存到: {config_path}")
    except Exception as e:
        logger.error(f"保存配置失败: {e}")

def get_config():
    """
    获取当前配置
    
    Returns:
        dict: 配置字典
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config

def _merge_configs(base, override):
    """
    递归合并配置字典
    
    Args:
        base (dict): 基础配置
        override (dict): 覆盖配置
        
    Returns:
        dict: 合并后的配置
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_configs(result[key], value)
        else:
            result[key] = value
            
    return result

def get(path, default=None):
    """
    通过点分隔路径获取配置值
    
    Args:
        path (str): 配置路径，例如 "database.postgresql.host"
        default: 如果路径不存在，返回的默认值
        
    Returns:
        配置值，如果路径不存在则返回默认值
    """
    config = get_config()
    keys = path.split('.')
    
    try:
        result = config
        for key in keys:
            result = result[key]
        return result
    except (KeyError, TypeError):
        return default