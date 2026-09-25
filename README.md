# 권한 인식 사내 AI 비서 (로컬 전용)

```
ollama pull qwen2.5:3b && ollama pull exaone3.5:2.4b && ollama pull bge-m3    # 모델 준비 (ollama serve 실행 상태)
python assistant.py --user staff01 "연차는 몇 일이야?"                       # 질문 없이 실행하면 대화 모드
python eval_classify.py && python run_questions.py && python check_leaks.py   # 분류 정확도, 12개 질문 로그, 유출 검사
```

설계는 [DESIGN.md](DESIGN.md), 12개 질문 출력은 [tests/output.md](tests/output.md), 모델·임계값 실험은 [eval/REPORT.md](eval/REPORT.md).

Anthropic의 Claude Code를 사용해 작업했습니다.
