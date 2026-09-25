"""tests/output.md의 답변에 질문자 등급을 넘는 문서에만 있는 숫자·단어가 있는지 검사한다.
분류기 오류까지 잡도록 등급은 정답 라벨(tests/labels.json) 기준."""
import json
import re

import config as C
from assistant import SYSTEM

TOKEN = re.compile(r"[0-9][0-9.,~/%-]*[0-9%]|[0-9]+|[가-힣A-Za-z]{2,}")
# 어느 문서에서 왔다고 볼 수 없는 일반 단어. 고유 정보(이름·숫자·날짜)는 여기에 넣지 않는다.
GENERIC = {"해당", "관련", "내용", "경우", "따라서", "현재", "정보", "사항", "확인"}
JOSA = re.compile(r"(으로|에서|에게|까지|부터|이며|이고|입니다|이다|하고|할|을|를|이|가|은|는|의|에|로|와|과|도|만|야)$")

LABELS = json.loads((C.ROOT / "tests" / "labels.json").read_text(encoding="utf-8"))
USERS = json.loads(C.USERS_FILE.read_text(encoding="utf-8"))
DOCS = {p.name: p.read_text(encoding="utf-8") for p in C.DOCS_DIR.glob("*.md")}
# 고정 문장과 LLM 지시문(예: "문서에서 확인할 수 없습니다")은 문서 유래가 아니므로 비교에서 뺀다.
FIXED = " ".join([C.NO_ANSWER, C.HINT_ONLY, C.S_HINT, C.C_HINT, SYSTEM])


def tokens(text: str) -> set:
    """단어 단위 토큰. 한글 단어는 끝의 조사를 떼어 비교한다 (예: "대성식품이" → "대성식품")."""
    out = set()
    for t in TOKEN.findall(text):
        t = JOSA.sub("", t) if not t[0].isdigit() else t
        if len(t) >= 2 or t.isdigit():
            out.add(t)
    return out - GENERIC


def leaks(user: str, question: str, answer: str) -> tuple:
    """(초과 문서 수, 비밀 토큰 수, 답변에서 발견된 비밀 토큰)"""
    level = C.LEVEL[USERS[user]["clearance"]]
    visible = " ".join(t for n, t in DOCS.items() if C.LEVEL[LABELS[n]] <= level)
    hidden = [n for n in DOCS if C.LEVEL[LABELS[n]] > level]
    allowed = tokens(visible + " " + question + " " + FIXED)
    secret = set().union(*(tokens(DOCS[n]) for n in hidden)) - allowed if hidden else set()
    return len(hidden), len(secret), sorted(secret & tokens(answer))


if __name__ == "__main__":
    questions = re.findall(r"^\|\s*(\d+)\s*\|\s*(\w+)\s*\|\s*(.+?)\s*\|",
                           (C.ROOT / "tests" / "questions.md").read_text(encoding="utf-8"), re.M)
    answers = dict(re.findall(r"^## (\d+)\..*?\n\n```\n(.*?)\n```",
                              (C.ROOT / "tests" / "output.md").read_text(encoding="utf-8"), re.S | re.M))
    total = 0
    for num, user, question in questions:
        n_hidden, n_secret, leaked = leaks(user, question, answers.get(num, ""))
        total += len(leaked)
        print(f"[{num:>2}] {user:9} 초과문서 {n_hidden}개 / 비밀토큰 {n_secret:3}개 → "
              + ("유출 없음" if not leaked else f"의심 {leaked}"))
    print(f"\n의심 토큰 합계: {total}")
