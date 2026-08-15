# -*- coding: utf-8 -*-
"""콘솔 출력 헬퍼 — 실험 결과를 표로 예쁘게 찍는다. 외부 의존성 없음."""

import shutil
import unicodedata


def _w(s: str) -> int:
    """동아시아 전각 문자를 2칸으로 세는 표시 폭."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def _pad(s: str, width: int, align: str = "l") -> str:
    gap = max(width - _w(s), 0)
    if align == "r":
        return " " * gap + str(s)
    if align == "c":
        left = gap // 2
        return " " * left + str(s) + " " * (gap - left)
    return str(s) + " " * gap


def title(text: str) -> None:
    cols = min(shutil.get_terminal_size((88, 20)).columns, 88)
    print()
    print("=" * cols)
    print(f"  {text}")
    print("=" * cols)


def section(text: str) -> None:
    print(f"\n── {text} " + "─" * max(2, 60 - _w(text)))


def table(headers, rows, aligns=None) -> None:
    headers = [str(h) for h in headers]
    rows = [[str(c) for c in r] for r in rows]
    aligns = aligns or ["l"] * len(headers)
    widths = [max(_w(headers[i]), *(_w(r[i]) for r in rows)) if rows else _w(headers[i])
              for i in range(len(headers))]
    print("  " + "  ".join(_pad(h, widths[i], "l") for i, h in enumerate(headers)))
    print("  " + "  ".join("-" * widths[i] for i in range(len(headers))))
    for r in rows:
        print("  " + "  ".join(_pad(c, widths[i], aligns[i]) for i, c in enumerate(r)))


def kv(label: str, value, note: str = "") -> None:
    line = f"  {_pad(label, 34)}{value}"
    if note:
        line += f"   {note}"
    print(line)


def verdict(claim: str, result: str, detail: str) -> None:
    print()
    print(f"  주장   : {claim}")
    print(f"  판정   : {result}")
    print(f"  근거   : {detail}")


def doc_sources(docstring: str) -> None:
    """모듈 docstring 의 '출처:' 블록을 그대로 콘솔에 출력한다.

    문서와 실행 결과에 같은 링크가 두 벌로 존재하면 반드시 어긋난다.
    docstring 하나만 고치면 양쪽이 같이 바뀌도록 여기서 파싱한다.
    """
    if not docstring or "출처:" not in docstring:
        return
    block = docstring[docstring.index("출처:") + len("출처:"):]
    section("출처")
    for line in block.rstrip().splitlines():
        # docstring 기준 2칸 들여쓰기를 콘솔 기준으로 맞춘다
        print("  " + line[2:] if line.startswith("  ") else line)
    print()
