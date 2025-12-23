from typing import List, Dict
import json

from agent_server.communication import A2ACommunicator
from agent_server.communication.a2a import A2ASession
from agent_server.config import SCORING_WEIGHTS, PIPELINE_OPTIONS
from agent_server.teams.scoring import auto_score
from agent_server.a2a.cards import get_agent_card
from agent_server.agents.experts.utils.agent_result_store import get_store


class Debate:
    def __init__(self):
        self.c = A2ACommunicator()

    async def run(self, prompts: List[str]) -> List[str]:
        return await self.c.debate(prompts)


class Delphi:
    def __init__(self):
        self.c = A2ACommunicator()

    async def run(self, prompts: List[str]) -> List[str]:
        return await self.c.delphi(prompts)


class NVariant:
    def __init__(self):
        self.c = A2ACommunicator()

    async def run(self, prompts: List[str]) -> List[str]:
        return await self.c.n_variant(prompts)


class TeamOrchestrator:
    def __init__(self):
        self.session = A2ASession()

    async def run(self, mode: str, agents: List, query: str) -> Dict:
        if not agents or not isinstance(agents[0], dict):
            raise RuntimeError("Agents must be provided with cards for A2A communication")
        
        # 检查是否是多时间维度分析结果
        try:
            query_data = json.loads(query) if isinstance(query, str) else query
            if isinstance(query_data, dict) and "analysis_by_timeframe" in query_data:
                # 多时间维度分析：直接传递给 trading_decision
                return await self._run_multi_timeframe(mode, agents, query_data)
        except:
            pass
        
        # 单事件分析（原有逻辑）
        # 分离决策 Agent 和其他 Agent
        decision_agents = [a for a in agents if (a.get("name") or getattr(a["agent"], "name", "")) == "trading_decision"]
        analysis_agents = [a for a in agents if (a.get("name") or getattr(a["agent"], "name", "")) != "trading_decision"]
        analysis_names = [a.get("name") or getattr(a["agent"], "name", "agent") for a in analysis_agents]
        
        # 先执行分析 Agent（不包括决策 Agent）
        prompts = await self.session.broadcast(analysis_agents, query) if analysis_agents else []
        if mode == "debate":
            outputs = await Debate().run(prompts)
        elif mode == "delphi":
            outputs = await Delphi().run(prompts)
        elif mode == "n_variant":
            outputs = await NVariant().run(prompts)
        else:
            outputs = prompts
        import json
        scores = auto_score(outputs)
        outputs_scored: List[str] = []
        for i, t in enumerate(outputs):
            s = scores.get(i, 0.0)
            try:
                obj = json.loads(t)
                m = obj.get("metrics") or {}
                m["auto_score"] = s
                obj["metrics"] = m
                outputs_scored.append(json.dumps(obj, ensure_ascii=False))
            except Exception:
                obj = {
                    "agent": analysis_names[i] if i < len(analysis_names) else f"agent-{i}",
                    "task": "analysis",
                    "content": {"summary": (t or "")[:160], "details": t or ""},
                    "confidence": 0.0,
                    "rationale": "",
                    "metrics": {"auto_score": s},
                    "sources": [],
                    "tool_calls": [],
                    "timestamp": "",
                }
                outputs_scored.append(json.dumps(obj, ensure_ascii=False))
        outputs = outputs_scored
        
        # 保存分析 Agent 结果到 Redis
        try:
            # 尝试解析 query 为字典
            if isinstance(query, str):
                try:
                    payload_obj = json.loads(query)
                except (json.JSONDecodeError, ValueError):
                    # 如果解析失败，尝试从原始事件中提取
                    payload_obj = {"symbol": "unknown"}
            else:
                payload_obj = query if isinstance(query, dict) else {}
            
            event_id = payload_obj.get("event_id") or payload_obj.get("id") or payload_obj.get("symbol", "unknown")
            
            store = await get_store()
            for i, (name, output_str) in enumerate(zip(analysis_names, outputs)):
                try:
                    # 解析输出为字典
                    output_obj = json.loads(output_str) if isinstance(output_str, str) else output_str
                    
                    # 保存到 Redis
                    await store.save_agent_result(
                        event_id=str(event_id),
                        agent_name=name,
                        result=output_obj,
                        original_output=output_str if isinstance(output_str, str) else None
                    )
                except Exception as e:
                    print(f"⚠️  保存 {name} Agent 结果失败: {e}")
        except Exception as e:
            print(f"⚠️  保存 Agent 结果到 Redis 失败: {e}")
        
        from a2a.client import ClientFactory, ClientConfig
        from a2a.types import Message, Part, TextPart, Role, TransportProtocol
        options = PIPELINE_OPTIONS.get(mode, {"reflection": True, "fusion": True})
        refl_card = get_agent_card("reflection")
        config = ClientConfig(streaming=False, supported_transports=[TransportProtocol.jsonrpc], use_client_preference=False)
        factory = ClientFactory(config)
        refl_payload = json.dumps({"names": analysis_names, "outputs": outputs, "mode": mode}, ensure_ascii=False)
        if options.get("reflection", False):
            try:
                refl_client = factory.create(refl_card)
                reflection = None
                async for event in refl_client.send_message(Message(role=Role.user, parts=[Part(root=TextPart(text=refl_payload))])):
                    if hasattr(event, "parts"):
                        from a2a.utils import get_message_text
                        reflection = get_message_text(event)
                        break
                    break
                try:
                    refl_obj = json.loads(reflection or "{}")
                except Exception:
                    refl_obj = {}
            except Exception:
                rs = {}
                for i, t in enumerate(outputs):
                    n = analysis_names[i] if i < len(analysis_names) else f"agent-{i}"
                    rs[n] = min(1.0, max(0.0, len(t) / 1000.0))
                refl_obj = {"mode": mode, "reflection_scores": rs, "notes": []}
        else:
            refl_obj = {"mode": mode, "reflection_scores": {}, "notes": []}
        scores = scores
        fused = None
        weights = {}
        if options.get("fusion", True):
            fusion_card = get_agent_card("fusion")
            fus_client = factory.create(fusion_card)
            fus_payload = json.dumps({
                "names": analysis_names,
                "outputs": outputs,
                "base_weights": {n: SCORING_WEIGHTS.get(n, 0.0) for n in analysis_names},
                "reflection_scores": refl_obj.get("reflection_scores", {}),
                "auto_scores": scores,
            }, ensure_ascii=False)
            try:
                async for event in fus_client.send_message(Message(role=Role.user, parts=[Part(root=TextPart(text=fus_payload))])):
                    if hasattr(event, "parts"):
                        from a2a.utils import get_message_text
                        res = get_message_text(event)
                        try:
                            obj = json.loads(res)
                        except Exception:
                            obj = {}
                        fused = obj.get("fused")
                        weights = obj.get("weights") or {}
                        break
                    break
            except Exception:
                fused = None
            if fused is None:
                norm = sum(SCORING_WEIGHTS.get(n, 0.0) for n in analysis_names) or 1.0
                weights = {n: (SCORING_WEIGHTS.get(n, 0.0) / norm) for n in analysis_names}
                parts = []
                for i, t in enumerate(outputs):
                    n = analysis_names[i] if i < len(analysis_names) else f"agent-{i}"
                    parts.append(f"[{n}:{weights.get(n, 0.0):.2f}] {t}")
                fused = "\n".join(parts)
        else:
            fused = "\n".join(outputs)
            weights = {}
        try:
            payload_obj = json.loads(query) if isinstance(query, str) else query
        except Exception:
            payload_obj = {}
        
        trade_id = payload_obj.get("trade_id") or payload_obj.get("id") or payload_obj.get("symbol")
        event_id = payload_obj.get("event_id") or trade_id or "unknown"
        
        # 调用决策 Agent（如果团队中包含）
        trading_decision = None
        if decision_agents:
            try:
                decision_agent = decision_agents[0]["agent"]
                
                # 构建决策 Agent 的输入
                decision_input = {
                    "event_id": str(event_id),
                    "symbol": payload_obj.get("symbol", "BTCUSDT"),
                    "event_type": payload_obj.get("event_type"),
                    "event_level": payload_obj.get("event_level", 2),
                    "original_event": payload_obj,
                }
                
                # 调用决策 Agent
                decision_output = await decision_agent.run(json.dumps(decision_input, ensure_ascii=False))
                
                # 解析决策结果
                try:
                    trading_decision = json.loads(decision_output) if isinstance(decision_output, str) else decision_output
                except:
                    trading_decision = {"action": "hold", "error": "failed_to_parse_decision"}
                
                # 执行交易（如果不是保持不动）
                if trading_decision and trading_decision.get("action") != "hold":
                    try:
                        from agent_server.utils.trading_executor import get_executor
                        executor = await get_executor()
                        execution_result = await executor.execute_trade(trading_decision)
                        trading_decision["execution_result"] = execution_result
                    except Exception as e:
                        print(f"⚠️  执行交易失败: {e}")
                        trading_decision["execution_error"] = str(e)
                
            except Exception as e:
                print(f"⚠️  决策 Agent 执行失败: {e}")
                import traceback
                traceback.print_exc()
                trading_decision = {"action": "hold", "error": str(e)}
        
        # 保存到记忆（如果有 trade_id）
        if trade_id:
            try:
                from agent_server.memory.store import MemoryStore
                ms = MemoryStore()
                await ms.log_event(str(trade_id), {
                    "type": "a2a_analysis",
                    "payload": payload_obj,
                    "outputs": outputs,
                    "reflection": refl_obj,
                    "fusion": fused,
                    "weights": weights,
                    "trading_decision": trading_decision,
                })
            except Exception:
                pass
            try:
                mem_card = get_agent_card("memory")
                mem_client = factory.create(mem_card)
                mem_payload = json.dumps({
                    "trade_id": str(trade_id),
                    "fused": fused,
                    "outputs": outputs,
                    "reflection": refl_obj,
                    "weights": weights,
                    "event": payload_obj,
                    "trading_decision": trading_decision,
                }, ensure_ascii=False)
                async for _ in mem_client.send_message(Message(role=Role.user, parts=[Part(root=TextPart(text=mem_payload))])):
                    break
            except Exception:
                pass
        
        # 合并所有 Agent 名称（包括决策 Agent）
        all_names = analysis_names + (["trading_decision"] if decision_agents else [])
        
        return {
            "names": all_names,
            "outputs": outputs,
            "scores": scores,
            "reflection": refl_obj,
            "fusion": fused,
            "weights": weights,
            "trading_decision": trading_decision
        }
    
    async def _run_multi_timeframe(self, mode: str, agents: List, query_data: Dict) -> Dict:
        """处理多时间维度分析结果"""
        symbol = query_data.get("symbol", "BTCUSDT")
        analysis_by_timeframe = query_data.get("analysis_by_timeframe", {})
        base_event = query_data.get("base_event", {})
        
        # 整合各时间维度的结果
        all_names = set()
        all_outputs_by_timeframe = {}
        
        for timeframe, analysis_result in analysis_by_timeframe.items():
            if "error" in analysis_result:
                continue
            
            names = analysis_result.get("names", [])
            outputs = analysis_result.get("outputs", [])
            
            all_names.update(names)
            all_outputs_by_timeframe[timeframe] = {
                "names": names,
                "outputs": outputs,
                "scores": analysis_result.get("scores", {}),
                "weights": analysis_result.get("weights", {})
            }
        
        names = list(all_names)
        
        # 调用交易决策 Agent（传递多时间维度数据）
        decision_agents = [a for a in agents if (a.get("name") or getattr(a["agent"], "name", "")) == "trading_decision"]
        
        trading_decision = None
        if decision_agents:
            try:
                decision_agent = decision_agents[0]["agent"]
                
                # 将多时间维度数据传递给决策 Agent
                decision_input = json.dumps(query_data, ensure_ascii=False)
                decision_output = await decision_agent.run(decision_input)
                
                # 解析决策结果
                try:
                    trading_decision = json.loads(decision_output) if isinstance(decision_output, str) else decision_output
                except:
                    trading_decision = {"action": "hold", "error": "failed_to_parse_decision"}
                
                # 执行交易（如果不是保持不动）
                if trading_decision and trading_decision.get("action") != "hold":
                    try:
                        from agent_server.utils.trading_executor import get_executor
                        executor = await get_executor()
                        execution_result = await executor.execute_trade(trading_decision)
                        trading_decision["execution_result"] = execution_result
                    except Exception as e:
                        print(f"⚠️  执行交易失败: {e}")
                        trading_decision["execution_error"] = str(e)
                
            except Exception as e:
                print(f"⚠️  多时间维度决策 Agent 执行失败: {e}")
                import traceback
                traceback.print_exc()
                trading_decision = {"action": "hold", "error": str(e)}
        
        # 构建返回结果
        return {
            "names": names + (["trading_decision"] if decision_agents else []),
            "outputs": [],  # 多时间维度模式下，outputs 在各时间维度中
            "scores": {},
            "reflection": {"mode": mode, "reflection_scores": {}, "notes": []},
            "fusion": "",
            "weights": {},
            "trading_decision": trading_decision,
            "multi_timeframe": True,
            "analysis_by_timeframe": all_outputs_by_timeframe,
            "symbol": symbol,
            "base_event": base_event
        }