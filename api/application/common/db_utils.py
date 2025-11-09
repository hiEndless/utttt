import psycopg2
from psycopg2.extras import execute_batch
from typing import List, Dict, Any
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

class PostgresDB:
    def __init__(self):
        self.conn_params = {
            'dbname': os.getenv('DB_DATABASE'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'host': os.getenv('DB_HOST'),
            'port': os.getenv('DB_PORT')
        }
        self.conn = None
        self.cursor = None

    def connect(self):
        """建立数据库连接"""
        try:
            self.conn = psycopg2.connect(**self.conn_params)
            self.cursor = self.conn.cursor()
        except Exception as e:
            print(f"数据库连接失败: {e}")
            raise

    def disconnect(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            # print("数据库连接已关闭")

    def execute_batch(self, sql: str, params_list: List[Dict[str, Any]]):
        """执行批量SQL操作"""
        if not params_list:
            return

        try:
            # 确保连接是打开的
            if not self.conn or self.conn.closed:
                self.connect()

            # 执行批量操作
            execute_batch(self.cursor, sql, params_list)
            self.conn.commit()
            print(f"成功执行批量操作，共 {len(params_list)} 条数据")

        except Exception as e:
            self.conn.rollback()
            print(f"执行批量操作失败: {e}")
            raise

    def execute(self, sql: str, params: Dict[str, Any] = None):
        """执行单条SQL操作"""
        try:
            # 确保连接是打开的
            if not self.conn or self.conn.closed:
                self.connect()

            # 执行SQL操作
            self.cursor.execute(sql, params)
            self.conn.commit()
            # print("SQL执行成功")

        except Exception as e:
            self.conn.rollback()
            print(f"SQL执行失败: {e}")
            raise

    def fetch_all(self, sql: str, params: Dict[str, Any] = None) -> List[tuple]:
        """执行查询并返回所有结果"""
        try:
            # 确保连接是打开的
            if not self.conn or self.conn.closed:
                self.connect()

            # 执行查询
            self.cursor.execute(sql, params)
            return self.cursor.fetchall()

        except Exception as e:
            print(f"查询执行失败: {e}")
            raise

    def fetch_one(self, sql: str, params: Dict[str, Any] = None) -> tuple:
        """执行查询并返回单条结果"""
        try:
            # 确保连接是打开的
            if not self.conn or self.conn.closed:
                self.connect()

            # 执行查询
            self.cursor.execute(sql, params)
            return self.cursor.fetchone()

        except Exception as e:
            print(f"查询执行失败: {e}")
            raise

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()