import os
from dataclasses import dataclass


@dataclass
class Config:
    redis_host: str = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "1"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    raw_stream: str = os.getenv("RAW_STREAM", "raw_event_stream")
    l0_stream: str = os.getenv("L0_STREAM", "l0_events")
    l1_stream: str = os.getenv("L1_STREAM", "l1_events")
    final_stream: str = os.getenv("FINAL_STREAM", "final_events")

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


cfg = Config()