#!/usr/bin/env python3
# 자비스 (macOS) — 귀(STT) · 두뇌(Claude Code 상시 연결) · 입(say) · 얼굴(브라우저) · 폰 접속
# 흐름: 마이크 → VAD로 말 구간 자르기 → 글자로 바꾸기 → "자비스" 호출어 확인 → 대화 모드
#       → Claude Code 에 보내고 문장 단위로 받아 바로 말하기 → 30초 조용하면 대기로
import base64, difflib, io, json, os, queue, re, subprocess, sys, tempfile, threading, time, wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

import numpy as np

HERE = Path(__file__).resolve().parent
RATE, FRAME_MS = 16000, 30                       # VAD 가 받는 형식: 16kHz 모노, 30ms 조각
FRAME = RATE * FRAME_MS // 1000                  # 조각 하나 = 480 샘플
END_SIL = float(os.getenv("JARVIS_END_SIL", "0.8"))     # 이만큼 조용하면 말이 끝난 것으로 봄 (v7: 0.8초)
MORE_WAIT = 1.5                                  # "…그리고" 처럼 안 끝난 말은 이만큼 더 기다림
CHAT_TIMEOUT = 30                                # 대화 모드에서 30초 말이 없으면 대기로
MIN_DB = -50                                     # 이보다 작은 소리는 보내지 않음 (v2: "감사합니다" 환청 방지)
VOICE = os.getenv("JARVIS_VOICE", "Yuna")        # macOS 한국어 목소리 (say -v '?' | grep ko_KR)
MODEL = os.getenv("JARVIS_MODEL", "sonnet")
PORT = int(os.getenv("JARVIS_PORT", "8765"))
KEY = os.getenv("JARVIS_KEY", "")                # 폰 접속 비밀번호 (비우면 검사 안 함)
HEADPHONES = os.getenv("JARVIS_HEADPHONES") == "1"  # 이어폰이면 아무 말에나 끼어들기 가능

WAKE = re.compile(r"(횃비스|햇비스|자비스|쟈비스|재비스|제비스|저비스|자비즈|자빗|jarvis|javis|jervis)[,.!?\s]*", re.I)
HALLUCINATIONS = ("감사합니다", "시청해 주셔서", "구독과 좋아요", "MBC 뉴스", "자막 제공")
CONTINUE_END = re.compile(r"(그리고|그런데|근데|는데|은데|인데|하고|해서|이랑|랑|이고)[.,]?$")
QUESTION_END = re.compile(r"(니|까|나요|가요|냐|죠|래|는지|은지)$")
QUESTION_WORD = re.compile(r"(몇|뭐|무엇|무슨|어디|언제|누구|왜|어떻게|얼마|어때|어떤)")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---------- 글자 다듬기 (호출어 · 물음표 · 환청) ----------
def is_wake(text):
    return bool(WAKE.search(text))


def strip_wake(text):
    return WAKE.sub("", text, count=1).strip(" ,.")


def add_qmark(text):
    t = text.strip()
    if not t or t[-1] in ".?!~":
        return t
    if QUESTION_END.search(t) or (QUESTION_WORD.search(t) and re.search(r"(야|어|요|지)$", t)):
        return t + "?"
    return t


def clean(text):
    t = text.strip()
    if any(h in t for h in HALLUCINATIONS) and len(t) < 20:
        return ""
    return t


# ---------- 귀: 글자로 바꾸기 ----------
def stt(audio_bytes, suffix=".wav"):
    """Groq Whisper(키가 있으면) → 없으면 내 맥에서 mlx-whisper. 서비스 비용·한도는 제공자 정책을 따른다."""
    prompt = "안녕하세요. 지금 몇 시야? 자비스, 오늘 날씨 어때?"   # 부호 붙은 예시 → 물음표가 잘 붙음
    if os.getenv("GROQ_API_KEY"):
        import requests
        r = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"]},
            files={"file": ("a" + suffix, audio_bytes)},
            data={"model": "whisper-large-v3", "language": "ko", "prompt": prompt},
            timeout=30)
        r.raise_for_status()
        return r.json()["text"]
    import mlx_whisper
    with tempfile.NamedTemporaryFile(suffix=suffix) as f:
        f.write(audio_bytes); f.flush()
        return mlx_whisper.transcribe(f.name, path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
                                      language="ko", initial_prompt=prompt)["text"]


def to_wav(pcm):
    """int16 PCM → wav 바이트. 소리가 작으면 자동으로 키움 (v8: 작은 목소리 대책)."""
    x = pcm.astype(np.float32)
    peak = np.abs(x).max() or 1
    x = np.clip(x * min(8.0, 0.9 * 32767 / peak), -32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(x.tobytes())
    return buf.getvalue()


def db(pcm):
    rms = np.sqrt(np.mean((pcm.astype(np.float32) / 32768) ** 2)) or 1e-9
    return 20 * np.log10(rms)


# ---------- 얼굴: 상태를 브라우저로 보내기 ----------
class Face:
    def __init__(self):
        self.clients, self.lock = [], threading.Lock()
        self.last = {"state": "idle", "text": ""}

    def send(self, **ev):
        self.last.update(ev)
        msg = "data: " + json.dumps(ev, ensure_ascii=False) + "\n\n"
        with self.lock:
            for q in self.clients:
                q.put(msg)


face = Face()


# ---------- 입: 문장 단위로 바로 말하기 ----------
class Mouth:
    def __init__(self):
        self.q, self.proc, self.speaking, self.now = queue.Queue(), None, False, ""
        self.recent = []  # 받아쓰기가 늦게 도착해도 최근 출력 문장을 에코로 식별한다.
        threading.Thread(target=self._run, daemon=True).start()

    def say(self, text):
        if text.strip():
            self.q.put(text)

    def _run(self):
        while True:
            text = self.q.get()
            self.speaking, self.now = True, text
            self.recent = (self.recent + [(time.monotonic(), text)])[-6:]
            face.send(state="speaking", text=text)
            self.proc = subprocess.Popen(["say", "-v", VOICE, text])
            self.proc.wait()
            self.recent = [(time.monotonic(), text) if t == text else (at, t) for at, t in self.recent]
            self.proc = None
            if self.q.empty():
                self.speaking, self.now = False, ""
                face.send(state="listening")

    def stop(self):
        while not self.q.empty():
            self.q.get_nowait()
        if self.proc:
            self.proc.terminate()
        self.speaking = False


def synth_file(text):
    """폰으로 돌려줄 목소리 파일 (m4a)."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "r.m4a"
        subprocess.run(["say", "-v", VOICE, "--file-format=m4af", "--data-format=aac", "-o", str(out), text], check=True)
        return out.read_bytes()


# ---------- 두뇌: Claude Code 를 한 번 켜 두고 계속 대화 ----------
class Brain:
    def __init__(self):
        persona = (HERE / "persona.md").read_text(encoding="utf-8")
        self.proc = subprocess.Popen(
            ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json",
             "--verbose", "--include-partial-messages", "--model", MODEL,
             "--setting-sources", "project",          # 내 PC 개인 설정(권한 건너뛰기 등)을 끌어오지 않음
             "--settings", str(HERE / "permissions.json"),
             "--permission-mode", "dontAsk",          # permissions.json 허용 목록 밖은 자동 거절
             "--append-system-prompt", persona],
            cwd=HERE, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.lock = threading.Lock()   # 마이크와 폰이 동시에 물어도 한 번에 하나씩
        self.busy = False
        self.cancel = threading.Event()

    def ask(self, text, on_sentence, on_tool=lambda: None):
        """답을 쓰는 대로 받아, 문장이 하나 완성될 때마다 on_sentence 호출."""
        with self.lock:
            self.busy = True
            self.cancel.clear()
            self.proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n")
            self.proc.stdin.flush()
            buf = ""
            for line in self.proc.stdout:
                e = json.loads(line)
                if e.get("type") == "result":
                    break
                if e.get("type") != "stream_event":
                    continue
                ev = e["event"]
                if ev.get("type") == "content_block_start" and ev["content_block"].get("type") == "tool_use":
                    on_tool()
                if ev.get("type") == "content_block_delta" and ev["delta"].get("type") == "text_delta":
                    buf += ev["delta"]["text"]
                    *done, buf = re.split(r"(?<=[.!?。\n])\s*", buf)
                    for s in done:
                        if s.strip() and not self.cancel.is_set():
                            on_sentence(s.strip())
            if buf.strip() and not self.cancel.is_set():
                on_sentence(buf.strip())
            self.busy = False

    def interrupt(self):
        """생각/작업 중인 답을 바로 멈춤 (끼어들기 · "멈춰")."""
        if self.busy:
            self.cancel.set()
            self.proc.stdin.write(json.dumps({"type": "control_request", "request_id": str(time.time()),
                                              "request": {"subtype": "interrupt"}}) + "\n")
            self.proc.stdin.flush()


# ---------- 마이크 → 말 구간 ----------
def mic_frames():
    import sounddevice as sd
    q = queue.Queue()
    log("마이크:", sd.query_devices(kind="input")["name"])
    stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=FRAME,
                            callback=lambda d, *_: q.put(d[:, 0].copy()))
    with stream:
        while True:
            yield q.get()


def wav_frames(paths):
    """시험용: wav 파일을 마이크 대신 흘려 넣음 (파일 사이에 2초 무음)."""
    for p in paths:
        with wave.open(p) as w:
            assert w.getframerate() == RATE and w.getnchannels() == 1, "16kHz 모노 wav 만"
            x = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        x = np.concatenate([np.zeros(RATE // 2, np.int16), x, np.zeros(RATE * 2, np.int16)])
        for i in range(0, len(x) - FRAME, FRAME):
            yield x[i:i + FRAME]


def segments(frames, on_start):
    """VAD 로 사람 말소리만 골라 구간으로 자름. 말 시작 0.24초 앞도 같이 담아 첫 글자 잘림 방지."""
    import webrtcvad
    vad = webrtcvad.Vad(2)
    pre, cur, sil, n = [], [], 0, 0
    for f in frames:
        n += 1
        if n % 3 == 0:
            face.send(level=round(max(0.0, (float(db(f)) + 60) / 50), 2))
        speech = vad.is_speech(f.tobytes(), RATE)
        if cur:
            cur.append(f)
            sil = 0 if speech else sil + 1
            if sil * FRAME_MS / 1000 >= END_SIL:
                pcm = np.concatenate(cur)
                cur = []
                if len(pcm) > RATE * 0.25 and db(pcm) > MIN_DB:
                    yield pcm
        elif speech:
            cur, sil = pre + [f], 0
            on_start()
        pre = (pre + [f])[-8:]


# ---------- 본체 ----------
class Jarvis:
    def __init__(self):
        from demo_brain import DemoBrain
        self.mouth = Mouth()
        self.brain = DemoBrain(face) if "--demo" in sys.argv else Brain()
        self.mode, self.last = "idle", time.time()
        self.pending = ""            # 생각하는 도중 끼어든 말과 합치기 위해 보관
        self.texts = queue.Queue()

    def on_speech_start(self):
        # 이어폰 모드: 말을 시작하자마자 자비스가 멈춤 (스피커 모드는 "자비스"라고 불러야 멈춤)
        if HEADPHONES and self.mode == "chat" and self.mouth.speaking:
            self.mouth.stop(); self.brain.interrupt()

    def ear(self, frames):
        try:
            for pcm in segments(frames, self.on_speech_start):
                t0 = time.time()
                try:
                    text = add_qmark(clean(stt(to_wav(pcm))))
                except Exception as e:           # 네트워크 끊김 등 — 이번 말만 버리고 계속 듣기
                    log("받아쓰기 실패:", e); continue
                if text:
                    log(f"들음({time.time() - t0:.1f}s):", text)
                    self.texts.put(text)
        finally:
            self.texts.put(None)

    def respond(self, text):
        self.pending, self.last = text, time.time()
        face.send(state="thinking", text=text)
        t0, first = time.time(), []

        def sentence(s):
            if not first:
                first.append(1); log(f"첫마디까지 {time.time() - t0:.1f}s")
            log("자비스:", s)
            self.mouth.say(s)

        def tool():
            face.send(state="working")
            if not first:
                first.append(1); self.mouth.say("확인해 볼게요.")

        self.brain.ask(text, sentence, tool)
        if not self.brain.cancel.is_set():
            self.pending = ""
        self.last = time.time()

    def submit(self, text):
        threading.Thread(target=self.respond, args=(text,), daemon=True).start()

    def typed(self, text):
        """글자로 지시: 호출어 없이 바로 대화. 하던 말·생각은 멈추고 새 지시를 받음."""
        self.mode, self.last = "chat", time.time()
        self.mouth.stop(); self.brain.interrupt()
        while self.brain.busy:
            time.sleep(0.05)
        face.send(state="listening", text=text)
        self.submit(add_qmark(text))

    def keyboard(self):
        """터미널에 글자를 치고 Enter → 지시."""
        try:
            while True:
                line = input().strip()
                if line:
                    self.typed(line)
        except EOFError:                         # 자동 실행(launchd)처럼 키보드가 없을 때
            pass

    def echo(self, text):
        """스피커 모드에서 자비스 자기 목소리가 다시 들린 것인지 (글자 비교로 거름)."""
        normalize = lambda s: re.sub(r"[^가-힣a-z0-9]", "", s.lower())
        heard = normalize(text)
        recent = [s for at, s in self.mouth.recent if time.monotonic() - at < 12]
        return any(difflib.SequenceMatcher(None, heard, normalize(s)).ratio() > 0.55
                   or (len(heard) >= 8 and heard in normalize(s)) for s in recent)

    def handle(self, text):
        if not HEADPHONES and self.echo(text):
            log("스피커 에코 제외:", text)
            return
        self.last = time.time()
        if self.mouth.speaking:
            if not (HEADPHONES or (is_wake(text) and not self.echo(text))):
                return                          # 스피커 모드: 내 목소리 울림일 가능성 → 무시
            self.mouth.stop(); self.brain.interrupt()
            text = strip_wake(text)
            if not text:
                self.mouth.say("네?"); return
        if self.mode == "idle":
            if not is_wake(text):
                return
            self.mode = "chat"
            face.send(state="listening", text="")
            text = strip_wake(text)
            if not text:
                self.mouth.say("네?"); return
        if re.search(r"(대기|그만 들어|잘 자)", text) and len(text) < 12:
            self.mode = "idle"; self.mouth.stop(); self.brain.interrupt()
            self.mouth.say("대기할게요."); face.send(state="idle", text="")
            return
        if self.brain.busy:                     # 생각 중에 말을 더 하면 앞말과 합쳐 다시 생각
            self.brain.interrupt()
            text = (self.pending + " " + text).strip()
            while self.brain.busy:
                time.sleep(0.05)
        self.submit(text)

    def run(self, frames=None):
        if frames is not None:                   # --text 모드면 마이크 없이 글자로만
            threading.Thread(target=self.ear, args=(frames,), daemon=True).start()
        if sys.stdin.isatty():
            threading.Thread(target=self.keyboard, daemon=True).start()
        face.send(state="idle")
        log("대기 중 — '자비스'라고 부르거나, 여기에 글자를 치고 Enter.  얼굴: http://localhost:%d" % PORT)
        while True:
            try:
                text = self.texts.get(timeout=1)
            except queue.Empty:
                busy = self.brain.busy or self.mouth.speaking
                if self.mode == "chat" and not busy and time.time() - self.last > CHAT_TIMEOUT:
                    self.mode = "idle"; face.send(state="idle", text=""); log("30초 조용 → 대기")
                continue
            if text is None:
                break
            if CONTINUE_END.search(text):        # "…그리고" 로 끝나면 1.5초 더 기다려 다음 말과 합침
                try:
                    more = self.texts.get(timeout=MORE_WAIT)
                    if more:
                        text += " " + more
                except queue.Empty:
                    pass
            self.handle(text)
        while self.brain.busy or self.mouth.speaking or not self.mouth.q.empty():
            time.sleep(0.2)


# ---------- 폰 · 얼굴 서버 ----------
class Handler(BaseHTTPRequestHandler):
    jarvis = None

    def log_message(self, *a):
        pass

    def ok_key(self):
        return not KEY or parse_qs(urlsplit(self.path).query).get("key") == [KEY]

    def do_GET(self):
        if not self.ok_key():
            return self.send_error(403)
        if self.path.startswith("/events"):
            q = queue.Queue()
            q.put("data: " + json.dumps(face.last, ensure_ascii=False) + "\n\n")
            with face.lock:
                face.clients.append(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    self.wfile.write(q.get().encode()); self.wfile.flush()
            except OSError:
                with face.lock:
                    face.clients.remove(q)
            return
        if not self.ok_key():
            return self.send_error(403)
        body = (HERE / "face.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        """폰·얼굴 화면: 녹음 파일 또는 글자({"text":…, "audio":true}) → 두뇌 → 답 (+목소리 파일)."""
        if not self.path.startswith("/api/talk") or not self.ok_key():
            return self.send_error(403)
        body = self.rfile.read(int(self.headers["Content-Length"]))
        ctype = self.headers.get("Content-Type", "")
        want_audio = True
        if "json" in ctype:                      # 글자로 지시
            req = json.loads(body)
            text, want_audio = add_qmark(req.get("text", "").strip()), bool(req.get("audio"))
        else:                                    # 녹음으로 지시
            suffix = ".m4a" if "mp4" in ctype else ".webm" if "webm" in ctype else ".wav"
            text = add_qmark(clean(strip_wake(stt(body, suffix))))
        reply = []
        if text:
            log("화면·폰:", text)
            face.send(state="thinking", text=text)
            self.jarvis.mouth.stop()
            self.jarvis.brain.interrupt()
            self.jarvis.brain.ask(text, reply.append, lambda: face.send(state="working"))
            face.send(state="idle", text=" ".join(reply))
        out = {"heard": text, "reply": " ".join(reply)}
        if reply and want_audio:
            self.jarvis.mouth.recent = (self.jarvis.mouth.recent + [(time.monotonic() + len(out["reply"]) / 5, out["reply"])])[-6:]
            out["audio"] = base64.b64encode(synth_file(out["reply"])).decode()
        data = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(data)


def main():
    j = Jarvis()
    face.send(demo="--demo" in sys.argv, input_mode="browser" if "--text" in sys.argv else "desktop")
    Handler.jarvis = j
    # 127.0.0.1 에만 엶 — 폰은 `tailscale serve` 로 HTTPS 를 씌워 내 기기끼리만 접속
    threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever, daemon=True).start()
    if "--wav" in sys.argv:
        j.run(wav_frames(sys.argv[sys.argv.index("--wav") + 1:]))
    elif "--text" in sys.argv:                  # 마이크 없이 글자로만 (조용한 곳 · 마이크 권한 없을 때)
        j.run(None)
    else:
        if "--no-face" not in sys.argv:
            subprocess.run(["open", f"http://localhost:{PORT}" + (f"/?key={KEY}" if KEY else "")])
        j.mouth.say("횃비스 준비됐어요.")
        j.run(mic_frames())


if __name__ == "__main__":
    main()
