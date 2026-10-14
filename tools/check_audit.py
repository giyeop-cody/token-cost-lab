#!/usr/bin/env python3
"""Run the offline verification gate and record actual exit codes/test counts.

Does not regenerate primary evidence, call a paid LLM or claim a GitHub CI run.
PDF generation is separate: tools/reproduce_audit.py --with-pdf.
"""
import hashlib
import argparse
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]


def run_check(name, args, logs, timeout=240):
    """Record setup failures/timeouts and keep running independent checks."""
    start=time.monotonic()
    try:
        p=subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True,timeout=timeout)
        code, output, status=p.returncode, p.stdout+p.stderr, "completed"
    except subprocess.TimeoutExpired as exc:
        def decoded(value):
            return value.decode(errors="replace") if isinstance(value,bytes) else (value or "")
        code, status=124, "timeout"
        output=decoded(exc.stdout)+decoded(exc.stderr)+f"\nUNVERIFIED: timeout after {timeout}s\n"
    except OSError as exc:
        code, status=126, "setup_error"
        output=f"UNVERIFIED: {type(exc).__name__}: {exc}\n"
    path=logs/(name+".txt")
    path.write_text("\n".join(line.rstrip() for line in output.splitlines()).rstrip()+"\n",encoding="utf-8")
    record=dict(name=name,command=["python",*map(str,args)],exit_code=code,status=status,
                seconds=round(time.monotonic()-start,3),log=os.path.relpath(path,ROOT))
    print(f"{'PASS' if code==0 else 'FAIL'} {name} (exit {code})",flush=True)
    if code: print(output[-4000:])
    return record


def pytest_counts(path, executed):
    # Never read a stale XML from a previous run when pytest did not create one.
    if not executed or not path.exists():
        return None
    try:
        tree=ET.parse(path)
        suites=tree.findall('.//testsuite')
        if tree.getroot().tag == 'testsuite': suites=[tree.getroot()]
        if not suites: return None
        counts={k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','failures','errors','skipped')}
        counts['passed']=counts['tests']-counts['failures']-counts['errors']-counts['skipped']
        return counts
    except (ET.ParseError, ValueError):
        return None


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out-dir',type=Path,default=ROOT/'results',help='separate verification outputs from published evidence')
    args=ap.parse_args()
    output=args.out_dir.resolve()
    output.mkdir(parents=True,exist_ok=True)
    xml=output/'pytest.xml'
    xml.unlink(missing_ok=True)
    started=datetime.now(ZoneInfo('Asia/Seoul'))
    commands=[
        ("pytest",["-m","pytest","-q",f"--junitxml={xml}"]),
        ("free-experiments",["run_all.py"]),
        ("memo-browser",["tools/browser_ac.py","memo","--out",str(output/'browser_memo.json')]),
        ("cafe-browser",["tools/browser_ac.py","cafe","--out",str(output/'browser_cafe.json')]),
        ("cafe-full-ac",["demo/vibe_vs_spec/verify_ac.py"]),
        *[("analysis-"+name,["analysis/"+name+".py"]) for name in (
            "calibrate_growth","lean_vs_full","replay_logs","ab_efficacy","ab_value","case_ac_gap","ladder_keep_or_kill")],
        ("all-decks",["tools/verify_deck.py","--with-pdf","--json",str(output/'deck_checks.json')]),
        ("case-deck",["presentation/case_vibe_vs_spec/verify_case.py","--with-pdf"]),
    ]
    logs=output/"audit_checks"
    logs.mkdir(parents=True,exist_ok=True)
    records=[run_check(name,cmd,logs) for name,cmd in commands]
    counts=pytest_counts(xml,records[0]['status']=='completed')
    artifacts=[*sorted((ROOT/"presentation").glob('*.pptx')),*sorted((ROOT/"presentation").glob('*.pdf')),
               *sorted((ROOT/"presentation/case_vibe_vs_spec").glob('*.pptx')),
               *sorted((ROOT/"presentation/case_vibe_vs_spec").glob('*.pdf')),
               ROOT/"results/audit_metrics.json",ROOT/"LIVE_RESULTS.md",ROOT/"docs/CORRECTIONS.md",
               ROOT/"docs/REASSERTED.md",ROOT/"docs/RETIRED.md"]
    on_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    packages={}
    for package in ('pytest','tiktoken','scipy','playwright','python-pptx','pymupdf'):
        try: packages[package]=version(package)
        except PackageNotFoundError: packages[package]=None
    result=dict(evidence_type="software_verification",execution_environment="GitHub Actions" if on_actions else "local workspace",audit_date=started.date().isoformat(),started_at=started.isoformat(),timezone="Asia/Seoul",
                evidence_snapshot_date="2026-09-20",dependencies=packages,
                python=platform.python_version(),new_paid_api_calls=0,log_normalization="trailing whitespace only",
                all_executed_checks_passed=all(r['exit_code']==0 for r in records) and counts is not None,
                pytest=counts,commands=records,
                artifact_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts},
                not_run=["new paid vendor API requests", "real policy A/B or quality-equivalence trial",
                         "invoice comparison", "IDE GUI and physical presentation-device checks",
                         "MCP SDK/Inspector/config clients (raw protocol subprocess test was run)"] +
                        ([] if on_actions else ["GitHub Actions remote run (workflow added; these results are local)"]))
    (output/"verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding="utf-8")
    return 0 if result['all_executed_checks_passed'] else 1


if __name__ == '__main__': sys.exit(main())
