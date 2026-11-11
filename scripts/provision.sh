#!/usr/bin/env bash
# 在全新的 Ubuntu/Debian 服务器上初始化 Onefold。
# 前提：代码已经 rsync 到 ~/onefold，且 .env 已经放好。
set -euo pipefail

DIR="$HOME/onefold"
DOMAIN="${ONEFOLD_DOMAIN:-_}"
PYTHON_BIN="${ONEFOLD_PYTHON:-python3}"

cd "$DIR"

echo "→ 1/6 系统依赖"
sudo apt-get update -qq
sudo apt-get install -y -qq "$PYTHON_BIN-venv" nginx

echo "→ 2/6 Python 环境"
[ -d .venv ] || "$PYTHON_BIN" -m venv .venv
.venv/bin/pip -q install --upgrade pip
.venv/bin/pip -q install -r requirements.txt
.venv/bin/python -c "import fastapi, sqlmodel, trafilatura, jieba, numpy" && echo "  依赖 OK"

echo "→ 3/6 数据初始化"
mkdir -p data logs
.venv/bin/python -m app.cli bootstrap

echo "→ 4/6 前端静态文件"
sudo mkdir -p /var/www/onefold
sudo cp -r web/dist/* /var/www/onefold/
sudo chown -R www-data:www-data /var/www/onefold

echo "→ 5/6 systemd 服务"
sudo tee /etc/systemd/system/onefold-api.service >/dev/null <<EOF
[Unit]
Description=Onefold API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/onefold-daily.service >/dev/null <<EOF
[Unit]
Description=Onefold daily fetch and pipeline

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python -m app.cli daily
StandardOutput=append:$DIR/logs/daily.log
StandardError=append:$DIR/logs/daily.log
EOF

sudo tee /etc/systemd/system/onefold-daily.timer >/dev/null <<'EOF'
[Unit]
Description=Run Onefold daily at 00:00

[Timer]
OnCalendar=*-*-* 00:00:00
Persistent=true
Unit=onefold-daily.service

[Install]
WantedBy=timers.target
EOF

echo "→ 6/6 nginx"
# limit_req_zone 只能写在 http 上下文，单独放 conf.d
sudo tee /etc/nginx/conf.d/onefold-limit.conf >/dev/null <<'EOF'
limit_req_zone $binary_remote_addr zone=onefold:10m rate=30r/s;
EOF

sudo tee /etc/nginx/sites-available/onefold >/dev/null <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name $DOMAIN;

    root /var/www/onefold;
    index index.html;

    server_tokens off;
    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;

    # 只读站，限流防刷
    limit_req_zone \$binary_remote_addr zone=onefold:10m rate=30r/s;

    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /api/ {
        limit_req zone=onefold burst=60 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 60s;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/onefold /etc/nginx/sites-enabled/onefold
sudo nginx -t && sudo systemctl reload nginx

sudo systemctl daemon-reload
sudo systemctl enable --now onefold-api.service onefold-daily.timer

echo
echo "完成。检查一下："
systemctl is-active onefold-api
systemctl list-timers onefold-daily.timer --no-pager | head -2
curl -s -o /dev/null -w "首页 %{http_code}\n" http://127.0.0.1/
