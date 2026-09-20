#!/usr/bin/env python3
"""Recompute derived evidence/reports/decks without paid API calls.

Original 110 rows and FLORES source files are hash-checked before running.
--with-pdf needs LibreOffice + NanumGothic. This script writes generated outputs;
it does not manufacture missing live data, run a policy A/B or push to GitHub.
"""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lab.evidence import save, verify_sources
from tools.render_reports import write_reports
from tools.render_demo import render_demo
from presentation.deckgen.build_verified import build_all


def run(args, log=None):
    print('+', ' '.join(args),flush=True)
    result=subprocess.run([sys.executable,*args],cwd=ROOT,text=True,capture_output=True,timeout=180)
    if log:
        (ROOT/log).write_text(result.stdout,encoding="utf-8")
    if result.returncode:
        print(result.stdout+result.stderr,file=sys.stderr)
        raise SystemExit(result.returncode)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--with-pdf',action='store_true')
    args=ap.parse_args()
    verify_sources()
    run(['tools/parallel_tokenizer_bench.py'])
    run(['tools/stats_test.py','results/live_lang_thinking.jsonl'],'results/stats_thinking.txt')
    run(['tools/stats_test.py','results/live_lang_thinking.jsonl','--price-basis','legacy'],'results/stats_thinking_legacy.txt')
    run(['tools/thinking_sweep.py','--summarize','results/thinking_sweep.jsonl'],'results/sweep_summary.txt')
    run(['demo/compare_personas.py','--scenario','legacy','--write-results','demo/results.json'])
    run(['demo/compare_personas.py','--write-results','demo/results_current.json'])
    run(['analysis/calibrate_growth.py'])
    run(['demo/vibe_vs_spec/sensitivity.py'])
    e=save()
    write_reports(e)
    (ROOT/'demo/compare.html').write_text(render_demo(),encoding='utf-8')
    build_all(evidence=e)
    if args.with_pdf:
        run(['presentation/deckgen/make_pdf.py','--check'])
    else:
        print('PDFs were NOT regenerated. If slide content changed, run with --with-pdf before publication.')
    print('Derived artifacts regenerated. Run pytest and verify_deck.py --with-pdf; regeneration alone is not a test PASS.')


if __name__ == '__main__': main()
