# 部署

**目标服务器待定。** 之前部署在公司配发的机器上，已按要求撤下（服务停用、站点下线，文件保留）。

确定服务器后，两条命令完成部署：

```bash
# 1 本地：同步代码与前端
export ONEFOLD_HOST=user@your-server        # SSH 免密登录
./scripts/deploy.sh

# 2 服务器：初始化系统
ssh user@your-server 'cd ~/onefold && ONEFOLD_DOMAIN=your.domain ./scripts/provision.sh'
```

`provision.sh` 会装依赖、建 venv、初始化数据、写 systemd 服务、配 nginx（含限流），并跑一次健康检查。

## 服务器要求

| 项 | 最低 | 说明 |
| --- | --- | --- |
| 系统 | Ubuntu 22.04+ / Debian 12+ | 其它发行版要改 apt 命令 |
| Python | 3.11+ | 3.12 最稳 |
| 内存 | 1G | 抓取时峰值 300M 左右 |
| 磁盘 | 10G | 主要是 venv 和依赖 |
| 软件 | nginx + systemd | `provision.sh` 会装 |

不需要 Docker，不需要 Node（前端在本地构建好再推上去）。

## 架构

```
Nginx :80  ──/       → /var/www/onefold（静态文件）
           ──/api/   → 127.0.0.1:8000（uvicorn）
systemd    onefold-api        常驻，挂了自动重启
           onefold-daily.timer  每天 00:00 跑抓取 + 管道
```

API 只监听 127.0.0.1，公网拿不到，必须经过 nginx。这样限流、日志、TLS 都集中在 nginx 一层。

## 域名与备案（重要）

服务器放在哪里，决定你要不要备案：

| 位置 | 备案 | 能立刻用 | 中国大陆访问 |
| --- | --- | --- | --- |
| 中国大陆（阿里云/腾讯云） | **需要 ICP 备案**，约 1–3 周 | 否 | 最快 |
| 香港 / 新加坡 / 日本 | 不需要 | 是 | 50–150ms，可用 |

毕设有时限，如果不想等备案，选境外轻量服务器即可，`provision.sh` 不用改。

域名建议 `.com` 或 `.news`，一年几十块。买了之后把 DNS 的 A 记录指向服务器 IP。

## 每日任务

```bash
systemctl list-timers onefold-daily.timer   # 下次触发时间
systemctl start onefold-daily               # 手动跑一次
tail -f ~/onefold/logs/daily.log            # 日志
```

`Persistent=true`：机器半夜关机，开机后会补跑。

## 更新

```bash
./scripts/deploy.sh
```

构建前端 → rsync 代码 → 同步静态文件 → 重启 API。`data/`、`.env`、`.venv`、`logs/` 不会被覆盖。

## 安全基线

`provision.sh` 里已经包含的：

- `server_tokens off`，不回显 nginx 版本
- API 路径限流 30 r/s，burst 60
- API 只监听 127.0.0.1
- 静态资源 30 天缓存

还需要你自己做的：

```bash
# 防火墙：只放行 22 和 80
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw enable

# TLS：有域名之后
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain
```

## 备份（还没做）

SQLite 是单文件，复制即备份：

```bash
# 每天 00:30 备份，保留 7 天
0 30 * * * cp ~/onefold/data/onefold.db ~/onefold/data/backup-$(date +\%F).db && find ~/onefold/data -name "backup-*.db" -mtime +7 -delete
```

建议和 M6 的「快照降级」一起做。

## 撤下旧服务器时做了什么

公司那台机器上：

```bash
sudo systemctl disable --now onefold-daily.timer onefold-api.service
sudo rm /etc/nginx/sites-enabled/onefold /etc/nginx/sites-available/onefold
sudo systemctl reload nginx
```

文件保留在 `~/onefold`（269M，含 venv）和 `/var/www/onefold`（500K），彻底删除：

```bash
rm -rf ~/onefold /var/www/onefold
sudo rm -f /etc/systemd/system/onefold-{api,daily}.{service,timer}
sudo rm -f /etc/nginx/conf.d/onefold-limit.conf
sudo systemctl daemon-reload
```

nginx 本身是那次部署装的，留着不影响，也可以 `sudo apt remove nginx`。


## 静态托管（Vercel / GitHub Pages）

前端可以脱离后端单独托管。数据用 `export` 导出成 JSON 快照：

```bash
.venv/bin/python -m app.cli export --out web/public/data
```

### Vercel

仓库根目录的 `web/vercel.json` 已经配好：构建命令 `npm run build:static`、输出 `dist`、SPA 重写。

用面板导入仓库时，**Root Directory 必须填 `web`**，其它保持默认。

用 CLI：

```bash
cd web
npx vercel login
npx vercel --prod
```

免费 Hobby 计划支持私有仓库，不需要把源码公开。

### GitHub Pages（需要公开仓库）

免费账号只能从公开仓库发布 Pages。构建用 `npm run build:pages`（base 是 `/Onefold/`），并需要把 `dist/index.html` 复制成 `404.html` 做 SPA 回退——脚本里已经带了。

对应的工作流（需要有 `workflow` 权限的 token 才能推送）：

```yaml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: web/package-lock.json
      - working-directory: web
        run: npm ci
      - working-directory: web
        run: npm run build:pages
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web/dist
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

### 静态模式的三个限制

1. 管理页、实验台不可用（需要后端）
2. 搜索降级为前端子串匹配，没有分词
3. 数据是快照，更新要重新 export 再部署
