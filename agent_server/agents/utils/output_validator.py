import logging
from typing import Any, Dict, List, Optional, Union, Type, Callable

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """验证失败且无法自动修复时抛出的异常。"""
    pass


class LLMOutputValidator:
    def __init__(self, schema: Dict[str, Any]):
        """
        使用 schema 初始化验证器。
        
        Schema 格式:
        {
            "field_name": {
                "type": type or str,  # 例如: str, int, "string", "integer"
                "required": bool,     # 默认 True
                "description": str,   # 用于错误信息
                "options": list,      # 有效值列表 (枚举)
                "range": (min, max),  # 数值范围
                "schema": dict,       # 嵌套 object 的子 schema（递归校验并按子 schema 严格裁剪字段）
                "case_sensitive": bool # 键名是否大小写敏感 (默认为 False，由验证器逻辑处理)
            }
        }
        """
        self.schema = schema

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证并尝试自动修复数据。
        如果成功，返回修复后的数据。
        如果发现严重错误，抛出 ValidationError。
        """
        if not isinstance(data, dict):
            raise ValidationError(f"输出必须是字典类型，实际类型: {type(data)}")

        if not self.schema:
            return data

        fixed_data = {}
        errors = []

        # 创建输入数据键的大小写不敏感映射
        data_keys_map = {k.lower(): k for k in data.keys()}

        for field, rules in self.schema.items():
            field_lower = field.lower()
            required = rules.get("required", True)

            # 1. 检查字段是否存在 (不区分大小写)
            if field_lower in data_keys_map:
                original_key = data_keys_map[field_lower]
                value = data[original_key]

                # 自动修复：使用 schema 中定义的正确字段名
                final_key = field
            else:
                if required:
                    errors.append(f"缺少必填字段: '{field}'")
                continue

            # 如果找到了字段，进行验证
            try:
                fixed_value = self._validate_value(value, rules, field)
                fixed_data[final_key] = fixed_value
            except ValidationError as e:
                errors.append(str(e))
            except Exception as e:
                errors.append(f"字段 '{field}' 发生意外错误: {str(e)}")

        if errors:
            raise ValidationError("; ".join(errors))

        # 是否保留额外字段？
        # 目前，为了安全起见（严格模式），我们只返回 schema 中定义的字段。
        # 如果需要允许额外字段，可以在此处进行合并。
        # 用户需求：“防止不符的字段”。这可能意味着严格的 schema。
        # 因此，我将坚持只返回经过验证的字段以确保安全。

        return fixed_data

    def _validate_value(self, value: Any, rules: Dict, field_name: str) -> Any:
        # 类型检查和转换
        expected_type = rules.get("type")
        if expected_type:
            value = self._ensure_type(value, expected_type, field_name)

        # 选项 (枚举) 检查
        options = rules.get("options")
        if options and value not in options:
            # 尝试对字符串进行不区分大小写的匹配
            if isinstance(value, str) and all(isinstance(o, str) for o in options):
                found = False
                for opt in options:
                    if value.lower() == opt.lower():
                        value = opt
                        found = True
                        break
                if not found:
                    raise ValidationError(f"字段 '{field_name}' 的值 '{value}' 不在选项中: {options}")
            else:
                raise ValidationError(f"字段 '{field_name}' 的值 '{value}' 不在选项中: {options}")

        # 范围检查
        val_range = rules.get("range")
        if val_range:
            min_val, max_val = val_range
            if value < min_val or value > max_val:
                raise ValidationError(f"字段 '{field_name}' 的值 {value} 超出范围 [{min_val}, {max_val}]")

        # 嵌套 object 校验：当字段是 dict 且提供了子 schema 时，递归验证并裁剪多余字段
        nested_schema = rules.get("schema")
        if nested_schema is not None:
            if not isinstance(value, dict):
                raise ValidationError(f"字段 '{field_name}' 期望类型 dict, 实际得到 {type(value)}")
            if not isinstance(nested_schema, dict):
                raise ValidationError(f"字段 '{field_name}' 的 schema 必须是 dict, 实际得到 {type(nested_schema)}")
            value = LLMOutputValidator(nested_schema).validate(value)

        return value

    def _ensure_type(self, value: Any, target_type: Any, field_name: str) -> Any:
        # 处理字符串类型的类型名称
        if isinstance(target_type, str):
            type_map = {
                "str": str, "string": str,
                "int": int, "integer": int,
                "float": float, "number": float,
                "bool": bool, "boolean": bool,
                "list": list, "array": list,
                "dict": dict, "object": dict
            }
            target_type = type_map.get(target_type.lower(), target_type)

        # 如果类型已经正确
        if isinstance(value, target_type):
            return value

        # 粗略处理 Optional/Union 类型 (如果 target_type 是元组)
        if isinstance(target_type, tuple):
            if isinstance(value, target_type):
                return value
            # 尝试转换为第一个？不，太复杂了。
            # 如果都不匹配则失败。
            raise ValidationError(f"字段 '{field_name}' 期望类型 {target_type}, 实际得到 {type(value)}")

        # 尝试转换
        try:
            if target_type == int:
                return int(float(value))  # 处理 "1.0" 为 1
            elif target_type == float:
                return float(value)
            elif target_type == str:
                return str(value)
            elif target_type == bool:
                if isinstance(value, str):
                    if value.lower() in ('true', 'yes', '1', 'on'): return True
                    if value.lower() in ('false', 'no', '0', 'off'): return False
                return bool(value)
            elif target_type == list:
                if isinstance(value, (str, int, float, bool)):
                    return [value]  # 自动包装单个项目？为了安全起见可能报错更好。
                    # 用户说“简单的错误可以修复”。
                    # 除非我们确定，否则对列表包装保持保守。
                pass
        except Exception:
            pass

        raise ValidationError(
            f"字段 '{field_name}' 期望类型 {target_type.__name__ if hasattr(target_type, '__name__') else target_type}, 实际得到 {type(value)}")


async def validate_with_retry(
        llm_runner: Callable[[], Any],
        validator: LLMOutputValidator,
        max_retries: int = 3,
        on_retry: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """
    运行 LLM 任务并验证其输出，支持重试的辅助函数。
    """
    import asyncio
    import json
    from .json_utils import _extract_json_from_text
    from json_repair import repair_json

    last_error = None

    for i in range(max_retries):
        try:
            # 检查 llm_runner 是否为异步函数
            if asyncio.iscoroutinefunction(llm_runner):
                raw_output = await llm_runner()
            else:
                raw_output = llm_runner()
                if asyncio.iscoroutine(raw_output):
                    raw_output = await raw_output

            # 1. 解析 JSON
            data = None
            if isinstance(raw_output, str):
                try:
                    data = json.loads(raw_output)
                except json.JSONDecodeError:
                    # 优先使用 regex 提取（在 _extract_json_from_text 内部已集成 repair_json fallback）
                    extracted = _extract_json_from_text(raw_output)
                    if extracted is not None:
                        data = extracted
                    else:
                        # 最后尝试对原始字符串直接修复
                        try:
                            data = repair_json(raw_output, return_objects=True, skip_json_loads=True)
                        except Exception:
                            raise ValidationError(f"无法从输出中解析 JSON: {raw_output[:100]}...")
            elif isinstance(raw_output, dict):
                data = raw_output
            elif hasattr(raw_output, 'model_dump'):
                data = raw_output.model_dump()
            else:
                # 尝试强制转换为字符串
                try:
                    s = str(raw_output)
                    extracted = _extract_json_from_text(s)
                    if extracted is not None:
                        data = extracted
                    else:
                        raise ValidationError(f"意外的输出类型: {type(raw_output)}")
                except:
                    raise ValidationError(f"意外的输出类型: {type(raw_output)}")

            # 2. 验证
            return validator.validate(data)

        except ValidationError as e:
            last_error = e
            if on_retry:
                on_retry(f"验证失败 (尝试 {i + 1}/{max_retries}): {e}")
            # 可选: 增加延迟或指数退避？
            # 用户需求只是“重新生成”。

        except Exception as e:
            last_error = e
            if on_retry:
                on_retry(f"意外错误 (尝试 {i + 1}/{max_retries}): {e}")

    if last_error:
        raise last_error
    raise ValidationError("超过最大重试次数且无具体错误信息")
