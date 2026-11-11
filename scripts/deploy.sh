#!/usr/bin/env bash
# 把本地代码发布到服务器：构建前端 → 同步 → 重启 API。
set -euo pipefail

HOST="${ONEFOLD_HOST:?请先 export ONEFOLD_HOST=user@your-server}"
KEY="${ONEFOLD_SSH_KEY:-$HOME/.ssh/id_ed25519}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "→ 构建前端"
(cd web && npm run build >/dev/null)
echo "  完成：$(du -sh web/dist | cut -f1)"

echo "→ 同步代码"
rsync -az --delete -e "ssh -i $KEY" \
  --exclude .venv --exclude node_modules --exclude .git \
  --exclude data --exclude logs --exclude .env --exclude 'design' \
  ./ "$HOST:~/onefold/"

echo "→ 同步静态文件"
rsync -az -e "ssh -i $KEY" web/dist/ "$HOST:~/onefold/web/dist/"

echo "→ 发布并重启"
ssh -i "$KEY" "$HOST" '
  sudo cp -r ~/onefold/web/dist/* /var/www/onefold/ &&
  sudo chown -R www-data:www-data /var/www/onefold &&
  sudo systemctl restart onefold-api &&
  sleep 1 && systemctl is-active onefold-api
'
echo "完成：http://$HOST"
