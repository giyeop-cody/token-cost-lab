"""Self-contained persona scenario viewer (no network, no model calls)."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def render_demo():
    data={key:json.loads((ROOT/path).read_text()) for key,path in (
        ("current","demo/results_current.json"),("legacy","demo/results.json"))}
    payload=json.dumps(data,ensure_ascii=False).replace("</", "<\\/")
    return '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>같은 목표, 두 가지 습관 — 비용 시나리오</title>
<style>*{box-sizing:border-box}body{margin:0;background:#0e141b;color:#edf3fa;font:16px/1.7 system-ui,sans-serif}main{max-width:1050px;margin:auto;padding:56px 24px}h1{font-size:clamp(28px,5vw,46px);line-height:1.2;margin:12px 0 24px}h2{font-size:22px}.eyebrow{color:#36d399;letter-spacing:.12em;font-size:12px}p{color:#a9b9c9}.note{border-left:3px solid #36d399;background:#16232c;padding:18px 24px;margin:24px 0}.row{display:grid;grid-template-columns:1fr 1fr;gap:20px}.card{border:1px solid #2e414f;border-radius:14px;padding:28px;background:#14202a}.amount{font-size:38px;font-weight:750;line-height:1.3}.red{color:#fb8595}.green{color:#36d399}.hero{font-size:60px;font-weight:800;color:#36d399;line-height:1.3}button{font:inherit;background:#1b2a36;border:1px solid #425666;color:#edf3fa;padding:10px 16px;border-radius:8px;cursor:pointer;margin:4px}button[aria-pressed=true]{background:#36d399;color:#0e141b;border-color:#36d399}table{border-collapse:collapse;width:100%}td,th{padding:13px 8px;text-align:right;border-bottom:1px solid #293946}td:first-child,th:first-child{text-align:left}code{color:#36d399}small{color:#90a5b7}@media(max-width:700px){.row{grid-template-columns:1fr}.hero{font-size:48px}main{padding:32px 16px}.card{padding:22px}}</style>
<main><div class="eyebrow">TOKEN COST LAB / COST SCENARIO / 2026-09-20</div>
<h1>같은 목표 결과물.<br>다른 습관의 비용 모형.</h1>
<p>메모장 한 개를 목표로, 턴 수·출력량·사고량·캐시 조건을 다르게 가정합니다.<br>실제 품질 동등 정책 A/B나 모델의 새 실측 결과가 아닙니다.</p>
<button id="current" aria-pressed="true" onclick="show('current')">수정 기본 가정</button><button id="legacy" aria-pressed="false" onclick="show('legacy')">기존 20.8배 재현</button>
<div class="note"><div class="hero" id="ratio">19.0×</div><div id="condition"></div></div>
<div class="row"><section class="card"><small>A / 김낭비 · 6턴 가정</small><h2>재작업·전체 재출력</h2><div class="amount red" id="a"></div><p>일부 인코딩 + 확대 출력 2.9배와 사고량 가정. 캐시 쓰기를 시도하지만 선두 동적값으로 매번 미스인 조건.</p></section>
<section class="card"><small>B / 박절약 · 2턴 가정</small><h2>결정된 스펙·짧은 수정</h2><div class="amount green" id="b"></div><p>memo.html 인코딩과 작은 패치. 사고 effort 승수 0.35는 가정이지 벤더가 보장한 절감률이 아닙니다.</p></section></div>
<h2>같은 산식으로 비교</h2><table><thead><tr><th>시나리오 토큰</th><th>A</th><th>B</th></tr></thead><tbody id="rows"></tbody></table>
<p id="price"></p>
<div class="note"><b>기존 20.8배를 지우지 않았습니다.</b><br>다만 한국어 hidden 사고 승수 1.44와 최소 길이를 무시한 캐시 가정을 포함한 역사적 계산입니다. 기본 가정은 사고 승수 1.0, 최소 길이 미달 캐시는 미적용합니다. 두 경우 모두 6→2턴 감소와 품질 동등성을 관측한 것은 아닙니다.</div>
<h2>해석의 경계</h2><ul><li>동일한 목표 파일을 둔 것이 실제 두 세션의 성공·품질 동등성 증명은 아닙니다.</li><li>입력·출력 전부가 실측인 것은 아닙니다. 확대 출력과 설명량, hidden 사고량은 가정입니다.</li><li>A는 전체 이력 끝에 쓰기 지점을 두고 매번 미스, B는 짧은 시스템 프리픽스만 표시한다는 가정입니다. 실제 캐시 usage 기록은 없습니다.</li><li>연간 환산이나 단일 레버의 인과 효과를 실제 절감 성과로 주장하지 않습니다.</li></ul>
<h2>재현</h2><p><code>python demo/compare_personas.py</code><br><code>python demo/compare_personas.py --scenario legacy</code></p><small>근거: demo/results_current.json · demo/results.json · lab/pricing.py<br>상세: docs/CORRECTIONS.md · 원본 목표 파일 demo/memo.html</small></main>
<script>const data=PAYLOAD;function show(key){const d=data[key];document.getElementById('ratio').textContent=d.ratio+'×';document.getElementById('condition').textContent=key==='legacy'?'기존 환산 가정 · 사고 언어 승수 1.44 · 캐시 최소 길이 무시':'수정 기본 가정 · 사고 언어 승수 1.0 · 모델별 캐시 최소 길이 적용';document.getElementById('a').textContent='$'+d.A.cost.toFixed(5);document.getElementById('b').textContent='$'+d.B.cost.toFixed(5);document.getElementById('price').textContent=d.price_model+' · 입력 $'+d.price_input+' / 출력 $'+d.price_output+' per 1M · 리스트 단가 시나리오, 실제 청구서 아님';const rows=document.getElementById('rows');rows.replaceChildren();for(const [label,k] of [['전체 입력','in'],['보이는 출력','out'],['가정한 사고','think']]){const tr=document.createElement('tr');for(const v of [label,Math.round(d.A[k]).toLocaleString(),Math.round(d.B[k]).toLocaleString()]){const td=document.createElement('td');td.textContent=v;tr.appendChild(td)}rows.appendChild(tr)}for(const k of ['current','legacy'])document.getElementById(k).setAttribute('aria-pressed',k===key?'true':'false')}show('current');</script></html>'''.replace('PAYLOAD',payload)


if __name__ == "__main__":
    (ROOT/"demo/compare.html").write_text(render_demo(),encoding="utf-8")
