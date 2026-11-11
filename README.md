# Onefold · 归一

把多个来源里「同一件事」的报道合并成一个事件，每个事件配一句话摘要。

> Manifold reports, onefold story.

## 状态

前后端已在本地跑通，部署目标服务器待定（原先部署在公司机器上，已撤下）。

M0 完成 · 前后端骨架跑通。首页已经从 `/api/events` 读真实数据，八个事件、二十个来源是种子数据。
产品需求见 [docs/PRD.md](docs/PRD.md)（Word 版：[docs/PRD.docx](docs/PRD.docx)）。

## 技术栈

| 层 | 选择 |
| --- | --- |
| 后端 | Python 3.12+ · FastAPI · SQLModel |
| 数据库 | SQLite（WAL）+ FTS5，中文 jieba 预分词 |
| 前端 | React 19 · TypeScript · Vite |
| 部署 | Nginx 静态托管 + uvicorn，单机 |

## 本地运行

```bash
# 后端
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.cli seed --force      # 建表 + 灌示例数据
.venv/bin/uvicorn app.main:app --port 8000    # 接口文档 /docs

# 前端（另开一个终端）
cd web
npm install
npm run dev                                    # http://127.0.0.1:5173
```

抓取真实 RSS，再跑数据管道：

```bash
.venv/bin/python -m app.cli fetch --limit 10      # 抓
.venv/bin/python -m app.cli pipeline              # 抽取 → 去重 → 聚类 → 摘要
.venv/bin/python -m pytest tests -q               # 管道测试
```

摘要走 DeepSeek，配置写进 `.env`（模板见 `.env.example`）：

```bash
cp .env.example .env      # 填 ONEFOLD_LLM_API_KEY
.venv/bin/python -m app.cli summarize --force
```

管道细节、阈值与已知局限见 [docs/pipeline.md](docs/pipeline.md)。

每天 00:00 自动跑整条链路：

```bash
./scripts/install_cron.sh       # 写入 crontab
.venv/bin/python -m app.cli report   # 看每个源最近一次抓取
```

定时方案、systemd timer、日志与补跑见 [docs/scheduling.md](docs/scheduling.md)。

发布到服务器：`./scripts/deploy.sh` + `scripts/provision.sh`，见 [docs/deploy.md](docs/deploy.md)。

Vite 已把 `/api` 代理到 `127.0.0.1:8000`，前端不需要处理跨域。

## 目录

```
app/        后端：models / api / cli / db
web/        前端：React + Vite
docs/       PRD（Markdown 为准，docx 为交付版）+ 管道说明
tests/      管道测试（pytest）
design/     视觉规范与四个页面的 HTML 原型（暗色）
scripts/    探针与文档生成脚本
data/       SQLite 与快照（不进版本库）
```

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/events` | 事件列表，支持 `topic` / `limit` / `offset` |
| GET | `/api/events/{id}` | 事件详情，含多源文章与相似度 |
| GET | `/api/topics` | 主题列表 |
| GET | `/api/stats` | 事件数、来源数、最后更新时间 |
| GET | `/api/search?q=` | 事件与文章检索（FTS5 + jieba 预分词） |

管理接口（需 `X-Admin-Token` 请求头，值取自 `.env` 的 `ONEFOLD_ADMIN_TOKEN`）：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/admin/sources` | 数据源列表 |
| POST | `/api/admin/sources` | 新增源 |
| PATCH | `/api/admin/sources/{id}` | 改名 / 换主题 / 启停 |
| DELETE | `/api/admin/sources/{id}` | 删除（有文章时拒绝，改用停用） |
| POST | `/api/admin/fetch` | 后台触发一次抓取 |
| GET | `/api/admin/fetch-log` | 最近抓取记录 |
| GET | `/api/admin/eval/pairs` | 待标注的文章对 |
| POST | `/api/admin/eval/pairs/{id}` | 提交标注 |
| GET | `/api/admin/eval/metrics` | 阈值扫描与 P/R/F1 |

管理页在页脚「管理入口」或 `/?admin=1`，阈值实验台在 `/?eval=1`。实验台用法与口径见 [docs/eval.md](docs/eval.md)，中文检索方案见 [docs/search.md](docs/search.md)。

## 快捷键

| 键 | 作用 |
| --- | --- |
| ⌘K / Ctrl+K | 打开搜索面板 |
| ↑ ↓ | 在结果间移动 |
| ↵ | 打开选中项（事件进详情，文章开原文） |
| Esc | 关闭面板 / 详情 |

## 收藏与已读

无账号，状态存在浏览器 `localStorage`（PRD 4.1 的有意取舍）：

| key | 内容 |
| --- | --- |
| `onefold_read` | 已读事件 id 数组 |
| `onefold_starred` | 收藏事件 id 数组 |
| `onefold_admin_token` | 管理令牌 |

列表上方有「全部 / 未读 / 收藏」筛选，收藏不为空时出现「导出」，把收藏导出成 JSON（F16）。换设备不同步，清缓存会丢——这是零注册的代价。

## 约定

- 品牌名统一写作 `Onefold`（首字母大写，连写），中文名「归一」
- 只做桌面端，`min-width: 1200px`，不写响应式
- 提交信息用中文或英文均可，一句话说清做了什么
