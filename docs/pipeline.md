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

## 4 摘要（DeepSeek）

调用 DeepSeek 的 OpenAI 兼容接口，`deepseek-chat`，只要一句、不超过 60 字，提示词限定「只陈述材料里出现过的事实」。

```bash
cp .env.example .env
# 填 ONEFOLD_LLM_API_KEY=sk-...
.venv/bin/python -m app.cli summarize --force
```

没有密钥或调用失败时降级为抽取式（取最接近事件中心那篇的首句），并把来源写进 `event.summary_source`：

- `deepseek-chat` → 前端显示「AI 摘要 · deepseek-chat」
- `extractive` → 前端显示「抽取式摘要」，不冒充模型写的

命令会打印 token 数与估算花费：

```
摘要 33 条：模型 33，抽取式 0；tokens 入 13500 / 出 1338，估算花费 ¥0.0162
```

2026-11-11 实测：33 个事件（含种子数据）全量重跑，41.8 秒，1.35 万输入 token，¥0.016。

成本对应的 PRD 指标是 ≤5 元/天。按每天 40 个事件、每个事件 6 篇 700 字材料估算，一天大约 0.3–0.6 元，留了一到两个数量级的余量。

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
