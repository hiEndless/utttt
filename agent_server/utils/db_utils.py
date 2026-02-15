import psycopg2
from psycopg2.extras import execute_batch
from psycopg2 import pool
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import os
import time
import logging
from contextlib import contextmanager

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostgresDB:
    _pool = None
    _pool_lock = False

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0,
                 min_conn: int = 1, max_conn: int = 20):
        self.conn_params = {
            'dbname': os.getenv('DB_DATABASE'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'host': os.getenv('DB_HOST'),
            'port': os.getenv('DB_PORT')
        }
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.min_conn = min_conn
        self.max_conn = max_conn
        self.conn = None
        self.cursor = None

        # 初始化连接池
        self._init_connection_pool()

    def _init_connection_pool(self):
        """初始化连接池"""
        if PostgresDB._pool is None and not PostgresDB._pool_lock:
            PostgresDB._pool_lock = True
            try:
                PostgresDB._pool = pool.ThreadedConnectionPool(
                    minconn=self.min_conn,
                    maxconn=self.max_conn,
                    **self.conn_params
                )
                logger.info(f"连接池初始化成功，最小连接数: {self.min_conn}, 最大连接数: {self.max_conn}")
            except Exception as e:
                logger.error(f"连接池初始化失败: {e}")
                self._log_connection_error(e)
                raise
            finally:
                PostgresDB._pool_lock = False

    def _log_connection_error(self, error: Exception):
        """记录连接错误信息，包括数据库IP"""
        db_host = self.conn_params.get('host', 'unknown')
        db_port = self.conn_params.get('port', 'unknown')
        logger.error(f"数据库连接失败 - 主机: {db_host}:{db_port}, 错误: {str(error)}")
        print(f"数据库连接失败 - 主机: {db_host}:{db_port}, 错误: {str(error)}")

    def _retry_operation(self, operation, *args, **kwargs):
        """重试机制装饰器。失败时先 rollback 再重试，避免连接处于 aborted 状态。"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if self.conn and not self.conn.closed:
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                if attempt < self.max_retries:
                    logger.warning(f"操作失败，第 {attempt + 1} 次重试，{self.retry_delay}秒后重试: {str(e)}")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"操作失败，已达到最大重试次数 {self.max_retries}")
                    self._log_connection_error(e)

        raise last_exception

    @contextmanager
    def get_connection(self):
        """从连接池获取连接的上下文管理器"""
        conn = None
        try:
            if PostgresDB._pool is None:
                self._init_connection_pool()

            conn = self._retry_operation(PostgresDB._pool.getconn)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                PostgresDB._pool.putconn(conn)

    def connect(self):
        """建立数据库连接（保持向后兼容）"""
        try:
            if PostgresDB._pool is None:
                self._init_connection_pool()

            self.conn = self._retry_operation(PostgresDB._pool.getconn)
            self.cursor = self.conn.cursor()
            logger.info("数据库连接建立成功")
        except Exception as e:
            self._log_connection_error(e)
            raise

    def disconnect(self):
        """关闭数据库连接（保持向后兼容）"""
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.conn:
            try:
                self.conn.rollback()
            except Exception as e:
                logger.debug(f"rollback 时忽略异常: {e}")
            if PostgresDB._pool:
                PostgresDB._pool.putconn(self.conn)
            else:
                self.conn.close()
            self.conn = None
            logger.info("数据库连接已关闭")

    @classmethod
    def close_all_connections(cls):
        """关闭所有连接池连接"""
        if cls._pool:
            cls._pool.closeall()
            cls._pool = None
            logger.info("所有数据库连接已关闭")

    def execute_batch(self, sql: str, params_list: List[Dict[str, Any]]):
        """执行批量SQL操作"""
        if not params_list:
            return

        def _execute_batch_operation():
            # 确保连接是打开的
            if not self.conn or self.conn.closed:
                self.connect()

            # 执行批量操作
            execute_batch(self.cursor, sql, params_list)
            self.conn.commit()
            logger.info(f"成功执行批量操作，共 {len(params_list)} 条数据")
            print(f"成功执行批量操作，共 {len(params_list)} 条数据")

        try:
            self._retry_operation(_execute_batch_operation)
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            logger.error(f"执行批量操作失败: {e}")
            print(f"执行批量操作失败: {e}")
            raise

    def execute(self, sql: str, params: Dict[str, Any] = None):
        """执行单条SQL操作"""

        def _execute_operation():
            # 确保连接是打开的
            if not self.conn or self.conn.closed:
                self.connect()

            # 执行SQL操作
            self.cursor.execute(sql, params)
            self.conn.commit()
            logger.debug("SQL执行成功")

        try:
            self._retry_operation(_execute_operation)
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            logger.error(f"SQL执行失败: {e}")
            print(f"SQL执行失败: {e}")
            raise

    def fetch_all(self, sql: str, params: Dict[str, Any] = None) -> List[tuple]:
        """执行查询并返回所有结果"""

        def _fetch_all_operation():
            # 确保连接是打开的
            if not self.conn or self.conn.closed:
                self.connect()

            # 执行查询
            self.cursor.execute(sql, params)
            return self.cursor.fetchall()

        try:
            return self._retry_operation(_fetch_all_operation)
        except Exception as e:
            if self.conn:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            logger.error(f"查询执行失败: {e}")
            print(f"查询执行失败: {e}")
            raise

    def fetch_one(self, sql: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行查询并返回单条结果（字典格式）"""

        def _fetch_one_operation():
            # 确保连接是打开的
            if not self.conn or self.conn.closed:
                self.connect()

            # 执行查询
            self.cursor.execute(sql, params)
            result = self.cursor.fetchone()

            if result is None:
                return None

            # 获取列名
            columns = [desc[0] for desc in self.cursor.description]
            # 将结果转换为字典
            return dict(zip(columns, result))

        try:
            return self._retry_operation(_fetch_one_operation)
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            print(f"查询执行失败: {e}")
            raise

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        if exc_type is not None:
            logger.error(f"上下文管理器中发生异常: {exc_val}")

    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态信息"""
        if PostgresDB._pool:
            return {
                'pool_exists': True,
                'min_conn': self.min_conn,
                'max_conn': self.max_conn,
                'database_host': self.conn_params.get('host', 'unknown'),
                'database_port': self.conn_params.get('port', 'unknown'),
                'database_name': self.conn_params.get('dbname', 'unknown')
            }
        else:
            return {
                'pool_exists': False,
                'database_host': self.conn_params.get('host', 'unknown'),
                'database_port': self.conn_params.get('port', 'unknown'),
                'database_name': self.conn_params.get('dbname', 'unknown')
            }