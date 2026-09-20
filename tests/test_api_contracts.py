"""Fabricated API fixtures test requests/accounting, NOT live performance."""
import copy
import json
from types import SimpleNamespace

import pytest

from lab import pricing
from experiments import exp10_thinking_cross_vendor as cross
from experiments import exp11_tool_output_bloat as tool


def args_for(tmp_path, n=1):
    return SimpleNamespace(n=n, run_id="mock-only", out=tmp_path / "mock.jsonl")


def gemini_response(parts=None, finish="STOP", prompt=1000, cached=400):
    return {"modelVersion": "gemini-3.1-flash-lite", "usageMetadata": {
        "promptTokenCount": prompt, "cachedContentTokenCount": cached,
        "candidatesTokenCount": 20, "thoughtsTokenCount": 30,
        "toolUsePromptTokenCount": 999999},
        "candidates": [{"finishReason": finish,
                        "content": {"role": "model", "parts": parts or [{"text": "1"}]}}]}


@pytest.mark.parametrize("vendor", ["gemini", "anthropic", "openai"])
def test_all_failed_calls_never_confirm_vendor(vendor, monkeypatch, tmp_path, capsys):
    def fail(*a, **kw):
        raise OSError("secret-key-must-not-appear")
    monkeypatch.setattr(cross, "_post", fail)
    args = args_for(tmp_path, n=2)
    result = cross.run_vendor(vendor, args, "fake-secret")
    assert result["attempted"] == 6
    assert result["valid"] == 0
    assert all(not r["valid"] and "error" in r for r in result["records"])
    log = args.out.read_text()
    assert len(log.splitlines()) == 6
    assert "secret-key-must-not-appear" not in log
    assert "fake-secret" not in log
    output = capsys.readouterr().out
    assert "valid 0/6" in output
    assert "확인됨" not in output


def test_gemini_config_usage_price_and_truncation(monkeypatch, tmp_path):
    payloads = []
    def post(url, payload, headers):
        payloads.append(copy.deepcopy(payload))
        return gemini_response([{ "text": "hidden summary", "thought": True}, {"text": "1"}],
                               finish="MAX_TOKENS" if len(payloads) == 2 else "STOP")
    monkeypatch.setattr(cross, "_post", post)
    r = cross.run_vendor("gemini", args_for(tmp_path), "not-a-real-key")
    assert [p["generationConfig"]["thinkingConfig"] for p in payloads] == [
        {"thinkingLevel": level} for level in ("minimal","low","high")]
    assert {p["generationConfig"]["maxOutputTokens"] for p in payloads} == {12000}
    assert all(p["contents"][0]["role"] == "user" and "parts" in p["contents"][0] for p in payloads)
    assert r["valid"] == 2 and r["attempted"] == 3
    assert [x["valid"] for x in r["records"]] == [True,False,True]
    assert all(x["text"] == "1" and x["out"] == 50 and x["think"] == 30 for x in r["records"])
    expected = (600*.25+400*.025+50*1.5)/1e6
    assert all(x["cost_usd"] == pytest.approx(expected) for x in r["records"])
    assert r["observed_cost_usd"] == pytest.approx(3*expected)  # truncated usage isn't free


def test_missing_usage_not_zero_cost_success(monkeypatch, tmp_path):
    d = gemini_response()
    del d["usageMetadata"]
    monkeypatch.setattr(cross, "_post", lambda *a: copy.deepcopy(d))
    r = cross.run_vendor("gemini", args_for(tmp_path), "fake")
    assert r["valid"] == 0
    assert all(not x["usage_present"] for x in r["records"])


@pytest.mark.parametrize("known_split", [False, True])
def test_claude_disjoint_cache_fields_and_optional_native_thinking_split(monkeypatch, known_split):
    usage = dict(input_tokens=100, cache_read_input_tokens=200, cache_creation_input_tokens=300, output_tokens=500)
    if known_split:
        usage["output_tokens_details"] = {"thinking_tokens": 400}
    payloads = []
    def post(url, payload, headers):
        payloads.append(payload)
        return {"model":"claude-haiku-4-5", "stop_reason":"end_turn", "usage":usage,
                "content":[{"type":"thinking","thinking":"not counted by local tokenizer"}, {"type":"text","text":"1"}]}
    monkeypatch.setattr(cross, "_post", post)
    r = cross.call_anthropic("claude-haiku-4-5", "low", 1024, 12000, "fake")
    assert r["inp"] == 600 and r["cached"] == 200 and r["cache_write"] == 300
    assert r["think"] == (400 if known_split else None)
    assert r["vis"] == (100 if known_split else None)
    assert payloads[0]["thinking"]["budget_tokens"] == 1024
    assert cross.observed_cost(r, pricing.get("haiku")) == pytest.approx(.002995)


def test_openai_reasoning_is_subset_of_output(monkeypatch):
    monkeypatch.setattr(cross, "_post", lambda *a: {
        "model":"gpt-5", "usage":{"prompt_tokens":100,"completion_tokens":200,
        "prompt_tokens_details":{"cached_tokens":20},"completion_tokens_details":{"reasoning_tokens":150}},
        "choices":[{"finish_reason":"stop","message":{"content":"1"}}]})
    r = cross.call_openai("gpt-5", "low", "low", 12000, "fake")
    assert (r["out"],r["think"],r["vis"]) == (200,150,50)
    assert cross.observed_cost(r,pricing.get("gpt5")) == pytest.approx(.0021025)


def test_missing_keys_return_failure_not_verified(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("sys.argv", ["exp10", "--vendor", "all", "--out", str(tmp_path/"unused.jsonl")])
    assert cross.main() == 1
    assert "미검증" in capsys.readouterr().out
    assert not (tmp_path/"unused.jsonl").exists()


def test_explicit_price_override_is_labelled(monkeypatch, tmp_path):
    monkeypatch.setattr(cross, "_post", lambda *a: gemini_response())
    args = args_for(tmp_path)
    args.price_model_gemini = "gemini-25"
    r = cross.run_vendor("gemini", args, "fake")
    assert all(x["price_override"] and "counterfactual" in x["price_basis"] for x in r["records"])


def test_signature_id_and_other_parts_survive_follow_up():
    parts = [{"text":"summary", "thought":True,"thoughtSignature":"sig-thought"},
             {"functionCall":{"name":"read_file","id":"fc-7","args":{"path":"x.py"}},"thoughtSignature":"sig-call"}]
    original = gemini_response(parts)
    before = copy.deepcopy(original)
    contents = [{"role":"user","parts":[{"text":"read x.py"}]}]
    after = tool.follow_up(contents, original, "file contents")
    assert original == before
    assert after[1] == original["candidates"][0]["content"]
    assert after[1] is not original["candidates"][0]["content"]
    assert after[2] == {"role":"user", "parts":[{"functionResponse":{
        "name":"read_file","id":"fc-7","response":{"content":"file contents"}}}]}
    assert len(contents) == 1
    after[1]["parts"][0]["text"] = "mutate the copy"
    assert original == before


def test_three_requests_first_injection_then_history_replay(monkeypatch, tmp_path):
    calls = []
    parts = [{"functionCall":{"name":"read_file","id":"f-123","args":{"path":"docs/service.py"}},
              "thoughtSignature":"keep-verbatim"}]
    def post(url,payload,key):
        calls.append(copy.deepcopy(payload))
        return gemini_response(parts if len(calls)==1 else [{"text":"handler_000"}])
    monkeypatch.setattr(tool,"_post",post)
    args=SimpleNamespace(api_model="gemini-3.1-flash-lite",out=tmp_path/"tool.jsonl",price_model=None)
    # Synthetic $2/$10 model makes cache double-subtraction numerically obvious.
    m=pricing.Model("mock price fixture",2,10,.1,1)
    records=tool.mode_live(args,m,"not-a-key")
    assert len(calls) == len(records) == 3
    assert [len(p["contents"]) for p in calls] == [1,3,5]
    assert tool.SYNTH_FILE not in json.dumps(calls[0])
    for p in calls[1:]:
        assert p["contents"][1]["parts"][0]["thoughtSignature"] == "keep-verbatim"
        fr=p["contents"][2]["parts"][0]["functionResponse"]
        assert fr["id"] == "f-123" and fr["response"]["content"] == tool.SYNTH_FILE
        assert all("role" in c and "parts" in c for c in p["contents"])
    assert all(r["cost_usd"] == pytest.approx(.00178) for r in records)
    assert all(r["cost_usd"] != pytest.approx(.00098) for r in records)
    assert all(r["valid"] for r in records)
    assert len(args.out.read_text().splitlines()) == 3
    assert len({r["run_id"] for r in records}) == 1


@pytest.mark.parametrize("mode", ["http_failure","missing_usage","truncated"])
def test_tool_failures_are_logged_and_raise(monkeypatch,tmp_path,mode):
    def post(*a):
        if mode == "http_failure": raise OSError("private-error-message")
        d=gemini_response(finish="MAX_TOKENS" if mode == "truncated" else "STOP")
        if mode == "missing_usage": del d["usageMetadata"]
        return d
    monkeypatch.setattr(tool,"_post",post)
    args=SimpleNamespace(api_model="gemini-3.1-flash-lite",out=tmp_path/"failures.jsonl")
    with pytest.raises(RuntimeError,match="incomplete"):
        tool.mode_live(args,pricing.get("flash-lite"),"fake")
    row=json.loads(args.out.read_text())
    assert not row["valid"] and row["step"] == 1
    assert "private-error-message" not in args.out.read_text()


def test_no_legacy_budget_requests_by_default(monkeypatch):
    from tools import thinking_sweep
    monkeypatch.setattr("sys.argv",["thinking_sweep"])
    with pytest.raises(SystemExit) as exc:
        thinking_sweep.main()
    assert exc.value.code == 2


def test_claude_off_is_explicit_not_omitted(monkeypatch):
    payloads=[]
    def post(url,payload,headers):
        payloads.append(payload)
        return {"content":[{"type":"text","text":"1"}],"stop_reason":"end_turn",
                "usage":{"input_tokens":20,"output_tokens":5}}
    monkeypatch.setattr(cross,"_post",post)
    cross.call_anthropic("claude-haiku-4-5","off",None,12000,"fake")
    assert payloads[0]["thinking"] == {"type":"disabled"}


def test_exp08_gemini3_uses_levels_and_failure_never_confirms(monkeypatch):
    from experiments import exp08_gemini_live as exp
    payloads=[]
    def post(url,payload,key):
        payloads.append(payload)
        return gemini_response(finish="MAX_TOKENS")
    monkeypatch.setattr(exp,"_post",post)
    args=SimpleNamespace(model="gemini-3.1-flash-lite",price_model=None,prompt=None,max_out=400)
    with pytest.raises(SystemExit,match="미완료"):
        exp.mode_thinking(args,"fake")
    assert [x["generationConfig"]["thinkingConfig"] for x in payloads] == [
        {"thinkingLevel":x} for x in ("minimal","low","high")]
    assert len({x["generationConfig"]["maxOutputTokens"] for x in payloads}) == 1


def test_exp08_missing_usage_or_finish_does_not_become_a_success(monkeypatch):
    from experiments import exp08_gemini_live as exp
    monkeypatch.setattr(exp,"_post",lambda *a:{"candidates":[{"content":{"parts":[{"text":"1"}]}}]})
    r=exp.generate("gemini-3.1-flash-lite","question","fake")
    assert not r["valid"] and not r["usage_present"]
