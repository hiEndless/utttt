"""
Agent 结果存储模块
统一管理 Agent 分析结果的存储和读取
"""
import json
import os
from typing import Dict, List, Optional, Any
import redis.asyncio as aioredis
from datetime import datetime


class AgentResultStore:
    """Agent 结果存储管理器"""
    
    def __init__(self):
        # Redis 配置
        self.redis_host = os.getenv("REDIS_HOST", "38.147.173.111")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", "112233Ww..")
        self.redis_db = int(os.getenv("REDIS_DB", "8"))
        
        # 配置
        self.key_prefix = "agent_results"
        self.ttl = int(os.getenv("AGENT_RESULT_TTL", "3600"))  # 默认 1 小时
        
        self.redis: Optional[aioredis.Redis] = None
    
    async def _get_redis(self) -> aioredis.Redis:
        """获取 Redis 连接（懒加载）"""
        if self.redis is None:
            self.redis = aioredis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                db=self.redis_db,
                decode_responses=True
            )
        return self.redis
    
    def _get_key(self, event_id: str, agent_name: str) -> str:
        """生成存储 key"""
        return f"{self.key_prefix}:{event_id}:{agent_name}"
    
    def _get_event_key(self, event_id: str) -> str:
        """生成事件相关的 key 前缀"""
        return f"{self.key_prefix}:{event_id}:*"
    
    async def save_agent_result(
        self, 
        event_id: str, 
        agent_name: str, 
        result: Dict[str, Any],
        original_output: Optional[str] = None
    ) -> bool:
        """
        保存 Agent 结果到 Redis
        
        Args:
            event_id: 事件ID
            agent_name: Agent 名称
            result: Agent 结果（字典）
            original_output: 原始输出字符串（可选）
            
        Returns:
            是否保存成功
        """
        try:
            redis = await self._get_redis()
            
            # 构建存储数据
            store_data = {
                "event_id": event_id,
                "agent_name": agent_name,
                "timestamp": int(datetime.now().timestamp() * 1000),
                "result": result,
            }
            
            if original_output:
                store_data["original_output"] = original_output
            
            # 保存到 Redis
            key = self._get_key(event_id, agent_name)
            await redis.set(
                key,
                json.dumps(store_data, ensure_ascii=False),
                ex=self.ttl
            )
            
            # 记录事件ID到集合中（用于快速查找）
            event_set_key = f"{self.key_prefix}:events:{event_id}"
            await redis.sadd(event_set_key, agent_name)
            await redis.expire(event_set_key, self.ttl)
            
            return True
            
        except Exception as e:
            print(f"❌ 保存 Agent 结果失败: {e}")
            return False
    
    async def get_agent_result(self, event_id: str, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定 Agent 的结果
        
        Args:
            event_id: 事件ID
            agent_name: Agent 名称
            
        Returns:
            Agent 结果，如果不存在则返回 None
        """
        try:
            redis = await self._get_redis()
            key = self._get_key(event_id, agent_name)
            
            data = await redis.get(key)
            if not data:
                return None
            
            return json.loads(data)
            
        except Exception as e:
            print(f"❌ 获取 Agent 结果失败: {e}")
            return None
    
    async def get_agent_results(self, event_id: str) -> Dict[str, Dict[str, Any]]:
        """
        获取事件的所有 Agent 结果
        
        Args:
            event_id: 事件ID
            
        Returns:
            字典，key 为 agent_name，value 为 Agent 结果
        """
        try:
            redis = await self._get_redis()
            
            # 获取该事件的所有 Agent 名称
            event_set_key = f"{self.key_prefix}:events:{event_id}"
            agent_names = await redis.smembers(event_set_key)
            
            if not agent_names:
                return {}
            
            # 获取所有 Agent 的结果
            results = {}
            for agent_name in agent_names:
                result = await self.get_agent_result(event_id, agent_name)
                if result:
                    results[agent_name] = result
            
            return results
            
        except Exception as e:
            print(f"❌ 获取所有 Agent 结果失败: {e}")
            return {}
    
    async def clear_agent_results(self, event_id: str) -> bool:
        """
        清除事件的所有 Agent 结果
        
        Args:
            event_id: 事件ID
            
        Returns:
            是否清除成功
        """
        try:
            redis = await self._get_redis()
            
            # 获取该事件的所有 Agent 名称
            event_set_key = f"{self.key_prefix}:events:{event_id}"
            agent_names = await redis.smembers(event_set_key)
            
            # 删除所有 Agent 结果
            for agent_name in agent_names:
                key = self._get_key(event_id, agent_name)
                await redis.delete(key)
            
            # 删除事件集合
            await redis.delete(event_set_key)
            
            return True
            
        except Exception as e:
            print(f"❌ 清除 Agent 结果失败: {e}")
            return False
    
    async def list_agent_names(self, event_id: str) -> List[str]:
        """
        列出事件的所有 Agent 名称
        
        Args:
            event_id: 事件ID
            
        Returns:
            Agent 名称列表
        """
        try:
            redis = await self._get_redis()
            event_set_key = f"{self.key_prefix}:events:{event_id}"
            agent_names = await redis.smembers(event_set_key)
            return list(agent_names) if agent_names else []
            
        except Exception as e:
            print(f"❌ 列出 Agent 名称失败: {e}")
            return []
    
    async def close(self):
        """关闭 Redis 连接"""
        if self.redis:
            await self.redis.aclose()
            self.redis = None


# 全局实例
_store_instance: Optional[AgentResultStore] = None


async def get_store() -> AgentResultStore:
    """获取全局存储实例"""
    global _store_instance
    if _store_instance is None:
        _store_instance = AgentResultStore()
    return _store_instance
