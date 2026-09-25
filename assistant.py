#!/usr/bin/env python3
"""권한 인식 사내 AI 비서.

사용: python assistant.py --user staff01 "질문"   (질문 없이 실행하면 대화 모드)

사용자 등급을 넘는 문서의 본문은 프롬프트에 넣지 않는다. 초과 문서는 유사도 점수로
힌트 여부만 정하고, 힌트가 붙으면 답변 없이 config.py의 고정 문장만 낸다.
"""
import argparse
import json
import re

import config as C
from index import best_line, closest, cosine, embed_query, load_index, score
from llm import embed, generate

SYSTEM = """당신은 하늘물류의 사내 AI 비서입니다.
아래 [문서]에 적힌 내용만 근거로 한국어로 짧고 정확하게 답하세요.
문서에 없는 내용은 추측하지 말고 "문서에서 확인할 수 없습니다"라고 답하세요.

답변 예시 (형식 참고용 가상 문서):
[문서] 출장비: 1일 5만 원, 연 2회까지 증액 신청 가능. 해외 출장 시 항공권은 회사 부담.
[질문] 출장 가면 하루에 얼마 받아?
[답변] 출장비는 1일 5만 원이며, 연 2회까지 증액 신청이 가능합니다.
[질문] 해외 출장 항공권은 내가 내?
[답변] 아니요, 해외 출장 항공권은 회사가 부담합니다."""


def _hint(level: int, visible_scores: dict, hidden: dict) -> str:
    """hidden: {파일명: (등급, 점수)}"""
    if any(g == "S" and s >= C.S_HINT_THRESHOLD for g, s in hidden.values()):
        return C.S_HINT
    # C 문서는 존재 자체가 기밀이라, S 사용자에게만 그리고 질문의 주된 주제가
    # 열람 가능한 문서일 때만 알린다.
    c_max = max((s for g, s in hidden.values() if g == "C"), default=0)
    v_max = max(visible_scores.values(), default=0)
    if level == C.LEVEL["S"] and c_max >= C.C_HINT_THRESHOLD and v_max >= C.RELEVANT_THRESHOLD and v_max > c_max:
        return C.C_HINT
    return ""


def _clean(line: str) -> str:
    line = line.replace("**", "").lstrip("- ").strip()
    if line.startswith("|"):
        line = ", ".join(c.strip() for c in line.strip("|").split("|"))
    return line


def _snippet(line: str, vec: list) -> str:
    line = _clean(line)
    if len(line) <= C.SOURCE_MAX_CHARS:
        return f'"{line}"'
    parts = [p.strip(" ,.") for p in re.split(r"(?<=[,.])\s+", line) if p.strip(" ,.")]
    return f'"…{closest(vec, parts)}…"'


def _title(text: str) -> str:
    return next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), "문서")


def _sources(answer: str, qvec: list, used: list, lines: dict, index: dict) -> str:
    """답변 밑에 붙일 출처. 답변과 가장 가까운 원문 줄을 고르고, 질문과 아주 가까운 줄이
    따로 있으면 함께 붙인다. 모델이 '정보 없음'이라고 답하면 가까운 줄이 없어 생략된다."""
    avec = embed_query(answer)
    titles = {n: _title(index[n]["text"]) for n in used}
    by_answer = max(((best_line(avec, index[n]), n) for n in used), key=lambda x: x[0][1])
    if by_answer[0][1] < C.EVIDENCE_THRESHOLD:  # 제목에만 있는 정보(보고서 날짜 등)
        vecs = embed([titles[n] for n in used])
        by_answer = max((((titles[n], cosine(avec, v)), n) for n, v in zip(used, vecs)), key=lambda x: x[0][1])
    by_question = max(((lines[n], n) for n in used), key=lambda x: x[0][1])

    picked = {}
    for ((line, sim), doc), th, vec in ((by_answer, C.EVIDENCE_THRESHOLD, avec),
                                        (by_question, C.QUESTION_EVIDENCE_THRESHOLD, qvec)):
        if sim < th:
            continue
        snip = "" if line == titles[doc] else _snippet(line, vec)
        if snip not in picked.get(doc, []):
            picked.setdefault(doc, []).append(snip)

    out = []
    for doc, snips in picked.items():
        quotes = " / ".join(s for s in snips if s)
        out.append(f"출처: {titles[doc]}" + (f" — {quotes}" if quotes else ""))
    return "\n".join(out)


def ask(user_id: str, question: str) -> str:
    users = json.loads(C.USERS_FILE.read_text(encoding="utf-8"))
    level = C.LEVEL[users[user_id]["clearance"]]
    index = load_index()
    qvec = embed_query(question)
    scores = score(qvec, index)

    # 권한 필터. 이 아래에서 hidden 문서의 본문은 쓰지 않는다.
    visible = {n: s for n, s in scores.items() if C.LEVEL[index[n]["grade"]] <= level}
    hidden = {n: (index[n]["grade"], s) for n, s in scores.items() if n not in visible}

    # 상위 문서가 답에 영향을 주면 힌트만 준다. LLM 답변과 출처를 붙이지 않아
    # 문서 고유 정보가 섞이거나 모델이 상위 내용을 추측할 여지를 없앤다.
    hint = _hint(level, visible, hidden)
    if hint:
        return f"{C.HINT_ONLY}\n\n{hint}"

    # 핸드북처럼 주제가 섞인 문서는 문서 점수가 낮게 나와서, 문장 점수도 같이 본다.
    lines = {n: best_line(qvec, index[n]) for n in visible}
    relevance = {n: max(s, lines[n][1]) for n, s in visible.items()}
    used = [n for n in sorted(relevance, key=relevance.get, reverse=True)[:C.TOP_K]
            if relevance[n] >= C.RELEVANT_THRESHOLD]

    if not used:
        answer = C.NO_ANSWER
    else:
        context = "\n\n".join(index[n]["text"] for n in used)
        answer = generate(f"[문서]\n{context}\n\n[질문]\n{question}", system=SYSTEM)
        # 모델이 예시의 [답변] 표시를 따라 쓰거나 "확인할 수 없습니다."로 시작한 뒤 답을 잇는 경우 정리
        answer = re.split(r"\**\[답변\]\**:?\s*", answer)[-1].strip()
        answer = re.sub(r"^문서에서 확인할 수 없습니다\.\s+(?=\S)", "", answer)
        src = _sources(answer, qvec, used, lines, index)
        if src:
            answer += "\n" + src
    return answer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("question", nargs="?")
    a = ap.parse_args()
    if a.question:
        print(ask(a.user, a.question))
        return
    users = json.loads(C.USERS_FILE.read_text(encoding="utf-8"))
    u = users[a.user]
    print(f"{u['name']}님({u['role']}), 무엇이든 물어보세요. 종료: exit")
    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q in ("exit", "quit", "종료"):
            break
        if q:
            print(ask(a.user, q), end="\n\n")


if __name__ == "__main__":
    main()
