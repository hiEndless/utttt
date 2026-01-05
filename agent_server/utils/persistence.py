import json
import time
import os
from typing import Any, Dict
from agent_server.config import settings
from agent_server.utils.redis_client import RedisClient


class WorkflowPersistence:
    @staticmethod
    async def save_trace(workflow_id: str, trace_data: Dict[str, Any]):
        """
        Persists the workflow execution trace.
        """
        # 1. Save to Redis Stream for real-time monitoring/replay
        try:
            rc = RedisClient()
            await rc.xadd(
                "workflow_traces",
                {"workflow_id": workflow_id, "data": json.dumps(trace_data, ensure_ascii=False)},
                maxlen=10000
            )
        except Exception as e:
            print(f"[Persistence] Redis save failed: {e}")

        # 2. Save to local file (as a backup/log)
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "traces")
            os.makedirs(log_dir, exist_ok=True)

            # Group by date
            date_str = time.strftime("%Y-%m-%d")
            file_path = os.path.join(log_dir, f"trace_{date_str}.jsonl")

            record = {
                "ts": int(time.time() * 1000),
                "workflow_id": workflow_id,
                "trace": trace_data
            }

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        except Exception as e:
            print(f"[Persistence] File save failed: {e}")
