from fastapi import FastAPI, Depends
from dotenv import load_dotenv
from tortoise.contrib.fastapi import register_tortoise
from .apps.account.views import app as account_app

from . import settings
from fastapi.middleware.cors import CORSMiddleware



def create_app() -> FastAPI:
    """工厂函数：创建App对象"""
    app = FastAPI()
    # 读取环境配置文件的信息，加载到环境变量
    load_dotenv()
    
    # 配置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 允许所有源，生产环境建议配置具体的源
        allow_credentials=True,
        allow_methods=["*"],  # 允许所有HTTP方法
        allow_headers=["*"],  # 允许所有请求头
    )
    
    # 把tortoise-orm注册到App应用对象中
    register_tortoise(
        app,
        config=settings.TORTOISE_ORM,
        generate_schemas=False,  # 是否自动生成表结构[自动根据配置项中apps.models的路径自动识别模型]
        add_exception_handlers=True,  # 是否启用自动异常处理
    )

    # 注册各个分组应用中的视图接口代码到App应用对象中
    app.include_router(account_app, prefix='/api', tags=['注册登录接口'])  # prefix url路径前缀，

    return app
