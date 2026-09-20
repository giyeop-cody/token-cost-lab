"""Render and execute real HTML; dependencies missing means test failure, not skip."""
from pathlib import Path
import re
import subprocess
import sys

from tools.browser_ac import browser_checks
from demo.vibe_vs_spec.verify_ac import run as verify_cafe

ROOT=Path(__file__).resolve().parents[1]


def test_actual_memo_persists_selects_and_deletes():
    checks=browser_checks("memo",ROOT/"demo/memo.html")
    assert len(checks) >= 4
    assert all(c["ok"] for c in checks), checks


def test_keyword_present_but_nonfunctional_memo_is_rejected(tmp_path):
    original=(ROOT/"demo/memo.html").read_text()
    broken=re.sub(r"<script\b[^>]*>.*?</script>",
                  "<script>/* localStorage.setItem getItem onclick input render save */</script>",
                  original,flags=re.S)
    assert broken != original
    path=tmp_path/"broken-memo.html"
    path.write_text(broken)
    checks=browser_checks("memo",path)
    assert any(not c["ok"] for c in checks)
    result=subprocess.run([sys.executable,str(ROOT/"tools/browser_ac.py"),"memo","--file",str(path)],
                          text=True,capture_output=True,timeout=40)
    assert result.returncode == 1


def test_cafe_real_viewports_and_anchors():
    checks=browser_checks("cafe",ROOT/"demo/vibe_vs_spec/artifacts/index_spec.html")
    assert len(checks) >= 29
    assert all(c["ok"] for c in checks),checks


def test_two_column_mobile_mutation_defeats_old_strings_not_browser(tmp_path):
    original=(ROOT/"demo/vibe_vs_spec/artifacts/index_spec.html").read_text()
    broken=original.replace("</head>","<style>@media(max-width:820px){.menu-grid{grid-template-columns:repeat(2,1fr)!important}}</style></head>")
    assert broken != original
    path=tmp_path/"two-column-mobile.html"
    path.write_text(broken)
    assert verify_cafe(path,static_only=True) == 0   # demonstrates former false pass
    checks=browser_checks("cafe",path)
    assert any("390px .menu-grid" in c["name"] and not c["ok"] for c in checks)
    assert verify_cafe(path) == 1
