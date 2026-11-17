"""기술 스택 로고를 포함한 횃비스 아키텍처 SVG를 생성한다. 실행 위치와 무관하다."""
from copy import deepcopy
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets" / "tech-logos"
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

# 도식의 고정 좌표와 역할별 색상은 하나의 캔버스에서 관리한다.
parts = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1200" viewBox="0 0 1800 1200" role="img" aria-labelledby="title desc">
<title id="title">횃비스 기술 스택 아키텍처</title>
<desc id="desc">HTML CSS JavaScript 브라우저와 마이크가 Python 앱에 입력한다. 받아쓰기는 로컬 MLX Whisper 또는 키가 있을 때 외부 Groq를 사용한다. 일반 모드는 Claude Code를 통해 추론 제공자와 통신하고 시연 모드는 예시를 반환한다. 음성은 macOS say로 출력한다. Tailscale은 선택적 원격 접속이다.</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#61748b"/></marker><marker id="cloud-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#b76a43"/></marker></defs>
<style>
text{font-family:-apple-system,BlinkMacSystemFont,'Noto Sans KR',sans-serif;fill:#172e49}
.title{font-size:40px;font-weight:700;letter-spacing:-1px}.subtitle{font-size:21px;fill:#64758a}
.section{font-size:22px;font-weight:650}.label{font-size:25px;font-weight:650}.body{font-size:20px;fill:#53677e}.small{font-size:17px;fill:#64758a}.tag{font-size:16px;font-weight:600}
.wire{fill:none;stroke:#61748b;stroke-width:2.4;marker-end:url(#arrow)}.return{stroke-dasharray:8 7}.cloud{stroke:#b76a43;marker-end:url(#cloud-arrow)}.both{marker-start:url(#arrow)}
.edge-label{font-size:18px;fill:#53677e;paint-order:stroke;stroke:#fff;stroke-width:7px;stroke-linejoin:round}
</style>
<rect width="1800" height="1200" fill="#fff"/>
<text x="60" y="65" class="title">횃비스</text><text x="202" y="65" class="title" style="font-weight:400;fill:#64758a">기술 스택 아키텍처</text>
<text x="60" y="104" class="subtitle">음성 입력 → Python 제어 → AI 응답 → 음성·화면 출력</text>
<rect x="400" y="155" width="875" height="830" rx="22" fill="#f4f8fc" stroke="#bfd1e3" stroke-width="1.5"/>
<rect x="1325" y="155" width="415" height="830" rx="22" fill="#fcf6f1" stroke="#e4cfbe" stroke-width="1.5"/>
<text x="60" y="196" class="section">사용자 기기</text><text x="430" y="196" class="section">로컬 실행 · 사용자 Mac</text><text x="1355" y="196" class="section">외부 서비스</text>
''']


def text(x, y, value, cls="body", anchor="start"):
    # 기술 명칭과 한글 라벨을 SVG 텍스트로 유지해 확대·편집할 수 있게 한다.
    parts.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{escape(value)}</text>')


def card(x, y, w, h, fill="#fff", stroke="#c6d3e0"):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')


def logo(name, x, y, w, h=None, color=None):
    # 내려받은 원본 벡터를 내부에 넣어 외부 네트워크 없이 로고가 보이게 한다.
    node = deepcopy(ET.parse(ASSETS / (name + ".svg")).getroot())
    prefix = f"{name}-{x}-{y}-"
    ids = {n.attrib["id"]: prefix + n.attrib["id"] for n in node.iter() if "id" in n.attrib}
    for child in node.iter():
        for key, value in list(child.attrib.items()):
            if key == "id":
                child.set(key, ids[value])
            else:
                for old, new in ids.items():
                    value = value.replace("url(#" + old + ")", "url(#" + new + ")")
                    if value == "#" + old:
                        value = "#" + new
                if color:
                    value = value.replace("currentColor", color)
                child.set(key, value)
    node.attrib.update(x=str(x), y=str(y), width=str(w), height=str(h or w))
    node.set("preserveAspectRatio", "xMidYMid meet")
    node.set("style", "overflow:visible" + (f";color:{color};fill:{color}" if color else ""))
    parts.append(ET.tostring(node, encoding="unicode"))


def wire(path, label=None, lx=0, ly=0, cls="wire"):
    parts.append(f'<path d="{path}" class="{cls}"/>')
    if label:
        text(lx, ly, label, "edge-label")


# 연결선을 먼저 그리고 노드를 위에 올려 선이 로고·설명을 관통하지 않게 한다.
wire("M350 530H450", "HTTP POST", 354, 508)
wire("M450 630H350", "SSE · 응답", 354, 662, "wire return")
wire("M350 835H380V720H450", "PCM", 358, 809)
wire("M610 430V330H880", "키 없음 · 로컬 전사", 640, 315, "wire both")
wire("M700 430V228H1530V260", "키 있음 · Groq 음성 전사", 1000, 215, "wire cloud")
wire("M800 560H880", "JSON", 812, 542, "wire both")
wire("M1215 560H1370", "모델 요청·응답", 1219, 542, "wire cloud")
wire("M1370 585H1215", None, cls="wire return cloud")
wire("M625 740V845H880", "문장 → 음성", 675, 830)
wire("M1045 660V710", "허용된 도구 사용", 1060, 699)

# 사용자 UI: 실제 웹 표준의 로고를 나란히 배치한다.
card(60, 345, 290, 350)
logo("html5", 89, 380, 64)
logo("css3", 173, 380, 64)
logo("javascript", 257, 380, 64)
text(205, 483, "웹 브라우저", "label", "middle")
text(205, 522, "HTML · CSS · JavaScript", "body", "middle")
text(205, 568, "음성 녹음 · 글자 입력", "body", "middle")
text(205, 601, "질문 · 답변 · 상태 카드", "body", "middle")
text(205, 653, "MediaRecorder / EventSource", "small", "middle")

card(60, 760, 290, 170)
# 마이크는 서비스 로고가 아닌 보편적인 입출력 기호다.
parts.append('<g transform="translate(95 793)" fill="none" stroke="#53677e" stroke-width="3"><rect x="7" y="0" width="20" height="37" rx="10"/><path d="M0 25V30A17 17 0 0 0 34 30V25M17 47V61M6 61H28"/></g>')
text(154, 818, "맥 마이크", "label")
text(154, 854, "sounddevice", "body")
text(90, 902, "WebRTC VAD · 16 kHz PCM", "small")

# 가운데 Python 런타임이 앱 제어와 두 입력 경로를 담당한다.
card(450, 430, 350, 310, "#fff", "#8bb2d4")
logo("python", 575, 462, 100)
text(625, 604, "Python 앱", "label", "middle")
text(625, 644, "http.server · threading · queue", "small", "middle")
text(625, 681, "호출어 · 대화 · 중단 제어", "body", "middle")
logo("numpy", 493, 702, 24)
text(532, 722, "NumPy · 오디오 처리", "small")

card(880, 260, 335, 150)
logo("mlx", 915, 280, 165, 54)
text(910, 365, "mlx-whisper · 로컬 받아쓰기", "body")
text(910, 393, "Apple Silicon · 키 없을 때", "small")

card(1370, 260, 325, 150, "#fff", "#dfc2ab")
logo("groq", 1395, 285, 62, color="#f55036")
text(1476, 325, "Groq", "label")
text(1395, 365, "Whisper API · 외부 받아쓰기", "body")
text(1395, 393, "GROQ_API_KEY가 있을 때", "small")

card(880, 470, 335, 190)
logo("claude", 912, 496, 66, color="#d97757")
text(997, 535, "Claude Code", "label")
text(910, 593, "CLI · stream-json", "body")
text(910, 631, "일반 모드 · 사용자 인증", "small")

card(1370, 470, 325, 190, "#fff", "#dfc2ab")
logo("anthropic", 1398, 498, 68, color="#191919")
text(1483, 539, "Anthropic", "label")
text(1395, 593, "또는 설정된 추론 제공자", "body")
text(1395, 631, "입력·도구 결과 전송 가능", "small")

# 권한 실행과 음성 출력은 실제 macOS 기능으로 묶어 보여준다.
card(880, 714, 335, 70, "#edf3f9", "#d5e0eb")
text(1047, 744, "검색 · 파일 · 화면 조작", "body", "middle")
text(1047, 770, "AppleScript / Quartz / hands.py", "small", "middle")

card(880, 810, 335, 130)
logo("apple", 910, 839, 50, color="#263b50")
text(982, 852, "macOS say", "label")
text(982, 887, "한국어 음성 출력", "body")
text(910, 923, "맥 스피커 / 브라우저 재생용 음성", "small")

card(450, 862, 350, 78, "#edf3f9", "#d5e0eb")
text(475, 894, "--demo · 시연 모드", "body")
text(475, 921, "Claude 대신 정해진 응답·카드 반환", "small")

# 선택적 통신 도구는 기본 런타임과 별도로 표시한다.
card(60, 1015, 1155, 80, "#f8fafc", "#d5e0eb")
logo("tailscale", 84, 1036, 42, color="#53677e")
text(149, 1048, "Tailscale Serve", "body")
text(149, 1077, "선택적 폰 접속 · 같은 tailnet에서 HTTPS로 로컬 브라우저 화면 사용", "small")
text(1355, 728, "연결 방식", "section")
text(1355, 766, "Groq: 녹음 → 전사 텍스트", "body")
text(1355, 803, "Claude: 요청 → 모델 응답", "body")
text(1355, 860, "전사 엔진은 키 유무로 선택", "small")
text(1355, 891, "장애 시 자동 전환 구조는 아님", "small")

parts.append('<line x1="60" y1="1128" x2="1740" y2="1128" stroke="#dbe4ed"/>')
text(60, 1163, "현재 코드 기준 · 날씨·교통·학식·자료 검색·iCloud는 시연 예시 · 실제 DB·RAG·클라우드 동기화 없음", "small")
text(1740, 1163, "HWATVIS  /  2026.11", "small", "end")
parts.append('</svg>')
(HERE / "tech-stack-architecture.svg").write_text("\n".join(parts), encoding="utf-8")
print("생성: tech-stack-architecture.svg")
