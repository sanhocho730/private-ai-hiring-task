#!/usr/bin/env python3
"""뼈대. 갈아엎어도 됨. 사용: python starter/assistant.py --user staff01 "질문"
로컬 모델만 사용할 것(Ollama http://127.0.0.1:11434 등). 외부 API 금지."""
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEVEL = {"O": 0, "S": 1, "C": 2}

def load_docs():
    return {p.name: p.read_text(encoding="utf-8") for p in sorted((ROOT / "data/docs").glob("*.md"))}

def classify(doc_text: str) -> str:
    """TODO: 'C' | 'S' | 'O'. 라벨 파일 하드코딩 금지."""
    raise NotImplementedError

def ask(user_id: str, question: str) -> str:
    """TODO: 사용자 등급 이하 문서로 답하고, 초과 문서는 힌트만."""
    users = json.loads((ROOT / "data/users.json").read_text(encoding="utf-8"))
    clearance = users[user_id]["clearance"]
    docs = load_docs()
    visible = {n: t for n, t in docs.items() if LEVEL[classify(t)] <= LEVEL[clearance]}
    hidden = {n: t for n, t in docs.items() if n not in visible}
    raise NotImplementedError

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("question")
    a = ap.parse_args()
    print(ask(a.user, a.question))
