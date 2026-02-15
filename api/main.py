import uvicorn, os

try:
    from api.application import create_app, FastAPI
except ModuleNotFoundError:
    from application import create_app, FastAPI

app: FastAPI = create_app()


if __name__ == '__main__':
    uvicorn.run(
        app,
        host=os.environ.get('APP_HOST', '0.0.0.0'),
        port=int(os.environ.get('APP_PORT', 8000)),
        reload=bool(os.environ.get('APP_DEBUG'))
    )