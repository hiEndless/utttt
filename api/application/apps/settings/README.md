# Settings 模块架构说明

## 目录结构

```
settings/
├── __init__.py              # 主路由注册文件
├── views.py                 # 向后兼容入口点
├── models.py                # 数据模型定义
└── api/                     # API 路由模块目录
    ├── __init__.py          # API 模块初始化
    ├── exchange_accounts.py  # 交易所账户接口
    ├── model_providers.py   # 模型供应商接口
    ├── agent_model_configs.py # Agent 模型配置接口
    └── notification_channels.py # 通知渠道接口
```

## 架构优势

### 1. 功能模块化
- 每个设置功能都有独立的路由文件，职责清晰
- 便于团队协作开发，避免多人同时修改同一个大文件
- 代码维护成本低，易于测试和调试

### 2. 快速定位接口
- 接口按功能分类存放在 `api/` 目录下
- 文件命名直观反映功能（如 `exchange_accounts.py` 对应交易所账户功能）
- 通过 IDE 的文件搜索功能可以快速找到特定功能的接口

### 3. 统一路由管理
- 所有子路由在 `__init__.py` 中统一注册
- 主应用通过 `from . import app` 导入整个 settings 路由
- 添加新功能只需在 `__init__.py` 中导入并注册新路由

### 4. Swagger 文档优化
- 每个路由模块使用独立的标签（tags）
- 在 Swagger UI 中自动分组显示，提高可读性
- 标签命名规范：`Settings - {功能名称}`

## 现有功能模块

### 交易所账户管理 (`exchange_accounts.py`)
- `POST /api/settings/exchange_accounts` - 创建交易所账户
- `GET /api/settings/exchange_accounts` - 获取所有交易所账户列表
- `GET /api/settings/exchange_accounts/{account_id}` - 获取单个交易所账户
- `PATCH /api/settings/exchange_accounts/{account_id}` - 更新交易所账户
- `DELETE /api/settings/exchange_accounts/{account_id}` - 删除交易所账户

### 模型供应商配置 (`model_providers.py`)
- `POST /api/settings/model_providers` - 创建模型供应商
- `GET /api/settings/model_providers` - 获取所有模型供应商列表
- `GET /api/settings/model_providers/{provider_id}` - 获取单个模型供应商
- `PATCH /api/settings/model_providers/{provider_id}` - 更新模型供应商
- `DELETE /api/settings/model_providers/{provider_id}` - 删除模型供应商

### Agent 模型配置 (`agent_model_configs.py`)
- `POST /api/settings/agent_model_configs` - 创建/更新 Agent 模型配置（UPSERT）
- `GET /api/settings/agent_model_configs` - 获取所有 Agent 模型配置列表
- `GET /api/settings/agent_model_configs/{config_id}` - 获取单个 Agent 模型配置

### 通知渠道配置 (`notification_channels.py`)
- `POST /api/settings/notification_channels` - 创建/更新通知渠道（UPSERT）
- `GET /api/settings/notification_channels` - 获取所有通知渠道列表
- `GET /api/settings/notification_channels/{channel_id}` - 获取单个通知渠道

## 添加新功能接口

### 步骤 1: 创建新的路由文件
在 `api/` 目录下创建新的 Python 文件，例如 `system_preferences.py`：

```python
from fastapi import APIRouter

router = APIRouter(tags=["Settings - System Preferences"])

@router.get("/settings/system-preferences")
async def get_system_preferences():
    # 实现逻辑
    pass
```

### 步骤 2: 在 `__init__.py` 中注册路由
```python
# 导入新的路由
from .api.system_preferences import router as system_preferences_router

# 注册路由
app.include_router(system_preferences_router)
```

### 步骤 3: 验证应用启动
运行以下命令确保应用能正常启动：
```bash
cd /Users/lichaoyuan/Desktop/UTaker/api
python -c "from application import create_app; app = create_app(); print('应用创建成功！')"
```

## 最佳实践

1. **单一职责原则**：每个路由文件只处理一个功能领域
2. **一致的命名规范**：路由文件名与功能名称保持一致
3. **详细的文档注释**：每个接口都要有清晰的 docstring
4. **统一的错误处理**：使用项目统一的异常处理机制
5. **类型提示**：所有函数参数和返回值都要有完整的类型注解
6. **数据脱敏**：敏感信息（如 API Key）必须进行脱敏处理

通过这种架构设计，settings 模块可以轻松支持更多的配置功能，同时保持代码的清晰性和可维护性。