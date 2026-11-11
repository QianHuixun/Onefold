"""应用配置。全部走环境变量，默认值只适合本地开发。"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("ONEFOLD_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.getenv("ONEFOLD_DB", DATA_DIR / "onefold.db"))

# 管理接口令牌：生产环境必须改
ADMIN_TOKEN = os.getenv("ONEFOLD_ADMIN_TOKEN", "dev-token")

# 前端开发服务器
DEV_ORIGIN = os.getenv("ONEFOLD_DEV_ORIGIN", "http://127.0.0.1:5173")

# 抓取
USER_AGENT = os.getenv(
    "ONEFOLD_UA",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
)
FETCH_TIMEOUT = float(os.getenv("ONEFOLD_FETCH_TIMEOUT", "15"))
