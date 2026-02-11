import json
from typing import Dict, List, Optional
try:
    from utils.redis_client import get_redis_client
except ImportError:
    from .redis_client import get_redis_client


class RedisStreamWriter:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 2,
        stream_key: str = "raw_events",
        decode_responses: bool = True,
    ):
        self.stream_key = stream_key
        # 使用统一的 Redis 客户端管理，避免连接数过多
        self.client = get_redis_client(db=db, decode_responses=decode_responses)

    async def write(self, event: Dict) -> str:
        data = dict(event)
        if isinstance(data.get("payload"), (dict, list)):
            data["payload"] = json.dumps(data["payload"], ensure_ascii=False)
        return await self.client.xadd(self.stream_key, data)

    async def write_many(self, events: List[Dict]) -> List[str]:
        ids = []
        for e in events:
            ids.append(await self.write(e))
        return ids