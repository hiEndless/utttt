from __future__ import annotations

from tortoise import fields
from tortoise.models import Model


class User(Model):
    id = fields.UUIDField(pk=True, description="用户ID")
    email = fields.CharField(max_length=255, null=True, description="邮箱")
    display_name = fields.CharField(max_length=128, null=True, description="显示名称")
    avatar_url = fields.TextField(null=True, description="头像URL")
    plan = fields.CharField(max_length=32, default="free", description="订阅计划")
    plan_expires_at = fields.DatetimeField(null=True, description="订阅到期时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")


class UserIdentity(Model):
    id = fields.UUIDField(pk=True, description="用户身份ID")
    user = fields.ForeignKeyField("models.User", related_name="identities", description="关联用户")
    provider = fields.CharField(max_length=32, description="身份提供方")
    provider_subject = fields.CharField(max_length=255, description="提供方用户唯一标识")
    provider_email = fields.CharField(max_length=255, null=True, description="提供方邮箱")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        unique_together = ("provider", "provider_subject")


class OAuthToken(Model):
    id = fields.UUIDField(pk=True, description="OAuth令牌ID")
    user = fields.ForeignKeyField("models.User", related_name="oauth_tokens", description="关联用户")
    provider = fields.CharField(max_length=32, description="OAuth提供方")
    access_token = fields.TextField(null=True, description="访问令牌")
    refresh_token = fields.TextField(null=True, description="刷新令牌")
    app_refresh_token = fields.CharField(max_length=128, null=True, description="App刷新令牌")
    scope = fields.TextField(null=True, description="授权范围")
    expires_at = fields.DatetimeField(null=True, description="过期时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        unique_together = ("user", "provider")


class OAuthLoginSession(Model):
    id = fields.UUIDField(pk=True, description="登录会话ID")
    code_verifier = fields.TextField(description="PKCE code_verifier")
    state = fields.CharField(max_length=128, description="OAuth state")
    redirect_uri = fields.TextField(description="redirect_uri")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    expires_at = fields.DatetimeField(description="过期时间")
