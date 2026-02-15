# trade_decision LLM 通道配置参考

> 用于切换分支时快速恢复配置。**第一个（lcy）不是我的通道**，其余均为我的通道。

---

## 非我的通道（勿用）

### lcy - SiliconFlow
```python
"model_id": "deepseek-ai/DeepSeek-V3",
"llm_base_url": "https://api.siliconflow.cn/v1",
"llm_api_key": "sk-kfbnznycbjvseqxfqbthkytcwquklptyastuhzjcdutnvbfa",
"a2a_url": "http://localhost:10008/",
```

---

## 我的通道

### 1. DashScope - deepseek-v3（当前常用）
```python
"model_id": "deepseek-v3",
"llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
"llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
"a2a_url": "http://localhost:10008/",
```

### 2. ModelScope（阿里云模型服务平台）
```python
"model_id": "deepseek-ai/DeepSeek-V3.2",
"llm_base_url": "https://api-inference.modelscope.cn/v1",
"llm_api_key": "ms-b3ea64d3-5c65-4146-aec9-5dddd1cb5ee7",
"a2a_url": "http://localhost:10008/",
```

### 3. DashScope - deepseek-v3.2（通义千问）
```python
"model_id": "deepseek-v3.2",
"llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
"llm_api_key": "sk-6d60ccdfae2041db8df70ec3d50fe36e",
"a2a_url": "http://localhost:10008/",
```

### 4. DeepSeek 官方
```python
"model_id": "deepseek-chat",
"llm_base_url": "https://api.deepseek.com/v1",
"llm_api_key": "sk-98e1a74bf9e74352bf28ea11115a637a",
"a2a_url": "http://localhost:10008/",
```

### 5. Qwen（通义千问）
```python
"model_id": "qwen3-max",
"llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
"llm_api_key": "sk-9e17aabeaeca4a5b8a6dce517de0d8a7",
"a2a_url": "http://localhost:10008/",
```

---

## 公共字段（按需保留）

```python
"theory_type": "wave",  # "wave" | "chan" | None
```
