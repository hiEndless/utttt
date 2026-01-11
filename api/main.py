import uvicorn, os
import sys
from pathlib import Path

# 确保可以找到 application 模块
api_dir = Path(__file__).parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from application import create_app, FastAPI

app: FastAPI = create_app()


if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host=os.environ.get('APP_HOST', '0.0.0.0'),
        port=int(os.environ.get('APP_PORT', 8000)),
        reload=bool(os.environ.get('APP_DEBUG'))
    )