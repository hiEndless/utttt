from abc import ABC, abstractmethod
from typing import List

class Plugin(ABC):
    # ===== 必须声明的依赖 =====
    name: str = ""
    tf_scope: List[str] = []
    indicators: List[str] = []
    requires_prev: bool = False

    @abstractmethod
    def generate(self, indicator_view: dict) -> list:
        """
        输入：裁剪后的指标视图
        输出：Factor / Score / Event（中间态）
        """
        pass
