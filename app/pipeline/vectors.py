"""文本表示：SimHash 指纹 + 轻量 TF-IDF 向量。

指纹用于文章级去重（F04），向量用于事件聚类（F05）。

向量没有用外部 embedding：jieba 分词 + 语料内 IDF + 余弦。
好处是完全离线、可复现、每次运行能解释「为什么这两篇被判为同一件事」；
代价是对同义改写不敏感，这一点写进论文的局限里。
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

MASK64 = (1 << 64) - 1
_FALLBACK = re.compile(r"[\u4e00-\u9fff]{2}|[a-zA-Z]{2,}")


def tokens(text: str) -> list[str]:
    """优先用 jieba，装不上就退回字符/英文词切分。"""
    try:
        import jieba

        return [w for w in (t.strip() for t in jieba.cut(text)) if len(w) > 1]
    except Exception:  # noqa: BLE001
        return _FALLBACK.findall(text)


def simhash64(text: str) -> int:
    parts = tokens(text)
    if not parts:
        return 0
    weights = Counter(parts)
    vector = [0.0] * 64
    for token, weight in weights.items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        for bit in range(64):
            vector[bit] += weight if (value >> bit) & 1 else -weight
    out = 0
    for bit in range(64):
        if vector[bit] > 0:
            out |= 1 << bit
    return out


def hamming(a: int, b: int) -> int:
    return ((a ^ b) & MASK64).bit_count()


def to_signed(value: int) -> int:
    """SQLite 的 INTEGER 是有符号 64 位，SimHash 要转一下再入库。"""
    return value - (1 << 64) if value >= (1 << 63) else value


class TfidfSpace:
    """在一个语料上算 IDF，然后把任意文本映射成稀疏向量。"""

    def __init__(self, documents: list[list[str]]):
        total = len(documents)
        df: Counter[str] = Counter()
        for doc in documents:
            for token in set(doc):
                df[token] += 1
        self.idf = {t: math.log((total + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        self.default_idf = math.log(total + 1) + 1.0 if total else 1.0

    def vector(self, text: str) -> dict[str, float]:
        counts = Counter(tokens(text))
        if not counts:
            return {}
        vec = {
            t: (1.0 + math.log(c)) * self.idf.get(t, self.default_idf)
            for t, c in counts.items()
        }
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


def centroid(vectors: list[dict[str, float]]) -> dict[str, float]:
    if not vectors:
        return {}
    acc: dict[str, float] = {}
    for vec in vectors:
        for token, value in vec.items():
            acc[token] = acc.get(token, 0.0) + value
    norm = math.sqrt(sum(v * v for v in acc.values())) or 1.0
    return {t: v / norm for t, v in acc.items()}
