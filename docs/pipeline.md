# 数据管道

`python -m app.cli pipeline`，四步：抽取 → 去重 → 聚类 → 摘要。

对应 PRD 的 F03、F04、F05、F06。每一步都能单独跑，也都能跳过重跑：

```bash
.venv/bin/python -m app.cli fetch --limit 10     # 抓 RSS，落 article
.venv/bin/python -m app.cli pipeline             # 跑完整管道
.venv/bin/python -m app.cli pipeline --rebuild   # 清掉自动聚出来的事件后重跑
.venv/bin/python -m app.cli pipeline --skip-extract
```

## 1 正文抽取

RSS 摘要长度不可靠（量子位的摘要中位数只有 20 字），所以对正文不足 200 字的文章回原文抓一次，用 `trafilatura` 抽正文。失败或过短就保留原摘要，不把文章丢掉。

抓取必须带浏览器 UA：探针阶段用默认 `curl` UA 时量子位返回 403、InfoQ 返回 451。

## 2 文章去重

SimHash 64 位指纹，汉明距离 ≤ 3 判为转载重复，状态置为 `dup`，不再进入聚类。

注意：指纹是无符号 64 位，SQLite 的 INTEGER 是有符号的，入库前要转成有符号数，否则会 `OverflowError`。

## 3 事件聚类

**表示**：jieba 分词 → 语料内 IDF → 稀疏向量 → 余弦相似度。没有用外部 embedding，理由是完全离线、可复现、能解释「为什么这两篇被判为同一件事」。

**判定**：同主题、时间窗 24 小时内，与事件中心（成员向量的质心）相似度 ≥ 阈值（默认 0.35）则并入，否则新建事件。

阈值和时间窗存在 `topic.config_json` 里，换主题不用改代码：

```json
{"cosine_threshold": 0.35, "time_window_hours": 24}
```

## 4 摘要

有 `ONEFOLD_LLM_API_KEY` 就走 OpenAI 兼容接口（默认 DeepSeek），提示词限定「只陈述报道里出现过的事实」。

没有密钥时降级为抽取式：取最接近事件中心那篇报道的首句，截 60 字。降级结果不是模型写的，展示时不要冒充。

```bash
export ONEFOLD_LLM_API_KEY=sk-...
export ONEFOLD_LLM_BASE_URL=https://api.deepseek.com/v1
export ONEFOLD_LLM_MODEL=deepseek-chat
```

## 实测（2026-11-11）

25 篇真实抓取的文章，跑完整管道：

| 步骤 | 结果 |
| --- | --- |
| 正文抽取 | 20/20 成功（另 5 篇摘要已够长，跳过） |
| 文章去重 | 25 篇，0 篇判为重复 |
| 事件聚类 | 25 篇 → 25 个事件，0 次合并 |
| 摘要 | 25 条，全部抽取式降级 |

0 次合并不是 bug：这 25 篇来自 5 个源的最新内容，本来就是 25 件不同的事。两两相似度最高的一对只有 0.197，低于阈值。

真正验证合并能力的是 `tests/test_pipeline.py`：6 篇构造文章（3 篇说 Gemini、3 篇说波士顿动力）应聚成 2 个事件，实际聚成 2 个。

## 已知局限

1. **跨语言不合并**。纯词面相似度，中文和英文报道同一件事不会被判为同一事件。PRD 明确不做翻译，所以这是设计取舍，不是缺陷，但会让 `source_count` 偏小。
2. **同义改写不敏感**。两条标题用词完全不同但指同一件事时，相似度可能低于阈值。这也是 F13 阈值实验台要解决的问题。
3. **阈值靠人工调**。0.35 是在当前语料上目测的，换成金融主题要重调。

## 测试

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests -q
```

5 条用例覆盖：指纹稳定性、不同事件的指纹距离、TF-IDF 的区分度、端到端聚类（2 个事件、3+2 篇）、跨语言不合并的已知局限。
