#!/usr/bin/env python3
"""测试数据库连接"""

import sys
import argparse
import psycopg2
from media_analyzer.utils.config_manager import get_config

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="测试数据库连接")
    parser.add_argument('--config', type=str, help='配置文件路径', default='config/config-media-analyzer-test.yaml')
    args = parser.parse_args()
    
    # 加载配置
    config = get_config()
    if args.config:
        print(f"加载配置文件: {args.config}")
        config.load_config(args.config)
    
    print(f"配置信息:\n{config}")
    
    # 获取数据库配置
    db_type = config.get('database.type')
    print(f"数据库类型: {db_type}")
    
    if db_type == 'postgresql':
        # 获取 PostgreSQL 连接信息
        db_name = config.get('database.postgres.database', 'media_analyzer')
        username = config.get('database.postgres.username', 'postgres')
        password = config.get('database.postgres.password', 'postgres')
        host = config.get('database.postgres.host', 'localhost')
        port = config.get('database.postgres.port', 5432)
        
        print(f"尝试连接到 PostgreSQL: {host}:{port}/{db_name} (用户: {username})")
        
        # 尝试连接
        try:
            conn = psycopg2.connect(
                dbname=db_name,
                user=username,
                password=password,
                host=host,
                port=port
            )
            cursor = conn.cursor()
            
            # 测试查询
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            print(f"连接成功! PostgreSQL 版本: {version}")
            
            # 列出所有表
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = cursor.fetchall()
            print("数据库中的表:")
            for table in tables:
                print(f"  - {table[0]}")
            
            # 关闭连接
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"连接错误: {e}")
            return 1
    else:
        print(f"不支持的数据库类型: {db_type}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 