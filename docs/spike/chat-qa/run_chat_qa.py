"""TEST-11(챗봇 실사용 시나리오 종합 QA) 테스트 러너.

사용법(backend/.venv 사용 — httpx 등 이미 설치돼 있음):
    cd docs/spike/chat-qa
    /home/tigrelli/projects/tft_hideout/backend/.venv/bin/python3 run_chat_qa.py <카테고리(A~H)> <출력파일.json> [문항수 제한]

예: python3 run_chat_qa.py B results_B.json 10   # B카테고리 앞 10문항만
    python3 run_chat_qa.py C results_C.json      # C카테고리 전체

- questions.json(같은 폴더)의 카테고리별 문항을 순서대로 프로덕션 챗봇
  (https://tft-hideout-backend.onrender.com)에 실제로 질의하고 결과를
  <출력파일.json>에 저장한다.
- rate limit(정책: /api/v1/chat 분당 10회) 대비 8문항마다 65초 대기.
- 시작 전에 반드시 가벼운 호출 1회("안녕" 등)로 Groq 할당량이 살아있는지
  먼저 확인할 것 — 2026-08-14 세션에서 확인된 바, Groq TPD(토큰/일)는
  자정에 리셋되는 게 아니라 24시간 롤링 윈도우라 큰 배치(25문항 등) 직후엔
  몇 시간 동안 여유가 거의 없다. 자세한 내용은 ../../verification/TEST-11-작업결과.md.
"""

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE_URL = "https://tft-hideout-backend.onrender.com/api/v1/chat/message"
QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.json"


def ask(question: str, session_id: str) -> tuple[str, list[str]]:
    """(답변 텍스트, 후속질문 목록)을 반환한다. SSE는 기본 이벤트(명시 안 됨)로
    답변 토큰을, `event: followups`로 후속질문 JSON을, `event: done`으로 종료를
    보낸다 — 이걸 구분 안 하고 "data: "로 시작하는 줄을 전부 답변으로 합치면
    followups JSON 배열이 답변 끝에 그대로 붙어버리는 파싱 버그가 있었다."""
    with httpx.Client(timeout=60) as client:
        with client.stream(
            "POST",
            BASE_URL,
            json={"session_id": session_id, "message": question},
        ) as resp:
            if resp.status_code != 200:
                return f"[HTTP {resp.status_code}] {resp.text}", []
            parts = []
            followups: list[str] = []
            current_event = "message"
            for line in resp.iter_lines():
                if line.startswith("event: "):
                    current_event = line[len("event: ") :]
                    continue
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: ") :]
                if current_event == "done":
                    break
                if current_event == "followups":
                    try:
                        followups = json.loads(payload)
                    except json.JSONDecodeError:
                        pass
                    continue
                parts.append(payload.replace("\\n", "\n"))
            # 프론트(use-chat-conversation.ts)와 동일하게 토큰을 공백으로 join한다
            # (백엔드가 답변을 " " 기준으로 split해 토큰 단위로 보내므로).
            return " ".join(parts), followups


def main() -> None:
    category = sys.argv[1]
    out_path = sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        all_qs = json.load(f)
    questions = all_qs[category][:limit] if limit else all_qs[category]

    results = []
    batch_count = 0
    for item in questions:
        session_id = str(uuid.uuid4())
        started = time.monotonic()
        answer, followups = ask(item["q"], session_id)
        elapsed = time.monotonic() - started
        results.append(
            {
                "no": item["no"],
                "question": item["q"],
                "answer": answer,
                "followups": followups,
                "elapsed_s": round(elapsed, 1),
            }
        )
        print(f"[{category}{item['no']}] ({elapsed:.1f}s) {item['q']}", flush=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        batch_count += 1
        if batch_count >= 8:
            print("-- rate limit pacing: sleeping 65s --", flush=True)
            time.sleep(65)
            batch_count = 0
        else:
            time.sleep(2)

    print(f"DONE: {len(results)} questions -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
