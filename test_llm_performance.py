#!/usr/bin/env python3
"""
LLM 性能测试脚本
用于测试 LLM API 调用的响应时间和性能
支持批量测试多个模型并生成对比报告
"""

import asyncio
import time
import sys
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agno.models.message import Message

# 优先从环境变量读取，否则从配置文件读取，最后使用默认值
def get_modelscope_config():
    """获取 ModelScope 配置"""
    base_url = os.getenv("MODELSCOPE_BASE_URL", "https://api-inference.modelscope.cn/v1")
    api_key = os.getenv("MODELSCOPE_API_KEY")
    
    # 如果环境变量没有，尝试从 source.py 读取
    if not api_key:
        try:
            from agent_server.configs.source import query_db_env
            cfg = query_db_env()
            # 从任意一个 agent 配置中获取（它们都使用相同的 key）
            if cfg and "technical" in cfg:
                api_key = cfg["technical"].get("llm_api_key")
        except Exception:
            pass
    
    # 如果还是没有，使用硬编码的默认值（可能已过期）
    if not api_key:
        api_key = "ms-b3ea64d3-5c65-4146-aec9-5dddd1cb5ee7"
    
    return {
        "base_url": base_url,
        "api_key": api_key,
    }

# 从 llm_configs.py 导入模型配置
try:
    from llm_configs import (
        MODELSCOPE_CONFIG,
        REQUIRED_MODELS,
        TOP_QUANTITATIVE_MODELS
    )
except ImportError:
    # 如果导入失败，使用函数获取配置
    MODELSCOPE_CONFIG = get_modelscope_config()
    REQUIRED_MODELS = {}
    TOP_QUANTITATIVE_MODELS = {}


# 推荐的测试模型列表（从配置文件中提取）
RECOMMENDED_TEST_MODELS = [
    # {
    #     "name": "DeepSeek-V3.2",
    #     "model_id": "deepseek-ai/DeepSeek-V3.2",
    #     "type": "快速响应",
    #     "description": "快速分析、实时决策"
    # },
    {
        "name": "Qwen3-235B-Instruct",
        "model_id": "Qwen/Qwen3-235B-A22B-Instruct-2507",
        "type": "质量最高",
        "description": "深度分析、策略制定"
    }
    # {
    #     "name": "DeepSeek-R1-Qwen-32B",
    #     "model_id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
    #     "type": "推理展示",
    #     "description": "突破分析、推理展示（当前使用）"
    # },
    # {
    #     "name": "DeepSeek-R1-0528",
    #     "model_id": "deepseek-ai/DeepSeek-R1-0528",
    #     "type": "最新版本",
    #     "description": "复杂策略、最新版本"
    # },
    # {
    #     "name": "Qwen3-235B-Thinking",
    #     "model_id": "Qwen/Qwen3-235B-A22B-Thinking-2507",
    #     "type": "思考模型",
    #     "description": "深度分析、思考展示"
    # },
]


class LLMPerformanceTester:
    def __init__(self, model_id: str, model_name: str = "", base_url: str = None, api_key: str = None):
        self.model_id = model_id
        self.model_name = model_name or model_id
        
        # 确保使用最新的配置
        current_config = get_modelscope_config()
        self.base_url = base_url or os.getenv("MODELSCOPE_BASE_URL") or current_config["base_url"]
        self.api_key = api_key or os.getenv("MODELSCOPE_API_KEY") or current_config["api_key"]
        
        if not self.api_key or self.api_key.startswith("ms-") and len(self.api_key) < 40:
            print(f"⚠️  警告: API Key 可能无效或已过期: {self.api_key[:20]}...")
        
        # 初始化模型和Agent
        self.model = OpenAILike(
            id=self.model_id,
            base_url=self.base_url,
            api_key=self.api_key
        )
        self.agent = Agent(model=self.model)
    
    async def test_single_call(self, query: str, verbose: bool = True) -> Dict:
        """测试单次LLM调用"""
        if verbose:
            print(f"\n{'='*60}")
            print(f"📊 测试模型: {self.model_name}")
            print(f"   Model ID: {self.model_id}")
            print(f"{'='*60}")
        
        # 记录时间
        start_time = time.time()
        connection_time = None
        response_time = None
        
        try:
            # 测试连接和调用
            connection_start = time.time()
            message = Message(role="user", content=query)
            connection_time = time.time() - connection_start
            
            response_start = time.time()
            resp = await self.agent.arun(message, stream=False)
            response_time = time.time() - response_start
            
            total_time = time.time() - start_time
            
            # 获取响应内容
            content = str(resp.content) if hasattr(resp, 'content') else str(resp)
            content_length = len(content)
            
            # 尝试提取推理内容（如果有）
            reasoning_content = ""
            if hasattr(resp, 'reasoning_content') and resp.reasoning_content:
                reasoning_content = str(resp.reasoning_content)
            elif hasattr(resp, 'thinking_content') and resp.thinking_content:
                reasoning_content = str(resp.thinking_content)
            
            result = {
                "success": True,
                "model_name": self.model_name,
                "model_id": self.model_id,
                "total_time": total_time,
                "connection_time": connection_time,
                "response_time": response_time,
                "content_length": content_length,
                "content": content,
                "content_preview": content[:300] + "..." if len(content) > 300 else content,
                "reasoning_content": reasoning_content,
                "has_reasoning": bool(reasoning_content),
                "error": None
            }
            
            if verbose:
                print(f"✅ 调用成功")
                print(f"⏱️  总耗时: {total_time:.2f} 秒")
                print(f"🔌 连接时间: {connection_time:.4f} 秒")
                print(f"💬 响应时间: {response_time:.2f} 秒")
                print(f"📝 响应长度: {content_length} 字符")
                if reasoning_content:
                    print(f"🧠 推理内容: {len(reasoning_content)} 字符")
                print(f"\n响应预览:\n{result['content_preview']}")
            
            return result
            
        except Exception as e:
            total_time = time.time() - start_time
            result = {
                "success": False,
                "model_name": self.model_name,
                "model_id": self.model_id,
                "total_time": total_time,
                "connection_time": connection_time,
                "response_time": response_time,
                "content_length": 0,
                "content": "",
                "content_preview": "",
                "reasoning_content": "",
                "has_reasoning": False,
                "error": str(e)
            }
            
            if verbose:
                print(f"\n❌ 调用失败")
                print(f"⏱️  总耗时: {total_time:.2f} 秒")
                print(f"❌ 错误信息: {str(e)}")
            
            return result


async def test_all_models(query: str, models: List[Dict] = None, save_results: bool = True):
    """批量测试所有推荐模型"""
    if models is None:
        models = RECOMMENDED_TEST_MODELS
    
    print(f"\n{'='*80}")
    print(f"🚀 批量测试 {len(models)} 个模型")
    print(f"{'='*80}")
    print(f"测试查询长度: {len(query)} 字符")
    print(f"测试查询预览:\n{query[:200]}...")
    print(f"{'='*80}\n")
    
    results = []
    start_time = time.time()
    
    for i, model_config in enumerate(models, 1):
        print(f"\n[{i}/{len(models)}] 测试模型: {model_config['name']}")
        print(f"   类型: {model_config.get('type', 'N/A')}")
        print(f"   描述: {model_config.get('description', 'N/A')}")
        
        tester = LLMPerformanceTester(
            model_id=model_config['model_id'],
            model_name=model_config['name']
        )
        
        result = await tester.test_single_call(query, verbose=True)
        result['type'] = model_config.get('type', '')
        result['description'] = model_config.get('description', '')
        results.append(result)
        
        # 每个模型测试后稍作延迟，避免API限流
        if i < len(models):
            await asyncio.sleep(1)
    
    total_test_time = time.time() - start_time
    
    # 生成对比报告
    print_comparison_report(results, total_test_time)
    
    # 保存结果
    if save_results:
        save_test_results(results, query)
    
    return results


def print_comparison_report(results: List[Dict], total_test_time: float):
    """打印对比报告"""
    print(f"\n\n{'='*80}")
    print(f"📊 模型对比报告")
    print(f"{'='*80}\n")
    
    # 按响应时间排序
    successful_results = [r for r in results if r["success"]]
    failed_results = [r for r in results if not r["success"]]
    
    if successful_results:
        successful_results.sort(key=lambda x: x["response_time"])
        
        print(f"✅ 成功测试: {len(successful_results)}/{len(results)} 个模型\n")
        
        # 性能对比表
        print(f"{'='*80}")
        print(f"⏱️  性能对比（按响应时间排序）")
        print(f"{'='*80}")
        print(f"{'模型名称':<25} {'类型':<12} {'响应时间':<12} {'总耗时':<12} {'内容长度':<12} {'推理':<8}")
        print(f"{'-'*80}")
        
        for r in successful_results:
            reasoning_mark = "✅" if r.get("has_reasoning") else "❌"
            print(f"{r['model_name']:<25} {r.get('type', ''):<12} "
                  f"{r['response_time']:>8.2f}s  {r['total_time']:>8.2f}s  "
                  f"{r['content_length']:>8}  {reasoning_mark:<8}")
        
        # 速度排名
        print(f"\n{'='*80}")
        print(f"🏆 速度排名（从快到慢）")
        print(f"{'='*80}")
        for i, r in enumerate(successful_results, 1):
            print(f"{i}. {r['model_name']:<25} - {r['response_time']:.2f}秒")
        
        # 内容质量对比
        print(f"\n{'='*80}")
        print(f"📝 内容质量对比")
        print(f"{'='*80}")
        for r in successful_results:
            print(f"\n【{r['model_name']}】({r.get('type', 'N/A')})")
            print(f"响应时间: {r['response_time']:.2f}秒 | 内容长度: {r['content_length']}字符")
            if r.get("has_reasoning"):
                print(f"🧠 包含推理过程: {len(r.get('reasoning_content', ''))} 字符")
            print(f"内容预览:\n{r['content_preview']}")
            print(f"{'-'*80}")
    
    if failed_results:
        print(f"\n{'='*80}")
        print(f"❌ 失败模型")
        print(f"{'='*80}")
        for r in failed_results:
            print(f"{r['model_name']}: {r.get('error', 'Unknown error')}")
    
    # 统计信息
    print(f"\n{'='*80}")
    print(f"📈 统计信息")
    print(f"{'='*80}")
    print(f"总测试时间: {total_test_time:.2f} 秒")
    print(f"成功: {len(successful_results)}/{len(results)}")
    print(f"失败: {len(failed_results)}/{len(results)}")
    
    if successful_results:
        avg_time = sum(r["response_time"] for r in successful_results) / len(successful_results)
        min_time = min(r["response_time"] for r in successful_results)
        max_time = max(r["response_time"] for r in successful_results)
        print(f"平均响应时间: {avg_time:.2f} 秒")
        print(f"最快: {min_time:.2f} 秒 ({successful_results[0]['model_name']})")
        print(f"最慢: {max_time:.2f} 秒 ({successful_results[-1]['model_name']})")
        print(f"速度差异: {max_time/min_time:.2f}x")


def save_test_results(results: List[Dict], query: str):
    """保存测试结果到文件"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"llm_performance_test_{timestamp}.json"
        
        output = {
            "test_time": timestamp,
            "test_query": query,
            "total_models": len(results),
            "successful": len([r for r in results if r["success"]]),
            "failed": len([r for r in results if not r["success"]]),
            "results": results
        }
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 测试结果已保存: {filename}")
        
    except Exception as e:
        print(f"⚠️  保存结果失败: {e}")


async def main():
    """主函数"""
    print("🚀 LLM 性能批量测试工具")
    print("="*80)
    
    # 解析参数
    # 格式: python test_llm_performance.py [single|all] [model_name|model_id]
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    # 测试查询（模拟实际的技术分析查询）
    test_query = """请分析以下技术指标数据：

时间维度: 1m
- KDJ: K=53.3, D=45.3, J=69.3 (bullish)
- MACD: -0.0000046
- EMA20: 0.0687, EMA50: 0.0689, EMA200: 0.0690
- 支撑位: 0.0681, 阻力位: 0.0714

时间维度: 5m
- KDJ: K=39.2, D=42.8, J=31.9 (bearish)
- MACD: -0.0000936
- EMA20: 0.0690, EMA50: 0.0685, EMA200: 0.0622

请给出简要的技术分析结论（50字以内）。"""
    
    if mode.lower() == "all":
        # 批量测试所有推荐模型
        await test_all_models(test_query)
    elif mode.lower() == "single":
        # 测试单个模型
        model_id = sys.argv[2] if len(sys.argv) > 2 else RECOMMENDED_TEST_MODELS[0]['model_id']
        model_name = sys.argv[3] if len(sys.argv) > 3 else model_id
        
        tester = LLMPerformanceTester(model_id=model_id, model_name=model_name)
        result = await tester.test_single_call(test_query, verbose=True)
    else:
        # 使用模型名称或ID测试
        model_id = mode
        model_name = sys.argv[2] if len(sys.argv) > 2 else model_id
        
        tester = LLMPerformanceTester(model_id=model_id, model_name=model_name)
        result = await tester.test_single_call(test_query, verbose=True)
    
    print(f"\n{'='*80}")
    print("✅ 测试完成")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    # 使用示例:
    # python test_llm_performance.py all                    # 批量测试所有推荐模型
    # python test_llm_performance.py single deepseek-ai/DeepSeek-V3.2  # 测试单个模型
    # python test_llm_performance.py deepseek-ai/DeepSeek-V3.2        # 直接测试指定模型
    
    asyncio.run(main())
