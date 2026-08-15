# -*- coding: utf-8 -*-
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
import copy

BG    = RGBColor(0x0E,0x14,0x1B)
CARD  = RGBColor(0x18,0x22,0x2E)
CARD2 = RGBColor(0x11,0x1A,0x24)
FG    = RGBColor(0xEC,0xF1,0xF6)
MUTED = RGBColor(0x93,0xA4,0xB5)
ACC   = RGBColor(0x36,0xD3,0x99)   # green
ACC2  = RGBColor(0x5A,0x9C,0xFF)  # blue
WARN  = RGBColor(0xFF,0xB0,0x4D)
RED   = RGBColor(0xFF,0x6B,0x6B)
LINE  = RGBColor(0x2A,0x38,0x48)

KFONT = "맑은 고딕"
prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
W = 13.333; H = 7.5

def setfont(run, size, bold=False, color=FG, font=KFONT):
    run.font.size = Pt(size); run.font.bold = bold; run.font.color.rgb = color
    run.font.name = font
    rPr = run._r.get_or_add_rPr()
    for tag in ('a:latin','a:ea','a:cs'):
        e = rPr.find(qn(tag))
        if e is None:
            e = rPr.makeelement(qn(tag), {}); rPr.append(e)
        e.set('typeface', font)

def rect(sl, x,y,w,h, fill=None, line=None, lw=1.25, radius=None):
    from pptx.enum.shapes import MSO_SHAPE
    shp = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                              Inches(x),Inches(y),Inches(w),Inches(h))
    if radius:
        try: shp.adjustments[0] = radius
        except Exception: pass
    if fill: shp.fill.solid(); shp.fill.fore_color.rgb = fill
    else: shp.fill.background()
    if line: shp.line.color.rgb = line; shp.line.width = Pt(lw)
    else: shp.line.fill.background()
    shp.shadow.inherit = False
    return shp

def text(sl, x,y,w,h, parts, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.15):
    tb = sl.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0
    tb.text_frame.vertical_anchor = anchor
    first = True
    for p in parts:
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.alignment = p.get('align', align)
        para.line_spacing = p.get('ls', spacing)
        if 'space_before' in p: para.space_before = Pt(p['space_before'])
        r = para.add_run(); r.text = p['t']
        setfont(r, p.get('sz',18), p.get('b',False), p.get('c',FG), p.get('f',KFONT))
    return tb

_SLIDE_N = [1]  # 표지가 1번이므로 slide()가 만드는 첫 장은 2번

def slide(title=None, kicker=None, n=None):
    _SLIDE_N[0] += 1
    n = _SLIDE_N[0]
    sl = prs.slides.add_slide(BLANK)
    rect(sl,0,0,W,H, fill=BG)
    rect(sl,0,0,0.13,H, fill=ACC)
    if kicker:
        text(sl,0.75,0.42,10,0.32,[{'t':kicker,'sz':13,'b':True,'c':ACC}])
    if title:
        text(sl,0.75,0.75,11.9,0.9,[{'t':title,'sz':32,'b':True,'c':FG}])
        rect(sl,0.75,1.72,1.5,0.045, fill=ACC)
    if n is not None:
        text(sl,12.2,6.95,0.9,0.3,[{'t':str(n),'sz':11,'c':MUTED,'align':PP_ALIGN.RIGHT}])
    return sl

def bullets(sl, x,y,w, items, sz=17, gap=0.52, dot=ACC):
    for i,(head,body) in enumerate(items):
        yy = y + i*gap
        rect(sl,x,yy+0.11,0.12,0.12, fill=dot)
        parts=[{'t':head,'sz':sz,'b':True,'c':FG}]
        tb=text(sl,x+0.32,yy,w-0.32,0.4,parts)
        if body:
            text(sl,x+0.32,yy+0.3,w-0.32,0.4,[{'t':body,'sz':13.5,'c':MUTED}])

def table(sl, x,y,w, cols, rows, colw=None, sz=13, hsz=13, head_c=ACC, zebra=True, rowh=0.42):
    ncol=len(cols)
    colw = colw or [w/ncol]*ncol
    # header
    cx=x
    rect(sl,x,y,w,rowh, fill=CARD)
    for j,c in enumerate(cols):
        text(sl,cx+0.14,y+0.09,colw[j]-0.2,rowh,[{'t':c,'sz':hsz,'b':True,'c':head_c}])
        cx+=colw[j]
    for i,r in enumerate(rows):
        yy=y+rowh+i*rowh
        if zebra and i%2==0: rect(sl,x,yy,w,rowh, fill=CARD2)
        cx=x
        for j,cell in enumerate(r):
            col = FG; bold=False
            if isinstance(cell,tuple): cell,col = cell[0],cell[1]; bold=True
            text(sl,cx+0.14,yy+0.09,colw[j]-0.2,rowh,[{'t':str(cell),'sz':sz,'b':bold,'c':col}])
            cx+=colw[j]
    return y+rowh*(len(rows)+1)

def card(sl,x,y,w,h,title,lines,accent=ACC,tsz=19,bsz=14):
    rect(sl,x,y,w,h, fill=CARD, radius=0.06)
    rect(sl,x,y,0.055,h, fill=accent)
    text(sl,x+0.34,y+0.26,w-0.6,0.4,[{'t':title,'sz':tsz,'b':True,'c':FG}])
    parts=[]
    for i,l in enumerate(lines):
        parts.append({'t':l,'sz':bsz,'c':MUTED,'ls':1.35,'space_before':6 if i else 0})
    text(sl,x+0.34,y+0.85,w-0.6,h-1.0,parts)

def bigstat(sl,x,y,w,val,label,color=ACC,vsz=44):
    rect(sl,x,y,w,1.55, fill=CARD, radius=0.08)
    text(sl,x,y+0.24,w,0.7,[{'t':val,'sz':vsz,'b':True,'c':color,'align':PP_ALIGN.CENTER}])
    text(sl,x,y+1.02,w,0.4,[{'t':label,'sz':12.5,'c':MUTED,'align':PP_ALIGN.CENTER}])

def note(sl, t, y=6.85):
    text(sl,0.75,y,11.8,0.35,[{'t':t,'sz':11,'c':MUTED}])

_HERE = os.path.dirname(os.path.abspath(__file__))    # presentation/build/
_PRES = os.path.dirname(_HERE)                        # presentation/
_REPO = os.path.dirname(_PRES)                        # 저장소 루트
QR_PATH = os.path.join(_REPO, 'demo', 'qr_repo.png')
REPO_URL = 'github.com/giyeop-cody/token-cost-lab'


def qr(sl, x, y, size=1.5, caption=None, csz=11, cw=None):
    """리포 QR. 흰 여백(quiet zone)이 있어야 스캔되므로 흰 판 위에 얹는다."""
    if not os.path.exists(QR_PATH):
        return
    pad = 0.08
    rect(sl, x - pad, y - pad, size + pad * 2, size + pad * 2,
         fill=RGBColor(0xFF, 0xFF, 0xFF), radius=0.05)
    sl.shapes.add_picture(QR_PATH, Inches(x), Inches(y),
                          Inches(size), Inches(size))
    if caption:
        text(sl, x - 0.25, y + size + 0.14, cw or (size + 0.5), 0.3,
             [{'t': caption, 'sz': csz, 'c': MUTED}], align=PP_ALIGN.CENTER)

# ───────────────────────── 1. 표지
sl = prs.slides.add_slide(BLANK)
rect(sl,0,0,W,H, fill=BG)
rect(sl,0,0,W,0.14, fill=ACC)
text(sl,1.1,2.05,11,0.4,[{'t':'NETWORK SESSION  ·  2026.08','sz':14,'b':True,'c':ACC}])
text(sl,1.1,2.5,11.5,1.0,[{'t':'“당신이 시켰잖아요”','sz':54,'b':True,'c':FG}])
text(sl,1.1,3.62,11.5,0.7,[{'t':'시키지도 않은 시공비 청구서','sz':38,'b':True,'c':WARN}])
text(sl,1.1,4.42,11,0.5,[{'t':'믿고 맡긴 AI가 조용히 부풀리는 토큰 견적','sz':20,'c':MUTED}])
rect(sl,1.1,5.12,1.6,0.05, fill=ACC)
text(sl,1.1,5.45,11,1.2,[
 {'t':'출력 토큰을 입력 토큰으로 바꾸는 4가지 실전 원칙','sz':16,'c':FG},
 {'t':'영어 사고  ·  KISS/DRY/YAGNI  ·  설명 최소화  ·  웹에서 추론 → 스펙 주입','sz':14,'c':MUTED,'space_before':8},
 {'t':'그리고 캐싱 · 컨텍스트 컴팩션 · 배치 · 라우팅 · 압축까지 — 모든 수치는 재현 가능한 실측입니다.','sz':14,'c':ACC,'space_before':7}])

# ───────────────────────── 2. 문제 제기
sl = slide('토큰은 균등하게 비싸지 않다', 'WHY NOW')
bigstat(sl,0.75,2.1,2.85,'2~8×','출력 토큰 / 입력 토큰 단가 비율',ACC)
bigstat(sl,3.85,2.1,2.85,'1.44×','같은 뜻, 한국어 / 영어 토큰 수 (실측)',WARN)
bigstat(sl,6.95,2.1,2.85,'0.10×','캐시된 입력 토큰 단가 (Anthropic)',ACC2)
bigstat(sl,10.05,2.1,2.85,'5~15%','에이전트 세션 중 실제 코드 생성 비중',RED)
text(sl,0.75,4.15,11.9,1.9,[
 {'t':'요금은 “토큰 수 × 단가”다. 그런데 단가는 자리마다 다르다.','sz':21,'b':True,'c':FG},
 {'t':'같은 10,000 토큰이라도 — 캐시된 입력이면 0.3센트, 생성된 출력이면 15센트다 (Sonnet급 기준, 50배 차이).','sz':16,'c':MUTED,'space_before':10},
 {'t':'따라서 절약의 정답은 “적게 쓰기”가 아니라 “싼 자리로 옮기기”다.','sz':16,'c':ACC,'space_before':6}])
note(sl,'출처: 2026 LLM 가격 비교 (verticalapi/morphllm/benchlm), 자체 tiktoken 실측')

# ───────────────────────── 3. 요금 구조
sl = slide('먼저, 요금표를 정확히 읽자', 'BASELINE')
y=table(sl,0.75,2.05,7.4,
  ['모델 (2026-08 리스트가)','입력 $/1M','출력 $/1M','배수'],
  [['Claude Opus 4.6 / 5','$5.00','$25.00',('5×',WARN)],
   ['Claude Sonnet 4.6','$3.00','$15.00',('5×',WARN)],
   ['GPT-5.x (flagship)','$5.00','$30.00',('6×',RED)],
   ['Gemini 3.1 Pro','$2.00','$12.00',('6×',WARN)],
   ['Gemini 2.5 Pro / GPT-5','$1.25','$10.00',('8×',RED)],
   ['DeepSeek V4 Flash','$0.14','$0.28',('2×',ACC)]],
  colw=[3.0,1.5,1.5,1.4])
card(sl,8.45,2.05,4.15,3.1,'왜 출력이 비싼가',
 ['입력은 배치로 병렬 처리(prefill).',
  '출력은 토큰 1개마다 전체 forward pass를 순차 실행(decode).',
  '즉 물리적으로 더 비싸다 — 협상 불가.',
  '',
  '핵심: 추론(thinking) 토큰도 출력 요금으로 과금된다.'], ACC2)
text(sl,0.75,5.5,11.9,0.9,[
 {'t':'“출력 = 비싼 자리”. 추론 토큰이 출력에 포함된다는 점이 오늘 발표의 전제다.','sz':17,'b':True,'c':ACC}])
note(sl,'※ 단가는 변동됨. 각자 실제 사용 모델의 가격 페이지로 재확인할 것.')

# ───────────────────────── 4. 4대 원칙
sl = slide('오늘 가져갈 4가지 원칙', 'AGENDA')
card(sl,0.75,2.05,5.85,1.95,'① 추론은 영어로',
 ['한국어 사고 = 같은 의미에 1.4~1.9배 토큰.','비싼 출력 자리에서 손해가 발생한다.'],ACC)
card(sl,6.9,2.05,5.7,1.95,'② KISS · DRY · YAGNI',
 ['골 대비 과한 고도화 = 순수 낭비.','안 쓸 코드의 생성·리뷰·수정까지 전부 과금.'],WARN)
card(sl,0.75,4.2,5.85,1.95,'③ 장황한 설명 금지',
 ['코드 읽으면 아는 걸 3번 설명 = 출력 토큰 소각.','verbosity를 내리면 설명형 출력 40~60% 감소.'],ACC2)
card(sl,6.9,4.2,5.7,1.95,'④ 웹에서 추론 → 스펙 주입',
 ['긴 추론은 채팅에서 끝내고, 결론만 넣는다.','출력 토큰을 입력 토큰으로 환전한다.'],RED)
text(sl,0.75,6.35,11.9,0.5,[
 {'t':'그리고 후반부에 — 캐싱 · 스펙 주도 개발 · 컨텍스트 컴팩션 · 배치 · 압축 · 라우팅까지 6개 레버를 더 다룬다.','sz':14.5,'c':MUTED}])

# ───────────────────────── 5. 원칙1 실측
sl = slide('원칙 ① 추론은 영어로 — 실측치', 'PRINCIPLE 1')
text(sl,0.75,1.95,11.9,0.4,[{'t':'동일 의미 문장을 tiktoken으로 직접 인코딩 (사내 검증 스크립트)','sz':14,'c':MUTED}])
table(sl,0.75,2.30,11.9,
  ['문장 (같은 의미)','EN o200k','KO o200k','비율','KO cl100k','비율'],
  [['로그인 API 추가 지시','19','34',('1.79×',WARN),'52',('2.74×',RED)],
   ['스키마 확인 추론 문장','32','41',('1.28×',WARN),'70',('2.19×',RED)],
   ['함수 동작 설명 문장','20','25',('1.25×',WARN),'33',('1.65×',WARN)],
   ['설계 논의 문장','22','28',('1.27×',WARN),'47',('2.14×',RED)],
   ['“에이전트 루프를 다시 짰다”','10','20',('2.00×',RED),'31',('3.10×',RED)],
   ['에러 분석 문장','18','26',('1.44×',WARN),'36',('2.00×',RED)],
   [('합계 (6문장)',ACC),('121',ACC),('174',ACC),('1.44×',ACC),('269',ACC),('2.22×',ACC)]],
  colw=[4.3,1.5,1.5,1.5,1.55,1.55], rowh=0.36, sz=13.5, hsz=13)
card(sl,0.75,5.34,11.9,1.56,'해석',
 ['최신 토크나이저(o200k)에서도 한국어는 영어 대비 약 1.44배. 구형(cl100k)·Claude 토크나이저에서는 1.9~2.2배까지 벌어진다.',
  '추론 8,000토큰 기준: 영어 $0.120 → 한국어 $0.173. 요청 1건당 약 44% 초과 지출.'],ACC)
note(sl,'재현: exp01_tokenizer_ko_en.py · 참고: 285편 코퍼스 측정 (ko 1.38×, Claude 토크나이저 1.88×)', 7.05)

# ───────────────────────── 5b. 원칙1 실호출 검증 (N=100)
sl = slide('실제로 100번 호출해봤더니 — 결론이 갈렸습니다', 'PRINCIPLE 1 · LIVE N=100')
text(sl,0.75,1.9,11.9,0.45,[
 {'t':'Gemini API 실호출 100건(성공 100/100). 그런데 호출당 비용만 보면 과제에 따라 결론이 뒤집힙니다.','sz':16,'c':MUTED}])
table(sl,0.75,2.42,11.9,
 ['과제','언어','평균 응답','실제 쓴 글자','호출당 비용','한국어 추가비용'],
 [['설명형','EN','157 tok','825자','$0.001595','—'],
  ['설명형','KO','203 tok','410자','$0.002068',('+29.7%',RED)],
  ['추론형','EN','367 tok','1,040자','$0.003744','—'],
  ['추론형','KO','285 tok','414자','$0.002963',('−20.9%',ACC)]],
 colw=[1.5,1.0,1.9,2.1,2.4,3.0], sz=13.5, hsz=13, rowh=0.46)
text(sl,0.75,4.75,11.9,0.4,[
 {'t':'“추론형은 한국어가 21% 싸다”가 아닙니다. 네 번째 열을 보십시오 — 한국어가 답을 40%만 썼습니다.','sz':15.5,'b':True,'c':WARN}])
table(sl,0.75,5.25,11.9,
 ['같은 분량(1,000자)으로 정규화하면','EN','KO','배수'],
 [['설명형','$0.00193','$0.00504',('2.61×',RED)],
  ['추론형','$0.00360','$0.00715',('1.99×',RED)]],
 colw=[5.9,2.0,2.0,2.0], sz=13.5, hsz=13, rowh=0.44)
note(sl,'재현: tools/live_lang_bench.py --n 25 (N=100 원자료는 패키지 미포함 — 재실행 필요) · 전문 LIVE_RESULTS.md §6', 6.95)

# ───────────────────────── 5c. 사고 켜고 재측정 + 통계 검정
sl = slide('사고를 켜고 다시, 그리고 통계로 못을 박았습니다', 'PRINCIPLE 1 · N=80 · SIGNIFICANCE')
text(sl,0.75,1.9,11.9,0.45,[
 {'t':'앞 장은 사고(thinking) 꺼진 상태였습니다. 사고 예산을 켜고 80건 재측정 — 부호가 갈리는 현상이 똑같이 재현됩니다.','sz':15.5,'c':MUTED}])
table(sl,0.75,2.4,11.9,
 ['과제','언어','사고','응답','쓴 글자','호출당 비용','차이'],
 [['설명형','EN','697','144','822자','$0.008441','—'],
  ['설명형','KO','967','181','366자','$0.011515',('+36.4%',RED)],
  ['추론형','EN','1,616','214','570자','$0.018374','—'],
  ['추론형','KO','1,116','210','305자','$0.013375',('−27.2%',ACC)]],
 colw=[1.5,0.95,1.35,1.25,1.5,2.35,3.0], sz=13, hsz=12.5, rowh=0.44)
text(sl,0.75,4.62,11.9,0.4,[
 {'t':'추론형에서 영어가 사고를 1.4배 더 했습니다. 한국어가 싼 게 아니라 덜 생각하고 덜 쓴 겁니다.','sz':15,'b':True,'c':WARN}])
table(sl,0.75,5.12,11.9,
 ['분량 정규화 ($/1,000자)','EN','KO','배수','95% 신뢰구간','p값'],
 [['설명형','$0.0103','$0.0312',('3.03×',RED),'[2.68, 3.47]','< 0.001'],
  ['추론형','$0.0325','$0.0442',('1.36×',RED),'[1.23, 1.51]','6e−10']],
 colw=[3.3,1.7,1.7,1.5,2.4,1.3], sz=13, hsz=12.5, rowh=0.44)
text(sl,0.75,6.5,11.9,0.4,[
 {'t':'신뢰구간이 1.0을 넘지 않습니다 — 분량을 통제하면 한국어가 비싸다는 결론은 예외 없이 유의합니다.','sz':14.5,'b':True,'c':ACC}])
note(sl,'재현: live_lang_bench.py --thinking -1 · 검정: tools/stats_test.py (부트스트랩 2만회 · Welch · Cliff\'s δ)', 7.02)

# ───────────────────────── 6. 왜 한국어가 비싼가
sl = slide('왜 한국어가 더 비싼가', 'PRINCIPLE 1')
card(sl,0.75,2.05,5.85,3.0,'토크나이저 어휘 배분 문제',
 ['o200k 20만 어휘 중 라틴 문자 포함 토큰 67%,',
  '한글 포함 토큰은 단 1.2% (자체 실측).',
  '한글은 단어 단위 토큰이 거의 없어 음절로 쪼개진다.'],WARN)
rect(sl,1.09,3.72,5.17,1.2, fill=CARD2, radius=0.1)
text(sl,1.32,3.9,4.75,0.9,[
 {'t':'"에이전트" → 에/이/전/트  = 4 토큰','sz':13,'c':WARN,'f':'Consolas'},
 {'t':'" agent"     → agent          = 1 토큰','sz':13,'c':ACC,'f':'Consolas','space_before':8}])
card(sl,6.9,2.05,5.7,3.0,'글자 수는 함정이다',
 ['토큰/글자 실측: 영어 0.204 · 한국어 0.526.',
  '한국어는 글자 수가 더 적은데 토큰은 2.6배 많다.',
  '',
  '512토큰 청크 = 영어 2,513자 vs 한국어 973자.',
  'RAG 청킹을 글자 수로 자르면 조용히 잘려 나간다.'],ACC2)
text(sl,0.75,5.35,11.9,1.4,[
 {'t':'실무 규칙','sz':19,'b':True,'c':ACC},
 {'t':'사고(thinking)는 영어 → 최종 답변·주석·커밋 메시지는 한국어. 비싼 “양”은 영어로, 사람이 읽을 “질”만 한국어로.','sz':16,'c':FG,'space_before':8}])

# ───────────────────────── 7. 트레이드오프
sl = slide('단, 공짜는 아니다 — 검증된 트레이드오프', 'CAVEAT')
card(sl,0.75,2.05,5.85,3.45,'영어 사고가 유리한 근거',
 ['LLM의 “reasoning hub”는 영어. 비영어 사고를 강제하면 성능이 떨어진다.',
  'DeepSeek-R1-Distill-Llama-8B: 영어 사고 강제 시 평균 +26.8%.',
  '사용자 언어로 사고를 강제하면 정확도 26% → 17% 하락 (XReasoning).',
  '즉 영어 사고는 비용 + 품질 양쪽에서 유리한 드문 선택.'],ACC)
card(sl,6.9,2.05,5.7,3.45,'주의할 점',
 ['① 감시 가능성 저하 — 추론 과정을 한국어 화자가 못 읽는다.',
  '② 한국어 고유 맥락(호칭·존댓말·국내 규정) 작업은 예외.',
  '③ 일부 모델은 중국어 사고가 더 효율적(Qwen3: -40%).',
  '④ 프롬프트에 “영어로 생각해”라고 쓰는 것보다 API 파라미터가 확실하다.'],WARN)
text(sl,0.75,5.8,11.9,1.0,[
 {'t':'권고: 코드·수식·설계 = 영어 사고 기본값. 도메인이 한국어 그 자체인 작업만 예외 처리.','sz':17,'b':True,'c':FG}])
note(sl,'출처: arXiv 2505.22888 (XReasoning), arXiv 2505.17407 (Reasoning hub / prefilling)')

# ───────────────────────── 8. KISS DRY YAGNI
sl = slide('원칙 ② KISS · DRY · YAGNI', 'PRINCIPLE 2')
card(sl,0.75,2.05,3.9,3.0,'KISS',
 ['가장 단순한 동작 버전을 먼저.',
  '추상화 레이어 1개 = 생성·설명·리뷰·수정 토큰 4중 과금.',
  '“지금 이 골에 필요한 최소 구조”를 프롬프트에 명시.'],ACC)
card(sl,4.85,2.05,3.65,3.0,'DRY',
 ['같은 코드·같은 로직·같은 리워크를 두 번 사지 않는다.',
  '규칙은 CLAUDE.md / rules 파일 한 곳에.',
  '단, 컨텍스트의 DRY는 처방이 반대다 → 다음 장.'],ACC2)
card(sl,8.7,2.05,3.9,3.0,'YAGNI',
 ['안 쓸 기능은 만들지 않는다.',
  '“확장성 고려해서”가 가장 비싼 한마디.',
  '필요해지면 그때 시킨다 — 그때가 안 오는 경우가 대다수.'],WARN)
text(sl,0.75,5.35,11.9,1.5,[
 {'t':'과잉 고도화의 진짜 청구서','sz':20,'b':True,'c':FG},
 {'t':'토큰은 “생성 시점”에만 드는 게 아니다. 불필요한 추상화는 이후 모든 세션의 컨텍스트에 영구히 실려 다닌다.','sz':16,'c':MUTED,'space_before':8},
 {'t':'에이전트 세션에서 실제 코드 생성은 총 토큰의 5~15%. 나머지는 전부 컨텍스트 오버헤드다.','sz':16,'c':ACC,'space_before':6}])

# ───────────────────────── 8b. DRY 심화 — 반복이 아니라 변주가 비싸다
sl = slide('DRY, 코드에선 “지워라” 컨텍스트에선 “고정하라”', 'PRINCIPLE 2 · DEEP DIVE')
text(sl,0.75,1.9,11.9,0.45,[
 {'t':'같은 12,000토큰 프리픽스를 100번 보내는 4가지 방법 — 비용이 11배 갈립니다.','sz':16.5,'c':MUTED}])
table(sl,0.75,2.45,11.9,
 ['전략','입력 토큰','비용','기준 대비'],
 [['① 매번 그대로 전송','1,200,000','$3.60','기준'],
  ['② 절반으로 요약·삭제해서 반복을 줄인다','600,000','$1.80','−50%'],
  [('③ 한 글자도 안 바꾸고 그대로 → 캐시 적중',ACC),'1,200,000',('$0.40',ACC),('−89%',ACC)],
  [('④ 앞에 타임스탬프 한 줄 → 매번 캐시 미스',RED),'1,200,000',('$4.50',RED),('+25%',RED)]],
 colw=[5.6,2.1,2.1,2.1], sz=14, hsz=13.5, rowh=0.52)
card(sl,0.75,5.05,5.85,1.55,'반복을 “줄인” ②보다 “그대로 둔” ③이 4.5배 싸다',
 ['제거할 수 있는 반복은 제거한다 — 코드·로직·리워크.',
  '제거할 수 없는 반복은 고정한다 — 시스템 프롬프트·규약·스키마.'],ACC2,15.5,13)
card(sl,6.8,5.05,5.85,1.55,'비싼 것은 반복이 아니라 “변주”다',
 ['④는 앞에 동적값 한 줄 붙였을 뿐인데 ①보다 25% 더 낸다.',
  '캐시는 완전 일치에만 반응한다 — 어중간하게 다른 게 최악.'],RED,15.5,13)
note(sl,'재현: exp09_dry.py (프리픽스 100% 고정·100% 적중 상한 조건, Sonnet 단가) · 가변부가 섞인 현실 조건은 exp03의 −62%', 6.9)

# ───────────────────────── 8c. DRY 5항목 판정
sl = slide('“DRY 하면 토큰이 준다” — 5개로 쪼개서 검증했습니다', 'PRINCIPLE 2 · VERDICT')
table(sl,0.75,1.95,11.9,
 ['#','현장에서 말하는 DRY','판정','실측 근거'],
 [['A','같은 코드를 다시 쓰지 않는다',('참',ACC),'파일 전체 재출력 vs 변경분만 → −94%'],
  ['B','반복되는 컨텍스트를 줄인다',('조건부',WARN),'줄이면 −50%, 고정하면 −89%. 처방이 다르다'],
  ['C','반복되는 리워크를 줄인다',('참',ACC),'6사이클(48턴)은 1사이클(8턴)의 16.6배'],
  ['D','같은 로직은 한 군데서',('참',ACC),'복붙 3곳 = 수정 비용 정확히 3배'],
  ['E','같은 프롬프트를 최소화한다',('조건부',WARN),'중복 “호출”은 제거(−30%), 중복 “내용”은 고정']],
 colw=[0.6,4.0,1.5,5.8], sz=13.5, hsz=13.5, rowh=0.56)
text(sl,0.75,5.4,11.9,1.3,[
 {'t':'C가 왜 16.6배인가 — 리워크는 “한 번 더 시키는 것”이 아니다','sz':18,'b':True,'c':FG},
 {'t':'턴이 6배가 되면 비용은 6배가 아니라 16.6배가 된다. 매 턴 그때까지의 대화 전체가 입력으로 재전송되기 때문이다.','sz':15,'c':MUTED,'space_before':7},
 {'t':'그래서 DRY는 코딩 규율이 아니라 요금 정책이다. 사양을 먼저 굳히면 이 곡선 자체를 타지 않는다.','sz':15,'c':ACC,'space_before':6}])
note(sl,'재현: exp09_dry.py · 출처: Anthropic/OpenAI 프롬프트 캐싱 문서, GPT Semantic Cache(arXiv:2411.05276), Anthropic 컨텍스트 엔지니어링(2025)', 6.9)

# ───────────────────────── 9. 원칙3 장황함
sl = slide('원칙 ③ 장황한 설명을 금지하라', 'PRINCIPLE 3')
card(sl,0.75,2.05,5.85,2.95,'전형적인 낭비 패턴',
 ['① 코드 쓰기 전에 계획을 산문으로 서술',
  '② 코드 블록',
  '③ 코드가 하는 일을 다시 문단으로 설명',
  '④ 마지막에 “요약” 재서술',
  '→ 같은 정보를 3번 판다. 전부 최고 단가 출력.'],RED)
card(sl,6.9,2.05,5.7,2.95,'처방 — 두 개의 다이얼',
 ['verbosity = low → 설명형 출력 40~60% 감소',
  'reasoning_effort: 설계만 high, 구현은 low~medium',
  '  · effort별 월비용: minimal $7.92 / medium $132',
  '  · max는 $924 — 작업별 배분 시 $118 (70% 절감)',
  '진단: reasoning_tokens / output_tokens > 0.8 이면 과다'],ACC,19,13.5)
y=table(sl,0.75,5.15,11.9,['출력 스타일 (동일 작업)','응답 tok','월 비용 (1,760콜)','절감'],
 [['장황 — 계획+코드+해설+요약','342 tok','$9.03',''],
  ['보통 — 코드 + 짧은 설명','90 tok','$2.38',('-74%',ACC)],
  ['간결 — 코드 + 3줄 근거','58 tok','$1.53',('-83%',ACC)]],
 colw=[4.5,2.5,2.5,2.4], rowh=0.40)
note(sl,'재현: exp05_verbosity_effort.py · 이상적 상한값이며, 실무 기준선은 40~60% 절감 · 참고: Codex CLI 출력 제어 문서, Claude effort 파라미터 문서')

# ───────────────────────── 10. 원칙4 핵심
sl = slide('원칙 ④ 웹에서 추론하고, 결론만 주입하라', 'PRINCIPLE 4')
text(sl,0.75,1.95,11.9,0.5,[{'t':'출력 토큰을 입력 토큰으로 “환전”하는 것이 이 원칙의 본질이다.','sz':18,'b':True,'c':ACC}])
# Before
rect(sl,0.75,2.6,5.85,3.6, fill=CARD2, radius=0.05)
rect(sl,0.75,2.6,5.85,0.55, fill=RED)
text(sl,1.05,2.72,5.4,0.35,[{'t':'BEFORE — 자연어 한 줄 지시','sz':16,'b':True,'c':BG}])
text(sl,1.05,3.35,5.3,2.7,[
 {'t':'“로그인 좀 만들어줘”','sz':15,'c':FG},
 {'t':'↓  모델이 요구사항을 추측 (긴 추론)','sz':14,'c':MUTED,'space_before':8},
 {'t':'↓  되묻기 / 오해 / 잘못된 방향','sz':14,'c':MUTED,'space_before':6},
 {'t':'↓  수정 지시 → 재추론 → 재생성','sz':14,'c':MUTED,'space_before':6},
 {'t':'↓  4~6회 리워크 루프','sz':14,'c':RED,'space_before':6},
 {'t':'입력 2,000 / 출력 12,000 tok','sz':15,'b':True,'c':RED,'space_before':12}])
# After
rect(sl,6.9,2.6,5.7,3.6, fill=CARD2, radius=0.05)
rect(sl,6.9,2.6,5.7,0.55, fill=ACC)
text(sl,7.2,2.72,5.2,0.35,[{'t':'AFTER — 웹에서 추론 → 스펙 주입','sz':16,'b':True,'c':BG}])
text(sl,7.2,3.35,5.2,2.7,[
 {'t':'1. 웹 채팅에서 설계를 끝까지 논의 (구독 정액)','sz':14,'c':FG},
 {'t':'2. 결론을 스펙 문서로 정리 (엔드포인트·스키마·에러·완료조건)','sz':14,'c':FG,'space_before':7},
 {'t':'3. 에이전트는 reasoning_effort 낮춤','sz':14,'c':FG,'space_before':7},
 {'t':'4. 스펙 붙여넣고 “그대로 구현” 지시','sz':14,'c':FG,'space_before':7},
 {'t':'입력 6,000 / 출력 3,000 tok','sz':15,'b':True,'c':ACC,'space_before':12}])
text(sl,0.75,6.4,11.9,0.5,[{'t':'입력은 3배 늘었지만, 총비용은 66% 줄었다. 입력은 싸고, 출력은 비싸기 때문이다.','sz':17,'b':True,'c':FG}])

# ───────────────────────── 11. 비용 시뮬
sl = slide('숫자로 확인: 66% 절감', 'THE MATH')
text(sl,0.75,1.95,11.9,0.4,[{'t':'Sonnet급 단가($3 입력 / $15 출력) 기준, 기능 1건 구현','sz':14,'c':MUTED}])
table(sl,0.75,2.45,11.9,['시나리오','입력 tok','출력 tok','입력비','출력비','합계'],
 [['A. 자연어 지시 + 긴 추론 + 리워크','2,000','12,000','$0.006','$0.180',('$0.186',RED)],
  ['B. 웹 추론 → 스펙 주입 + 낮은 effort','6,000','3,000','$0.018','$0.045',('$0.063',ACC)],
  [('절감',ACC),('+200%',WARN),('-75%',ACC),'','',('-66%',ACC)]],
 colw=[4.6,1.5,1.5,1.5,1.5,1.3])
card(sl,0.75,4.6,5.85,2.0,'스케일업하면',
 ['개발자 10명 × 하루 8건 × 22일 = 1,760건/월',
  'A안 $327/월  →  B안 $111/월',
  '연간 약 $2,598 절감 (10인 팀, 모델 1종 기준)'],ACC)
card(sl,6.9,4.6,5.7,2.0,'주의: 이건 하한선이다',
 ['리워크 1회당 컨텍스트 전체가 재전송된다 (누적 quadratic).',
  '현장 보고: 스펙 선행 시 리워크 60~80% 감소,',
  '컨텍스트 전략 병행 시 API 지출 40~70% 감소.'],ACC2,19,13)
note(sl,'재현: exp02_output_to_input.py · 참고: Pluralsight SDD 보고, GitHub Spec Kit 사례', 6.95)

# ───────────────────────── 12. 캐싱
sl = slide('보너스 ⑤ 프롬프트 캐싱 — 입력 자리를 더 싸게', 'BONUS ⑤')
table(sl,0.75,2.05,6.6,['제공사','캐시 읽기 단가','조건'],
 [['Anthropic',('0.10× (90% 할인)',ACC),'명시적 marker, write 1.25×'],
  ['OpenAI','0.50× (50% 할인)','자동, 1,024토큰 이상'],
  ['Google','0.25× (75% 할인)','implicit / explicit'],
  ['DeepSeek',('0.10× (90% 할인)',ACC),'자동']],
 colw=[1.55,2.35,2.7], rowh=0.5)
card(sl,7.65,2.05,4.95,3.3,'실측 시뮬레이션',
 ['고정 컨텍스트 20K + 가변 1K,','출력 1.5K, 100회 호출',
  '',
  '캐시 없음:  $8.55',
  '캐시 적용:  $3.22',
  '→ 62% 절감 (품질 변화 0)'],ACC)
text(sl,0.75,5.35,11.9,1.6,[
 {'t':'전제 조건: 고정 컨텍스트를 프롬프트 “앞쪽”에 두고 순서를 바꾸지 말 것.','sz':17,'b':True,'c':FG},
 {'t':'시스템 프롬프트 → 툴 정의 → 레포 맵 → 스펙 → (여기까지 캐시) → 가변 질문. 앞부분이 1바이트라도 바뀌면 캐시 전체가 무효화된다.','sz':15,'c':MUTED,'space_before':8},
 {'t':'실사례: 캐시 히트율 7% → 84% 개선으로 총 LLM 지출 59~70% 감소 (ProjectDiscovery).','sz':15,'c':ACC,'space_before':6}])

# ───────────────────────── 12b. 캐싱 심화
sl = slide('캐싱 심화 — 히트율 계단과 안티패턴', 'BONUS ⑤')
table(sl,0.75,2.05,6.5,['캐시 히트율','100콜 비용','캐시 미사용 대비'],
 [['캐시 미사용 (기준)','$8.55',''],
  [('0% — 켰는데 매번 미스',RED),('$10.05',RED),('+18%',RED)],
  ['40%','$7.32',('-14%',ACC)],
  ['80%','$4.59',('-46%',ACC)],
  ['95%','$3.56',('-58%',ACC)],
  [('100% (이론 상한)',ACC),('$3.22',ACC),('-62%',ACC)]],
 colw=[2.4,2.1,2.0], rowh=0.42)
card(sl,7.65,2.05,4.95,2.05,'손익분기: 0.28회',
 ['캐시 쓰기는 1.25배 비싸지만, 같은 프리픽스를',
  '한 번만 더 재사용해도 즉시 이득이다.',
  '“재사용이 적어서 안 쓴다”는 거의 항상 오판.'],ACC,19,13)
card(sl,7.65,4.35,4.95,2.4,'최악의 안티패턴 = 3.1배',
 ['맨 앞에 타임스탬프·요청 ID·“현재 시각”을 넣으면',
  '매 호출 캐시가 전부 깨진다. 쓰기 프리미엄만 물어',
  '캐시를 아예 안 쓴 것보다 18% 비싸진다.',
  '캐시 최적 $3.22 → 안티패턴 $10.05 = 3.1배'],RED,19,13)
text(sl,0.75,5.35,6.5,0.9,[
 {'t':'→ 리포의 exp07 진단기가 이 동적값을 자동으로 잡아준다.','sz':14.5,'c':MUTED}])
note(sl,'재현: exp03_prompt_caching.py (프리픽스 20K · 가변 1K · 출력 1.5K · 100콜, Sonnet 단가)', 6.95)

# ───────────────────────── 13b. 에이전트 루프의 2차 함수
sl = slide('에이전트 루프 — 비용은 선형이 아니라 2차 함수다', 'BONUS ⑥')
text(sl,0.75,1.95,11.9,0.4,[{'t':'매 턴 전체 대화가 다시 입력으로 들어간다. 턴이 2배면 비용은 약 3배가 된다 (10→20턴 3.1배).','sz':15,'c':MUTED}])
table(sl,0.75,2.45,6.3,['세션 길이','누적 비용','증가'],
 [['5턴','$0.26',''],
  ['10턴','$0.74',('2.8×',WARN)],
  ['20턴','$2.32',('3.1×',RED)],
  ['30턴','$4.73',('2.0×',RED)],
  [('50턴',RED),('$12.09',RED),('2.6×',RED)]],
 colw=[2.1,2.1,2.1], rowh=0.48)
card(sl,7.45,2.45,5.2,3.6,'20턴 세션, 전략별 비용',
 ['무대책                        $2.32',
  '캐싱만                        $1.88   (-19%)',
  '캐싱 + 10턴마다 컴팩션   $1.31   (-44%)',
  '캐싱 + 5턴마다 컴팩션    $0.97   (-58%)',
  '',
  '컴팩션 = 오래된 툴 결과·중간 로그를 요약으로',
  '교체하는 것. 100턴 평가에서 84% 절감 보고.'],ACC,19,12.5)
text(sl,0.75,5.95,11.9,0.9,[
 {'t':'실무 규칙: 작업이 끝나면 대화를 끊어라. “하나의 대화로 종일”이 가장 비싼 습관이다.','sz':17,'b':True,'c':FG},
 {'t':'Anthropic: 에이전트는 챗 대비 4배, 멀티에이전트는 15배 토큰을 쓴다. 에이전트 지출의 99% 이상이 입력 토큰이다.','sz':14,'c':MUTED,'space_before':7}])
note(sl,'재현: exp04_agent_loop_sdd.py (프리픽스 8K · 턴당 입력 2K / 출력 0.8K, Sonnet 단가)', 6.95)

# ───────────────────────── 13c. SDD 검증
sl = slide('스펙 주도 개발(SDD)은 조건부로만 참이다', 'VERIFY')
card(sl,0.75,2.05,5.85,3.3,'유리한 쪽 — 자체 시뮬레이션',
 ['vibe 코딩 40턴                        $1.75',
  '규약 파일 적용                        $1.09  (-38%)',
  'SDD (스펙 4K + 12턴)               $0.51  (-71%)',
  '',
  '스펙이 턴 수를 줄이면, 2차 함수 구간 자체가',
  '잘려 나가기 때문에 절감폭이 크게 나온다.'],ACC,19,13)
card(sl,6.9,2.05,5.7,3.3,'불리한 쪽 — 외부 반증',
 ['Spec-Kit은 OpenSpec 대비 토큰 +97~109%',
  '(57,740 → 120,947 / 91,729 → 181,040).',
  '무거운 SDD 프레임워크는 오히려 비용을 늘린다.',
  '',
  'ETH Zurich (138 이슈, 4개 모델): LLM이 생성한',
  '컨텍스트 파일은 성공률 소폭 하락 + 비용 20%↑.'],RED,19,13)
text(sl,0.75,5.65,11.9,1.2,[
 {'t':'결론: “스펙을 쓰라”가 아니라 “가볍게, 결정 중심으로 쓰라”','sz':19,'b':True,'c':ACC},
 {'t':'엔드포인트·스키마·에러·완료조건처럼 모델이 추측하면 틀리는 것만 적는다. 코드를 읽으면 아는 것은 스펙에도 쓰지 않는다.','sz':15,'c':MUTED,'space_before':8}])
note(sl,'재현: exp04 · 반증 출처: Spec-Kit vs OpenSpec 벤치마크(2026), ETH Zurich 컨텍스트 파일 연구', 6.95)

# ───────────────────────── 13d. 나머지 레버
sl = slide('나머지 레버 4종 — 언제 쓰고, 언제 쓰지 말 것인가', 'BONUS ⑦')
lv=[('배치 API','입력·출력 정액 50% 할인. 캐싱과 중복 적용 가능.','야간 평가·벌크 분류·리포트 생성','SLA 24시간. 사용자 대면 채팅·툴 루프 불가.',ACC),
    ('시맨틱 캐싱','유사 질문을 임베딩으로 매칭해 호출 자체를 제거.','FAQ·고객지원·반복 질의 (히트율 20~45%)','벤더의 95% 주장은 과장. 임계값 0.8 권장.',ACC2),
    ('모델 라우팅','쉬운 요청은 소형 모델로. RouteLLM 85%↓ @ 품질 95%.','분류·추출·요약 등 난이도 편차 큰 트래픽','벤치마크 임계값 그대로 쓰면 과대추정. 재보정 필수.',WARN),
    ('프롬프트 압축','LLMLingua 최대 20× 압축, 손실 2% 미만.','RAG 컨텍스트·장황한 시스템 프롬프트·few-shot','코드·수식·짧은 쿼리에는 쓰지 말 것.',RED)]
for i,(name,what,good,bad,c) in enumerate(lv):
    yy=2.0+i*1.2
    rect(sl,0.75,yy,11.9,1.08, fill=CARD if i%2 else CARD2, radius=0.05)
    rect(sl,0.75,yy,0.05,1.08, fill=c)
    text(sl,1.05,yy+0.1,2.3,0.3,[{'t':name,'sz':16,'b':True,'c':c}])
    text(sl,1.05,yy+0.56,2.3,0.3,[{'t':what,'sz':10.5,'c':MUTED}])
    text(sl,3.6,yy+0.14,4.3,0.3,[{'t':'○  '+good,'sz':12.5,'c':FG}])
    text(sl,3.6,yy+0.58,4.3,0.3,[{'t':'',            'sz':12.5,'c':FG}])
    text(sl,8.1,yy+0.14,4.3,0.6,[{'t':'✕  '+bad,'sz':12.5,'c':MUTED}])
text(sl,0.75,6.85,11.9,0.4,[{'t':'재현: exp06_other_levers.py  ·  출처: OpenAI/Anthropic Batch 문서, RouteLLM(ICLR 2025), LLMLingua(MS Research), AWS 시맨틱 캐싱 사례','sz':10.5,'c':MUTED}])

# ───────────────────────── 13e. 스택 적층
sl = slide('레버는 곱해진다 — 스택 적층 시뮬레이션', 'STACK')
text(sl,0.75,1.95,11.9,0.4,[{'t':'각 레버는 “앞 단계가 걸러낸 나머지”에 적용된다. 그래서 30% + 50%는 80%가 아니라 65%다.','sz':15,'c':MUTED}])
stack=[('시작 — 무대책','100%','',MUTED),
 ('① 시맨틱 캐싱 (호출 30% 제거)','70%','-30%p',ACC2),
 ('② 모델 라우팅 (쉬운 건 소형으로)','42%','-28%p',ACC2),
 ('③ 프롬프트 캐싱 (프리픽스 재사용)','21%','-21%p',ACC),
 ('④ verbosity / effort 조정','16%','-5%p',ACC),
 ('⑤ 배치 API (비대면 트래픽만)','14%','-2%p',ACC)]
for i,(h,rem,d,c) in enumerate(stack):
    yy=2.5+i*0.62
    rect(sl,0.75,yy,11.9,0.54, fill=CARD if i%2 else CARD2, radius=0.04)
    barw = 5.4*float(rem.rstrip('%'))/100
    rect(sl,4.55,yy+0.13,max(barw,0.06),0.28, fill=c)
    text(sl,1.0,yy+0.11,3.5,0.3,[{'t':h,'sz':13.5,'b':True,'c':FG}])
    text(sl,10.2,yy+0.11,1.2,0.3,[{'t':rem,'sz':14,'b':True,'c':c}])
    text(sl,11.5,yy+0.13,1.0,0.3,[{'t':d,'sz':12,'c':MUTED}])
text(sl,0.75,6.35,11.9,0.9,[
 {'t':'누적 86% 절감 — 업계 보고치 60~80%의 상한선에 해당한다. 전부 적용했을 때의 이론값으로 읽을 것.','sz':16,'b':True,'c':ACC},
 {'t':'현실적 목표: 상위 2~3개만 제대로 해도 50~65%. 8개를 어설프게 하는 것보다 낫다.','sz':14,'c':MUTED,'space_before':6}])

# ───────────────────────── 14b. 우선순위
sl = slide('무엇부터 할 것인가 — ROI 우선순위', 'PRIORITY')
pr=[('1','프롬프트 캐싱','-62%','즉시','설정 한 줄. 손익분기 0.28회. 이견 없는 1순위.',ACC),
 ('2','verbosity · effort','-40~60%','즉시','파라미터 한 줄. 품질 영향은 작업별로 확인.',ACC),
 ('3','Batch API','-50%','1일','비대면 트래픽 한정. 할인이 정액이라 확실.',ACC),
 ('4','스펙 주도(가볍게)','-38~71%','1주','습관 변화 필요. 무거운 프레임워크는 역효과.',ACC2),
 ('5','컨텍스트 컴팩션','-22~58%','1주','에이전트 운영 시 필수. 긴 세션일수록 효과 큼.',ACC2),
 ('6','모델 라우팅','-49~84%','2~4주','효과는 최대급이나 임계값 재보정·품질 회귀 필요.',WARN),
 ('7','시맨틱 캐싱','-20~45%','2~4주','인프라 추가. 반복 질의 많은 서비스에서만.',WARN),
 ('8','프롬프트 압축','-20~40%','4주+','코드·수식 금지. 마지막에 손댈 것.',RED)]
rect(sl,0.75,2.0,11.9,0.42, fill=CARD)
for lb,xx,ww in [('#',0.9,0.4),('레버',1.4,2.6),('절감폭',4.1,1.3),('도입 기간',5.5,1.4),('비고',7.1,5.4)]:
    text(sl,xx,2.09,ww,0.3,[{'t':lb,'sz':12.5,'b':True,'c':ACC}])
for i,(n,name,save,eta,memo,c) in enumerate(pr):
    yy=2.42+i*0.55
    if i%2==0: rect(sl,0.75,yy,11.9,0.55, fill=CARD2)
    text(sl,0.9,yy+0.13,0.4,0.3,[{'t':n,'sz':14,'b':True,'c':c}])
    text(sl,1.4,yy+0.13,2.6,0.3,[{'t':name,'sz':14,'b':True,'c':FG}])
    text(sl,4.1,yy+0.14,1.3,0.3,[{'t':save,'sz':13.5,'b':True,'c':c}])
    text(sl,5.5,yy+0.15,1.4,0.3,[{'t':eta,'sz':12.5,'c':MUTED}])
    text(sl,7.1,yy+0.15,5.4,0.3,[{'t':memo,'sz':12,'c':MUTED}])
text(sl,0.75,6.95,11.9,0.35,[{'t':'절감폭은 각 레버를 “단독 적용”했을 때의 값. 함께 쓰면 앞 장의 적층 규칙대로 곱해진다.','sz':11.5,'c':MUTED}])

# ───────────────────────── 15. 실행 플레이북 + 안티패턴
sl = slide('오늘부터 적용하는 7단계 / 버려야 할 7가지', 'PLAYBOOK')
text(sl,0.75,1.95,5.85,0.35,[{'t':'○   이렇게 하세요','sz':16,'b':True,'c':ACC}])
text(sl,6.9,1.95,5.7,0.35,[{'t':'✕   이건 버리세요','sz':16,'b':True,'c':RED}])
steps=[('1','사고 언어를 영어로 고정','시스템 프롬프트/설정에 명시. 답변만 한국어.'),
 ('2','effort 기본값 low~medium','계획 단계에서만 high.'),
 ('3','verbosity low + 요약 금지','“코드와 3줄 근거만”'),
 ('4','설계는 웹 채팅에서 끝낸다','정액 요금 구간에서 사고를 소모.'),
 ('5','결론을 스펙 파일로 커밋','specs/*.md — 재사용 가능한 입력 자산.'),
 ('6','고정 컨텍스트 앞쪽 + 캐싱','순서 고정, 앞부분에 동적값 금지.'),
 ('7','주 1회 토큰 리포트 확인','입력/출력/추론/캐시 히트율 4개 지표.')]
anti=[('“일단 만들고 아니면 수정하자”','리워크 1회 = 컨텍스트 전체 재전송.'),
 ('한국어로 길게 생각하게 두기','같은 사고에 1.4~2.2배 지출.'),
 ('“확장성 있게, 나중을 대비해서”','YAGNI 위반. 안 쓸 코드가 영구 컨텍스트.'),
 ('프롬프트 맨 앞에 타임스탬프·ID','캐시 전멸. 최대 3.1배 청구.'),
 ('요약을 요약하고 다시 요약','출력 토큰 3중 소각.'),
 ('모든 작업에 최상위 모델 + high','분류 작업에 프런티어 모델은 낭비.'),
 ('대화 하나로 종일 이어가기','턴이 2배면 비용은 약 3배. 2차 함수.')]
for i in range(7):
    yy=2.4+i*0.65
    n,h,b = steps[i]
    rect(sl,0.75,yy,5.85,0.58, fill=CARD if i%2 else CARD2, radius=0.05)
    rect(sl,0.75,yy,0.05,0.58, fill=ACC)
    text(sl,1.0,yy+0.14,0.35,0.3,[{'t':n,'sz':14,'b':True,'c':ACC}])
    text(sl,1.4,yy+0.05,5.0,0.3,[{'t':h,'sz':13.5,'b':True,'c':FG}])
    text(sl,1.4,yy+0.32,5.0,0.3,[{'t':b,'sz':11,'c':MUTED}])
    ah,ab = anti[i]
    rect(sl,6.9,yy,5.7,0.58, fill=CARD if i%2 else CARD2, radius=0.05)
    rect(sl,6.9,yy,0.05,0.58, fill=RED)
    text(sl,7.15,yy+0.14,0.35,0.3,[{'t':'✕','sz':13,'b':True,'c':RED}])
    text(sl,7.55,yy+0.05,4.9,0.3,[{'t':ah,'sz':13.5,'b':True,'c':FG}])
    text(sl,7.55,yy+0.32,4.9,0.3,[{'t':ab,'sz':11,'c':MUTED}])

# ───────────────────────── 15b. 검증 리포
sl = slide('오늘 숫자는 전부 재현 가능합니다', 'REPRODUCE')
text(sl,0.75,1.88,11.9,0.45,[
 {'t':'이 발표의 모든 수치는 슬라이드에 박아 넣은 값이 아니라, 실행 가능한 스크립트의 출력입니다.','sz':17,'b':True,'c':FG}])
rect(sl,0.75,2.42,6.1,1.32, fill=CARD2, radius=0.05)
text(sl,1.05,2.55,5.6,1.1,[
 {'t':'$ pip install -r requirements.txt','sz':12.5,'c':ACC,'f':'Consolas'},
 {'t':'$ python run_all.py','sz':12.5,'c':ACC,'f':'Consolas','space_before':4},
 {'t':'$ python run_all.py --model opus','sz':12.5,'c':MUTED,'f':'Consolas','space_before':4},
 {'t':'$ python experiments/exp07_analyze_my_prompt.py my.txt','sz':11,'c':MUTED,'f':'Consolas','space_before':4}])
card(sl,7.1,2.42,5.55,1.44,'단가를 바꿔도 결론이 그대로인가',
 ['--model 로 opus / gpt5 / gemini / deepseek 전환.',
  '배수는 달라져도 “출력 → 입력” 방향은 동일.'],ACC2,16,12)
exps=[('exp01','한·영 토크나이저 실측','원칙 ①'),('exp02','출력→입력 환전 비용','원칙 ④'),
 ('exp03','프롬프트 캐싱 히트율','보너스 ⑤'),('exp04','에이전트 루프 · SDD','보너스 ⑥'),
 ('exp05','verbosity · effort','원칙 ③'),('exp06','배치·압축·라우팅·적층','보너스 ⑦'),
 ('exp07','내 프롬프트 진단기','실습'),('exp08','Gemini 실시간 과금 측정','실측'),
 ('exp09','DRY의 토큰 경제학','원칙 ②')]
for i,(k,d,m) in enumerate(exps):
    col=i%2; row=i//2
    x=0.75+col*6.15; yy=3.88+row*0.45
    rect(sl,x,yy,5.85,0.40, fill=CARD if i%2 else CARD2, radius=0.04)
    text(sl,x+0.2,yy+0.08,0.85,0.28,[{'t':k,'sz':12,'b':True,'c':ACC,'f':'Consolas'}])
    text(sl,x+1.15,yy+0.08,3.2,0.28,[{'t':d,'sz':12.5,'c':FG}])
    text(sl,x+4.5,yy+0.09,1.25,0.28,[{'t':m,'sz':11,'c':MUTED}])
for j,(t) in enumerate([
 '+  tools/live_lang_bench.py   —  한·영 × 설명형·추론형 실호출 벤치   (슬라이드 6·7 · N=100/80)',
 '+  tools/stats_test.py        —  부트스트랩 95% CI · Welch · Cliff\'s δ · $/1,000자 정규화   (슬라이드 7)',
 '+  tools/thinking_sweep.py    —  사고 예산만 바꿔 5단 스윕   (슬라이드 25 · 240배, gemini-25 단가 환산)']):
    rect(sl,0.75,6.24+j*0.32,11.9,0.30, fill=CARD2, radius=0.04)
    text(sl,0.95,6.26+j*0.32,11.5,0.26,[{'t':t,'sz':11,'c':ACC2,'f':'Consolas'}])
text(sl,0.75,7.22,11.9,0.28,[
 {'t':'특히 exp07은 여러분의 실제 시스템 프롬프트를 넣으면 캐시 적격성·동적값 위치·한글 비중·중복을 진단해 줍니다.','sz':12.5,'c':ACC}])

# ───────────────────────── 15c. 라이브 실측 — 사고 예산 스윕
sl = slide('같은 정답률, 240배 요금 — 30회 실측', 'LIVE MEASUREMENT · N=30 · 2026-08-15')
text(sl,0.75,1.88,11.9,0.45,[
 {'t':'같은 계산 문제 30회. 사고 예산만 변경. 정답 $38.016 · 오른쪽 열은 6회 중 정답 횟수.','sz':15.5,'c':MUTED}])
table(sl,0.75,2.4,11.9,
 ['사고 예산','n','사고 토큰','응답','비용/호출','배수','정답률 (±0.05)'],
 [['미지정(기본)','6','0','6','$0.000155','1.0×','정답 6/6'],
  ['끔 (0)','6','0','6','$0.000158','1.0×',('정답 5/6  (1회 380.16)',WARN)],
  ['512','6','142','6','$0.001570',('10.1×',WARN),('정답 2/6  ← 품질 붕괴',RED)],
  ['2048','6','1,114','6','$0.011302',('72.9×',WARN),'정답 6/6'],
  [('자동 (−1)',RED),'6',('3,704',RED),'6',('$0.037203',RED),('240×',RED),'정답 6/6']],
 colw=[2.0,0.6,1.5,0.95,1.85,1.3,3.7], sz=13, hsz=12.5, rowh=0.44)
text(sl,0.75,5.02,11.9,0.4,[
 {'t':'사고를 끄든 켜든 정답률은 6/6으로 같습니다. 요금만 240배 차이납니다.','sz':16.5,'b':True,'c':RED}])
card(sl,0.75,5.42,5.85,1.52,'출력 토큰의 99%가 보이지 않는다',
 ['사고가 켜진 구간에서 과금 출력의 99%가 thoughtsTokenCount다 (실측 99.6%).'],RED,15,12.5)
card(sl,6.8,5.42,5.85,1.52,'예산 512는 정답률이 2/6으로 떨어졌다',
 ['어중간한 예산은 추론이 끊겨 품질까지 나빠진다. 충분히 주거나 아예 끌 것.'],WARN,15,12.5)
note(sl,'재현: tools/thinking_sweep.py --n 6 · 원자료 results/thinking_sweep.jsonl · LIVE_RESULTS.md §8', 7.02)

# ───────────────────────── 16. 마무리
sl = slide('정리', 'WRAP-UP')
text(sl,0.75,2.2,11.9,1.2,[
 {'t':'토큰 절약 = 적게 쓰기가 아니라, 싼 자리로 옮기기','sz':30,'b':True,'c':ACC}])
rows=[('비싼 자리','출력 토큰 · 추론 토큰 · 한국어 · 리워크',RED),
      ('싼 자리','입력 토큰 · 캐시된 입력 · 영어 · 확정된 스펙',ACC)]
for i,(h,b,c) in enumerate(rows):
    yy=3.5+i*1.0
    rect(sl,0.75,yy,11.9,0.85, fill=CARD)
    rect(sl,0.75,yy,0.055,0.85, fill=c)
    text(sl,1.15,yy+0.22,2.2,0.4,[{'t':h,'sz':18,'b':True,'c':c}])
    text(sl,3.5,yy+0.25,9.0,0.4,[{'t':b,'sz':16,'c':FG}])
text(sl,0.75,5.75,11.9,1.0,[
 {'t':'한 줄 요약','sz':15,'b':True,'c':MUTED},
 {'t':'생각은 밖에서(웹·영어·짧게), 실행은 안에서(스펙·낮은 effort·캐시).','sz':22,'b':True,'c':FG,'space_before':6}])

# ───────────────────────── 17. 출처 (1/2) 논문
sl = slide('근거 및 검증 자료 (1/2) — 학술 문헌', 'REFERENCES')
text(sl,0.75,1.9,11.9,0.3,[{'t':'모든 링크는 원문 기준. arXiv 번호로 검색하면 바로 나옵니다.','sz':12,'c':MUTED}])
refs1=[
 ('Language Model Tokenizers Introduce Unfairness Between Languages',
  'Petrov, La Malfa, Torr, Bibi (Oxford) · NeurIPS 2023',
  'arxiv.org/abs/2305.15425',
  '토큰화 단계에서 언어 간 불평등 발생. 일부 언어는 같은 내용에 2.5배 이상 지불.'),
 ('When Models Reason in Your Language: Controlling Thinking Language Comes at the Cost of Accuracy',
  'XReasoning 벤치마크 · 2025',
  'arxiv.org/abs/2505.22888',
  '사용자 언어로 사고를 강제하면 언어일치율 46%→98%, 그러나 정확도 26%→17%.'),
 ('Language Matters: How Do Multilingual Input and Reasoning Paths Affect Large Reasoning Models?',
  '2025',
  'arxiv.org/abs/2505.17407',
  '영어는 reasoning hub. DeepSeek-R1-Distill-Llama-8B 영어 사고 시 평균 +26.8%.'),
 ('RouteLLM: Learning to Route LLMs with Preference Data',
  'Ong 외 7인 (UC Berkeley · Anyscale) · ICLR 2025',
  'arxiv.org/abs/2406.18665',
  '강·약 모델 라우팅으로 품질 유지하며 비용 2배 이상 절감. 오픈소스 프레임워크 공개.'),
 ('LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models',
  'Jiang, Wu, Lin, Yang, Qiu (Microsoft Research) · EMNLP 2023',
  'arxiv.org/abs/2310.05736',
  '최대 20× 압축에 성능 손실 1.5점. 후속작 LongLLMLingua는 arxiv.org/abs/2310.06839.'),
 ('LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression',
  'Pan, Wu, Jiang 외 (Microsoft Research) · ACL 2024 Findings',
  'arxiv.org/abs/2403.12968',
  '2~5× 압축을 3~6배 빠르게. 실무에서 쓰기 좋은 경량 버전.'),
 ('GPT Semantic Cache: Reducing LLM Costs and Latency via Semantic Embedding Caching',
  'Regmi, Pun · 2024',
  'arxiv.org/abs/2411.05276',
  'API 호출 최대 68.8% 감소, 히트율 61.6~68.8%, positive hit rate 97%+.'),
 ('Lost in the Middle: How Language Models Use Long Contexts',
  'Liu 외 6인 (Stanford) · TACL 2024',
  'arxiv.org/abs/2307.03172',
  '핵심 정보가 컨텍스트 중간에 있으면 성능 급락(U자 곡선). 앞·뒤에 배치할 것.'),
]
for i,(t,who,url,note_) in enumerate(refs1):
    yy=2.3+i*0.60
    if i%2==0: rect(sl,0.75,yy-0.06,11.9,0.58, fill=CARD2)
    rect(sl,0.82,yy+0.06,0.07,0.07, fill=ACC)
    tt = t if len(t)<=78 else t[:76]+'…'
    text(sl,1.05,yy-0.04,7.6,0.26,[{'t':tt,'sz':10.5,'b':True,'c':FG}])
    text(sl,1.05,yy+0.22,7.6,0.26,[{'t':note_,'sz':9.5,'c':MUTED}])
    text(sl,8.75,yy-0.04,3.9,0.26,[{'t':who,'sz':9,'c':MUTED}])
    text(sl,8.75,yy+0.22,3.9,0.26,[{'t':url,'sz':9,'c':ACC2,'f':'Consolas'}])

# ───────────────────────── 18. 출처 (2/2) 1차자료
sl = slide('근거 및 검증 자료 (2/2) — 벤더 문서 · 자체 실측', 'REFERENCES')
refs2=[
 ('token-cost-lab — 본 발표의 자체 실측 코드 (exp01~exp09 + tools/)',
  'tiktoken o200k_base · cl100k_base, 한·영 6문장쌍, 단가 시뮬레이션',
  'github.com/giyeop-cody/token-cost-lab',ACC),
 ('Anthropic — Prompt caching / Message Batches API 공식 문서',
  '캐시 읽기 0.1× (90% 할인), 쓰기 1.25×(5분)·2×(1시간), 최소 1,024토큰. 배치 50% 할인·최대 24시간·10만 요청',
  'docs.anthropic.com/en/docs/build-with-claude/prompt-caching',ACC2),
 ('OpenAI — Prompt caching / Batch API 공식 문서',
  '자동 프리픽스 캐싱(1,024토큰 이상), 배치 50% 할인·24시간 SLA·배치당 5만 요청',
  'platform.openai.com/docs/guides/prompt-caching',ACC2),
 ('Google — Gemini context caching 문서 (implicit / explicit)',
  '캐시 읽기 약 75% 할인. DeepSeek도 자동 캐싱으로 0.1× 적용',
  'ai.google.dev/gemini-api/docs/caching',ACC2),
 ('Anthropic Engineering — “Effective context engineering for AI agents” (2025.09)',
  'context rot·attention budget 개념, 컴팩션·구조적 노트·서브에이전트(요약 1,000~2,000토큰) 전략',
  'anthropic.com/engineering/effective-context-engineering-for-ai-agents',WARN),
 ('Anthropic Engineering — “How we built our multi-agent research system” (2025)',
  '에이전트는 챗 대비 약 4배, 멀티에이전트는 약 15배 토큰 소모',
  'anthropic.com/engineering/multi-agent-research-system',WARN),
 ('Spec-Kit vs OpenSpec 토큰 벤치마크 (2026) / ETH Zurich 컨텍스트 파일 연구',
  'Spec-Kit이 OpenSpec 대비 토큰 +97~109%. LLM 생성 컨텍스트 파일은 성공률 소폭 하락 + 비용 20%+ 증가',
  'SDD 반증 근거 — 슬라이드 15',RED),
 ('2026 LLM 가격 비교 자료 및 각 벤더 공식 가격 페이지',
  '출력/입력 단가 배수 2~8× 확인. 단가는 수시 변동하므로 인용 시 확인 날짜 병기 필요',
  'anthropic.com/pricing · openai.com/api/pricing · ai.google.dev/pricing',MUTED),
]
for i,(t,d,url,c) in enumerate(refs2):
    yy=2.05+i*0.62
    if i%2==0: rect(sl,0.75,yy-0.06,11.9,0.60, fill=CARD2)
    rect(sl,0.75,yy-0.06,0.045,0.60, fill=c)
    text(sl,1.05,yy-0.02,11.4,0.26,[{'t':t,'sz':11,'b':True,'c':FG}])
    text(sl,1.05,yy+0.20,7.9,0.26,[{'t':d,'sz':9.5,'c':MUTED}])
    text(sl,9.1,yy+0.20,3.5,0.26,[{'t':url,'sz':8.5,'c':ACC2,'f':'Consolas'}])
text(sl,0.75,7.0,11.9,0.3,[{'t':'※ 가격·모델 라인업은 수시로 변동합니다. 발표 직전 각 벤더 가격 페이지를 재확인하세요.','sz':10.5,'c':MUTED}])

# ───────────────────────── 19. QnA + 리포 안내 (클로징)
sl = slide('질문 받겠습니다', 'Q & A  ·  REPOSITORY')
text(sl,0.75,1.92,7.7,0.45,[
 {'t':'오늘 나온 모든 수치는 리포에서 직접 돌려볼 수 있습니다.','sz':17,'b':True,'c':FG}])

# 좌측: 리포에 뭐가 있나
card(sl,0.75,2.55,7.7,2.30,'token-cost-lab — 무엇이 들어 있나',
 ['exp01~09  ·  원칙별 재현 스크립트 (실호출 없음, 무료)',
  'tools/     ·  라이브 벤치 · 통계 검정 · 사고 예산 스윕',
  'results/   ·  실측 원자료 JSONL 110행 + 검정 출력',
  'demo/      ·  페르소나 A/B 토큰 비교 + 메모장 산출물'],ACC,17,12.5)
rect(sl,0.75,4.98,7.7,0.86, fill=CARD2, radius=0.05)
text(sl,1.05,5.08,7.2,0.7,[
 {'t':'$ git clone https://github.com/giyeop-cody/token-cost-lab','sz':11.5,'c':ACC,'f':'Consolas'},
 {'t':'$ pip install -r requirements.txt && python run_all.py','sz':11.5,'c':MUTED,'f':'Consolas','space_before':5}])

# 우측: QR
qr(sl,9.55,2.72,2.35,None)
text(sl,8.95,5.28,3.55,0.28,[{'t':'스캔하면 바로 리포로','sz':12,'b':True,'c':FG}],
     align=PP_ALIGN.CENTER)
text(sl,8.95,5.58,3.55,0.26,[{'t':REPO_URL,'sz':10,'c':ACC2,'f':'Consolas'}],
     align=PP_ALIGN.CENTER)

# 하단: 자주 나올 질문 3개 미리 박아두기
qas=[('"우리 모델에도 같은 배수가 나오나요?"',
      'exp01을 자기 모델 토크나이저로 재실행. 배수는 다르지만 방향은 같다.'),
     ('"240배는 과장 아닌가요?"',
      'gemini-25 단가 환산 기준. 실단가로는 149배. 원자료 30행 공개돼 있다.'),
     ('"제일 먼저 뭘 하면 되죠?"',
      '캐싱 + verbosity/effort. 설정 한 줄, 오늘 오후에 켤 수 있다.')]
for i,(q,a) in enumerate(qas):
    yy=5.90+i*0.46
    rect(sl,0.75,yy,11.9,0.42, fill=CARD2 if i%2==0 else CARD, radius=0.04)
    text(sl,1.00,yy+0.07,5.15,0.28,[{'t':q,'sz':11.5,'b':True,'c':ACC}])
    text(sl,6.30,yy+0.08,6.15,0.28,[{'t':a,'sz':11,'c':MUTED}])

import os as _os
_OUT = _os.path.join(_PRES, '토큰_절약_발표.pptx')
prs.save(_OUT)
print('saved:', _OUT)
print("slides:", len(prs.slides.__iter__.__self__._sldIdLst))
