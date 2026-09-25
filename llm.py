"""로컬 Ollama 호출 (urllib, 루프백 주소만 허용)"""
import json
import urllib.parse
import urllib.request

from config import CHAT_MODEL, EMBED_MODEL, OLLAMA_URL

_host = urllib.parse.urlparse(OLLAMA_URL).hostname
if _host not in ("127.0.0.1", "localhost", "::1"):
    raise RuntimeError(f"로컬 주소만 허용: {OLLAMA_URL}")


def _post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        OLLAMA_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def generate(prompt: str, system: str = "", model: str = CHAT_MODEL) -> str:
    out = _post("/api/generate", {
        "model": model,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "seed": 42},
    })
    return out["response"].strip()


def embed(texts: list) -> list:
    return _post("/api/embed", {"model": EMBED_MODEL, "input": texts})["embeddings"]
