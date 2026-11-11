# 每日自动更新（GitHub Actions）

目标：不用开电脑、不用服务器，每天自动跑一次管道，把新快照提交回仓库，Vercel 检测到 push 自动重新部署。

## 需要准备的东西

1. **仓库 Secret**：`ONEFOLD_LLM_API_KEY`
   Settings → Secrets and variables → Actions → New repository secret
   值就是 DeepSeek 的 key。不配也能跑，摘要会降级成抽取式。

2. **工作流文件**：`.github/workflows/daily.yml`
   因为推送 workflow 需要 token 带 `workflow` 权限，直接 `git push` 会被拒。用下面任一方式添加。

## 流程

```
UTC 16:00（北京 00:00）
  → 恢复上一次的 SQLite（actions/cache）
  → bootstrap（首次才有用，之后是幂等）
  → daily：抓 RSS → 抽取 → 去重 → 聚类 → DeepSeek 摘要
  → export：导出 JSON 到 web/public/data
  → 提交并推送
  → Vercel 自动构建部署
```

数据库通过 `actions/cache` 在两次运行之间传递，key 是 `onefold-db-${{ github.run_id }}`，`restore-keys: onefold-db-` 保证拿到最近一份。缓存 7 天不用会被清掉，那一次运行会从零开始，事件 id 会重排。

## 添加工作流

### 方式一：网页粘贴（最简单）

1. 打开 `https://github.com/QianHuixun/Onefold/new/main/.github/workflows`
2. 文件名填 `daily.yml`
3. 把仓库里 `docs/ci-daily.yml` 的内容整段粘进去
4. Commit

### 方式二：给 gh 加权限后推送

```bash
gh auth refresh -s workflow
git add .github/workflows/daily.yml && git commit -m "ci: 每日自动更新" && git push
```

## 手动触发

Actions → Daily refresh → Run workflow。第一次建议手动跑一次，确认 Secret 生效、提交能推上去。

## 检查点

- Actions 页面能看到一次成功运行，耗时 2–4 分钟
- 仓库里出现 `data: 每日快照 2026-11-12` 这样的提交
- Vercel 自动重新部署，首页「更新于」时间变了

## 已知限制

1. **定时可能延迟**。GitHub 的 cron 在高峰期会晚几分钟到半小时。
2. **60 天无活动会暂停**。这个仓库每天有提交，不会触发。
3. **缓存丢了 id 会重排**。`/e/14` 这类链接指向的事件可能变成别的，长期分享链接不稳定。
4. **每次都是全量重跑**。没有增量抓取的概念，本来就是抓最新 N 条。
