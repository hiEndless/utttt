#!/usr/bin/env python3
"""
获取Binance交易历史数据脚本
用于分析交易agent的问题
"""

import os
import sys
import json
import time
import hmac
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Dict, List, Optional
import requests
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量（.env文件）
load_dotenv()

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class BinanceTradeHistoryFetcher:
    """Binance交易历史数据获取器"""
    
    def __init__(self, api_key: str, api_secret: str, is_testnet: bool = True):
        """
        初始化
        
        Args:
            api_key: Binance API Key
            api_secret: Binance API Secret
            is_testnet: 是否使用测试网（默认True）
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_testnet = is_testnet
        
        if is_testnet:
            self.base_url = "https://demo.binance.com"
        else:
            self.base_url = "https://fapi.binance.com"
    
    def _sign_params(self, params: Dict) -> str:
        """HMAC-SHA256签名"""
        query_string = urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None, max_retries: int = 3) -> Dict:
        """
        发送API请求（带重试机制）
        
        Args:
            endpoint: API端点路径
            params: 请求参数
            max_retries: 最大重试次数
            
        Returns:
            API响应数据
        """
        if params is None:
            params = {}
        
        # 添加时间戳
        params['timestamp'] = int(time.time() * 1000)
        
        # 签名
        signature = self._sign_params(params)
        params['signature'] = signature
        
        # 构建URL
        url = f"{self.base_url}{endpoint}"
        
        # 请求头
        headers = {
            'X-MBX-APIKEY': self.api_key,
            'Content-Type': 'application/json'
        }
        
        # 重试机制
        last_exception = None
        for attempt in range(max_retries):
            try:
                # 直接连接，不使用代理
                proxies = None
                
                response = requests.get(
                    url, 
                    params=params, 
                    headers=headers, 
                    timeout=(10, 30),  # (connect_timeout, read_timeout)
                    proxies=proxies
                )
                response.raise_for_status()
                
                # 检查响应内容
                if not response.text:
                    print(f"⚠️  警告: API返回空响应")
                    return []
                
                # 检查是否是非JSON响应（如代理返回的 "ok"）
                content_type = response.headers.get('Content-Type', '').lower()
                response_text = response.text.strip().lower()
                
                # 调试信息
                if response.status_code == 200 and response_text == 'ok':
                    print(f"⚠️  警告: 代理或防火墙返回了非API响应")
                    print(f"   响应状态码: {response.status_code}")
                    print(f"   Content-Type: {content_type}")
                    print(f"   响应: {response.text}")
                    print(f"   请求URL: {url}")
                    print(f"   请求参数: {params}")
                    print(f"   响应头: {dict(response.headers)}")
                    print(f"   提示: 可能是代理健康检查响应，或请求被拦截")
                    raise ValueError(f"代理返回了非API响应: {response.text}")
                
                # 尝试解析JSON
                try:
                    return response.json()
                except json.JSONDecodeError as json_err:
                    print(f"⚠️  JSON解析失败: {json_err}")
                    print(f"   响应状态码: {response.status_code}")
                    print(f"   响应内容类型: {response.headers.get('Content-Type', 'unknown')}")
                    print(f"   响应内容（前500字符）: {response.text[:500]}")
                    # 如果看起来像HTML（可能是WAF挑战页面）
                    if response.text.strip().startswith('<'):
                        print(f"   提示: 响应似乎是HTML，可能是WAF挑战页面")
                    raise
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"⚠️  连接失败，{wait_time}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ API连接失败: {self.base_url}")
                    print(f"   错误: {e}")
                    print(f"   提示: 请检查网络连接，或设置代理环境变量 HTTP_PROXY/HTTPS_PROXY")
                    raise
            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"⚠️  请求超时，{wait_time}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ API请求超时: {self.base_url}")
                    print(f"   提示: 请检查网络连接或增加超时时间")
                    raise
            except requests.exceptions.HTTPError as e:
                # HTTP错误（如4xx, 5xx）
                print(f"⚠️  API HTTP错误: {e.response.status_code} {e}")
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        if e.response.text:
                            error_msg = e.response.json()
                            print(f"   错误详情: {json.dumps(error_msg, ensure_ascii=False, indent=2)}")
                        else:
                            print(f"   响应体为空")
                    except (json.JSONDecodeError, ValueError):
                        # 如果不是JSON，打印原始响应
                        print(f"   响应状态码: {e.response.status_code}")
                        print(f"   响应内容（前500字符）: {e.response.text[:500]}")
                raise
            except requests.exceptions.RequestException as e:
                # 其他请求错误
                print(f"⚠️  API请求失败: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        if e.response.text:
                            error_msg = e.response.json()
                            print(f"   响应内容: {json.dumps(error_msg, ensure_ascii=False, indent=2)}")
                    except (json.JSONDecodeError, ValueError):
                        print(f"   响应状态码: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}")
                        print(f"   响应内容: {str(e)[:200]}")
                raise
        
        # 所有重试都失败
        raise last_exception
    
    def get_all_orders(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000,
        order_id: Optional[int] = None
    ) -> List[Dict]:
        """
        获取所有订单（包括历史订单）
        
        Args:
            symbol: 交易对（必需）
            start_time: 开始时间（毫秒时间戳）
            end_time: 结束时间（毫秒时间戳）
            limit: 返回数量限制（默认500，最大1000）
            order_id: 只返回此orderID及之后的订单
            
        Returns:
            订单列表
        """
        # 使用币安官方API: GET /fapi/v1/allOrders
        endpoint = "/fapi/v1/allOrders"
        
        params = {
            'symbol': symbol,
            'limit': min(limit, 1000)
        }
        
        if order_id:
            params['orderId'] = order_id
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        result = self._make_request(endpoint, params)
        
        # 返回格式：直接是列表
        if isinstance(result, list):
            return result
        
        # 如果格式不符合预期，打印调试信息
        print(f"⚠️  未识别的响应格式: {type(result)}")
        if isinstance(result, dict):
            print(f"响应内容: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
        
        return []
    
    def get_all_orders_by_symbols(
        self,
        symbols: List[str],
        days: int = 7
    ) -> List[Dict]:
        """
        获取指定天数内的所有订单（支持多个交易对）
        
        Args:
            symbols: 交易对列表（必需）
            days: 查询天数（默认7天，最大7天）
            
        Returns:
            所有订单列表
        """
        all_orders = []
        end_time = int(time.time() * 1000)
        start_time = int((time.time() - days * 24 * 3600) * 1000)
        
        # 限制查询时间范围最大7天
        if days > 7:
            days = 7
            start_time = int((time.time() - days * 24 * 3600) * 1000)
        
        print(f"开始获取订单历史...")
        print(f"时间范围: {datetime.fromtimestamp(start_time/1000)} 至 {datetime.fromtimestamp(end_time/1000)}")
        print(f"交易对: {', '.join(symbols) if symbols else '全部'}")
        
        for symbol in symbols:
            try:
                print(f"\n查询交易对: {symbol}...")
                
                # 每次查询最多7天，如果超过7天需要分批查询
                current_start = start_time
                batch_size = 1000
                
                while current_start < end_time:
                    current_end = min(current_start + 7 * 24 * 3600 * 1000, end_time)  # 每次查询7天
                    
                    orders = self.get_all_orders(
                        symbol=symbol,
                        start_time=current_start,
                        end_time=current_end,
                        limit=batch_size
                    )
                    
                    if orders:
                        all_orders.extend(orders)
                        print(f"  获取到 {len(orders)} 条订单 (总计: {len(all_orders)})")
                    else:
                        print(f"  该时间段无订单")
                    
                    # 如果返回数量少于limit，说明已经获取完
                    if len(orders) < batch_size:
                        break
                    
                    # 更新时间范围
                    current_start = current_end + 1
                    
                    # 避免请求过快
                    time.sleep(0.5)
                
            except Exception as e:
                # 打印详细错误信息
                error_msg = str(e)
                print(f"  获取订单失败: {error_msg}")
                # 如果错误信息不包含详细内容，尝试获取更多信息
                if hasattr(e, '__cause__') and e.__cause__:
                    print(f"    原因: {e.__cause__}")
                if hasattr(e, '__context__') and e.__context__:
                    ctx_msg = str(e.__context__)
                    if "错误详情" not in error_msg and "Invalid API-key" in ctx_msg:
                        print(f"    详细错误: {ctx_msg}")
                continue
        
        return all_orders
    
    def save_to_file(self, trades: List[Dict], output_file: Optional[str] = None):
        """
        保存交易数据到文件
        
        Args:
            trades: 交易列表
            output_file: 输出文件路径（可选）
        """
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"agent_server/logs/trade_history_{timestamp}.json"
        
        # 确保目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # 保存数据
        output_data = {
            "fetch_time": datetime.now().isoformat(),
            "total": len(trades),
            "trades": trades
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n交易数据已保存到: {output_file}")
        print(f"总计: {len(trades)} 条交易记录")
        
        return output_file


def get_api_credentials_from_env() -> tuple:
    """从环境变量获取API凭证（支持os.environ和.env文件）"""
    # 优先从os.environ获取（conda环境变量）
    api_key = os.environ.get('BINANCE_API_KEY') or os.getenv('BINANCE_API_KEY')
    api_secret = os.environ.get('BINANCE_API_SECRET') or os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        raise ValueError("请设置环境变量 BINANCE_API_KEY 和 BINANCE_API_SECRET")
    
    return api_key, api_secret


def get_api_credentials_from_db(api_id: int = 2) -> tuple:
    """
    从数据库获取API凭证
    
    Args:
        api_id: API ID（默认2）
        
    Returns:
        (api_key, api_secret) 元组
    """
    try:
        # 尝试使用项目中的 PostgresDB 类（api/application/common/db_utils.py）
        try:
            from api.application.common.db_utils import PostgresDB
            
            db = PostgresDB()
            db.connect()
            
            # 执行查询
            db.cursor.execute(
                "SELECT flag, \"passPhrase\", api_key, secret_key FROM api_apiinfo WHERE id = %s",
                (api_id,)
            )
            result = db.cursor.fetchone()
            
            db.disconnect()
            
            if not result:
                raise ValueError(f"数据库中未找到 api_id={api_id} 的API信息")
            
            # 获取列名
            columns = [desc[0] for desc in db.cursor.description] if hasattr(db.cursor, 'description') else None
            if columns:
                result_dict = dict(zip(columns, result))
            else:
                # 如果没有列名，按顺序获取
                result_dict = {
                    'flag': result[0] if len(result) > 0 else None,
                    'passPhrase': result[1] if len(result) > 1 else None,
                    'api_key': result[2] if len(result) > 2 else None,
                    'secret_key': result[3] if len(result) > 3 else None
                }
            
            api_key = result_dict.get('api_key')
            api_secret = result_dict.get('secret_key')
            
        except (ImportError, AttributeError):
            # 如果无法导入PostgresDB，使用psycopg2直接连接
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            db_config = {
                'host': os.getenv('DB_HOST', '127.0.0.1'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'apeyes'),
                'dbname': os.getenv('DB_DATABASE', 'utaker')
            }
            
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(
                'SELECT flag, "passPhrase", api_key, secret_key FROM api_apiinfo WHERE id = %s',
                (api_id,)
            )
            result_dict = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if not result_dict:
                raise ValueError(f"数据库中未找到 api_id={api_id} 的API信息")
            
            api_key = result_dict.get('api_key')
            api_secret = result_dict.get('secret_key')
        
        if not api_key or not api_secret:
            raise ValueError(f"API信息不完整: api_id={api_id}")
        
        flag = result_dict.get('flag', 'unknown')
        print(f"从数据库获取API凭证成功: api_id={api_id}, flag={flag} (0=实盘, 1=模拟盘)")
        return api_key, api_secret
        
    except ImportError as e:
        raise ValueError(f"需要安装依赖库: {e}\n请运行: pip install psycopg2-binary python-dotenv")
    except Exception as e:
        raise ValueError(f"从数据库获取API凭证失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='获取Binance交易历史数据')
    parser.add_argument('--api-key', type=str, help='Binance API Key')
    parser.add_argument('--api-secret', type=str, help='Binance API Secret')
    parser.add_argument('--api-id', type=int, help='从数据库获取API凭证（API ID，如2）')
    parser.add_argument('--symbol', type=str, required=True, help='交易对（必需，如BTCUSDT，支持多个用逗号分隔）')
    parser.add_argument('--days', type=int, default=7, help='查询天数（默认7天）')
    parser.add_argument('--output', type=str, help='输出文件路径（可选）')
    parser.add_argument('--testnet', action='store_true', default=True, help='使用测试网（默认）')
    parser.add_argument('--mainnet', action='store_true', help='使用主网')
    
    args = parser.parse_args()
    
    # 获取API凭证（优先级：命令行参数 > 数据库 > 环境变量）
    api_key = None
    api_secret = None
    
    if args.api_key and args.api_secret:
        api_key = args.api_key
        api_secret = args.api_secret
        print("✓ 使用命令行参数提供的API凭证")
    elif args.api_id:
        try:
            api_key, api_secret = get_api_credentials_from_db(args.api_id)
            print("✓ 从数据库获取API凭证成功")
        except ValueError as e:
            print(f"⚠️  从数据库获取API凭证失败: {e}")
            print("\n尝试从环境变量获取...")
            try:
                api_key, api_secret = get_api_credentials_from_env()
                print("✓ 使用环境变量提供的API凭证")
            except ValueError:
                print("❌ 环境变量也未设置")
                print("\n请使用以下方式之一提供API凭证:")
                print("1. 设置环境变量: export BINANCE_API_KEY=xxx BINANCE_API_SECRET=xxx")
                print("2. 使用命令行参数: --api-key xxx --api-secret xxx")
                print("3. 检查数据库连接配置（DB_HOST, DB_PORT等）")
                return
    else:
        try:
            api_key, api_secret = get_api_credentials_from_env()
            print("✓ 使用环境变量提供的API凭证")
        except ValueError as e:
            print(f"❌ 错误: {e}")
            print("\n请使用以下方式之一提供API凭证:")
            print("1. 设置环境变量: export BINANCE_API_KEY=xxx BINANCE_API_SECRET=xxx")
            print("2. 使用命令行参数: --api-key xxx --api-secret xxx")
            print("3. 从数据库获取: --api-id 2")
            return
    
    # 判断是否使用测试网
    is_testnet = not args.mainnet
    
    # 限制查询天数最大7天
    if args.days > 7:
        print(f"⚠️  查询天数最大为7天，已调整为7天")
        args.days = 7
    
    # 检查是否提供了交易对
    if not args.symbol:
        print("❌ 错误: 必须提供交易对 (--symbol)")
        print("   示例: python -m agent_server.utils.fetch_trade_history --symbol BTCUSDT --days 7")
        return
    
    # 创建获取器
    fetcher = BinanceTradeHistoryFetcher(api_key, api_secret, is_testnet=is_testnet)
    
    # 获取订单历史
    symbols = [s.strip().upper() for s in args.symbol.split(',')]  # 支持多个交易对，用逗号分隔
    
    try:
        orders = fetcher.get_all_orders_by_symbols(symbols, days=args.days)
    except Exception as e:
        print(f"\n❌ 获取订单失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        print(f"\n详细错误信息:")
        traceback.print_exc()
        orders = []
    
    if not orders:
        print("\n" + "="*80)
        print("⚠️  未获取到订单记录")
        print("="*80)
        print("\n可能的原因:")
        print("1. API 权限不足（需要启用 'Enable Reading' 和 'USER_DATA' 权限）")
        print("2. IP 白名单限制（需要在币安 API 设置中添加当前 IP 或关闭白名单）")
        print("3. API Key/Secret 错误")
        print("4. 指定时间段内确实没有订单")
        print(f"\n当前请求 IP: 请查看上方错误信息中的 'request ip' 字段")
        return
    
    # 保存到文件
    output_file = fetcher.save_to_file(orders, args.output)
    
    # 打印统计信息（基于订单数据）
    print("\n=== 订单统计 ===")
    symbol_stats = {}
    buy_count = 0
    sell_count = 0
    status_count = {}
    
    for order in orders:
        symbol = order.get('symbol', 'UNKNOWN')
        if symbol not in symbol_stats:
            symbol_stats[symbol] = {
                'count': 0,
                'buy_count': 0,
                'sell_count': 0,
                'filled_qty': 0,
                'filled_quote': 0,
                'avg_price': 0,
                'statuses': {}
            }
        
        symbol_stats[symbol]['count'] += 1
        
        # 判断买卖方向
        side = order.get('side', '').upper()
        if side == 'BUY':
            symbol_stats[symbol]['buy_count'] += 1
            buy_count += 1
        elif side == 'SELL':
            symbol_stats[symbol]['sell_count'] += 1
            sell_count += 1
        
        # 订单状态
        status = order.get('status', 'UNKNOWN')
        if status not in status_count:
            status_count[status] = 0
        status_count[status] += 1
        
        if status not in symbol_stats[symbol]['statuses']:
            symbol_stats[symbol]['statuses'][status] = 0
        symbol_stats[symbol]['statuses'][status] += 1
        
        # 累计成交量（已成交的）
        executed_qty = float(order.get('executedQty', 0))
        cum_quote = float(order.get('cumQuote', 0))  # 成交金额
        avg_price = float(order.get('avgPrice', 0))
        
        symbol_stats[symbol]['filled_qty'] += executed_qty
        symbol_stats[symbol]['filled_quote'] += cum_quote
        
        # 更新平均价格（如果有成交）
        if executed_qty > 0 and avg_price > 0:
            symbol_stats[symbol]['avg_price'] = avg_price
    
    # 打印按交易对的统计
    print(f"\n总订单数: {len(orders)} 笔 (买入: {buy_count}, 卖出: {sell_count})")
    print(f"\n订单状态分布:")
    for status, count in sorted(status_count.items()):
        print(f"  {status}: {count}")
    
    print(f"\n按交易对统计:")
    print("-" * 80)
    
    for symbol, stats in sorted(symbol_stats.items()):
        print(f"{symbol}:")
        print(f"  订单数: {stats['count']} (买:{stats['buy_count']}, 卖:{stats['sell_count']})")
        print(f"  已成交量: {stats['filled_qty']:.6f}, 成交金额: {stats['filled_quote']:.2f} USDT")
        if stats['filled_qty'] > 0:
            calculated_avg = stats['filled_quote'] / stats['filled_qty'] if stats['filled_qty'] > 0 else 0
            print(f"  平均价格: {calculated_avg:.2f} USDT")
        print(f"  状态分布: {', '.join([f'{k}({v})' for k, v in stats['statuses'].items()])}")
        print()
    
    print("-" * 80)
    print(f"\n详细数据已保存到: {output_file}")


if __name__ == "__main__":
    main()

