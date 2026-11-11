# 定时抓取

每天 **00:00** 跑一次：抓 RSS → 抽取正文 → 去重 → 聚类 → DeepSeek 摘要。

一条命令就是整条链路，cron 只需要调它：

```bash
.venv/bin/python -m app.cli daily
```

## 安装

```bash
chmod +x scripts/install_cron.sh
./scripts/install_cron.sh
```

脚本会写进 crontab 这一行（重复执行只更新，不叠加）：

```
0 0 * * * cd /path/to/Onefold && .venv/bin/python -m app.cli daily >> logs/daily.log 2>&1
```

注意 cron 用的是**系统本地时区**。服务器在 UTC 的话，`0 0` 是北京时间 08:00，要在 crontab 里改成 `0 16 * * *`，或者在 crontab 顶部加 `TZ=Asia/Shanghai`。

## 备用：systemd timer

服务器是 systemd 的话，比 cron 好排查：

```ini
# /etc/systemd/system/onefold-daily.service
[Unit]
Description=Onefold daily fetch

[Service]
Type=oneshot
WorkingDirectory=/path/to/Onefold
ExecStart=/path/to/Onefold/.venv/bin/python -m app.cli daily
```

```ini
# /etc/systemd/system/onefold-daily.timer
[Unit]
Description=Run Onefold daily at 00:00

[Timer]
OnCalendar=*-*-* 00:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now onefold-daily.timer
journalctl -u onefold-daily -n 50
```

`Persistent=true` 的意思是：机器在 00:00 关机了，开机后会补跑一次。cron 不补跑。

## 日志与排错

```bash
tail -f logs/daily.log        # 每天一次运行的完整输出
.venv/bin/python -m app.cli report   # 每个源最近一次抓取的成败
```

`report` 的输出长这样：

```
时间             来源          新增 重复  状态
11-11 14:08   量子位          5    5  OK
11-11 14:08   Solidot        0    3  OK
11-11 14:08   某坏源          0    0  FAIL HTTP 403
```

连续失败 3 次的源会累加 `fail_count`，之后可以按这个字段停用。

## 手动补跑

```bash
.venv/bin/python -m app.cli daily --limit 10            # 抓最新 10 条并跑完整管道
.venv/bin/python -m app.cli fetch --limit 20            # 只抓，不跑管道
.venv/bin/python -m app.cli pipeline --skip-extract     # 只重跑聚类和摘要
```

## 实测（2026-11-11 14:08）

```
抓取 5 个源：新增 25，重复 25，失败 0
抽取 18/19 篇
去重：检查 25，判重 0
聚类：新事件 25，并入 0
摘要 25 条：模型 25，抽取 0，花费 ¥0.0118
完成，用时 50.5s
```

一天一次、每次 50 秒左右、成本一分钱出头。

## 一件值得再想想的事

00:00 抓取，意味着**白天发生的新闻要等到第二天零点才出现**。如果想让站上始终是最新的，建议再加一条中午的：

```
0 12 * * * cd /path/to/Onefold && .venv/bin/python -m app.cli daily >> logs/daily.log 2>&1
```

PRD 原本写的是 07:00 和 18:00 两次，也是为了这个。加不加你定，命令是现成的。
