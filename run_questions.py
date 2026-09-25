"""tests/questions.md의 12개 질문을 실행해 tests/output.md에 저장한다."""
import re
import time

from assistant import ask
from config import CHAT_MODEL, CLASSIFY_MODEL, EMBED_MODEL, ROOT

rows = re.findall(r"^\|\s*(\d+)\s*\|\s*(\w+)\s*\|\s*(.+?)\s*\|",
                  (ROOT / "tests" / "questions.md").read_text(encoding="utf-8"), re.M)

out = [f"# 12개 질문 실행 로그\n\n답변: `{CHAT_MODEL}` / 분류: `{CLASSIFY_MODEL}` / 임베딩: `{EMBED_MODEL}`\n"]
for num, user, question in rows:
    t = time.time()
    answer = ask(user, question)
    print(f"[{num}] {user}: {question}\n{answer}\n({time.time() - t:.0f}s)\n", flush=True)
    out.append(f"## {num}. `{user}` — {question}\n\n```\n{answer}\n```\n")

(ROOT / "tests" / "output.md").write_text("\n".join(out), encoding="utf-8")
print(f"저장: tests/output.md ({len(rows)}개)")
