"""프리폼 흐름용 예시 두뇌. --demo에서만 사용하며 외부 조회·파일 변경은 하지 않는다."""
import re, threading, json
from pathlib import Path
from datetime import datetime

class DemoBrain:
    def __init__(self, face):
        self.face, self.busy, self.cancel = face, False, threading.Event()
        self.lock = threading.Lock()
        self.last_topic = None
        self.spoken = json.loads((Path(__file__).parent / "spoken_responses.json").read_text())

    def interrupt(self):
        self.cancel.set()

    def ask(self, text, on_sentence, on_tool=lambda: None):
        with self.lock:
            self.busy = True
            self.cancel.clear()
            try:
                answer, title, rows = self.answer(text)
                self.face.send(card={'title': title, 'rows': rows})
                if not self.cancel.is_set():
                    on_sentence(answer)
            finally:
                self.busy = False

    def answer(self, t):
        answer, title, rows = self._answer(t)
        return self.spoken.get(title, answer), title, rows

    def _answer(self, t):
        if re.search('몇 시|현재 시간', t):
            now = datetime.now().astimezone()
            return f'지금은 {now.hour}시 {now.minute}분이에요.', '현재 시각', [('시각', now.strftime('%H:%M'))]
        if re.search('정답|모르겠|모르겠어', t) and self.last_topic == 'quiz':
            return '정답은 8이에요. 2의 3제곱으로 계산해요.', '퀴즈 해설 · 예시', [('풀이', 'n개 입력 → 2ⁿ개 조합\n입력이 3개면 2³ = 8')]
        if re.search('퀴즈|문제|복습', t) and not re.search('메모|기록', t):
            self.last_topic = 'quiz'
            return '자료 기반 퀴즈를 시작할게요. 입력이 3개인 논리 회로의 입력 조합은 몇 개일까요?', '자료 기반 퀴즈 · 예시', [('문제', '입력이 3개일 때 가능한 입력 조합의 수는?'), ('자료 연결', '수업 슬라이드 → 개념 노트 → 연습 문제'), ('이어 말하기', '“정답 알려줘”라고 말씀해 주세요.')]
        if self.last_topic == 'quiz' and re.search('8|여덟|팔', t):
            return '맞아요. 입력 3개의 조합은 8개예요.', '퀴즈 결과 · 예시', [('결과', '정답 · 2³ = 8')]
        if re.search('그래프|graph|관계|연결된', t):
            return '수업 자료에서 개념 노트, 퀴즈로 이어지는 관계를 보여드릴게요.', '자료 관계 · 예시', [('강의 자료', '10주차 슬라이드 → 논리 회로'), ('개념', '논리 회로 → 진리표 → 입력 조합'), ('학습', '입력 조합 → 연습 문제 → 복습')]
        if re.search('클라우드|아이클라우드|동기화|icloud', t, re.I):
            return '아이클라우드 자료가 연결된 시연 화면이에요. 파일을 읽고 정리본을 찾는 흐름을 보여드려요.', 'iCloud 연결 · 예시', [('원본', 'iCloud / 공부 / 디지털집적회로'), ('연결', '수업 슬라이드 → 설명 자료'), ('범위', '시연 데이터 · 실제 동기화 상태는 조회하지 않음')]
        if re.search('정리|데이터베이스|DB|새 자료', t, re.I):
            return '새 자료 두 개를 분류하고 검색 목록에 연결하는 시연이에요.', '자료 정리 · 예시', [('새 자료', '수업 슬라이드.pdf\n수업 필기.pdf'), ('분류', '디지털집적회로 / 10주차'), ('검색 연결', '원본 → 파일 정보 → 개념 → 퀴즈'), ('변경', '실제 파일 이동·DB 쓰기 없음')]
        if re.search('메모|기록', t):
            memo = re.sub(r'^.*?(메모|기록)[\s:,.]*', '', t).strip() or '다음 수업 전에 슬라이드 복습하기'
            return '메모하는 흐름을 보여드릴게요. 내용과 작성 시각을 화면에 남겼어요.', '메모 · 예시', [('내용', memo), ('작성 시각', datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')), ('저장', '시연 화면에만 표시 · 파일 미생성')]
        if re.search('찾|자료|슬라이드|열어', t):
            return '디지털집적회로 수업 자료와 설명 자료를 찾은 예시예요. 관련 개념이나 퀴즈도 이어서 물어보세요.', '자료 검색 · 예시', [('슬라이드', '디지털집적회로 / 10주차 슬라이드.pdf'), ('설명', '디지털집적회로 / 10주차 설명.pdf'), ('이어 말하기', '“관련 퀴즈 내줘” · “자료 관계 보여줘”')]
        if re.search('버스|교통|통학|길찾|내비|어떻게 가', t):
            return '학교 방향 버스는 7분 뒤, 다음 버스는 19분 뒤에 오는 예시예요. 길찾기는 목적지를 말해서 이어갈 수 있어요.', '교통 · 예시', [('방향', '집 앞 정류장 → 학교'), ('도착', '첫 차 7분 후 · 다음 차 19분 후'), ('길찾기', '정류장 → 환승 → 목적지 · 예시 경로')]
        if re.search('날씨|비 와|우산|기온', t):
            return '오늘은 12도에 흐리고, 오후 강수 확률은 60퍼센트인 예시예요. 우산을 챙겨 주세요.', '날씨 · 예시', [('현재', '12°C · 흐림'), ('오후', '강수 확률 60%')]
        if re.search('학식|점심|식단|밥', t):
            return '점심은 제육볶음 정식이고 5천5백 원인 예시예요.', '학식 · 예시', [('점심', '제육볶음 정식 · 5,500원'), ('저녁', '순두부찌개 · 5,000원')]
        if re.search('오늘|브리핑|일정|대시보드', t):
            return '오늘은 오전 수업과 오후 팀 미팅이 있어요. 비 소식이 있고 버스는 7분 뒤 도착하는 예시예요. 자세한 내용은 화면에 남겼어요.', '오늘 브리핑 · 예시', [('일정', '10:00 전공 수업\n15:00 팀 미팅'), ('날씨', '12°C · 오후 강수 확률 60%'), ('교통', '학교 방향 · 7분 후, 19분 후'), ('학식', '제육볶음 정식 · 5,500원')]
        return '브리핑, 교통, 날씨, 학식, 자료 찾기와 퀴즈를 물어보세요.', '음성으로 물어보세요', [('질문 예', '오늘 뭐 있어?\n학교 버스 언제 와?\n자료 기반 퀴즈 내줘\n아이클라우드 자료 보여줘')]
