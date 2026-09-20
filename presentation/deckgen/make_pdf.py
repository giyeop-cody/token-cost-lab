#!/usr/bin/env python3
"""Convert all canonical PPTX with LibreOffice; --check verifies actual PDF text."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    if not shutil.which('soffice'):
        raise SystemExit('UNVERIFIED: install libreoffice-impress + fonts-nanum; no PDF generated')
    paths = sorted((ROOT/'presentation').glob('*.pptx')) + sorted((ROOT/'presentation/case_vibe_vs_spec').glob('*.pptx'))
    if len(paths) != 5:
        raise SystemExit(f'Expected five canonical PPTX; found {len(paths)}')
    with tempfile.TemporaryDirectory() as profile:
        for p in paths:
            # Stale PDF must not survive a failed conversion and look freshly verified.
            pdf=p.with_suffix('.pdf')
            if pdf.exists(): pdf.unlink()
            subprocess.run(['soffice', '-env:UserInstallation='+Path(profile).as_uri(), '--headless',
                            '--convert-to', 'pdf', '--outdir', str(p.parent), str(p)], check=True, timeout=180)
            if not pdf.is_file(): raise SystemExit('Conversion produced no PDF: '+str(p))
    if args.check:
        subprocess.run([sys.executable, str(ROOT/'tools/verify_deck.py'), '--with-pdf'], check=True, cwd=ROOT)

if __name__ == '__main__': main()
