"""
交易决策 Agent
综合分析所有 Agent 的结果，生成标准化的交易决策
"""
import json
from typing import Dict, Any, Optional
from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
from agent_server.configs.prompts.trading_decision import prompt
from agent_server.agents.experts.utils.agent_result_store import get_store
from agent_server.agents.experts.utils import (
    _extract_json_from_text,
    _ensure_json_serializable,
    _json_dumps_safe,
)


class TradingDecisionExpert:
    name = "trading_decision"

    async def run(self, query: str) -> str:
        """
        执行交易决策分析
        
        Args:
            query: JSON 字符串，包含事件信息
                {
                    "event_id": "...",
                    "symbol": "BTCUSDT",
                    "event_type": "...",
                    "event_level": 2,
                    "original_event": {...}
                }
        
        Returns:
            JSON 字符串，包含交易决策
        """
        try:
            # 解析输入
            if isinstance(query, str):
                try:
                    query_data = json.loads(query)
                except:
                    query_data = {"raw": query}
            else:
                query_data = query
            
            event_id = query_data.get("event_id") or query_data.get("id") or "unknown"
            symbol = query_data.get("symbol", "BTCUSDT")
            
            # 从 Redis 加载所有 Agent 结果
            store = await get_store()
            agent_results = await store.get_agent_results(str(event_id))
            
            if not agent_results:
                # 如果没有结果，返回保持不动
                return json.dumps({
                    "action": "hold",
                    "symbol": symbol,
                    "confidence": 0.0,
                    "rationale": "未找到 Agent 分析结果",
                    "error": "no_agent_results"
                }, ensure_ascii=False)
            
            # 调用 LLM 进行决策分析
            cfg = get_agent_config(self.name)
            model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
            base_url = cfg.get("llm_base_url")
            api_key = cfg.get("llm_api_key")
            
            model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)
            
            # 构建 prompt
            prompt = self._build_decision_prompt(query_data, agent_results)
            
            agent = Agent(
                model=model,
                instructions=prompt,
            )
            
            # 调用 LLM
            from agno.models.message import Message
            run_output = await agent.arun(
                Message(role="user", content=prompt),
                stream=False,
                debug_mode=True,
            )
            
            content = run_output.content
            
            # 解析输出
            if isinstance(content, str):
                try:
                    decision = json.loads(content)
                except json.JSONDecodeError:
                    extracted = _extract_json_from_text(content)
                    if extracted is not None:
                        decision = extracted
                    else:
                        decision = self._fallback_decision(query_data, agent_results)
            elif hasattr(content, "model_dump"):
                decision = content.model_dump(exclude_none=True)
            else:
                decision = self._fallback_decision(query_data, agent_results)
            
            # 格式化决策
            formatted_decision = self._format_decision(decision, query_data, agent_results)
            
            return _json_dumps_safe(formatted_decision)
            
        except Exception as e:
            print(f"❌ 交易决策失败: {e}")
            import traceback
            traceback.print_exc()
            # 返回保持不动的决策
            return json.dumps({
                "action": "hold",
                "symbol": query_data.get("symbol", "BTCUSDT") if 'query_data' in locals() else "BTCUSDT",
                "confidence": 0.0,
                "rationale": f"决策生成失败: {str(e)}",
                "error": str(e)
            }, ensure_ascii=False)
    
    
    def _build_decision_prompt(self, query_data: Dict, agent_results: Dict) -> str:
        """构建决策 prompt"""
        prompt_parts = []
        
        # 事件信息
        prompt_parts.append("## 事件信息")
        prompt_parts.append(json.dumps({
            "event_id": query_data.get("event_id"),
            "symbol": query_data.get("symbol"),
            "event_type": query_data.get("event_type"),
            "event_level": query_data.get("event_level"),
        }, indent=2, ensure_ascii=False))
        
        # Agent 结果
        prompt_parts.append("\n## Agent 分析结果")
        for agent_name, result_data in agent_results.items():
            prompt_parts.append(f"\n### {agent_name} Agent")
            result = result_data.get("result", {})
            prompt_parts.append(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 原始事件数据（如果有）
        if "original_event" in query_data:
            prompt_parts.append("\n## 原始事件数据")
            prompt_parts.append(json.dumps(query_data["original_event"], indent=2, ensure_ascii=False))
        
        prompt_parts.append("\n\n请根据以上信息，生成交易决策。")
        
        return "\n".join(prompt_parts)
    
    def _fallback_decision(self, query_data: Dict, agent_results: Dict) -> Dict:
        """备用决策逻辑（当 LLM 失败时）"""
        symbol = query_data.get("symbol", "BTCUSDT")
        
        # 简单的规则引擎
        buy_signals = 0
        sell_signals = 0
        total_confidence = 0.0
        count = 0
        
        for agent_name, result_data in agent_results.items():
            result = result_data.get("result", {})
            
            # 尝试提取信号
            content = result.get("content", {})
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except:
                    pass
            
            # 检查是否有 action 或 signal
            action = result.get("action") or content.get("action") or result.get("action_suggestion")
            confidence = float(result.get("confidence", 0.0) or 0.0)
            
            if action in ("buy", "open", "long"):
                buy_signals += 1
                total_confidence += confidence
                count += 1
            elif action in ("sell", "close", "short"):
                sell_signals += 1
                total_confidence += confidence
                count += 1
        
        avg_confidence = total_confidence / count if count > 0 else 0.0
        
        # 决策逻辑
        if buy_signals > sell_signals and avg_confidence >= 0.7:
            return {
                "action": "open",
                "positionSide": "LONG",
                "side": "BUY",
                "confidence": avg_confidence,
                "rationale": f"基于 {buy_signals} 个买入信号，平均置信度 {avg_confidence:.2f}"
            }
        elif sell_signals > buy_signals and avg_confidence >= 0.7:
            return {
                "action": "close",
                "positionSide": "LONG",
                "side": "SELL",
                "confidence": avg_confidence,
                "rationale": f"基于 {sell_signals} 个卖出信号，平均置信度 {avg_confidence:.2f}"
            }
        else:
            return {
                "action": "hold",
                "confidence": avg_confidence,
                "rationale": "信号不明确或置信度不足，保持不动"
            }
    
    def _format_decision(self, decision: Dict, query_data: Dict, agent_results: Dict) -> Dict:
        """格式化决策为标准化格式"""
        symbol = query_data.get("symbol", "BTCUSDT")
        event_level = int(query_data.get("event_level", 2))
        
        # 获取当前价格（从原始事件或 Agent 结果中）
        current_price = None
        
        # 方法1: 直接从 query_data 获取（因为 payload 已经被展开）
        if "close" in query_data:
            try:
                current_price = float(query_data["close"])
            except (ValueError, TypeError):
                pass
        
        # 方法2: 从 original_event 获取
        if not current_price and "original_event" in query_data:
            original_event = query_data["original_event"]
            if isinstance(original_event, dict):
                # 先尝试直接从 original_event 获取
                if "close" in original_event:
                    try:
                        current_price = float(original_event["close"])
                    except (ValueError, TypeError):
                        pass
                
                # 再尝试从 payload 中获取
                if not current_price:
                    payload = original_event.get("payload", {})
                    if isinstance(payload, dict):
                        if "close" in payload:
                            try:
                                current_price = float(payload["close"])
                            except (ValueError, TypeError):
                                pass
                        if not current_price and "price" in payload:
                            try:
                                current_price = float(payload["price"])
                            except (ValueError, TypeError):
                                pass
        
        # 方法3: 从 Agent 结果中获取
        if not current_price:
            for result_data in agent_results.values():
                result = result_data.get("result", {})
                metrics = result.get("metrics", {})
                if isinstance(metrics, dict):
                    if "close" in metrics:
                        try:
                            current_price = float(metrics["close"])
                            break
                        except (ValueError, TypeError):
                            pass
                    if "Current_Price" in metrics:
                        try:
                            current_price = float(metrics["Current_Price"])
                            break
                        except (ValueError, TypeError):
                            pass
                    if "Close_Price" in metrics:
                        try:
                            current_price = float(metrics["Close_Price"])
                            break
                        except (ValueError, TypeError):
                            pass
        
        if not current_price:
            current_price = 0.0
            print(f"⚠️  无法获取当前价格，使用默认值 0.0")
            print(f"   query_data keys: {list(query_data.keys())}")
            if "original_event" in query_data:
                print(f"   original_event keys: {list(query_data['original_event'].keys()) if isinstance(query_data['original_event'], dict) else 'not dict'}")
        
        # 处理 LLM 返回的各种格式
        # 1. 如果有 "decision" 字段，转换为 "action"
        decision_text = decision.get("decision", "").lower()
        action = decision.get("action", "hold")
        
        if not action or action == "hold":
            # 从 decision 文本中提取 action
            if "short" in decision_text or "sell" in decision_text or "bearish" in decision_text:
                # 判断是开仓还是平仓
                # "conditional_short" 应该被理解为开空仓
                if "conditional" in decision_text or "initiate" in decision_text or "open" in decision_text or "enter" in decision_text:
                    action = "open"
                    position_side = "SHORT"
                    side = "SELL"
                elif "close" in decision_text or "exit" in decision_text:
                    action = "close"
                    position_side = "LONG"  # 平多仓
                    side = "SELL"
                else:
                    # 默认：bearish 信号 → 开空仓
                    action = "open"
                    position_side = "SHORT"
                    side = "SELL"
            elif "long" in decision_text or "buy" in decision_text or "bullish" in decision_text:
                if "initiate" in decision_text or "open" in decision_text or "enter" in decision_text:
                    action = "open"
                    position_side = "LONG"
                    side = "BUY"
                else:
                    action = "close"
                    position_side = "SHORT"  # 平空仓
                    side = "BUY"
            elif "hold" in decision_text or "wait" in decision_text or "maintain" in decision_text:
                action = "hold"
            else:
                # 默认根据信号方向判断
                original_event = query_data.get("original_event", {})
                payload = original_event.get("payload", {}) if isinstance(original_event, dict) else {}
                signal_side = payload.get("side", "").lower()
                if signal_side == "bearish":
                    action = "open"
                    position_side = "SHORT"
                    side = "SELL"
                elif signal_side == "bullish":
                    action = "open"
                    position_side = "LONG"
                    side = "BUY"
                else:
                    action = "hold"
        
        # 处理 rationale（可能是字符串或字典）
        rationale = decision.get("rationale", "")
        if isinstance(rationale, dict):
            rationale = " | ".join([f"{k}: {v}" for k, v in rationale.items()])
        
        # 构建标准决策格式
        formatted = {
            "action": action,
            "symbol": symbol,
            "confidence": float(decision.get("confidence", 0.0)),
            "rationale": rationale,
            "risk_level": decision.get("risk_level", "medium"),
            "event_id": query_data.get("event_id"),
            "event_level": event_level,
        }
        
        # 如果是开仓或平仓，添加交易相关字段
        if action in ("open", "close"):
            # 从 decision 中提取 entry 信息
            entry = decision.get("entry", {})
            
            # 提取止损止盈价格
            stop_loss = None
            take_profit = None
            
            if isinstance(entry, dict):
                # 从 entry.target 和 entry.stoploss 提取
                target_text = str(entry.get("target", ""))
                stoploss_text = str(entry.get("stoploss", ""))
                
                # 尝试从文本中提取数字
                import re
                if target_text:
                    numbers = re.findall(r'\d+\.?\d*', target_text)
                    if numbers:
                        take_profit = float(numbers[0])
                if stoploss_text:
                    numbers = re.findall(r'\d+\.?\d*', stoploss_text)
                    if numbers:
                        stop_loss = float(numbers[0])
            
            # 如果没有从 entry 提取到，尝试直接从 decision 获取
            if not stop_loss:
                stop_loss = decision.get("stop_loss")
                if stop_loss:
                    stop_loss = float(stop_loss)
            if not take_profit:
                take_profit = decision.get("take_profit")
                if take_profit:
                    take_profit = float(take_profit)
            
            # 计算止损止盈（如果没有提供）
            if not stop_loss and action == "open":
                # 默认止损：当前价格的 -1% 到 -2%
                stop_loss = current_price * 0.98
            if not take_profit and action == "open":
                # 默认止盈：当前价格的 +1% 到 +3%
                take_profit = current_price * 1.02
            
            formatted.update({
                "positionSide": decision.get("positionSide") or position_side if 'position_side' in locals() else ("LONG" if action == "open" else "SHORT"),
                "side": decision.get("side") or side if 'side' in locals() else ("BUY" if action == "open" else "SELL"),
                "leverage": float(decision.get("leverage", 5.0)),
                "sums": str(decision.get("sums", "0.1")),
                "openAvgPx": float(decision.get("openAvgPx") or entry.get("price", current_price) if isinstance(entry, dict) else current_price),
            })
            
            # 添加止损止盈
            if stop_loss:
                formatted["stop_loss"] = stop_loss
            if take_profit:
                formatted["take_profit"] = take_profit
        
        # 添加 Agent 结果摘要
        formatted["agent_summary"] = {
            name: {
                "confidence": result_data.get("result", {}).get("confidence", 0.0),
                "action_suggestion": result_data.get("result", {}).get("action") or result_data.get("result", {}).get("action_suggestion", "unknown")
            }
            for name, result_data in agent_results.items()
        }
        
        return formatted

