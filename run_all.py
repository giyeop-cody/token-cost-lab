# -*- coding: utf-8 -*-
"""
전체 실험을 순서대로 실행한다.

  python run_all.py                 # 전부 실행 (과금 없음)
  python run_all.py --model opus    # 다른 모델 단가로
  python run_all.py --live          # exp08·exp10·exp11-B 를 실제 API 로 호출 (과금됨)
  python run_all.py > report.txt    # 결과를 파일로

exp08/10/11 의 라이브 모드는 각각 API 키가 필요합니다. 기본값은
dry-run(구조만) 또는 시뮬레이션으로 실행되므로 전체 실행은 여전히 무료입니다.
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, "experiments")

ORDER = [
    ("exp01_tokenizer_ko_en.py", "한국어 vs 영어 토큰 수", False),
    ("exp02_output_to_input.py", "출력→입력 환전", True),
    ("exp03_prompt_caching.py", "프롬프트 캐싱", True),
    ("exp04_agent_loop_sdd.py", "에이전트 루프와 SDD", True),
    ("exp05_verbosity_effort.py", "장황함과 추론 강도", True),
    ("exp06_other_levers.py", "그 밖의 절감 레버들", True),
    ("exp07_analyze_my_prompt.py", "내 프롬프트 진단기 (데모)", True),
    ("exp08_gemini_live.py", "Gemini 실시간 토큰 측정", False),
    ("exp09_dry.py", "DRY를 토큰 경제로 번역하면", True),
    ("exp10_thinking_cross_vendor.py", "사고 토큰·과금 벤더 횡단", False),
    ("exp11_tool_output_bloat.py", "툴 출력의 컨텍스트 팽창", True),
]

LIVE_KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY",
             "ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--only", help="특정 실험만 (예: 03)")
    ap.add_argument("--live", action="store_true",
                    help="exp08/10/11을 실제 API로 호출한다 (과금 발생, "
                         "GEMINI_API_KEY 필요)")
    args = ap.parse_args()

    failed, skipped, selected = [], [], 0
    for fname, label, takes_model in ORDER:
        if args.only and args.only not in fname:
            continue
        selected += 1
        cmd = [sys.executable, os.path.join(EXP, fname)]
        if takes_model:
            cmd += ["--model", args.model]
        if fname.startswith("exp07"):
            cmd += ["--demo"]
        if fname.startswith("exp08"):
            if args.live:
                if not (os.environ.get("GEMINI_API_KEY")
                        or os.environ.get("GOOGLE_API_KEY")):
                    print("\n  [건너뜀] exp08 --live 에는 GEMINI_API_KEY 가 필요합니다.\n")
                    skipped.append(label)
                    continue
            else:
                cmd += ["--dry-run"]
        if fname.startswith("exp10"):
            if args.live:
                if not any(os.environ.get(k) for k in LIVE_KEYS):
                    print("\n  [건너뜀] exp10 --live 에는 벤더 키(최소 1개)가 필요합니다.\n")
                    skipped.append(label)
                    continue
                cmd += ["--vendor", "all"]
            else:
                cmd += ["--dry-run"]
        if fname.startswith("exp11") and args.live:
            if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
                cmd += ["--live"]
            else:
                print("[미검증] exp11 live 키 없음 — 시뮬레이션만 실행")
                skipped.append(label + " live")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            failed.append(label)

    print()
    print("=" * 88)
    if not selected:
        print("선택된 실험 없음")
        return 2
    if failed:
        print("  실패한 실험:", ", ".join(failed))
        return 1
    if skipped:
        print("  미검증/생략:", ", ".join(skipped))
        return 2
    print("  선택한 실행 모드 완료. 기본 모드는 API 효과 검증이 아닙니다.")
    print("  숫자를 그대로 믿지 말고, 자기 팀 usage 로그로 파라미터를 바꿔 다시 돌리세요.")
    print("  예:  python experiments/exp02_output_to_input.py --model opus --devs 25")
    print()
    print("  새 API usage와 단가 환산을 보고 싶다면 (API 키 필요):")
    print("    export GEMINI_API_KEY=\"...\"")
    print("    python experiments/exp08_gemini_live.py --count-only   # 과금 없음")
    print("    python experiments/exp08_gemini_live.py --thinking     # 사고 토큰 관측")
    print("    python experiments/exp10_thinking_cross_vendor.py      # 3벤더 사고 토큰 대조")
    print("    python experiments/exp11_tool_output_bloat.py --live   # 3요청의 usage 관측")
    print("=" * 88)


if __name__ == "__main__":
    sys.exit(main())
