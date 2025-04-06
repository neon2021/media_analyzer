"""
数据库管理模块，负责数据库连接和基础数据库操作
"""

import os
import logging
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional, List, Tuple, Union

from media_analyzer.utils.config_manager import get_database_config, get_postgres_dsn, get_config

logger = logging.getLogger(__name__)


class DBManager:
    """数据库管理类，提供统一的数据库操作接口，支持SQLite和PostgreSQL"""

    def __init__(self, db_type: str = "postgresql", connection_string: Optional[str] = None):
        """
        初始化数据库管理器
        
        Args:
            db_type: 数据库类型，"sqlite"或"postgresql"/"postgres"
            connection_string: 连接字符串，如果为None则从配置中读取
        """
        self.db_type = db_type.lower()
        self.conn = None
        self.cursor = None
        
        if self.db_type == "sqlite":
            if connection_string is None:
                db_config = get_database_config()
                # 使用配置的路径，展开用户目录
                db_path = db_config.get("path", "media_analyzer.db")
                db_path = os.path.expanduser(db_path)
                # 确保目录存在
                os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
                connection_string = db_path
            self._connect_sqlite(connection_string)
        elif self.db_type in ["postgres", "postgresql"]:
            if connection_string is None:
                connection_string = get_postgres_dsn()
            self._connect_postgres(connection_string)
        else:
            raise ValueError(f"不支持的数据库类型: {db_type}")
        
        logger.info(f"已连接到 {self.db_type} 数据库")

    def _connect_sqlite(self, db_path: str):
        """
        连接到SQLite数据库
        
        Args:
            db_path: 数据库文件路径
        """
        try:
            self.conn = sqlite3.connect(db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
        except Exception as e:
            logger.error(f"连接SQLite数据库失败: {e}")
            raise

    def _connect_postgres(self, connection_string: str):
        """
        连接到PostgreSQL数据库
        
        Args:
            connection_string: 数据库连接字符串
        """
        try:
            self.conn = psycopg2.connect(connection_string)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        except Exception as e:
            logger.error(f"连接PostgreSQL数据库失败: {e}")
            raise

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.debug("数据库连接已关闭")

    def commit(self):
        """提交事务"""
        if self.conn:
            self.conn.commit()

    def rollback(self):
        """回滚事务"""
        if self.conn:
            self.conn.rollback()

    def execute(self, query: str, params: Optional[Tuple] = None) -> int:
        """
        执行SQL语句
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            受影响的行数
        """
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
                
            # 对于非查询操作，获取受影响的行数
            if query.strip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
                if self.db_type == "sqlite":
                    return self.cursor.rowcount
                else:  # postgres
                    return self.cursor.rowcount
            return 0
        except Exception as e:
            logger.error(f"执行SQL失败: {query}, 错误: {e}")
            self.rollback()
            raise

    def executemany(self, query: str, params_list: List[Tuple]) -> int:
        """
        批量执行SQL语句
        
        Args:
            query: SQL查询语句
            params_list: 查询参数列表
            
        Returns:
            受影响的行数
        """
        try:
            self.cursor.executemany(query, params_list)
            if self.db_type == "sqlite":
                return self.cursor.rowcount
            else:  # postgres
                return self.cursor.rowcount
        except Exception as e:
            logger.error(f"批量执行SQL失败: {query}, 错误: {e}")
            self.rollback()
            raise

    def fetch_one(self) -> Optional[Dict[str, Any]]:
        """
        获取一条查询结果
        
        Returns:
            结果字典，如果没有结果则返回None
        """
        row = self.cursor.fetchone()
        if row is None:
            return None
            
        if self.db_type == "sqlite":
            return {k: row[k] for k in row.keys()}
        return dict(row)

    def fetch_all(self) -> List[Dict[str, Any]]:
        """
        获取所有查询结果
        
        Returns:
            结果字典列表
        """
        rows = self.cursor.fetchall()
        if self.db_type == "sqlite":
            return [{k: row[k] for k in row.keys()} for row in rows]
        return [dict(row) for row in rows]

    def query(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        执行查询并返回所有结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            结果字典列表
        """
        self.execute(query, params)
        return self.fetch_all()

    def query_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """
        执行查询并返回一条结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            结果字典，如果没有结果则返回None
        """
        self.execute(query, params)
        return self.fetch_one()

    def create_table(self, table_name: str, columns: Dict[str, str], if_not_exists: bool = True):
        """
        创建表
        
        Args:
            table_name: 表名
            columns: 列定义字典，键为列名，值为列类型
            if_not_exists: 是否仅在表不存在时创建
        """
        column_defs = [f"{name} {type_}" for name, type_ in columns.items()]
        exists_clause = "IF NOT EXISTS " if if_not_exists else ""
        query = f"CREATE TABLE {exists_clause}{table_name} ({', '.join(column_defs)})"
        self.execute(query)
        self.commit()

    def table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在
        
        Args:
            table_name: 表名
            
        Returns:
            表是否存在
        """
        if self.db_type == "sqlite":
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
            self.execute(query, (table_name,))
        else:  # postgres
            query = "SELECT table_name FROM information_schema.tables WHERE table_name=%s"
            self.execute(query, (table_name,))
            
        return self.fetch_one() is not None

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """
        获取表结构
        
        Args:
            table_name: 表名
            
        Returns:
            表结构字典列表
        """
        if self.db_type == "sqlite":
            query = f"PRAGMA table_info({table_name})"
            self.execute(query)
        else:  # postgres
            query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            """
            self.execute(query, (table_name,))
            
        return self.fetch_all()

    def get_tables(self) -> List[str]:
        """
        获取所有表名
        
        Returns:
            表名列表
        """
        if self.db_type == "sqlite":
            query = "SELECT name FROM sqlite_master WHERE type='table'"
            self.execute(query)
            result = self.fetch_all()
            return [row['name'] for row in result]
        else:  # postgres
            query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
            self.execute(query)
            result = self.fetch_all()
            return [row['table_name'] for row in result]

# 全局数据库管理器实例
db = None

def get_db():
    """获取数据库管理器实例"""
    global db
    if db is None:
        config = get_config()
        logging.info(f'config: \n{config}')
        
        # 读取数据库类型配置 - 优先使用PostgreSQL
        db_type = config.get('database.type', 'postgresql').lower()
        
        try:
            if db_type == 'postgresql' or db_type == 'postgres':
                # 尝试连接PostgreSQL
                db = DBManager(db_type='postgres')
                logger.info(f"已成功连接到 PostgreSQL 数据库")
            elif db_type == 'sqlite':
                # 只有明确配置为sqlite时才使用sqlite
                db = DBManager(db_type='sqlite')
                logger.info(f"已成功连接到 SQLite 数据库 (配置指定)")
            else:
                # 不支持的数据库类型，回退到PostgreSQL
                logger.warning(f"不支持的数据库类型 '{db_type}'，回退到 PostgreSQL")
                db = DBManager(db_type='postgres')
        except Exception as e:
            # 数据库连接失败，抛出明确的异常
            logger.error(f"连接到 {db_type} 失败: {e}")
            
            # 判断是否需要回退到SQLite
            # 检查环境变量或配置来确定是否允许回退
            allow_fallback = os.environ.get('ALLOW_DB_FALLBACK', 'true').lower() == 'true'
            
            if allow_fallback and (db_type == 'postgresql' or db_type == 'postgres'):
                logger.warning("尝试回退到 SQLite 数据库")
                try:
                    db = DBManager(db_type='sqlite')
                    logger.info("已成功回退到 SQLite 数据库")
                except Exception as e2:
                    logger.error(f"连接到 SQLite 也失败: {e2}")
                    raise RuntimeError(f"无法连接到任何数据库: PostgreSQL - {e}, SQLite - {e2}")
            else:
                # 不回退或非PostgreSQL连接失败，则直接抛出异常
                raise RuntimeError(f"数据库连接失败，无法继续: {e}")
                
    return db 