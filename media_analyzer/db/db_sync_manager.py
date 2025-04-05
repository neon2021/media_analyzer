import psycopg2
from psycopg2.extras import execute_values
import logging
from media_analyzer.utils.config_manager import get_config
import time
from datetime import datetime, timedelta
import platform
import json
import socket

logger = logging.getLogger(__name__)

class DatabaseSyncManager:
    def __init__(self):
        self.config = get_config()
        # 使用配置中的system.id，如果没有则使用自动生成的
        self.system_id = self.config.get('system.id')
        if not self.system_id or self.system_id == 'auto':
            self.system_id = f"{platform.system()}-{platform.node()}"
        self.last_sync_time = None
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """建立数据库连接"""
        try:
            # 获取 PostgreSQL 连接信息
            db_name = self.config.get('database.postgres.database', 'media_analyzer')
            username = self.config.get('database.postgres.username', 'postgres')
            password = self.config.get('database.postgres.password', 'postgres')
            host = self.config.get('database.postgres.host', 'localhost')
            port = self.config.get('database.postgres.port', 5432)
            
            # 如果主机名是Docker容器名称，且不在Docker环境中，则切换到localhost
            if host == 'media_analyzer_postgres':
                try:
                    socket.gethostbyname(host)
                except socket.gaierror:
                    logger.warning(f"无法解析主机名 '{host}'，切换到 'localhost'")
                    host = 'localhost'
            
            logger.info(f"连接到 PostgreSQL 数据库: {host}:{port}/{db_name}")
            
            # 尝试连接
            try:
                self.conn = psycopg2.connect(
                    dbname=db_name,
                    user=username,
                    password=password,
                    host=host,
                    port=port
                )
            except psycopg2.OperationalError as e:
                if host != 'localhost':
                    logger.warning(f"连接到 {host} 失败，尝试连接到 localhost")
                    self.conn = psycopg2.connect(
                        dbname=db_name,
                        user=username,
                        password=password,
                        host='localhost',
                        port=port
                    )
                else:
                    raise
                    
            self.cursor = self.conn.cursor()
            logger.info(f"成功连接到 PostgreSQL 数据库，系统ID: {self.system_id}")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
            
    def disconnect(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")
            
    def sync_devices(self):
        """同步设备数据"""
        try:
            # 获取需要同步的设备
            self.cursor.execute("""
                SELECT id, uuid, mount_path, label, first_seen, last_seen, system_id, last_sync, is_active
                FROM devices
                WHERE last_sync < %s OR system_id != %s
            """, (self.last_sync_time, self.system_id))
            
            devices = self.cursor.fetchall()
            for device in devices:
                # 处理冲突
                if device[6] != self.system_id:  # 如果设备来自其他系统
                    # 检查设备是否仍然存在
                    if self._check_device_exists(device[1]):
                        # 更新设备状态
                        self.cursor.execute("""
                            UPDATE devices
                            SET last_seen = %s,
                                system_id = %s,
                                last_sync = %s,
                                is_active = true
                            WHERE uuid = %s
                        """, (datetime.now(), self.system_id, datetime.now(), device[1]))
                    else:
                        # 标记设备为非活动
                        self.cursor.execute("""
                            UPDATE devices
                            SET is_active = false,
                                last_sync = %s
                            WHERE uuid = %s
                        """, (datetime.now(), device[1]))
            
            self.conn.commit()
            logger.info(f"设备数据同步完成，处理了 {len(devices)} 条记录")
            
        except Exception as e:
            logger.error(f"设备数据同步失败: {e}")
            self.conn.rollback()
            raise
            
    def sync_files(self):
        """同步文件数据"""
        try:
            # 获取需要同步的文件
            self.cursor.execute("""
                SELECT id, device_uuid, path, hash, size, modified_time, scanned_time, system_id, last_sync
                FROM files
                WHERE last_sync < %s OR system_id != %s
            """, (self.last_sync_time, self.system_id))
            
            files = self.cursor.fetchall()
            for file in files:
                # 处理冲突
                if file[7] != self.system_id:  # 如果文件来自其他系统
                    # 检查文件是否仍然存在
                    if self._check_file_exists(file[1], file[2]):
                        # 更新文件信息
                        self.cursor.execute("""
                            UPDATE files
                            SET hash = %s,
                                size = %s,
                                modified_time = %s,
                                scanned_time = %s,
                                system_id = %s,
                                last_sync = %s
                            WHERE device_uuid = %s AND path = %s
                        """, (file[3], file[4], file[5], file[6], self.system_id, datetime.now(), file[1], file[2]))
                    else:
                        # 删除不存在的文件记录
                        self.cursor.execute("""
                            DELETE FROM files
                            WHERE device_uuid = %s AND path = %s
                        """, (file[1], file[2]))
            
            self.conn.commit()
            logger.info(f"文件数据同步完成，处理了 {len(files)} 条记录")
            
        except Exception as e:
            logger.error(f"文件数据同步失败: {e}")
            self.conn.rollback()
            raise
            
    def sync_scan_progress(self):
        """同步扫描进度数据"""
        try:
            # 获取需要同步的扫描进度
            self.cursor.execute("""
                SELECT id, device_uuid, total_files, new_files, last_updated, system_id, last_sync
                FROM scan_progress
                WHERE last_sync < %s OR system_id != %s
            """, (self.last_sync_time, self.system_id))
            
            progresses = self.cursor.fetchall()
            for progress in progresses:
                # 处理冲突
                if progress[5] != self.system_id:  # 如果进度来自其他系统
                    # 检查设备是否仍然存在
                    if self._check_device_exists(progress[1]):
                        # 更新进度信息
                        self.cursor.execute("""
                            UPDATE scan_progress
                            SET total_files = %s,
                                new_files = %s,
                                last_updated = %s,
                                system_id = %s,
                                last_sync = %s
                            WHERE device_uuid = %s
                        """, (progress[2], progress[3], progress[4], self.system_id, datetime.now(), progress[1]))
                    else:
                        # 删除不存在的设备进度
                        self.cursor.execute("""
                            DELETE FROM scan_progress
                            WHERE device_uuid = %s
                        """, (progress[1],))
            
            self.conn.commit()
            logger.info(f"扫描进度数据同步完成，处理了 {len(progresses)} 条记录")
            
        except Exception as e:
            logger.error(f"扫描进度数据同步失败: {e}")
            self.conn.rollback()
            raise
            
    def sync_image_analysis(self):
        """同步图像分析数据"""
        try:
            # 获取需要同步的图像分析数据
            self.cursor.execute("""
                SELECT id, file_id, camera_model, taken_time, gps_lat, gps_lon, has_faces, objects, analyzed_time, system_id, last_sync
                FROM image_analysis
                WHERE last_sync < %s OR system_id != %s
            """, (self.last_sync_time, self.system_id))
            
            analyses = self.cursor.fetchall()
            for analysis in analyses:
                # 处理冲突
                if analysis[9] != self.system_id:  # 如果分析数据来自其他系统
                    # 检查文件是否仍然存在
                    if self._check_file_exists_by_id(analysis[1]):
                        # 更新分析数据
                        self.cursor.execute("""
                            UPDATE image_analysis
                            SET camera_model = %s,
                                taken_time = %s,
                                gps_lat = %s,
                                gps_lon = %s,
                                has_faces = %s,
                                objects = %s,
                                analyzed_time = %s,
                                system_id = %s,
                                last_sync = %s
                            WHERE file_id = %s
                        """, (analysis[2], analysis[3], analysis[4], analysis[5], analysis[6], analysis[7], analysis[8], self.system_id, datetime.now(), analysis[1]))
                    else:
                        # 删除不存在的文件分析数据
                        self.cursor.execute("""
                            DELETE FROM image_analysis
                            WHERE file_id = %s
                        """, (analysis[1],))
            
            self.conn.commit()
            logger.info(f"图像分析数据同步完成，处理了 {len(analyses)} 条记录")
            
        except Exception as e:
            logger.error(f"图像分析数据同步失败: {e}")
            self.conn.rollback()
            raise
            
    def _check_device_exists(self, device_uuid):
        """检查设备是否仍然存在"""
        try:
            # 这里需要根据实际系统实现设备检查逻辑
            # 例如，检查设备是否仍然挂载
            return True
        except Exception as e:
            logger.error(f"检查设备存在性失败: {e}")
            return False
            
    def _check_file_exists(self, device_uuid, file_path):
        """检查文件是否仍然存在"""
        try:
            # 这里需要根据实际系统实现文件检查逻辑
            # 例如，检查文件是否仍然存在于设备上
            return True
        except Exception as e:
            logger.error(f"检查文件存在性失败: {e}")
            return False
            
    def _check_file_exists_by_id(self, file_id):
        """通过ID检查文件是否仍然存在"""
        try:
            self.cursor.execute("SELECT device_uuid, path FROM files WHERE id = %s", (file_id,))
            result = self.cursor.fetchone()
            if result:
                return self._check_file_exists(result[0], result[1])
            return False
        except Exception as e:
            logger.error(f"通过ID检查文件存在性失败: {e}")
            return False
            
    def sync_all(self):
        """同步所有数据"""
        try:
            self.connect()
            
            # 设置同步时间
            self.last_sync_time = datetime.now() - timedelta(minutes=5)
            
            # 执行同步
            self.sync_devices()
            self.sync_files()
            self.sync_scan_progress()
            self.sync_image_analysis()
            
            logger.info("所有数据同步完成")
            
        finally:
            self.disconnect()
            
    def start_sync_loop(self, interval=300):
        """启动同步循环"""
        try:
            while True:
                self.sync_all()
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("同步循环已停止")
        except Exception as e:
            logger.error(f"同步循环出错: {e}")
            raise 