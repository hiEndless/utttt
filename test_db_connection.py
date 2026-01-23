#!/usr/bin/env python3
"""
数据库连接验证脚本
用于测试 PostgreSQL 数据库连接的正确性
"""

import os
import sys
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
from contextlib import contextmanager
import time

# 加载环境变量
load_dotenv()

def get_db_config():
    """获取数据库配置"""
    config = {
        'dbname': os.getenv('DB_DATABASE'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'host': os.getenv('DB_HOST'),
        'port': os.getenv('DB_PORT', '5432')
    }
    return config

def print_config(config):
    """打印配置信息（隐藏密码）"""
    print("=" * 60)
    print("数据库配置信息:")
    print(f"  主机: {config.get('host', '未设置')}")
    print(f"  端口: {config.get('port', '未设置')}")
    print(f"  数据库: {config.get('dbname', '未设置')}")
    print(f"  用户: {config.get('user', '未设置')}")
    print(f"  密码: {'*' * len(config.get('password', '')) if config.get('password') else '未设置'}")
    print("=" * 60)

def check_config_complete(config):
    """检查配置是否完整"""
    required = ['host', 'dbname', 'user', 'password']
    missing = [key for key in required if not config.get(key)]
    if missing:
        print(f"错误: 缺少必要的配置项: {', '.join(missing)}")
        return False
    return True

def test_direct_connection(config):
    """测试直接连接"""
    print("\n[测试 1] 直接连接测试")
    print("-" * 60)
    try:
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        # 测试查询
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✓ 连接成功!")
        print(f"  PostgreSQL 版本: {version.split(',')[0]}")
        
        # 测试当前数据库
        cursor.execute("SELECT current_database(), current_user;")
        db_name, db_user = cursor.fetchone()
        print(f"  当前数据库: {db_name}")
        print(f"  当前用户: {db_user}")
        
        cursor.close()
        conn.close()
        return True
    except psycopg2.OperationalError as e:
        print(f"✗ 连接失败: {e}")
        return False
    except Exception as e:
        print(f"✗ 发生错误: {e}")
        return False

def test_connection_pool(config):
    """测试连接池"""
    print("\n[测试 2] 连接池测试")
    print("-" * 60)
    try:
        connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            **config
        )
        
        # 从连接池获取连接
        conn = connection_pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()
        print(f"✓ 连接池创建成功!")
        print(f"  测试查询结果: {result[0]}")
        
        cursor.close()
        connection_pool.putconn(conn)
        connection_pool.closeall()
        return True
    except Exception as e:
        print(f"✗ 连接池测试失败: {e}")
        return False

def test_basic_operations(config):
    """测试基本操作"""
    print("\n[测试 3] 基本操作测试")
    print("-" * 60)
    try:
        conn = psycopg2.connect(**config)
        conn.autocommit = False
        cursor = conn.cursor()
        
        # 测试查询
        cursor.execute("SELECT NOW();")
        now = cursor.fetchone()[0]
        print(f"✓ 查询操作成功: {now}")
        
        # 测试事务
        cursor.execute("SELECT 1 + 1;")
        result = cursor.fetchone()[0]
        print(f"✓ 事务操作成功: 1 + 1 = {result}")
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"✗ 基本操作测试失败: {e}")
        return False

def test_table_access(config):
    """测试表访问（如果存在）"""
    print("\n[测试 4] 表访问测试")
    print("-" * 60)
    try:
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        # 列出所有表
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
            LIMIT 10;
        """)
        tables = cursor.fetchall()
        
        if tables:
            print(f"✓ 找到 {len(tables)} 个表（显示前10个）:")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("  数据库中没有表")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"✗ 表访问测试失败: {e}")
        return False

def test_connection_with_context_manager(config):
    """测试使用上下文管理器"""
    print("\n[测试 5] 上下文管理器测试")
    print("-" * 60)
    try:
        @contextmanager
        def get_connection():
            conn = psycopg2.connect(**config)
            try:
                yield conn
            finally:
                conn.close()
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 'context_manager_test';")
            result = cursor.fetchone()[0]
            print(f"✓ 上下文管理器测试成功: {result}")
            cursor.close()
        
        return True
    except Exception as e:
        print(f"✗ 上下文管理器测试失败: {e}")
        return False

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("数据库连接验证脚本")
    print("=" * 60)
    
    # 获取配置
    config = get_db_config()
    print_config(config)
    
    # 检查配置完整性
    if not check_config_complete(config):
        sys.exit(1)
    
    # 转换端口为整数
    if config.get('port'):
        try:
            config['port'] = int(config['port'])
        except ValueError:
            print(f"错误: 端口号无效: {config['port']}")
            sys.exit(1)
    
    # 执行测试
    results = []
    
    results.append(("直接连接", test_direct_connection(config)))
    time.sleep(0.5)
    
    results.append(("连接池", test_connection_pool(config)))
    time.sleep(0.5)
    
    results.append(("基本操作", test_basic_operations(config)))
    time.sleep(0.5)
    
    results.append(("表访问", test_table_access(config)))
    time.sleep(0.5)
    
    results.append(("上下文管理器", test_connection_with_context_manager(config)))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 个通过, {failed} 个失败")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ 所有测试通过！数据库连接正常。")
        sys.exit(0)
    else:
        print("\n✗ 部分测试失败，请检查数据库配置和连接。")
        sys.exit(1)

if __name__ == "__main__":
    main()
