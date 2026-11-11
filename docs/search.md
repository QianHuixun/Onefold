# 中文全文检索（F09）

SQLite 的 FTS5 自带分词器不认识中文，直接建索引等于没有。落地方案是**预分词写入 + FTS5 倒排**。

## 结构

```
article.search_text    jieba 分词后的空格串，索引列
article_fts            FTS5 虚表（external content，只存倒排，不存正文）
三支触发器               INSERT / DELETE / UPDATE 时自动同步
```

```sql
CREATE VIRTUAL TABLE article_fts USING fts5(
    search_text,
    content='article', content_rowid='id',
    tokenize='unicode61'
);
```

`content='article'` 让 FTS 只存倒排表，原文还在 `article` 里，不重复占空间。触发器保证两者一致。

## 查询

用户输入先分词，每个词加双引号拼成 MATCH 表达式，词之间是隐式 AND：

```
"量子" "计算"
```

加引号是为了防止 `-`、`*`、`:` 被当成 FTS5 语法；不加的话搜 `C++` 会直接报错。

排序用 `bm25()`，事件命中按时间在前、文章按相关度在后。

## 踩过的坑：索引端和查询端分词不一致

第一版索引里存的是原文，查询时用 jieba 分词。结果搜「量子」一条都命中不了——因为索引把整句当成一个大 token，而查询拆成了两个词。

反过来也会出问题：文档里「量子计算」被 jieba 切成一个词，查询切成「量子」「计算」两个词，AND 起来反而匹配不上。

**规则：索引端和查询端必须用同一个分词函数。** `reindex` 命令会重算全部 `search_text` 再重建索引，改了分词口径就跑一次：

```bash
.venv/bin/python -m app.cli reindex
```

## 一个容易漏的过滤

评测夹具的文章 `status='eval'`，不参与聚类也不该出现在公开搜索里。`search_articles` 里显式过滤 `status='ok'`，FTS 路径和 LIKE 兜底路径都要加。

## 实测

| 查询 | 命中 |
| --- | --- |
| 量子 | 8 条文章 |
| 量子计算 | 1 条（事件 + 文章去重后） |
| 微软 | 4 条 |
| OpenAI | 11 条 |

## 阈值与参数

- 分词：jieba 默认模式（`cut`），不做 search mode
- 词间关系：AND，召回不足时可改 OR
- 排序：`bm25()`

## 已知限制

1. **没有近义词扩展**。搜「芯片」不会命中只写「半导体」的文章。
2. **没有拼音搜索**，打错字搜不到。
3. **标点被丢弃**，搜「.NET」实际是按 `net` 匹配。
4. **英文大小写归一**由 unicode61 处理，中文不受影响。
5. 数据量到十万级时应该考虑 `external content` 之外的分片策略，现在几万条以内没有压力。
