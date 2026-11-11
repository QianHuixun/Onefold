"""应用配置。全部走环境变量，支持仓库根目录的 .env。"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """极简 .env 读取：只支持 KEY=VALUE，不覆盖已存在的环境变量。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

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

# 大模型（OpenAI 兼容接口，默认 DeepSeek）
LLM_API_KEY = os.getenv("ONEFOLD_LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("ONEFOLD_LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("ONEFOLD_LLM_MODEL", "deepseek-chat")
LLM_TIMEOUT = float(os.getenv("ONEFOLD_LLM_TIMEOUT", "60"))

# 成本估算用（元 / 百万 token），只是估算，以账单为准
LLM_PRICE_IN = float(os.getenv("ONEFOLD_LLM_PRICE_IN", "1.0"))
LLM_PRICE_OUT = float(os.getenv("ONEFOLD_LLM_PRICE_OUT", "2.0"))
