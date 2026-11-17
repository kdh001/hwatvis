"""영상 촬영용: 마이크 없이 백엔드 질문 → 상태·횃불이 자세 → 예시 정보·실제 TTS."""
import argparse, json, subprocess, threading, time, sys
sys.argv.append('--demo')
import jarvis as J

scenes = ['오늘 뭐 있어?', '학교 버스 언제 와?', '오늘 날씨 알려줘', '점심 학식 뭐야?',
          '수업 자료 찾아줘', '자료 기반 퀴즈 내줘', '정답 알려줘', '자료 관계 보여줘',
          '새 자료 정리해줘', '아이클라우드 자료 보여줘', '메모: 다음 수업 전에 복습하기']
parser=argparse.ArgumentParser()
parser.add_argument('--delay',type=float,default=8)
parser.add_argument('--scene',default=None)
args,_=parser.parse_known_args()
j=J.Jarvis()
J.Handler.jarvis=j
server=J.ThreadingHTTPServer(('127.0.0.1',J.PORT),J.Handler)
J.face.send(showcase=True,demo=True,input_mode='desktop',state='idle',text='무엇을 도와드릴까요?')
threading.Thread(target=server.serve_forever,daemon=True).start()

def play():
    time.sleep(max(0,args.delay))
    for question in ([args.scene] if args.scene else scenes):
        J.face.send(showcase=True,state='listening',question=question,text=question,card=None)
        time.sleep(2)
        J.face.send(state='thinking',text='확인하고 있어요.')
        time.sleep(.8)
        answer,title,rows=j.brain.answer(question)
        # 예시 여부는 화면의 고정 표시로 알리고, 내레이션은 간결하게 읽는다.
        answer=answer.replace('인 예시예요.','이에요.').replace('하는 예시예요.','해요.').replace(' 예시예요.','.')
        J.face.send(state='speaking',text=answer,card={'title':title,'rows':rows})
        print(json.dumps({'question':question,'answer':answer,'scene':title},ensure_ascii=False),flush=True)
        subprocess.run(['say','-v',J.VOICE,answer],check=True)
        J.face.send(state='idle')
        time.sleep(3)
    print('시연 종료 · 마이크 꺼짐 · 화면은 유지됩니다.',flush=True)

threading.Thread(target=play,daemon=True).start()
print(f'영상 시연 준비: http://localhost:{J.PORT} · 마이크 사용 안 함',flush=True)
try:
    threading.Event().wait()
except KeyboardInterrupt:
    server.shutdown()
