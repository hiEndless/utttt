from fastapi import APIRouter
import os
from dotenv import load_dotenv
from .models import User
import jwt
from datetime import datetime, timedelta, timezone
from ...common.status_codes import StatusCode
import re
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext

# 加载环境变量
load_dotenv()
app = APIRouter()

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"

# 密码加密上下文（bcrypt）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _is_bcrypt_hash(value: str) -> bool:
    """简单判断字符串是否为 bcrypt 哈希。
    常见前缀：$2a$、$2b$、$2y$，长度通常为 60。
    """
    if not isinstance(value, str):
        return False
    return (value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")) and len(value) >= 60


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    account: str  # 用户名或邮箱
    password: str


@app.post("/register", description="用户注册")
async def register(request: RegisterRequest):
    username = request.username
    email = request.email
    password = request.password

    # 校验用户名格式不能有特殊符号
    username_regex = r"^[A-Za-z0-9_]+$"
    if not re.match(username_regex, username):
        return {"code": StatusCode.PARAM_ERROR, "msg": "用户名格式不正确"}

    if not username or not email or not password:
        return {"code": StatusCode.PARAM_ERROR, "msg": "用户名、邮箱和密码不能为空"}

    if len(password) < 6:
        return {"code": StatusCode.PARAM_ERROR, "msg": "密码长度不能小于6位"}

    exist_email = await User.filter(email=email).first()
    if exist_email:
        return {"code": StatusCode.PARAM_ERROR, "msg": "邮箱已存在"}

    exist_username = await User.filter(username=username).first()
    if exist_username:
        return {"code": StatusCode.PARAM_ERROR, "msg": "用户名已存在"}

    # 对密码进行哈希存储
    hashed_password = pwd_context.hash(password)

    user = await User.create(
        username=username,
        email=email,
        password=hashed_password,
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )

    # 注册成功后默认登录
    payload = {
        "user_id": user.id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=9999)  # 不设置过期
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    user.token = token
    await user.save()
    username = user.username

    return {"code": StatusCode.SUCCESS, "msg": "注册成功", "token": token, "user_id": user.id,
            "username": username, "email": email}


@app.post("/login", description="用户登录")
async def login(request: LoginRequest):
    account = request.account
    password = request.password
    # 仅支持邮箱登录
    user = await User.filter(email=account).first()
    if not user:
        return {"code": StatusCode.PARAM_ERROR, "msg": "用户不存在"}
    if not user.is_active:
        return {"code": StatusCode.PARAM_ERROR, "msg": "用户被禁用"}
    # 支持旧明文密码并自动迁移到哈希
    stored_password = user.password or ""
    if _is_bcrypt_hash(stored_password):
        if not pwd_context.verify(password, stored_password):
            return {"code": StatusCode.PARAM_ERROR, "msg": "密码错误"}
    else:
        # 旧数据为明文
        if password != stored_password:
            return {"code": StatusCode.PARAM_ERROR, "msg": "密码错误"}
        # 迁移：将明文更新为哈希
        user.password = pwd_context.hash(password)
        await user.save()
    payload = {
        "user_id": user.id,
        "email": user.email,
        "exp": datetime.now(timezone.utc) + timedelta(days=9999)  # 不设置过期
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    user.token = token
    await user.save()
    username = user.username
    return {"code": StatusCode.SUCCESS, "msg": "登录成功", "token": token, "user_id": user.id,
            "username": username, "email": account}


