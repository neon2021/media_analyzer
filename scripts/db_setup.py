#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库环境配置脚本
根据不同操作系统自动选择适合的配置
"""

import os
import sys
import platform
import subprocess
import shutil
import argparse
import logging
import yaml
from pathlib import Path
from media_analyzer.utils.config_manager import ConfigManager

# 获取配置管理器并设置日志
config_manager = ConfigManager()
config_manager.setup_logging()
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

def load_config(config_path=None):
    """加载配置文件"""
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "config-media-analyzer.yaml"
    
    config_path = Path(config_path)
    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.info(f"已加载配置文件: {config_path}")
        return config
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return None

def detect_os():
    """检测操作系统类型"""
    system = platform.system().lower()
    logger.info(f"检测到操作系统: {system}")
    
    if system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    else:
        logger.warning(f"未知操作系统: {system}，将使用通用配置")
        return "linux"  # 默认使用Linux配置

def generate_docker_compose(config, os_type):
    """根据配置和操作系统类型生成适合的Docker Compose配置"""
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    
    try:
        # 获取Docker配置
        docker_config = config.get('database', {}).get('docker', {})
        common_config = docker_config.get('common', {})
        os_config = docker_config.get(os_type, {})
        
        if not docker_config or not common_config or not os_config:
            logger.warning(f"配置文件中缺少Docker配置，将使用默认配置")
            return generate_default_docker_compose(os_type)
        
        # 构建Docker Compose配置
        version = os_config.get('version', '3')
        build_context = os_config.get('build_context', False)
        image = os_config.get('image', 'postgres:14')
        container_name = common_config.get('container_name', 'postgres-db')
        username = common_config.get('username', 'postgres')
        password = common_config.get('password', 'postgres')
        database = common_config.get('database', 'media_analyzer')
        port = common_config.get('port', 5433)
        volume_name = os_config.get('volume_name', 'postgres-data')
        
        # 是否使用环境变量替换语法
        env_vars_format = os_config.get('env_vars_format', 'template')
        if env_vars_format == 'direct':
            env_username = username
            env_password = password
            env_database = database
        else:
            env_username = "${POSTGRES_USER:-" + username + "}"
            env_password = "${POSTGRES_PASSWORD:-" + password + "}"
            env_database = "${POSTGRES_DB:-" + database + "}"
        
        # 根据操作系统生成不同的docker-compose.yml
        compose_content = f"version: '{version}'\n\n"
        compose_content += "services:\n"
        compose_content += "  postgres:\n"
        
        # 根据配置使用build或image
        if build_context:
            compose_content += "    build: .\n"
        else:
            compose_content += f"    image: {image}\n"
            
        compose_content += f"    container_name: {container_name}\n"
        compose_content += "    environment:\n"
        compose_content += f"      POSTGRES_USER: {env_username}\n"
        compose_content += f"      POSTGRES_PASSWORD: {env_password}\n"
        compose_content += f"      POSTGRES_DB: {env_database}\n"
        compose_content += "    ports:\n"
        compose_content += f"      - \"{port}:5432\"\n"
        compose_content += "    volumes:\n"
        compose_content += f"      - {volume_name}:/var/lib/postgresql/data\n"
        compose_content += "    restart: unless-stopped\n"
        
        # 添加健康检查配置（如果启用）
        if os_config.get('healthcheck', False):
            compose_content += "    healthcheck:\n"
            compose_content += "      test: [\"CMD-SHELL\", \"pg_isready -U postgres\"]\n"
            compose_content += "      interval: 5s\n"
            compose_content += "      timeout: 5s\n"
            compose_content += "      retries: 5\n"
        
        compose_content += "\nvolumes:\n"
        compose_content += f"  {volume_name}:\n"
        
        # 写入文件
        with open(compose_path, 'w') as f:
            f.write(compose_content)
        
        logger.info(f"已为 {os_type} 生成 Docker Compose 配置: {compose_path}")
        return compose_path
    except Exception as e:
        logger.error(f"生成Docker Compose配置失败: {e}")
        return generate_default_docker_compose(os_type)

def generate_default_docker_compose(os_type):
    """生成默认的Docker Compose配置（向后兼容）"""
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    
    # 默认配置模板
    if os_type == "macos":
        config = """version: '3.8'

services:
  postgres:
    build: .
    container_name: media_analyzer_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-media_analyzer}
    ports:
      - "5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
"""
    elif os_type == "linux":
        config = """version: '3'

services:
  postgres:
    image: postgres:14
    container_name: postgres-db
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-media_analyzer}
    ports:
      - "5433:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres-data:
"""
    elif os_type == "windows":
        config = """version: '3'

services:
  postgres:
    image: postgres:14
    container_name: postgres-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: media_analyzer
    ports:
      - "5433:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres-data:
"""
    else:
        # 默认使用Linux配置
        config = """version: '3'

services:
  postgres:
    image: postgres:14
    container_name: postgres-db
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-media_analyzer}
    ports:
      - "5433:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres-data:
"""

    with open(compose_path, "w") as f:
        f.write(config)
    
    logger.info(f"已为 {os_type} 生成默认 Docker Compose 配置: {compose_path}")
    return compose_path

def check_docker():
    """检查Docker环境是否准备就绪"""
    try:
        # 检查是否是Linux系统，如果是且不是root用户，则使用sudo
        use_sudo = platform.system().lower() == "linux" and os.geteuid() != 0
        
        if use_sudo:
            cmd = ["sudo", "docker", "--version"]
        else:
            cmd = ["docker", "--version"]
            
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            logger.info(f"Docker已安装: {result.stdout.strip()}")
            return True
        else:
            logger.error(f"Docker未安装或不可用: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"检查Docker时出错: {e}")
        return False

def check_docker_compose():
    """检查Docker Compose是否安装"""
    try:
        # 检查是否是Linux系统，如果是且不是root用户，则使用sudo
        use_sudo = platform.system().lower() == "linux" and os.geteuid() != 0
        
        if use_sudo:
            cmd = ["sudo", "docker-compose", "--version"]
        else:
            cmd = ["docker-compose", "--version"]
            
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            logger.info(f"Docker Compose已安装: {result.stdout.strip()}")
            return True
        else:
            logger.error(f"Docker Compose未安装或不可用: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"检查Docker Compose时出错: {e}")
        return False

def start_postgres_docker(config):
    """启动PostgreSQL Docker服务"""
    os.chdir(PROJECT_ROOT)
    
    try:
        logger.info("启动PostgreSQL Docker服务...")
        
        # 检查是否是Linux系统，如果是且不是root用户，则使用sudo
        use_sudo = platform.system().lower() == "linux" and os.geteuid() != 0
        
        if use_sudo:
            logger.info("检测到Linux系统，使用sudo执行Docker命令")
            cmd = ["sudo", "docker-compose", "up", "-d"]
        else:
            cmd = ["docker-compose", "up", "-d"]
            
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 检查是否遇到ContainerConfig错误
        if result.returncode != 0 and "ContainerConfig" in result.stderr:
            logger.warning("检测到Docker Compose版本兼容性问题，尝试使用直接的Docker命令...")
            return start_postgres_direct_docker(config)
        elif result.returncode == 0:
            logger.info("PostgreSQL Docker服务启动成功")
            show_connection_info(config)
            return True
        else:
            logger.error(f"启动PostgreSQL Docker服务失败: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"启动Docker服务时出错: {e}")
        return False

def start_postgres_direct_docker(config):
    """直接使用Docker命令启动PostgreSQL"""
    try:
        logger.info("使用直接的Docker命令启动PostgreSQL...")
        
        # 获取配置
        docker_config = config.get('database', {}).get('docker', {})
        common_config = docker_config.get('common', {})
        os_type = detect_os()
        os_config = docker_config.get(os_type, {})
        
        # 使用配置或默认值
        container_name = common_config.get('container_name', 'postgres-db')
        username = common_config.get('username', 'postgres')
        password = common_config.get('password', 'postgres')
        database = common_config.get('database', 'media_analyzer')
        port = common_config.get('port', 5433)
        image = os_config.get('image', 'postgres:14')
        
        # 检查是否是Linux系统，如果是且不是root用户，则使用sudo
        use_sudo = platform.system().lower() == "linux" and os.geteuid() != 0
        docker_cmd = "sudo docker" if use_sudo else "docker"
        
        # 首先确保旧容器已停止并删除
        subprocess.run(
            f"{docker_cmd} rm -f {container_name}".split(), 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        # 启动新容器
        cmd = f"{docker_cmd} run --name {container_name} -e POSTGRES_PASSWORD={password} -e POSTGRES_USER={username} -e POSTGRES_DB={database} -p {port}:5432 -d {image}"
        
        result = subprocess.run(
            cmd.split(), 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("PostgreSQL Docker服务启动成功 (直接Docker命令)")
            show_connection_info(config)
            return True
        else:
            logger.error(f"启动PostgreSQL Docker服务失败 (直接Docker命令): {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"使用直接Docker命令启动服务时出错: {e}")
        return False

def show_connection_info(config):
    """显示数据库连接信息"""
    # 获取配置
    docker_config = config.get('database', {}).get('docker', {})
    common_config = docker_config.get('common', {})
    
    # 使用配置或默认值
    host = 'localhost'
    port = common_config.get('port', 5433)
    username = common_config.get('username', 'postgres')
    password = common_config.get('password', 'postgres')
    database = common_config.get('database', 'media_analyzer')
    
    logger.info("数据库连接信息:")
    logger.info(f"  - 主机: {host}")
    logger.info(f"  - 端口: {port}")
    logger.info(f"  - 用户名: {username}")
    logger.info(f"  - 密码: {password}")
    logger.info(f"  - 数据库: {database}")

def stop_postgres_docker(config):
    """停止PostgreSQL Docker服务"""
    os.chdir(PROJECT_ROOT)
    
    try:
        logger.info("停止PostgreSQL Docker服务...")
        
        # 获取配置
        docker_config = config.get('database', {}).get('docker', {})
        common_config = docker_config.get('common', {})
        container_name = common_config.get('container_name', 'postgres-db')
        
        # 检查是否是Linux系统，如果是且不是root用户，则使用sudo
        use_sudo = platform.system().lower() == "linux" and os.geteuid() != 0
        
        # 先尝试docker-compose down
        if use_sudo:
            logger.info("检测到Linux系统，使用sudo执行Docker命令")
            cmd = ["sudo", "docker-compose", "down"]
        else:
            cmd = ["docker-compose", "down"]
            
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 如果失败，尝试直接使用docker stop和docker rm
        if result.returncode != 0:
            logger.warning("使用docker-compose停止服务失败，尝试直接使用docker命令...")
            docker_cmd = "sudo docker" if use_sudo else "docker"
            
            # 停止容器
            stop_result = subprocess.run(
                f"{docker_cmd} stop {container_name}".split(),
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 删除容器
            rm_result = subprocess.run(
                f"{docker_cmd} rm -f {container_name}".split(),
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if stop_result.returncode == 0 or rm_result.returncode == 0:
                logger.info("PostgreSQL Docker服务已停止 (直接Docker命令)")
                return True
            else:
                logger.error(f"停止PostgreSQL Docker服务失败 (直接Docker命令): {stop_result.stderr} {rm_result.stderr}")
                return False
        else:
            logger.info("PostgreSQL Docker服务已停止")
            return True
    except Exception as e:
        logger.error(f"停止Docker服务时出错: {e}")
        return False

def setup_database(config_path=None):
    """设置数据库环境"""
    # 加载配置
    config = load_config(config_path)
    if config is None:
        logger.error("无法加载配置文件，将使用默认配置")
        config = {}
    
    # 检测操作系统
    os_type = detect_os()
    
    # 检查Docker环境
    if not check_docker():
        logger.error("请先安装Docker")
        return False
    
    if not check_docker_compose():
        logger.error("请先安装Docker Compose")
        return False
    
    # 生成Docker Compose配置
    generate_docker_compose(config, os_type)
    
    # 启动PostgreSQL Docker服务
    return start_postgres_docker(config)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="数据库环境配置工具")
    parser.add_argument("--os", choices=["macos", "linux", "windows"], 
                        help="强制使用指定操作系统类型的配置")
    parser.add_argument("--stop", action="store_true", 
                        help="停止PostgreSQL Docker服务")
    parser.add_argument("--restart", action="store_true", 
                        help="重启PostgreSQL Docker服务")
    parser.add_argument("--config", type=str, default=None,
                        help="指定配置文件路径")
    parser.add_argument("--test", action="store_true",
                        help="使用测试配置")
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_args()
    
    # 确定配置文件路径
    config_path = args.config
    if args.test and config_path is None:
        config_path = PROJECT_ROOT / "config" / "config-media-analyzer-test.yaml"
    elif config_path is None:
        config_path = PROJECT_ROOT / "config" / "config-media-analyzer.yaml"
    
    # 加载配置
    config = load_config(config_path)
    if config is None:
        logger.error("无法加载配置文件，将使用默认配置")
        config = {}
    
    if args.stop:
        stop_postgres_docker(config)
        return
    
    if args.restart:
        stop_postgres_docker(config)
        # 继续执行启动
    
    # 如果指定了操作系统类型
    if args.os:
        logger.info(f"使用指定操作系统类型: {args.os}")
        generate_docker_compose(config, args.os)
        start_postgres_docker(config)
    else:
        # 自动检测并设置
        setup_database(config_path)

if __name__ == "__main__":
    main() 