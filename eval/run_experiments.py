"""분류·답변 모델 비교와 임계값 실험. 결과는 eval/*.csv, eval/answers.json에 저장한다.

사용: python eval/run_experiments.py
"""
import csv
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import assistant  # noqa: E402
import classify  # noqa: E402
import config as C  # noqa: E402
import llm  # noqa: E402
from check_leaks import leaks  # noqa: E402
from index import best_line, embed_query, load_index, score  # noqa: E402

OUT = ROOT / "eval"
MODELS = ["qwen2.5:3b", "exaone3.5:2.4b"]
LABELS = json.loads((ROOT / "tests" / "labels.json").read_text(encoding="utf-8"))
USERS = json.loads(C.USERS_FILE.read_text(encoding="utf-8"))
QUESTIONS = re.findall(r"^\|\s*(\d+)\s*\|\s*(\w+)\s*\|\s*(.+?)\s*\|",
                       (ROOT / "tests" / "questions.md").read_text(encoding="utf-8"), re.M)

# tests/questions.md의 "기대" 칸을 옮긴 채점 기준.
# EXPECTED: answer(권한 안에서 답함) / S(S 힌트) / C(C 힌트) / none(힌트 없이 거부)
EXPECTED = {"1": "answer", "2": "S", "3": "S", "4": "none", "5": "answer", "6": "answer",
            "7": "answer", "8": "none", "9": "C", "10": "answer", "11": "answer", "12": "answer"}
# 답변에 있어야 할 핵심 정보. 안쪽 목록은 같은 정보의 다른 표기.
FACTS = {"1": [["15"], ["25"]],
         "5": [["10만"]],
         "6": [["대성식품"], ["42"]],
         "7": [["90일"], ["2027-06", "2027년 6월"]],
         "10": [["180"], ["10/5", "10월 5"], ["11/15", "11월 15"]],
         "11": [["30%"], ["협상"], ["요청"]],
         "12": [["9/14", "9월 14"]]}
HAN = re.compile(r"[一-鿿぀-ヿ]")  # 한자·가나


def write_csv(name, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def count_facts(num, text):
    return sum(any(v in text for v in alts) for alts in FACTS.get(num, []))


# 1. 분류: 모델별 LLM 판단, 규칙, 최종 등급
def exp_classify():
    rows = []
    for path in sorted(C.DOCS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        row = {"doc": path.name, "label": LABELS[path.name], "rule": classify.classify_by_rules(text) or ""}
        for m in MODELS:
            ans = llm.generate(f"문서:\n{text}\n\n등급:", system=classify.SYSTEM, model=m)
            hit = re.search(r"[CSO]", ans.upper())
            row[m] = hit.group(0) if hit else "C"
        rows.append(row)
    write_csv("classify_result.csv", rows)

    def acc(pick):
        return sum(pick(r) == r["label"] for r in rows)

    summary = [{"method": "rules only (표식 없으면 O)", "correct": acc(lambda r: r["rule"] or "O"), "total": len(rows)}]
    for m in MODELS:
        summary.append({"method": f"{m} only", "correct": acc(lambda r: r[m]), "total": len(rows)})
        summary.append({"method": f"{m} + rules (높은 등급)",
                        "correct": acc(lambda r: max([g for g in (r[m], r["rule"]) if g], key=C.LEVEL.get)),
                        "total": len(rows)})
    write_csv("model_classify.csv", summary)
    return rows, summary


# 2. 답변: 모델별 12개 출력, 핵심 정보 포함, 한자 혼입, 유출 검사
def exp_answers():
    results, summary = {}, []
    for m in MODELS:
        assistant.generate = lambda prompt, system="", _m=m: llm.generate(prompt, system, model=_m)
        items = []
        for num, user, question in QUESTIONS:
            t = time.time()
            answer = assistant.ask(user, question)
            body = "\n".join(l for l in answer.splitlines() if not l.startswith("출처:"))
            items.append({"num": num, "user": user, "question": question, "answer": answer,
                          "seconds": round(time.time() - t, 1),
                          "facts_expected": len(FACTS.get(num, [])),
                          "facts_in_answer": count_facts(num, body),
                          "facts_with_source": count_facts(num, answer),
                          "han_chars": "".join(HAN.findall(body)),
                          "leaked_tokens": leaks(user, question, answer)[2]})
            print(f"  [{m}] {num}번 {items[-1]['seconds']}s", flush=True)
        results[m] = items
        summary.append({"model": m,
                        "facts_expected": sum(i["facts_expected"] for i in items),
                        "facts_in_answer": sum(i["facts_in_answer"] for i in items),
                        "facts_with_source": sum(i["facts_with_source"] for i in items),
                        "answers_with_han": sum(bool(i["han_chars"]) for i in items),
                        "leaked_tokens": sum(len(i["leaked_tokens"]) for i in items),
                        "avg_seconds": round(sum(i["seconds"] for i in items) / len(items), 1)})
    assistant.generate = llm.generate
    (OUT / "answers.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv("model_answers.csv", summary)
    return summary


# 3. 임계값: 12개 질문의 점수와, 임계값을 바꿨을 때 판정이 맞는 개수
def decide(q, s_th, c_th, r_th):
    """assistant.ask()와 같은 판정 규칙을 임계값만 바꿔 계산한다."""
    if q["s_max"] >= s_th:
        return "S"
    if q["level"] == C.LEVEL["S"] and q["c_max"] >= c_th and q["v_doc"] >= r_th and q["v_doc"] > q["c_max"]:
        return "C"
    return "answer" if q["v_rel"] >= r_th else "none"


def exp_thresholds():
    index = load_index()
    qs = []
    for num, user, question in QUESTIONS:
        level = C.LEVEL[USERS[user]["clearance"]]
        qvec = embed_query(question)
        s = score(qvec, index)
        vis = {n: x for n, x in s.items() if C.LEVEL[index[n]["grade"]] <= level}
        hid = {n: x for n, x in s.items() if n not in vis}
        qs.append({"num": num, "user": user, "level": level, "expected": EXPECTED[num],
                   "v_doc": max(vis.values()),
                   "v_rel": max(max(x, best_line(qvec, index[n])[1]) for n, x in vis.items()),
                   "s_max": max([x for n, x in hid.items() if index[n]["grade"] == "S"], default=0),
                   "c_max": max([x for n, x in hid.items() if index[n]["grade"] == "C"], default=0)})
    base = {"s": C.S_HINT_THRESHOLD, "c": C.C_HINT_THRESHOLD, "r": C.RELEVANT_THRESHOLD}
    write_csv("scores.csv", [{"num": q["num"], "user": q["user"], "expected": q["expected"],
                              "actual": decide(q, base["s"], base["c"], base["r"]),
                              "visible_doc_max": round(q["v_doc"], 3), "visible_line_max": round(q["v_rel"], 3),
                              "hidden_S_max": round(q["s_max"], 3), "hidden_C_max": round(q["c_max"], 3)}
                             for q in qs])
    sweep, ranges = [], {}
    for p, name in (("s", "S_HINT_THRESHOLD"), ("c", "C_HINT_THRESHOLD"), ("r", "RELEVANT_THRESHOLD")):
        ok_values = []
        for i in range(30, 81):
            th = dict(base, **{p: i / 100})
            correct = sum(decide(q, th["s"], th["c"], th["r"]) == q["expected"] for q in qs)
            sweep.append({"param": name, "value": i / 100, "correct": correct, "total": len(qs)})
            if correct == len(qs):
                ok_values.append(i / 100)
        ranges[name] = (min(ok_values), max(ok_values)) if ok_values else None
    write_csv("threshold_sweep.csv", sweep)
    return qs, ranges


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    print("1. 분류 모델 비교")
    _, cls = exp_classify()
    for r in cls:
        print(f"  {r['method']:30} {r['correct']}/{r['total']}")
    print("2. 답변 모델 비교")
    for r in exp_answers():
        print(f"  {r}")
    print("3. 임계값 실험 (다른 두 값은 config 기본값 고정, 12개 모두 맞는 구간)")
    for k, v in exp_thresholds()[1].items():
        print(f"  {k:20} 현재 {getattr(C, k):.2f} / 12개 모두 맞는 구간 {v}")
