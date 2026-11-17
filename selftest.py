#!/usr/bin/env python3
# 자체 점검: 글자 규칙 확인 → macOS 목소리로 만든 녹음을 마이크 대신 흘려 넣어 전체 흐름 확인
#   .venv/bin/python selftest.py          (규칙만: --quick)
import subprocess, sys, tempfile, time
from pathlib import Path

import jarvis as J

# 1) 글자 규칙
assert J.is_wake("자비스 지금 몇 시야") and J.is_wake("저비스?") and J.is_wake("Jarvis") and not J.is_wake("자전거")
assert J.strip_wake("자비스, 지금 몇 시야") == "지금 몇 시야"
assert J.add_qmark("지금 몇 시야") == "지금 몇 시야?" and J.add_qmark("뭐 하니") == "뭐 하니?"
assert J.add_qmark("불 꺼 줘") == "불 꺼 줘"
assert J.clean("감사합니다.") == "" and J.clean("자료 정리해 줘서 감사합니다 정말 큰 도움이 됐어요") != ""
assert J.CONTINUE_END.search("내일 일정은 그리고") and not J.CONTINUE_END.search("내일 일정 알려 줘")
print("규칙 OK")
if "--quick" in sys.argv:
    sys.exit()


def speak_wav(text, d):
    out = Path(d) / f"{abs(hash(text))}.wav"
    subprocess.run(["say", "-v", "Yuna", "--data-format=LEI16@16000", "-o", str(out), text], check=True)
    return str(out)


# 2) 전체 흐름: 호출 → 질문 → "…그리고" 이어 말하기 → 대기 (스피커 소리는 끔)
with tempfile.TemporaryDirectory() as d:
    clips = [speak_wav(t, d) for t in ["자비스", "오늘 무슨 요일이야", "내일 날짜는 그리고", "모레 날짜도 알려 줘", "자비스 대기"]]
    said = []
    J.Mouth.say = lambda self, s: said.append(s)          # 소리 대신 기록
    j = J.Jarvis()
    j.mouth.speaking = False
    orig = j.handle

    def handle(text):
        orig(text)
        while j.brain.busy:                               # 시험에선 대답이 끝난 뒤 다음 말을 흘려 넣음
            time.sleep(0.1)
    j.handle = handle
    t0 = time.time()
    j.run(J.wav_frames(clips))
    print("자비스가 한 말:", said, f"({time.time() - t0:.0f}s)")
    assert said[0] == "네?", "호출어에 '네?'로 대답해야 함"
    assert any(("요일" in s) for s in said), "요일 질문에 대답해야 함"
    assert said[-1] == "대기할게요." and j.mode == "idle", "'자비스 대기'로 대기 모드"
    print("흐름 OK")

    # 3) 글자로 지시: 대기 중이어도 호출어 없이 바로 대답
    said.clear()
    j.typed("일 더하기 일은 몇이야")
    time.sleep(0.5)
    while j.brain.busy:
        time.sleep(0.1)
    print("글자 지시 →", said)
    assert said and j.mode == "chat", "글자 지시에 대답해야 함"
    print("글자 OK")
