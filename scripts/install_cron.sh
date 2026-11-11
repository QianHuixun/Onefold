#!/usr/bin/env bash
# 安装每日抓取定时任务（cron）。重复执行不会叠加，只会更新那一行。
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$DIR/.venv/bin/python"
MARK="# onefold-daily"

if [ ! -x "$PY" ]; then
  echo "找不到虚拟环境：$PY" >&2
  echo "先在项目目录跑：python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

mkdir -p "$DIR/logs"

JOB="0 0 * * * cd $DIR && $PY -m app.cli daily >> $DIR/logs/daily.log 2>&1"

( crontab -l 2>/dev/null | grep -v -F "$MARK" | grep -v -F "app.cli daily" ; \
  echo "$MARK"; echo "$JOB" ) | crontab -

echo "已安装，当前生效的条目："
crontab -l | grep -A1 -F "$MARK"
echo
echo "日志：$DIR/logs/daily.log"
echo "时区：cron 用系统本地时区（当前 $(date +%Z)），0 0 就是本地时间零点。"
