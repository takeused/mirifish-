#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
생성된 시뮬레이션 리포트들을 하나의 index.html(탭 메뉴)로 종합한다.

backend/uploads/reports/<report_id>/ 아래의 완료된 리포트(full_report.md + progress.json)를
스캔해, 최신순 탭으로 묶은 자체완결형 HTML을 프로젝트 루트에 생성한다.
새 리포트가 생성되면 이 스크립트를 다시 실행하기만 하면 index.html이 갱신된다.

    python build_report_index.py
"""
import os
import re
import json
import html
import glob
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(ROOT, "backend", "uploads", "reports")
OUT = os.path.join(ROOT, "report_index.html")


def md_to_html(md: str) -> str:
    """리포트 본문용 경량 마크다운 변환(제목 # 는 별도 처리하므로 제거)."""
    lines = md.split("\n")
    out, in_ul = [], False

    def inline(t: str) -> str:
        t = html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
        return t

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("# "):
            continue  # 문서 제목 → 탭 헤더에서 별도 표시
        if line.strip() == "---":
            continue
        if re.match(r"^#{2,6}\s", line):
            if in_ul:
                out.append("</ul>"); in_ul = False
            level = len(line) - len(line.lstrip("#"))
            text = line.lstrip("#").strip()
            out.append(f"<h{level}>{inline(text)}</h{level}>")
            continue
        if line.startswith(">"):
            if in_ul:
                out.append("</ul>"); in_ul = False
            text = line.lstrip(">").strip()
            if text:
                out.append(f'<blockquote>{inline(text)}</blockquote>')
            continue
        m = re.match(r"^\s*[\*\-]\s+(.*)", line)
        if m:
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue
        if not line.strip():
            if in_ul:
                out.append("</ul>"); in_ul = False
            continue
        if in_ul:
            out.append("</ul>"); in_ul = False
        out.append(f"<p>{inline(line.strip())}</p>")

    if in_ul:
        out.append("</ul>")
    return "\n".join(out)


def collect():
    reports = []
    for pdir in sorted(glob.glob(os.path.join(REPORTS_DIR, "report_*"))):
        rid = os.path.basename(pdir)
        fr = os.path.join(pdir, "full_report.md")
        pj = os.path.join(pdir, "progress.json")
        if not (os.path.isfile(fr) and os.path.isfile(pj)):
            continue
        try:
            prog = json.load(open(pj, encoding="utf-8"))
        except Exception:
            continue
        if prog.get("status") != "completed":
            continue
        md = open(fr, encoding="utf-8").read()
        m = re.match(r"^#\s+(.+)", md)
        title = m.group(1).strip() if m else rid
        # 요약(첫 blockquote)
        bq = re.search(r"^>\s*(.+)", md, re.M)
        summary = bq.group(1).strip() if bq else ""
        sim = ""
        try:
            sim = json.load(open(os.path.join(pdir, "meta.json"), encoding="utf-8")).get("simulation_id", "")
        except Exception:
            pass
        reports.append({
            "id": rid,
            "title": title,
            "summary": summary,
            "date": (prog.get("updated_at") or "")[:16].replace("T", " "),
            "sections": len(prog.get("completed_sections", [])),
            "size": len(md.encode("utf-8")),
            "sim": sim,
            "body": md_to_html(md),
            "truncated": "잘림" in (prog.get("message") or ""),
        })
    # 최신순
    reports.sort(key=lambda r: r["date"], reverse=True)
    return reports


CSS = """
/* ── BMW M design language ── */
:root{
--canvas:#000;--surface-soft:#0d0d0d;--surface-card:#1a1a1a;--surface-elevated:#262626;--carbon:#2b2b2b;
--hairline:#3c3c3c;--hairline-strong:#262626;
--on-dark:#fff;--body:#bbb;--body-strong:#e6e6e6;--muted:#7e7e7e;
--m-blue-light:#0066b1;--m-blue-dark:#1c69d4;--m-red:#e22718;--warning:#f4b400;
--m-stripe:linear-gradient(90deg,#0066b1 0%,#1c69d4 50%,#e22718 100%);
--mono:"SFMono-Regular",Consolas,Menlo,monospace;}
*{box-sizing:border-box}
body{margin:0;background:var(--canvas);color:var(--on-dark);
font-family:"BMW Type Next Latin","Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Malgun Gothic","Apple SD Gothic Neo",sans-serif;
font-size:16px;line-height:1.6;letter-spacing:0;-webkit-font-smoothing:antialiased;}
.page{max-width:1200px;margin:0 auto;background:var(--canvas);min-height:100vh}
.mbar{height:4px;background:var(--m-stripe)}
/* 헤더 */
header.top{padding:56px 56px 34px;background:var(--canvas);border-bottom:1px solid var(--hairline)}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:2px;color:var(--muted);text-transform:uppercase;margin-bottom:18px}
header.top h1{font-size:52px;font-weight:700;line-height:1.02;margin:0 0 16px;text-transform:uppercase;letter-spacing:-.5px;color:var(--on-dark)}
header.top p{margin:0;color:var(--body);font-size:16px;font-weight:300;max-width:60ch}
.count{color:var(--muted);font-size:12px;margin-top:16px;text-transform:uppercase;letter-spacing:1.5px;font-weight:700}
/* 탭바 (category-tab: text-only uppercase, active = white underline) */
.tabbar{display:flex;flex-wrap:wrap;gap:28px;padding:0 56px;background:var(--canvas);
border-bottom:1px solid var(--hairline);position:sticky;top:0;z-index:5}
.tab{appearance:none;border:none;background:none;cursor:pointer;font-family:inherit;
padding:18px 0;font-size:13px;font-weight:700;color:var(--body);text-transform:uppercase;letter-spacing:1.5px;
border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap;transition:color .15s,border-color .15s;text-align:left}
.tab:hover{color:var(--on-dark)}
.tab.active{color:var(--on-dark);border-bottom-color:var(--on-dark)}
.tab .d{display:block;font-size:10px;font-weight:300;color:var(--muted);font-family:var(--mono);margin-top:4px;letter-spacing:.5px}
/* 패널 */
.panel{display:none;padding:48px 56px 88px}
.panel.active{display:block;animation:fade .25s ease}
@keyframes fade{from{opacity:0}to{opacity:1}}
.rtitle{font-size:38px;font-weight:700;margin:0 0 18px;line-height:1.08;letter-spacing:-.5px;color:var(--on-dark)}
.rmeta{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 40px}
.chip{font-size:11px;font-family:var(--mono);background:var(--surface-card);color:var(--body);
border:1px solid var(--hairline);border-radius:0;padding:5px 11px;letter-spacing:.5px}
.chip.warn{background:var(--surface-card);border-color:var(--warning);color:var(--warning)}
/* 리포트 본문 */
.body{font-weight:300;color:var(--body)}
.body blockquote{position:relative;margin:22px 0;padding:18px 24px 18px 28px;
background:var(--surface-card);color:var(--body-strong);font-size:15px;font-weight:300}
.body blockquote::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
background:linear-gradient(180deg,#0066b1 0%,#1c69d4 50%,#e22718 100%)}
.body h2{font-size:24px;font-weight:700;margin:44px 0 14px;color:var(--on-dark);letter-spacing:-.3px;
padding-top:28px;border-top:1px solid var(--hairline)}
.body h2:first-child{border-top:none;padding-top:0;margin-top:0}
.body h3{font-size:18px;font-weight:700;margin:26px 0 8px;color:var(--on-dark)}
.body h4{font-size:15px;font-weight:700;margin:22px 0 6px;color:var(--body-strong)}
.body p{margin:0 0 16px}
.body ul{padding-left:22px;margin:14px 0}
.body li{margin-bottom:10px}
.body strong{color:var(--on-dark);font-weight:700;background:none}
.body em{color:var(--body-strong);font-style:italic}
/* 개요 탭 */
.ov{font-weight:300;color:var(--body)}
.ov h2{font-size:26px;font-weight:700;margin:52px 0 6px;color:var(--on-dark);text-transform:uppercase;letter-spacing:-.3px;
padding-top:32px;border-top:1px solid var(--hairline)}
.ov h2:first-of-type{border-top:none;padding-top:0;margin-top:8px}
.ov .note-sub{color:var(--muted);font-size:12px;margin:0 0 20px;text-transform:uppercase;letter-spacing:1.5px;font-weight:700}
.ov h3{font-size:17px;font-weight:700;margin:22px 0 8px;color:var(--on-dark)}
.ov p{margin:0 0 16px}
.ov ul{padding-left:22px;margin:14px 0}.ov li{margin-bottom:10px}
.ov strong{color:var(--on-dark);font-weight:700}
.ov em{color:var(--body-strong);font-style:italic}
.lead{position:relative;font-size:18px;font-weight:300;line-height:1.55;color:var(--body-strong);
background:var(--surface-card);padding:26px 30px 26px 34px;margin:8px 0}
.lead::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
background:linear-gradient(180deg,#0066b1 0%,#1c69d4 50%,#e22718 100%)}
.lead strong{color:var(--on-dark);font-weight:700}
/* 파이프라인 (numbered square markers = engineered precision) */
.pipe{display:flex;flex-direction:column;margin:22px 0 6px}
.pstage{display:grid;grid-template-columns:44px 1fr;gap:20px;padding:22px 0;border-top:1px solid var(--hairline)}
.pstage:first-child{border-top:none}
.pnum{width:40px;height:40px;border-radius:0;background:var(--surface-elevated);color:var(--on-dark);display:flex;
align-items:center;justify-content:center;font-weight:700;font-size:16px;font-family:var(--mono)}
.pstage h4{margin:0 0 6px;font-size:17px;font-weight:700;color:var(--on-dark);text-transform:uppercase;letter-spacing:.3px}
.pstage p{margin:0;font-size:15px;font-weight:300;color:var(--body)}
.pstage .io{font-size:12px;color:var(--muted);font-family:var(--mono);margin-top:8px;letter-spacing:.3px}
/* 카드 그리드 */
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:1px;margin:20px 0;background:var(--hairline);border:1px solid var(--hairline)}
.card{background:var(--surface-card);border-radius:0;padding:24px}
.card h4{margin:0 0 8px;font-size:15px;font-weight:700;color:var(--on-dark);text-transform:uppercase;letter-spacing:.5px}
.card p{margin:0;font-size:14px;font-weight:300;color:var(--body)}
/* 한계 콜아웃 */
.callout{background:var(--surface-soft);border:1px solid var(--hairline);border-left:4px solid var(--warning);border-radius:0;
padding:22px 26px;margin:24px 0;font-size:14px;font-weight:300;color:var(--body)}
.callout strong{color:var(--warning);font-weight:700;text-transform:uppercase;letter-spacing:.5px;font-size:13px}
.callout ul{margin:12px 0 0;padding-left:20px}.callout li{margin-bottom:9px}
.callout li strong{color:var(--on-dark);text-transform:none;letter-spacing:0;font-size:inherit}
/* 환경 테이블 */
.envtable{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px}
.envtable td{padding:12px 16px;border-bottom:1px solid var(--hairline);vertical-align:top;font-weight:300;color:var(--body);background:var(--surface-soft)}
.envtable td:first-child{font-weight:700;color:var(--on-dark);width:30%;text-transform:uppercase;letter-spacing:.5px;font-size:12px}
.envtable .mono{font-family:var(--mono);font-size:13px}
footer{padding:40px 56px 64px;color:var(--muted);font-size:12px;font-weight:300;border-top:1px solid var(--hairline);background:var(--canvas);line-height:1.7}
@media(max-width:768px){
header.top,.tabbar,.panel,footer{padding-left:24px;padding-right:24px}
header.top h1{font-size:34px}.rtitle{font-size:28px}
.tabbar{gap:20px;overflow-x:auto}
.grid2{grid-template-columns:1fr}}
@media print{.tabbar,.mbar{display:none}.panel{display:block!important;page-break-before:always}
body,.page{background:#000}}
"""

OVERVIEW = """
<div class="ov">
  <p class="lead">
    본 프로젝트는 <strong>MiroFish</strong> — 오픈소스 멀티에이전트 AI 예측 엔진 — 을 이용해,
    하나의 문서(시드 자료)를 <strong>지식그래프 → 가상 이해관계자 에이전트 → 소셜 시뮬레이션</strong>으로
    전개하고, 그 안에서 형성된 담론을 근거로 <strong>이해관계자별 인식 변화 리포트</strong>를 도출한다.
    각 탭은 이 파이프라인으로 생성된 개별 리포트다.
  </p>

  <h2>1. 이 프로젝트는 무엇인가</h2>
  <p class="note-sub">요약이 아니라 “리허설”</p>
  <p>
    일반적인 LLM 문서 분석이 텍스트를 <em>요약·정리</em>하는 데 그친다면, 이 프로젝트는 문서에 등장하는
    이해관계자를 <strong>각각 독립된 에이전트로 되살려 서로 부딪히게 만든다.</strong> 경영진 에이전트는
    경영진의 관심사로, 규제기관 에이전트는 규제의 논리로 행동하며, 이들이 소셜 플랫폼에서 주고받는
    담론에서 원문에 명시되지 않았던 <strong>이해관계의 충돌과 반응 패턴</strong>이 드러난다.
    “디지털 샌드박스에서 미래를 미리 리허설”하는 것이 이 엔진의 목적이다.
  </p>

  <h2>2. 어떤 로직으로 구성되는가</h2>
  <p class="note-sub">세 개의 기술 축</p>
  <div class="grid2">
    <div class="card"><h4>① 지식그래프(GraphRAG)</h4>
      <p>문서를 개체·관계망으로 구조화해 에이전트의 공유 기억으로 삼는다. 에이전트는 이 그래프를
         근거로 발화하므로 서술이 원문에 정박된다.</p></div>
    <div class="card"><h4>② 멀티에이전트 시뮬레이션</h4>
      <p>OASIS 엔진 위에서 각 이해관계자가 고유 페르소나·기억·행동 논리를 갖고 Twitter·Reddit에서
         자율적으로 상호작용한다.</p></div>
    <div class="card"><h4>③ 근거 수집형 보고서(ReAct)</h4>
      <p>보고서 에이전트가 도구를 호출해 근거를 모으고 그 결과로 본문을 쓴다. 살아있는 시뮬레이션
         에이전트에게 직접 질문(인터뷰)할 수 있다.</p></div>
    <div class="card"><h4>로컬 실행(MiroFish-Ko)</h4>
      <p>한국어 환경 + 로컬 LLM(Ollama) 구동에 맞춘 구성. 외부 상용 API 없이 폐쇄망에서 전 과정
         수행이 가능하다.</p></div>
  </div>

  <h2>3. 절차와 방법</h2>
  <p class="note-sub">시드 문서에서 최종 리포트에 이르는 5단계 파이프라인</p>
  <div class="pipe">
    <div class="pstage"><div class="pnum">1</div><div>
      <h4>온톨로지 생성</h4>
      <p>LLM이 문서와 분석 요구사항을 읽고 이 도메인의 개체 유형·관계 유형을 설계한다.</p>
      <div class="io">입력: 문서 + 요구사항 → 출력: 개체/관계 유형 정의</div></div></div>
    <div class="pstage"><div class="pnum">2</div><div>
      <h4>지식그래프 구축</h4>
      <p>온톨로지를 적용해 문서를 그래프 DB에 적재. 실제 등장한 개체가 노드, 서술된 관계가 엣지가 된다.</p>
      <div class="io">입력: 문서 + 온톨로지 → 출력: 유형 라벨이 부여된 지식그래프</div></div></div>
    <div class="pstage"><div class="pnum">3</div><div>
      <h4>에이전트 준비</h4>
      <p>그래프에서 실제 행위자 노드만 선별(추상 개념은 제외)해 직무·관심사·성향을 담은 페르소나로 전환.</p>
      <div class="io">입력: 그래프 노드 → 출력: 에이전트 페르소나 + 행동 설정</div></div></div>
    <div class="pstage"><div class="pnum">4</div><div>
      <h4>소셜 시뮬레이션 실행</h4>
      <p>에이전트들이 두 플랫폼에 동시 참여해 매 라운드 게시·댓글·반응·무행동을 자율 선택한다.</p>
      <div class="io">입력: 에이전트 + 시드 게시물 → 출력: 라운드별 행동 로그</div></div></div>
    <div class="pstage"><div class="pnum">5</div><div>
      <h4>보고서 생성</h4>
      <p>보고서 에이전트가 목차를 기획하고, 섹션마다 도구로 근거를 모아 본문을 작성한다.</p>
      <div class="io">입력: 시뮬레이션 환경 + 그래프 → 출력: 섹션별 최종 리포트</div></div></div>
  </div>

  <h2>4. 결과는 어떻게 도출되는가</h2>
  <p class="note-sub">네 종류의 근거 수집 도구</p>
  <p>
    보고서의 각 섹션은 아래 도구들을 호출해 모은 근거 위에서 작성된다. <strong>그래프 기반 근거</strong>와
    <strong>시뮬레이션 내부 근거</strong>가 함께 반영되도록 설계되어 있다.
  </p>
  <ul>
    <li><strong>insight_forge</strong> — 그래프 전반을 종합해 특정 질문에 대한 심층 분석(사실·엔터티·관계)을 도출</li>
    <li><strong>panorama_search</strong> — 그래프 내 관련 노드·관계를 광범위하게 탐색</li>
    <li><strong>quick_search</strong> — 특정 사실을 좁은 범위로 신속 조회</li>
    <li><strong>interview_agents</strong> — <strong>실행 중인 시뮬레이션 에이전트에게 직접 질의</strong>해 응답을 수집(리포트의 인용문이 여기서 나온다)</li>
  </ul>

  <h2>5. 리포트 해석과 활용</h2>
  <p class="note-sub">무엇으로 읽고, 어디에 쓰는가</p>
  <p>
    각 리포트는 <strong>“입력 문서의 함의를 이해관계자 관점으로 전개한 해석”</strong>이다.
    시장을 실측한 값이 아니라, 문서가 내포한 쟁점을 에이전트 상호작용으로 드러낸 결과물로 읽어야 한다.
    본문의 큰따옴표 인용은 <strong>시뮬레이션 에이전트의 발화</strong>이며 실존 인물의 발언이 아니다.
  </p>
  <div class="callout">
    <strong>해석 시 반드시 전제할 한계</strong>
    <ul>
      <li><strong>근거의 원천</strong> — 입력 문서 1건과 그로부터 생성된 에이전트 발화에 기반한다. 외부 실측 데이터·통계는 포함되지 않는다.</li>
      <li><strong>시뮬레이션 규모</strong> — 관측 규모가 제한적이며, 장기 여론 역학보다는 초기 쟁점 도출에 적합하다.</li>
      <li><strong>모델 규모</strong> — 경량 로컬 모델(CPU)을 사용해, 상위 모델로 재실행하면 결론의 정밀도가 달라질 수 있다.</li>
      <li><strong>문서 의존성</strong> — 입력 문서에 등장하지 않는 이해관계자·쟁점은 구조적으로 결과에 반영되지 않는다.</li>
    </ul>
  </div>
  <p>
    따라서 리포트는 <strong>의사결정의 단독 근거가 아니라, 쟁점 도출·가설 수립·논의의 출발점</strong>으로
    활용하는 것이 적절하다. 실제 전략 수립에는 시장 데이터와 실인물 검증을 병행할 것을 권장한다.
    활용 예: ① 특정 문서·정책이 이해관계자별로 어떤 반응을 부를지 사전 점검, ② 간과된 쟁점·충돌 지점
    발굴, ③ 대응 논리·예상 질의 준비.
  </p>

  <h2>6. 수행 환경</h2>
  <p class="note-sub">결과 해석 시 함께 고려할 실행 조건</p>
  <table class="envtable">
    <tr><td>언어모델</td><td class="mono">gemma4:e4b (8.0B, Q4_K_M)</td></tr>
    <tr><td>실행 방식</td><td>로컬 Ollama — 외부 API 미사용, 전 과정 로컬 처리(대외비 문서 적용 가능)</td></tr>
    <tr><td>컨텍스트 창</td><td class="mono">16,384 토큰</td></tr>
    <tr><td>연산 장치</td><td>CPU (GPU 미사용)</td></tr>
    <tr><td>적용 범위</td><td>온톨로지·페르소나·시뮬레이션·보고서 전 단계 동일 모델</td></tr>
    <tr><td>기반 기술</td><td>MiroFish(github.com/666ghj/MiroFish, Shanda Group 지원) · 시뮬레이션 엔진 OASIS by CAMEL-AI · 지식계층 GraphRAG(Zep)</td></tr>
  </table>
</div>
"""

JS = """
(function(){
  var tabs=document.querySelectorAll('.tab');
  var panels=document.querySelectorAll('.panel');
  function show(id){
    tabs.forEach(function(t){t.classList.toggle('active',t.dataset.target===id)});
    panels.forEach(function(p){p.classList.toggle('active',p.id===id)});
    if(history.replaceState)history.replaceState(null,'','#'+id);
  }
  tabs.forEach(function(t){t.addEventListener('click',function(){show(t.dataset.target)})});
  var init=(location.hash||'').replace('#','');
  if(init&&document.getElementById(init))show(init);
})();
"""


def build(reports):
    # 첫 탭은 항상 프로젝트 개요, 이후 최신순 리포트 탭
    tabs = ['<button class="tab active" data-target="overview">'
            '프로젝트 개요<span class="d">방법론 · 해석 · 활용</span></button>']
    panels = [f'<div class="panel active" id="overview">{OVERVIEW}</div>']

    if not reports:
        panels.append('<div class="panel"><p>아직 완료된 리포트가 없습니다. '
                      '리포트 생성 후 <code>python build_report_index.py</code>를 다시 실행하세요.</p></div>')
    else:
        for r in reports:
            tabs.append(
                f'<button class="tab" data-target="{r["id"]}">'
                f'{html.escape(r["title"][:24])}{"…" if len(r["title"])>24 else ""}'
                f'<span class="d">{r["date"]}</span></button>'
            )
            chips = [
                f'<span class="chip">{r["date"]}</span>',
                f'<span class="chip">{r["sections"]}개 섹션</span>',
                f'<span class="chip">{r["size"]:,}B</span>',
                f'<span class="chip">{html.escape(r["id"])}</span>',
            ]
            if r["sim"]:
                chips.append(f'<span class="chip">{html.escape(r["sim"])}</span>')
            if r["truncated"]:
                chips.append('<span class="chip warn">일부 섹션 잘림</span>')
            panels.append(
                f'<div class="panel" id="{r["id"]}">'
                f'<h2 class="rtitle">{html.escape(r["title"])}</h2>'
                f'<div class="rmeta">{"".join(chips)}</div>'
                f'<div class="body">{r["body"]}</div></div>'
            )

    tabs = "\n".join(tabs)
    body = "\n".join(panels)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>멀티에이전트 시뮬레이션 분석 — 개요 및 리포트 (MiroFish)</title>
<style>{CSS}</style></head><body>
<div class="page">
<div class="mbar"></div>
<header class="top">
  <div class="eyebrow">Multi-Agent Simulation · MiroFish</div>
  <h1>멀티에이전트 시뮬레이션 분석<br>개요 및 리포트</h1>
  <p>프로젝트 개요·방법론과, 파이프라인으로 생성된 개별 분석 리포트를 탭에서 선택해 봅니다.</p>
  <div class="count">개요 1 · 리포트 {len(reports)}건 · 최신순 · 갱신 {now}</div>
</header>
<div class="tabbar">{tabs}</div>
{body}
<footer>MiroFish — 멀티에이전트 AI 예측 엔진 · 각 탭은 개별 시뮬레이션 리포트 본문입니다.
본 결과는 LLM 에이전트 시뮬레이션 산출물로, 실제 기업·인물의 발언이나 공식 입장이 아닙니다.</footer>
</div>
<script>{JS}</script>
</body></html>"""


if __name__ == "__main__":
    reports = collect()
    open(OUT, "w", encoding="utf-8", newline="\n").write(build(reports))
    print(f"index 생성: {OUT}")
    print(f"포함 리포트 {len(reports)}건:")
    for r in reports:
        print(f"  - [{r['date']}] {r['title']}  ({r['size']:,}B, {r['id']})")
