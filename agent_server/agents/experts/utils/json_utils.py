"""
JSON 工具函数
用于安全地处理 JSON 数据
"""
import json
import re
from typing import Any, Dict, Optional


def _extract_json_from_text(text: str) -> Optional[Dict]:
    """
    从文本中提取 JSON 对象
    
    Args:
        text: 可能包含 JSON 的文本
        
    Returns:
        提取的 JSON 字典，如果提取失败则返回 None
    """
    if not text or not isinstance(text, str):
        return None
    
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取 JSON 代码块
    # 匹配 ```json ... ``` 或 ``` ... ```
    json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(json_block_pattern, text, re.DOTALL)
    if matches:
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
    
    # 尝试提取第一个 { ... } 块
    brace_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(brace_pattern, text, re.DOTALL)
    if matches:
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
    
    return None


def _ensure_json_serializable(obj: Any) -> Any:
    """
    确保对象可 JSON 序列化
    将不可序列化的对象转换为可序列化的形式
    
    Args:
        obj: 要处理的对象
        
    Returns:
        可 JSON 序列化的对象
    """
    if obj is None:
        return None
    
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    if isinstance(obj, dict):
        return {k: _ensure_json_serializable(v) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple)):
        return [_ensure_json_serializable(item) for item in obj]
    
    # 处理其他类型
    if hasattr(obj, '__dict__'):
        return _ensure_json_serializable(obj.__dict__)
    
    if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
        try:
            return [_ensure_json_serializable(item) for item in obj]
        except TypeError:
            pass
    
    # 最后尝试转换为字符串
    try:
        return str(obj)
    except Exception:
        return None


def _json_dumps_safe(obj: Any, **kwargs) -> str:
    """
    安全地转储 JSON，处理不可序列化的对象
    
    Args:
        obj: 要转储的对象
        **kwargs: 传递给 json.dumps 的其他参数
        
    Returns:
        JSON 字符串
    """
    # 确保对象可序列化
    serializable_obj = _ensure_json_serializable(obj)
    
    # 设置默认参数
    default_kwargs = {
        "ensure_ascii": False,
        "indent": None,
        "separators": (",", ":")
    }
    default_kwargs.update(kwargs)
    
    try:
        return json.dumps(serializable_obj, **default_kwargs)
    except (TypeError, ValueError) as e:
        # 如果还是失败，返回错误信息
        return json.dumps({"error": f"JSON serialization failed: {str(e)}", "raw": str(obj)}, **default_kwargs)

