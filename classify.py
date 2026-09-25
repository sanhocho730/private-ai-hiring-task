"""문서 등급 분류. 보안 표식 규칙과 LLM 판단 중 높은 등급을 택한다."""
import re

from config import CLASSIFY_MODEL, LEVEL
from llm import generate

C_MARKERS = ["[기밀]", "대외비", "열람 금지", "극비", "이사회 보고", "개인정보위 신고"]
S_MARKERS = ["내부용", "팀장급", "법무팀", "계약 조건", "위약금", "협상 중", "고객별 매출"]

SYSTEM = """당신은 회사 문서 보안 등급 분류기입니다. 문서를 읽고 등급 한 글자만 답하세요.
C: 기밀. 유출 시 회사에 직접 손해 (인수합병, 보안 사고, 임원 보수 등). 최고 경영진만 열람.
S: 민감. 내부 의사결정, 고객별 매출, 계약 조건 등. 팀장 이상 열람.
O: 사내 공개. 전 직원이 봐도 되는 안내·규정·제품 설명.
답은 C, S, O 중 한 글자만."""


def classify_by_rules(text: str):
    if any(m in text for m in C_MARKERS):
        return "C"
    if any(m in text for m in S_MARKERS):
        return "S"
    return None


def classify_by_llm(text: str) -> str:
    answer = generate(f"문서:\n{text}\n\n등급:", system=SYSTEM, model=CLASSIFY_MODEL)
    m = re.search(r"[CSO]", answer.upper())
    return m.group(0) if m else "C"


def classify(doc_text: str) -> str:
    candidates = [classify_by_llm(doc_text)]
    rule = classify_by_rules(doc_text)
    if rule:
        candidates.append(rule)
    return max(candidates, key=LEVEL.get)
