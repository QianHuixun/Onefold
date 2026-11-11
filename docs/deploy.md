# 部署

跑在 `junxun@junxun.lan.zhili-edu.com`（192.168.2.103）上，Ubuntu 26.04 / 4 核 15G。

```
http://junxun.lan.zhili-edu.com     ← 局域网内可访问
http://192.168.2.103                ← 同一个站，用 IP 也能开
```

## 结构

| 位置 | 作用 |
| --- | --- |
| `~/onefold` | 代码 + 虚拟环境 + SQLite + `.env` |
| `/var/www/onefold` | 前端静态文件（nginx 直接伺服） |
| `127.0.0.1:8000` | uvicorn，只监听本机，不对外 |
| `/etc/nginx/sites-available/onefold` | 反代配置 |

nginx 承担两件事：`/` 出静态文件，`/api/` 反代到 uvicorn。所以浏览器只跟 80 端口打交道，没有跨域问题。

## 服务

```bash
systemctl status onefold-api          # API 服务
systemctl restart onefold-api         # 改后端后重启
journalctl -u onefold-api -n 50       # 后端日志

systemctl list-timers onefold-daily.timer   # 定时任务
systemctl start onefold-daily               # 立刻手动跑一次
tail -f ~/onefold/logs/daily.log            # 每日任务日志
```

`onefold-daily.timer` 每天 **00:00（服务器本地时间 CST）** 触发，`Persistent=true` 表示宕机错过会补跑。

## 更新

本地改完代码，一条命令推上去：

```bash
./scripts/deploy.sh
```

它做四件事：构建前端 → rsync 代码 → 同步 `dist` 到 `/var/www/onefold` → 重启 API。

`data/`、`.env`、`.venv`、`node_modules`、`logs/` 都在排除列表里，不会被覆盖或删除。

## 首次部署做了什么

```bash
# 1 依赖
sudo apt install python3.14-venv nginx
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2 数据
.venv/bin/python -m app.cli bootstrap        # 建主题与 5 个源，不灌演示数据
.venv/bin/python -m app.cli daily            # 抓一次并跑完整管道

# 3 服务
systemctl enable --now onefold-api onefold-daily.timer
```

`bootstrap` 和 `seed` 的区别：`seed` 会灌 8 个假事件用于看效果，生产环境不能用；`bootstrap` 只建主题和源。

## 已备份 / 未备份

**还没做备份。** SQLite 是单文件，`cp` 一下就是完整备份，加一条 timer 就行：

```bash
# 每天 00:30 存一份，保留 7 天
0 30 * * * cp ~/onefold/data/onefold.db ~/onefold/data/backup-$(date +\%F).db && find ~/onefold/data -name "backup-*.db" -mtime +7 -delete
```

建议在 M6 健壮性阶段一起做，配合「数据库异常时首页降级到快照」。

## 已知限制

1. **只有 HTTP，没有 HTTPS。** 局域网域名没有证书，现在明文传输。等买了公网域名、配了 TLS 再说。
2. **只能局域网访问。** 要让公网打开（PRD 的 G3 目标），需要公网 IP 或内网穿透，再加域名。
3. **仓库是私有的，服务器上没有 git。** 走 rsync 而不是 `git pull`，所以服务器上的代码没有版本历史，回溯靠本地仓库。
4. **API 没有任何鉴权。** 现在全是只读接口，问题不大；一旦加管理接口（F01），必须先做 Token 校验和限流。
