# Onefold · 归一

把多个来源里「同一件事」的报道合并成一个事件，每个事件配一句话摘要。

> Manifold reports, onefold story.

## 状态

M0 · 项目骨架，尚未开始开发。产品需求见 [docs/PRD.md](docs/PRD.md)（Word 版：[docs/PRD.docx](docs/PRD.docx)）。

## 技术取向（摘自 PRD）

- 后端：FastAPI + SQLite（FTS5 全文检索，jieba 预分词）
- 前端：时间线 / 事件详情 / 主题切换，零注册，收藏与已读存 localStorage
- 部署：单机、单文件数据库，公网只读 + 管理 Token

## 目录

```
docs/       PRD（Markdown 为准，docx 为交付版）
scripts/    构建与运维脚本（build_prd_docx.py 由 PRD.md 生成 PRD.docx）
app/        后端（待建）
data/       SQLite 与快照（不进版本库）
tests/      测试（待建）
```

## 约定

- 品牌名统一写作 `Onefold`（首字母大写，连写），中文名「归一」
- 提交信息用中文或英文均可，一句话说清做了什么
