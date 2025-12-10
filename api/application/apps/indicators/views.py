from fastapi import APIRouter
import os
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta, timezone
from ...common.status_codes import StatusCode
from ...common.redis_client import redis_client


