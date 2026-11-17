#!/usr/bin/env python3
# 자비스의 손 — 화면 찍기 · 누르기 · 글자 입력 · 키 · 스크롤 (모니터 여러 대 지원)
# 처음 한 번: 시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용 / 화면 기록 에 실행하는 앱(터미널 등)을 허용.
#   displays                      모니터 목록 (번호 · 원점 · 크기)
#   shot [N]                      N번 모니터를 찍어 shots/screen-N.png (모니터 좌표 그대로 · 100px 격자)
#   click X Y [--display N] [--double]
#   type "글자"   ·   key return|tab|esc|space|delete|up|down|left|right|cmd+l ...   ·   scroll -5
import subprocess, sys, time
from pathlib import Path

import Quartz as Q

KEYS = {"return": 36, "tab": 48, "space": 49, "delete": 51, "esc": 53, "left": 123, "right": 124,
        "down": 125, "up": 126, "a": 0, "c": 8, "v": 9, "l": 37, "t": 17, "w": 13, "r": 15, "f": 3}
MODS = {"cmd": Q.kCGEventFlagMaskCommand, "shift": Q.kCGEventFlagMaskShift,
        "alt": Q.kCGEventFlagMaskAlternate, "ctrl": Q.kCGEventFlagMaskControl}


def displays():
    ids = Q.CGGetActiveDisplayList(16, None, None)[1]
    return [Q.CGDisplayBounds(d) for d in ids]   # 1번 = 주 모니터 (screencapture -D 번호와 같음)


def post(e):
    Q.CGEventPost(Q.kCGHIDEventTap, e)


def click(x, y, n=1, double=False):
    b = displays()[n - 1]
    p = (b.origin.x + x, b.origin.y + y)        # 모니터 좌표 → 전체 화면 좌표
    post(Q.CGEventCreateMouseEvent(None, Q.kCGEventMouseMoved, p, 0))
    for i in range(2 if double else 1):
        for t in (Q.kCGEventLeftMouseDown, Q.kCGEventLeftMouseUp):
            e = Q.CGEventCreateMouseEvent(None, t, p, 0)
            Q.CGEventSetIntegerValueField(e, Q.kCGMouseEventClickState, i + 1)
            post(e)
        time.sleep(0.05)


def type_text(s):
    for ch in s:                                 # 한글도 그대로 입력 (유니코드 직접 전송)
        for down in (True, False):
            e = Q.CGEventCreateKeyboardEvent(None, 0, down)
            Q.CGEventKeyboardSetUnicodeString(e, len(ch.encode("utf-16-le")) // 2, ch)
            post(e)
        time.sleep(0.01)


def key(combo):
    *mods, k = combo.lower().split("+")
    flags = 0
    for m in mods:
        flags |= MODS[m]
    for down in (True, False):
        e = Q.CGEventCreateKeyboardEvent(None, KEYS[k], down)
        Q.CGEventSetFlags(e, flags)
        post(e)


def shot(n=1):
    b = displays()[n - 1]
    out = Path(__file__).resolve().parent / "shots"
    out.mkdir(exist_ok=True)
    raw, png = out / f"raw-{n}.png", out / f"screen-{n}.png"
    subprocess.run(["screencapture", "-x", "-D", str(n), str(raw)], check=True)
    w, h = int(b.size.width), int(b.size.height)  # 레티나 2배 이미지를 모니터 좌표 크기로 줄임
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(raw), "-vf",
                    f"scale={w}:{h},drawgrid=w=100:h=100:t=1:c=red@0.35", str(png)], check=True)
    raw.unlink()
    print(f"{png}  ({w}x{h}, 이미지 좌표 = 모니터 {n} 좌표)")


def main(a):
    cmd = a[0] if a else "displays"
    if cmd == "displays":
        for i, b in enumerate(displays(), 1):
            print(f"{i}: 원점 ({int(b.origin.x)},{int(b.origin.y)}) 크기 {int(b.size.width)}x{int(b.size.height)}")
    elif cmd == "shot":
        shot(int(a[1]) if len(a) > 1 else 1)
    elif cmd == "click":
        n = int(a[a.index("--display") + 1]) if "--display" in a else 1
        click(float(a[1]), float(a[2]), n, "--double" in a)
    elif cmd == "type":
        type_text(a[1])
    elif cmd == "key":
        key(a[1])
    elif cmd == "scroll":
        post(Q.CGEventCreateScrollWheelEvent(None, Q.kCGScrollEventUnitLine, 1, int(a[1])))
    else:
        sys.exit(__doc__ or "unknown command")


if __name__ == "__main__":
    main(sys.argv[1:])
