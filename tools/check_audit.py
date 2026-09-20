#!/usr/bin/env python3
"""Run the offline verification gate and record actual exit codes/test counts.

Does not regenerate primary evidence, call a paid LLM or claim a GitHub CI run.
PDF generation is separate: tools/reproduce_audit.py --with-pdf.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def main():
    commands=[
        ("pytest",["-m","pytest","-q","--junitxml=results/pytest.xml"]),
        ("free-experiments",["run_all.py"]),
        ("memo-browser",["tools/browser_ac.py","memo","--out","results/browser_memo.json"]),
        ("cafe-browser",["tools/browser_ac.py","cafe","--out","results/browser_cafe.json"]),
        ("cafe-full-ac",["demo/vibe_vs_spec/verify_ac.py"]),
        *[("analysis-"+name,["analysis/"+name+".py"]) for name in (
            "calibrate_growth","lean_vs_full","replay_logs","ab_efficacy","ab_value","case_ac_gap","ladder_keep_or_kill")],
        ("all-decks",["tools/verify_deck.py","--with-pdf","--json","results/deck_checks.json"]),
        ("case-deck",["presentation/case_vibe_vs_spec/verify_case.py","--with-pdf"]),
    ]
    logs=ROOT/"results/audit_checks"
    logs.mkdir(parents=True,exist_ok=True)
    records=[]
    for name,args in commands:
        start=time.monotonic()
        p=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True,timeout=240)
        path=logs/(name+".txt")
        path.write_text("\n".join(line.rstrip() for line in (p.stdout+p.stderr).splitlines()).rstrip()+"\n",encoding="utf-8")
        record=dict(name=name,command=["python",*args],exit_code=p.returncode,
                    seconds=round(time.monotonic()-start,3),log=str(path.relative_to(ROOT)))
        records.append(record)
        print(f"{'PASS' if p.returncode==0 else 'FAIL'} {name} (exit {p.returncode})",flush=True)
        if p.returncode: print((p.stdout+p.stderr)[-4000:])
    tree=ET.parse(ROOT/"results/pytest.xml")
    suites=tree.findall('.//testsuite')
    counts={k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','failures','errors','skipped')}
    counts['passed']=counts['tests']-counts['failures']-counts['errors']-counts['skipped']
    artifacts=[*sorted((ROOT/"presentation").glob('*.pptx')),*sorted((ROOT/"presentation").glob('*.pdf')),
               *sorted((ROOT/"presentation/case_vibe_vs_spec").glob('*.pptx')),
               *sorted((ROOT/"presentation/case_vibe_vs_spec").glob('*.pdf')),
               ROOT/"results/audit_metrics.json",ROOT/"LIVE_RESULTS.md",ROOT/"docs/CORRECTIONS.md",
               ROOT/"docs/REASSERTED.md"]
    on_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    result=dict(evidence_type="software_verification",execution_environment="GitHub Actions" if on_actions else "local workspace",audit_date="2026-09-20",timezone="Asia/Seoul",
                python=platform.python_version(),new_paid_api_calls=0,log_normalization="trailing whitespace only",
                all_executed_checks_passed=all(r['exit_code']==0 for r in records),
                pytest=counts,commands=records,
                artifact_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts},
                not_run=["new paid vendor API requests", "real policy A/B or quality-equivalence trial",
                         "invoice comparison", "IDE GUI and physical presentation-device checks",
                         "MCP SDK/Inspector/config clients (raw protocol subprocess test was run)"] +
                        ([] if on_actions else ["GitHub Actions remote run (workflow added; these results are local)"]))
    (ROOT/"results/verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding="utf-8")
    return 0 if result['all_executed_checks_passed'] else 1


if __name__ == '__main__': sys.exit(main())
