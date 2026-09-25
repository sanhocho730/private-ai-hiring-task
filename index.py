"""문서 등급과 문서·문장 임베딩을 .cache에 저장해 두고 유사도를 계산한다."""
import hashlib
import json
import math

from classify import classify
from config import CACHE_DIR, CLASSIFY_MODEL, DOCS_DIR, EMBED_MODEL
from llm import embed

CACHE_FILE = CACHE_DIR / "index.json"
INDEX_VERSION = "2"  # 캐시 형식이 바뀌면 올린다


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def _is_rule(line: str) -> bool:
    return bool(line) and set(line) <= set("|-: ")


def _lines(text: str) -> list:
    """제목, 빈 줄, 표 구분선과 머리행을 뺀 원문 줄"""
    ls = [l.strip() for l in text.splitlines()]
    return [l for i, l in enumerate(ls)
            if l and not l.startswith("#") and not _is_rule(l)
            and not (i + 1 < len(ls) and _is_rule(ls[i + 1]))]


def load_index() -> dict:
    """{파일명: {"text", "grade", "vec", "lines"}}"""
    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    index, dirty = {}, False
    for path in sorted(DOCS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        key = hashlib.sha256((INDEX_VERSION + CLASSIFY_MODEL + EMBED_MODEL + text).encode("utf-8")).hexdigest()
        entry = cache.get(path.name)
        if not entry or entry["hash"] != key:
            lines = _lines(text)
            entry = {"hash": key, "grade": classify(text), "vec": embed([text])[0],
                     "lines": list(zip(lines, embed(lines)))}
            dirty = True
        index[path.name] = {"text": text, **entry}
    if dirty:
        CACHE_DIR.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps({n: {k: e[k] for k in ("hash", "grade", "vec", "lines")}
                                          for n, e in index.items()}), encoding="utf-8")
    return index


def embed_query(question: str) -> list:
    return embed([question])[0]


def score(qvec: list, index: dict) -> dict:
    return {name: cosine(qvec, e["vec"]) for name, e in index.items()}


def closest(vec: list, texts: list) -> str:
    return max(zip(texts, embed(texts)), key=lambda x: cosine(vec, x[1]))[0]


def best_line(qvec: list, entry: dict):
    return max(((line, cosine(qvec, v)) for line, v in entry["lines"]), key=lambda x: x[1])
