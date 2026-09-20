# -*- coding: utf-8 -*-
"""문서 주장과 스크립트 출력·파일 참조의 정합 검사.

손으로 쓴 문서의 숫자는 원자료가 바뀌면 조용히 낡는다(2026-09-20 감사에서 확인된 유형).
여기서 막는 것은 세 가지다.

  1. `analysis/lean_vs_full.py`가 출력하는 값과 AGENTS.md·CORRECTIONS.md 표기 불일치
  2. 백틱으로 가리킨 저장소 파일이 실제로 없는 참조(유령 경로)
  3. 인코딩 깨짐(U+FFFD)·한국어 문서 안의 한자 혼입

검사는 실제 파일 내용을 읽는다. 통과했다고 외부 사실이 참이라는 뜻은 아니다.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEXT_EXT = {".md", ".py", ".json", ".jsonl", ".txt", ".sh", ".html"}
ARCHIVE = ("presentation/archive/", "docs/archive/")
# 저장소 안에 없는 것이 정상인 표기:
#   devtest/* 는 FLORES-200 상류 배포 구조를 그대로 적은 경로,
#   site/index.html 은 2026-08-15 세션 당시 경로(현재는 artifacts/index_vibe.html)
DOC_ALLOW = {"devtest/eng_Latn.devtest", "devtest/kor_Hang.devtest", "site/index.html"}


def documents():
    for path in sorted(ROOT.glob("**/*")):
        if not path.is_file() or path.suffix not in TEXT_EXT:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(rel.startswith(a) for a in ARCHIVE) or "/.git/" in rel:
            continue
        yield rel, path


def lean_vs_full_output():
    proc = subprocess.run([sys.executable, "analysis/lean_vs_full.py"], cwd=ROOT,
                          capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


@pytest.fixture(scope="module")
def lean_output():
    return lean_vs_full_output()


def test_agents_md_short_rework_percentages_match_script(lean_output):
    found = {m.group(1): m.group(2) for m in re.finditer(
        r"(\d)턴: 제자리 \$[\d.]+ → 사다리 \$[\d.]+  이득 (\d+)%", lean_output)}
    assert found.get("1") and found.get("2"), lean_output
    text = (ROOT / "agent_setup/antigravity/AGENTS.md").read_text(encoding="utf-8")
    assert f"1턴 {found['1']}%" in text, f"AGENTS.md의 1턴 표기가 스크립트({found['1']}%)와 다름"
    assert f"2턴 {found['2']}%" in text, f"AGENTS.md의 2턴 표기가 스크립트({found['2']}%)와 다름"


def test_lean_replay_ratio_in_corrections_matches_script(lean_output):
    m = re.search(r"축소가 \$[\d.]+ 낮음 \(([\d.]+)배 비용비\)", lean_output)
    assert m, lean_output
    correction = (ROOT / "docs/CORRECTIONS.md").read_text(encoding="utf-8")
    heading = [line for line in correction.splitlines() if line.startswith("| 사다리 3.06배")]
    assert heading, "CORRECTIONS.md에 사다리 3.06배 행이 없음"
    assert f"{m.group(1)}배" in heading[0], f"현재 재생값 {m.group(1)}배가 표에 없음: {heading[0]}"


def test_reasserted_doc_matches_generator(evidence):
    """docs/REASSERTED.md는 생성기 출력이어야 한다(손으로 옮겨 적은 숫자 금지)."""
    from tools.render_reports import reassertion_report
    on_disk = (ROOT / "docs/REASSERTED.md").read_text(encoding="utf-8")
    generated = reassertion_report(evidence)
    assert generated == on_disk, "docs/REASSERTED.md가 생성기 출력과 다름(수기 수정 여부 확인)"
    for heading in ("## 1. 다시 쓸 수 있는 절감 문장", "## 2. 근거를 새로 붙인 것",
                    "## 3. 다시 쓰지 않는 것", "## 4. 발표용 문장 형식"):
        assert heading in on_disk, heading


def test_retired_claim_tokens_do_not_reappear():
    """docs/RETIRED.md §E의 금지 표기가 현행 주장 표면에 다시 나타나지 않는지 검사.

    근거 없이 부활한 옛 수치(검증 건수, 라우팅 절감률, 미측정 비중 등)를 잡는다.
    목록의 단일 출처는 문서다. 값을 되살리려면 새 근거와 함께 문서를 고쳐야 한다.
    """
    doc = (ROOT / "docs/RETIRED.md").read_text(encoding="utf-8")
    block = re.search(r"```text\n(.*?)```", doc, re.S)
    assert block, "RETIRED.md에서 금지 표기 코드블록을 찾지 못함"
    tokens = block.group(1).split()
    assert len(tokens) >= 30, tokens
    skip = {"docs/RETIRED.md", "docs/CORRECTIONS.md", "docs/REASSERTED.md"}
    bad = []
    for rel, path in documents():
        if path.suffix in {".txt", ".html"} or rel.startswith(("results/", "tests/", "data/")) or rel in skip:
            continue
        text = path.read_text(encoding="utf-8")
        for t in tokens:
            if t in text:
                bad.append(f"{rel}: {t}")
    assert not bad, bad


def test_no_replacement_characters_or_stray_cjk():
    """손으로 쓴 문서·코드의 인코딩 깨짐/한자 혼입 검사.

    `results/` 아래 실행 로그는 이 검사 자신의 실패 메시지를 다시 담을 수 있어 제외한다.
    """
    bad = []
    for rel, path in documents():
        if rel.startswith("results/") or path.suffix not in {".md", ".py", ".sh"}:
            continue
        text = path.read_text(encoding="utf-8")
        if "\ufffd" in text:
            bad.append(f"{rel}: U+FFFD")
        for ch in text:
            if 0x4E00 <= ord(ch) <= 0x9FFF:
                bad.append(f"{rel}: 한자 {ch}")
                break
    assert not bad, bad


def test_backticked_repository_paths_exist():
    suffix = re.compile(r"\.(py|md|json|jsonl|sh|html|pptx|pdf|png|txt|csv)$")
    missing = []
    for rel, path in documents():
        if path.suffix != ".md":
            continue
        for m in re.finditer(r"`([^`\n]+)`", path.read_text(encoding="utf-8")):
            cand = m.group(1).strip()
            if (not suffix.search(cand) or "/" not in cand or " " in cand
                    or cand.startswith(("http", "python", "pip", "git"))
                    or cand in DOC_ALLOW):
                continue
            if "*" in cand:  # `demo/results*.json`처럼 묶어 가리키는 표기
                if list(ROOT.glob(cand)) or list(path.parent.glob(cand)):
                    continue
                missing.append(f"{rel}: {cand} (glob 불일치)")
                continue
            if (ROOT / cand).exists() or (path.parent / cand).exists():
                continue
            missing.append(f"{rel}: {cand}")
    assert not missing, missing
