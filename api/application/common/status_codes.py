# 状态码定义
from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")

class BaseResponse(GenericModel, Generic[T]):
    code: int
    message: str
    data: Optional[T] = None

class StatusCode:
    SUCCESS = 0  # 请求成功
    ERROR = 1  # 请求失败
    PARAM_ERROR = 1001  # 参数错误
    NOT_FOUND = 1002  # 资源未找到
    SERVER_ERROR = 1003  # 服务器内部错误
    VALIDATION_ERROR = 1004  # 数据验证错误
    DATABASE_ERROR = 1005  # 数据库操作错误
    
    # 认证相关 (2000-2999)
    AUTH_LOGIN_FAILED = 2001 # 登录失败
    AUTH_TOKEN_INVALID = 2002 # Token 无效
    AUTH_TOKEN_EXPIRED = 2003 # Token 过期
    AUTH_SESSION_EXPIRED = 2004 # 会话过期
    AUTH_MISSING_TOKEN = 2005 # 缺少 Token
    AUTH_PERMISSION_DENIED = 2006 # 权限不足
    AUTH_USER_NOT_FOUND = 2007 # 用户不存在
    
    # 业务相关 (3000-3999)
    # 账户/设置
    ACCOUNT_ALREADY_BOUND = 3001 # 账户已绑定
    PROVIDER_ALREADY_EXISTS = 3002 # 供应商已存在配置
    AGENT_CONFIG_EXISTS = 3003 # Agent 配置已存在
    FEATURE_NOT_ALLOWED = 3004 # 功能未授权
    
    # 状态码对应的消息
    MESSAGE = {
        SUCCESS: "请求成功",
        ERROR: "请求失败",
        PARAM_ERROR: "参数错误",
        NOT_FOUND: "资源未找到",
        SERVER_ERROR: "服务器内部错误",
        VALIDATION_ERROR: "数据验证错误",
        DATABASE_ERROR: "数据库操作错误",
        
        AUTH_LOGIN_FAILED: "登录失败",
        AUTH_TOKEN_INVALID: "Token 无效",
        AUTH_TOKEN_EXPIRED: "Token 过期",
        AUTH_SESSION_EXPIRED: "登录会话过期",
        AUTH_MISSING_TOKEN: "缺少认证 Token",
        AUTH_PERMISSION_DENIED: "权限不足",
        AUTH_USER_NOT_FOUND: "用户不存在",
        
        ACCOUNT_ALREADY_BOUND: "该账户已绑定，请先解绑后再绑定",
        PROVIDER_ALREADY_EXISTS: "该供应商已存在配置，请先删除后再创建",
        AGENT_CONFIG_EXISTS: "该 Agent 已存在配置",
        FEATURE_NOT_ALLOWED: "该功能未授权"
    }
    
    @classmethod
    def get_message(cls, code):
        """获取状态码对应的消息"""
        return cls.MESSAGE.get(code, "未知错误")

class BusinessException(Exception):
    def __init__(self, code: int, message: str = None, data: Any = None):
        self.code = code
        self.message = message or StatusCode.get_message(code)
        self.data = data
        super().__init__(self.message)

def success_response(data: T = None, message: str = None) -> BaseResponse[T]:
    return BaseResponse(
        code=StatusCode.SUCCESS,
        message=message or StatusCode.get_message(StatusCode.SUCCESS),
        data=data
    )

def error_response(code: int, message: str = None, data: T = None) -> BaseResponse[T]:
    return BaseResponse(
        code=code,
        message=message or StatusCode.get_message(code),
        data=data
    )
