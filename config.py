"""모델, 임계값, 고정 문장."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
DOCS_DIR = ROOT / "data" / "docs"
USERS_FILE = ROOT / "data" / "users.json"
CACHE_DIR = ROOT / ".cache"

# 로컬 Ollama만 사용
OLLAMA_URL = "http://127.0.0.1:11434"
CLASSIFY_MODEL = "qwen2.5:3b"   # exaone은 공개 문서를 S로 올려 7/9
CHAT_MODEL = "exaone3.5:2.4b"   # qwen2.5:3b는 한자가 섞여 나옴
EMBED_MODEL = "bge-m3"

LEVEL = {"O": 0, "S": 1, "C": 2}

# bge-m3 코사인 유사도 기준. 12개 질문 점수 분포를 보고 정함
TOP_K = 3
RELEVANT_THRESHOLD = 0.50   # 열람 가능 문서의 관련 기준
S_HINT_THRESHOLD = 0.55
C_HINT_THRESHOLD = 0.46
EVIDENCE_THRESHOLD = 0.56   # 답변-원문 줄
QUESTION_EVIDENCE_THRESHOLD = 0.60  # 질문-원문 줄
SOURCE_MAX_CHARS = 60       # 이보다 긴 출처는 관련 부분만 인용

# 고정 문장. 문서 내용을 끼워 넣지 않는다
NO_ANSWER = "제가 열람할 수 있는 문서에서는 관련 내용을 찾지 못했습니다."
HINT_ONLY = "제가 볼 수 있는 문서만으로는 확정해서 답하기 어렵습니다."  # 힌트가 붙을 때의 답변
S_HINT = "※ 상위 등급 문서에 관련 내용이 있어 답이 달라질 수 있습니다. 팀장에게 확인하세요. (상세 열람 권한 없음)"
C_HINT = "※ 상위 등급에서 관련 검토가 진행 중인 정황이 있어 내용이 바뀔 수 있습니다. (상세 열람 권한 없음)"
