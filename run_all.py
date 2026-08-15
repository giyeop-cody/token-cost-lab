# -*- coding: utf-8 -*-
"""
전체 실험을 순서대로 실행한다.

  python run_all.py                 # 전부 실행 (과금 없음)
  python run_all.py --model opus    # 다른 모델 단가로
  python run_all.py --live          # exp08 을 실제 Gemini API 로 호출 (과금됨)
  python run_all.py > report.txt    # 결과를 파일로

exp08 은 실제 API 키가 필요합니다. 기본값은 --dry-run 으로 구조만 출력하므로
전체 실행은 여전히 무료입니다.
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
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--only", help="특정 실험만 (예: 03)")
    ap.add_argument("--live", action="store_true",
                    help="exp08 을 실제 Gemini API 로 호출한다 (과금 발생, "
                         "GEMINI_API_KEY 필요)")
    args = ap.parse_args()

    failed = []
    for fname, label, takes_model in ORDER:
        if args.only and args.only not in fname:
            continue
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
                    continue
            else:
                cmd += ["--dry-run"]
        r = subprocess.run(cmd)
        if r.returncode != 0:
            failed.append(label)

    print()
    print("=" * 88)
    if failed:
        print("  실패한 실험:", ", ".join(failed))
        sys.exit(1)
    print("  모든 실험 완료.")
    print("  숫자를 그대로 믿지 말고, 자기 팀 usage 로그로 파라미터를 바꿔 다시 돌리세요.")
    print("  예:  python experiments/exp02_output_to_input.py --model opus --devs 25")
    print()
    print("  실제 과금 값을 보고 싶다면 (Gemini API 키 필요):")
    print("    export GEMINI_API_KEY=\"...\"")
    print("    python experiments/exp08_gemini_live.py --count-only   # 과금 없음")
    print("    python experiments/exp08_gemini_live.py --thinking     # 사고 토큰 관측")
    print("=" * 88)


if __name__ == "__main__":
    main()
