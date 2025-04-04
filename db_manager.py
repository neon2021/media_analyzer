import os
import sqlite3
import threading
from contextlib import contextmanager
from queue import Queue
from typing import Optional
from config_manager import get_config

class DatabaseManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        config = get_config()
        print(f'[DEBUG] DatabaseManager init - config from get_config: {config}')
        print(f'[DEBUG] DatabaseManager init - database.path: {config.get("database.path")}')
        self.db_path = os.path.expanduser(config.get('database.path', 'media_index.db'))
        print(f'[DEBUG] DatabaseManager init - final db_path: {self.db_path}')
        self.pool_size = 5
        self.connection_pool = Queue(maxsize=self.pool_size)
        self._lock = threading.Lock()
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        
        # 初始化连接池
        for _ in range(self.pool_size):
            conn = self._create_connection()
            self.connection_pool.put(conn)
            
        self._initialized = True
    
    def _create_connection(self) -> sqlite3.Connection:
        """创建一个新的数据库连接"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,  # 连接超时时间
            isolation_level='IMMEDIATE'  # 事务隔离级别
        )
        # 启用外键约束
        conn.execute('PRAGMA foreign_keys = ON')
        # 启用WAL模式以提高并发性能
        conn.execute('PRAGMA journal_mode=WAL')
        return conn
    
    @contextmanager
    def get_connection(self) -> sqlite3.Connection:
        """从连接池获取一个连接"""
        connection = self.connection_pool.get()
        try:
            yield connection
        finally:
            self.connection_pool.put(connection)
    
    @contextmanager
    def get_cursor(self, commit=True):
        """获取数据库游标，自动处理提交和回滚"""
        with self.get_connection() as connection:
            cursor = connection.cursor()
            try:
                yield cursor
                if commit:
                    connection.commit()
            except Exception as e:
                connection.rollback()
                raise e
            finally:
                cursor.close()
    
    def close_all(self):
        """关闭所有连接"""
        while not self.connection_pool.empty():
            conn = self.connection_pool.get()
            conn.close()

# 全局数据库管理器实例
db = None

def get_db():
    """获取数据库管理器实例"""
    global db
    if db is None:
        db = DatabaseManager()
    return db 