"""분류 정확도 평가"""
import json

from classify import classify_by_llm, classify_by_rules
from config import DOCS_DIR, LEVEL, ROOT

labels = json.loads((ROOT / "tests" / "labels.json").read_text(encoding="utf-8"))

correct = 0
print(f"{'문서':34} {'규칙':4} {'LLM':4} {'최종':4} {'정답':4}")
for path in sorted(DOCS_DIR.glob("*.md")):
    text = path.read_text(encoding="utf-8")
    rule = classify_by_rules(text)
    llm = classify_by_llm(text)
    final = max([g for g in (rule, llm) if g], key=LEVEL.get)
    ok = final == labels[path.name]
    correct += ok
    print(f"{path.name:34} {rule or '-':4} {llm:4} {final:4} {labels[path.name]:4} {'✓' if ok else '✗'}")
print(f"\n정확도: {correct}/{len(labels)}")
