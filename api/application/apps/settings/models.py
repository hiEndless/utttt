from tortoise import models, fields


class ExchangeAccount(models.Model):
    """
    交易所账户表：用于承载用户在某个交易所的 API 绑定信息。
    说明：当前按业务需求支持明文存储（只读或绑定 IP 的 API），仍建议避免在日志/接口响应中泄露。
    """

    id = fields.UUIDField(pk=True, description="交易所账户ID")
    user = fields.ForeignKeyField(
        "models.User",
        related_name="exchange_accounts",
        description="关联用户",
    )
    exchange = fields.CharField(max_length=32, description="交易所 (e.g. binance)")

    api_key = fields.CharField(max_length=256, null=True, description="API Key")
    api_secret = fields.TextField(null=True, description="API Secret")
    api_passphrase = fields.CharField(max_length=128, null=True, description="API Passphrase(部分交易所需要)")
    api_label = fields.CharField(max_length=64, null=True, description="账户备注/别名")
    is_read_only = fields.BooleanField(default=True, description="是否只读 API")

    is_active = fields.BooleanField(default=True, description="是否启用")
    is_deleted = fields.BooleanField(default=False, description="是否删除")
    deleted_at = fields.DatetimeField(null=True, description="删除时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "exchange_accounts"
        # unique_together = (("user", "exchange"),)
        indexes = ("user", "exchange", "is_active")


class ModelProvider(models.Model):
    """
    模型供应商配置表：用于存储模型 API 的 Base URL 与 API Key。
    说明：支持按用户隔离（未来多用户场景），当前单用户也可直接复用。
    """

    id = fields.UUIDField(pk=True, description="配置ID")
    user = fields.ForeignKeyField(
        "models.User",
        related_name="model_providers",
        null=True,
        description="关联用户",
    )

    provider = fields.CharField(max_length=64, description="供应商标识 (e.g. openai, azure_openai, ollama)")
    base_url = fields.CharField(max_length=512, description="API Base URL")
    api_key = fields.TextField(null=True, description="API Key")

    is_active = fields.BooleanField(default=True, description="是否启用")
    availability_status = fields.CharField(
        max_length=16,
        default="unknown",
        description="可用性状态(unknown/ok/unavailable)",
    )
    unavailable_reason = fields.TextField(null=True, description="不可用原因(用于展示与排障)")
    unavailable_until = fields.DatetimeField(null=True, description="不可用截止时间(到期后可尝试恢复)")
    last_check_at = fields.DatetimeField(null=True, description="最近一次可用性检查时间")
    last_error_at = fields.DatetimeField(null=True, description="最近一次错误时间")
    deleted_at = fields.DatetimeField(null=True, description="删除时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "model_providers"
        indexes = (("user", "provider", "is_active"), ("provider", "is_active"))


class AgentModelConfig(models.Model):
    """
    Agent 模型配置表：记录每个 Agent 使用的模型供应商与模型ID。
    说明：支持按用户隔离（未来多用户场景），当前单用户也可直接复用。
    """

    id = fields.UUIDField(pk=True, description="配置ID")
    user = fields.ForeignKeyField(
        "models.User",
        related_name="agent_model_configs",
        null=True,
        description="关联用户",
    )
    agent_name = fields.CharField(max_length=64, description="Agent 名称 (e.g. signal_validation)")
    provider = fields.ForeignKeyField(
        "models.ModelProvider",
        related_name="agent_configs",
        description="关联模型供应商",
    )
    model_id = fields.CharField(max_length=128, description="模型ID (e.g. gpt-4o-mini)")

    is_active = fields.BooleanField(default=True, description="是否启用")
    availability_status = fields.CharField(
        max_length=16,
        default="unknown",
        description="可用性状态(unknown/ok/unavailable)",
    )
    unavailable_reason = fields.TextField(null=True, description="不可用原因(用于展示与排障)")
    unavailable_until = fields.DatetimeField(null=True, description="不可用截止时间(到期后可尝试恢复)")
    last_check_at = fields.DatetimeField(null=True, description="最近一次可用性检查时间")
    last_error_at = fields.DatetimeField(null=True, description="最近一次错误时间")
    deleted_at = fields.DatetimeField(null=True, description="删除时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "agent_model_configs"
        unique_together = (("user", "agent_name"),)
        indexes = (("user", "agent_name", "is_active"), ("agent_name", "is_active"), ("provider", "is_active"))


class NotificationChannel(models.Model):
    """
    消息通知渠道配置表：用于存储各类通知渠道的参数。
    支持：飞书机器人/电报机器人/钉钉机器人/QQ邮箱/自定义发件邮箱。
    说明：明文参数仅用于运行时发送通知，需避免在日志/接口响应中泄露。
    """

    id = fields.UUIDField(pk=True, description="渠道ID")
    user = fields.ForeignKeyField(
        "models.User",
        related_name="notification_channels",
        null=True,
        description="关联用户",
    )
    channel_type = fields.CharField(
        max_length=32,
        description="渠道类型(feishu_bot/telegram_bot/dingtalk_bot/qq_email/smtp_email)",
    )
    name = fields.CharField(max_length=64, null=True, description="渠道名称/备注")

    config = fields.JSONField(null=True, description="渠道配置(JSON)")

    is_active = fields.BooleanField(default=True, description="是否启用")
    is_deleted = fields.BooleanField(default=False, description="是否删除")
    deleted_at = fields.DatetimeField(null=True, description="删除时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "notification_channels"
        indexes = (
            ("user", "channel_type", "is_active"),
            ("channel_type", "is_active"),
        )
