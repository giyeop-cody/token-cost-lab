"""Failure recording, statistical confounds, and total cache-cost regressions."""
import json
import subprocess
import sys

import pytest

from experiments.exp03_prompt_caching import session_cost
from lab.pricing import Model
from tools import check_audit, stats_test


def test_timeout_is_recorded_and_does_not_abort_next_check(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1, output=b'partial output')
    monkeypatch.setattr(check_audit.subprocess, 'run', timeout)
    result=check_audit.run_check('timed', ['missing.py'], tmp_path, timeout=1)
    assert result['exit_code']==124 and result['status']=='timeout'
    assert 'partial output' in (tmp_path/'timed.txt').read_text()
    monkeypatch.setattr(check_audit.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a[0],0,'ok',''))
    assert check_audit.run_check('next', ['ok.py'], tmp_path)['exit_code']==0


def test_absent_malformed_and_stale_pytest_xml_never_claim_pass(tmp_path):
    path=tmp_path/'pytest.xml'
    assert check_audit.pytest_counts(path,True) is None
    path.write_text('<testsuites><testsuite tests="100" failures="0"/></testsuites>')
    assert check_audit.pytest_counts(path,False) is None
    path.write_text('truncated xml')
    assert check_audit.pytest_counts(path,True) is None


def test_explicit_storage_can_reverse_cache_saving():
    m=Model('explicit storage scenario', .25, 1.5, .1, 1, cache_min_tokens=1)
    plain=session_cost(m,100000,0,0,2,cached=False)
    token_only=session_cost(m,100000,0,0,2)
    total=session_cost(m,100000,0,0,2,storage_usd_per_million_hour=1,storage_hours=1)
    assert (plain,token_only,total)==pytest.approx((.05,.0275,.1275))
    assert token_only < plain < total
    assert session_cost(m,100000,0,0,2,cached=False,storage_usd_per_million_hour=1,storage_hours=1)==plain
    with pytest.raises(ValueError):
        session_cost(m,100000,0,0,2,storage_hours=-1)


@pytest.mark.parametrize('a,b', [([], [1]),([1],[]),([1],[0,0]),([float('nan')],[1])])
def test_undefined_ratio_is_explicit(a,b):
    with pytest.raises(ValueError): stats_test.boot_ratio_ci(a,b)


@pytest.mark.parametrize('change', ['model','budget','language','empty'])
def test_stats_refuses_confounding_logs(tmp_path,monkeypatch,change):
    rows=[dict(model='gemini-3.1-flash-lite',budget=-1,lang=lang,task='reason',finish='STOP') for lang in ['en','ko']]
    if change=='model': rows[1]['model']='gpt-5'
    elif change=='budget': rows[1]['budget']=0
    elif change=='language': rows[1]['lang']='en'
    else: rows=[]
    path=tmp_path/'confounded.jsonl'
    path.write_text('\n'.join(json.dumps(r) for r in rows))
    monkeypatch.setattr(sys,'argv',['stats_test',str(path)])
    with pytest.raises(ValueError): stats_test.main()
