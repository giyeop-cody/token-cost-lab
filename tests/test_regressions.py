import pytest

from lab import pricing
from experiments.exp03_prompt_caching import session_cost
from experiments.exp04_agent_loop_sdd import naive_loop, compacted_loop, sdd_scenarios
from experiments.exp11_tool_output_bloat import simulate, scenario_cost
from router import Kind, Tier, classify, decision_cost, escalate, rework_cost, route
from orchestrator import Orchestrator
from ladder_b import rung_cost


@pytest.mark.parametrize("text,expected", [
    ("파일 업로드 기능 구현", Kind.IMPLEMENT),
    ("검색 엔진 설계", Kind.REASONING),
    ("포맷 변환 모듈 구현", Kind.IMPLEMENT),
    ("디렉터리 삭제 로직 버그 수정", Kind.IMPLEMENT),
    ("경로 탐색 알고리즘 설명", Kind.EXPLAIN),
    ("로그 파일 분석 전략 설계", Kind.REASONING),
    ("src/foo.py 이름을 bar.py로 바꿔줘", Kind.TOOL),
    ("TODO 전부 grep", Kind.TOOL),
])
def test_task_intent_beats_incidental_tool_nouns(text,expected):
    assert classify(text)[0] is expected


def test_total_growth_is_not_added_twice():
    r=rework_cost("버그 수정",1419,2500,2,strategy="retry",turn_growth_tok=4700)
    assert [s["tok_in"] for s in r["trail"]] == [1419,6119,10819]
    assert [s["carried"] for s in r["trail"]] == [0,4700,9400]


def test_identical_a_rung_pricing_in_router_and_orchestrator():
    r=rework_cost("버그 수정",1800,2500,3,strategy="escalate")
    assert r["trail"][-1]["step"] == "tier-up"
    assert r["trail"][-1]["tok_in"] == 3480
    assert r["trail"][-1]["out_tok"] == 400
    assert r["trail"][-1]["usd"] == pytest.approx(.05875)
    o=Orchestrator(tok_in=1800)
    first=o.user_turn("T","버그 수정")
    charged=[first["cost"]]+[o.inner("T",False)["cost"] for _ in range(3)]
    assert charged == pytest.approx([x["usd"] for x in r["trail"]])
    assert o.tasks["T"].cost == pytest.approx(r["usd"])


def test_terminal_respec_has_no_execution_cost():
    o=Orchestrator(max_inner=2)
    o.user_turn("T","버그 수정")
    o.inner("T",False)
    end=o.inner("T",False)
    assert end["action"] == "respec" and end["cost"] == 0
    before=o.tasks["T"].cost
    assert o.inner("T",True)["action"] == "respec"
    assert o.inner("T",False)["cost"] == 0
    assert o.tasks["T"].cost == before
    assert rung_cost(Tier.LARGE,1800,scope="respec",reset=True) == 0


def test_unknown_task_inner_is_error():
    with pytest.raises(ValueError,match="initialize"):
        Orchestrator().inner("uninitialized",False)


def test_same_command_on_new_task_does_not_escalate():
    o=Orchestrator(turn_growth_tok=4700)
    command="결제 실패 재시도 로직 구현해줘"
    first=o.user_turn("a",command)
    o.user_turn("a","결제 재시도 다시 해줘")
    second=o.user_turn("b",command)
    assert second["layer"] == "A" and second["action"] == "proceed"
    assert second["cost"] == first["cost"]
    assert o.tracker_for("a") is not o.tracker_for("b")
    assert o.tasks["a"].carried_tok != o.tasks["b"].carried_tok
    resumed=o.user_turn("a","결제 재시도 다시 해줘")
    assert resumed["layer"] == "B"


def test_new_intent_resets_tier_and_carried_context():
    o=Orchestrator(turn_growth_tok=4700)
    o.user_turn("task","결제 실패 재시도 로직 구현해줘")
    for _ in range(3): o.inner("task",False)
    assert o.tasks["task"].tier_floor is Tier.LARGE
    r=o.user_turn("task","이메일 뉴스레터 구독 폼 만들어줘")
    assert r["layer"] == "A" and r["tier"] is Tier.MID
    assert o.tasks["task"].carried_tok == 4700
    assert r["cost"] == decision_cost(route("이메일 뉴스레터 구독 폼 만들어줘"),1800,2500)["usd"]


@pytest.mark.parametrize("prefix,eligible", [(1024,False),(3000,False),(4095,False),(4096,True)])
def test_haiku_minimum_and_no_discount_below_it(prefix,eligible):
    m=pricing.get("haiku")
    assert pricing.cache_eligible(m,prefix) is eligible
    plain=session_cost(m,prefix,100,100,10,cached=False)
    cached=session_cost(m,prefix,100,100,10)
    assert (cached < plain) is eligible


def test_unknown_cache_threshold_is_not_invented():
    assert pricing.get("flash-lite").cache_min_tokens is None
    assert not pricing.cache_eligible(pricing.get("flash-lite"),100000)
    # Observed cache usage is still billable at the observed cache rate.
    assert pricing.cost(pricing.get("flash-lite"),100000,0,cached_tok=90000) > 0


@pytest.mark.parametrize("args", [(-1,5,0),(10,-1,0),(10,5,-1),(10,5,11)])
def test_invalid_cost_buckets_rejected(args):
    with pytest.raises(ValueError): pricing.cost(pricing.get("sonnet"),*args)


def test_model_mapping_and_verified_metadata():
    m=pricing.for_api("gemini-3.1-flash-lite")
    assert (m.inp,m.out) == (.25,1.5)
    with pytest.raises(ValueError): pricing.for_api("some-unmapped-preview")
    assert pricing.Model("scenario",1,2,.1,1).verified_on == ""
    with pytest.raises(ValueError): pricing.Model("unverified",1,2,.1,1,verified_on="2026-09-20")
    assert all(m.source and m.verified_on for m in pricing.MODELS.values())
    assert not pricing.LEGACY_TALK.source and not pricing.LEGACY_TALK.verified_on


def test_cold_sdd_charges_first_write_and_preparation():
    m=pricing.get("sonnet")
    cold,warm=sdd_scenarios(m),sdd_scenarios(m,warm_cache=True)
    assert cold[0]["total_usd"] == pytest.approx(1.89)
    assert cold[-1]["spec_preparation_usd"] == pytest.approx(.069)
    assert cold[-1]["total_usd"] == pytest.approx(.591)
    assert warm[-1]["total_usd"] == pytest.approx(.5082)
    # One execution with no reuse can't magically start at the read price.
    c,t=naive_loop(m,1,8000,2000,800,cached=True)
    assert c == pytest.approx((8000*3*1.25+800*15)/1e6)
    assert t == 8000


def test_compaction_call_itself_is_counted():
    m=pricing.get("sonnet")
    # histories 100,130; summary call on 160; next history 105.
    c,t=compacted_loop(m,3,100,10,20,every=2,summary=5,cached=False)
    assert t == 100+130+160+105
    assert c == pytest.approx(pricing.cost(m,t,3*20+5))


def test_equal_tool_work_includes_child_and_summary_cost():
    m=pricing.get("sonnet")
    for strategy,expected in (("naive",5.601),("compact",3.4425),("subagent",2.736)):
        counts=simulate(20,8000,5000,300,strategy)
        assert scenario_cost(m,counts) == pytest.approx(expected)
        if strategy == "subagent":
            assert counts["child_in"] == 20*(5000+8000)
            assert counts["child_out"] == 20*1500
        if strategy == "compact": assert counts["compact_in"] > 0 and counts["compact_out"] == 1500
    small=simulate(3,10,2,5,"naive")
    assert small["main_in"] == 3*2+10*3*4/2+5*3*2/2


@pytest.mark.parametrize("strategy", ["naive","compact","subagent"])
def test_invalid_tool_scenario_parameters(strategy):
    with pytest.raises(ValueError): simulate(0,10,2,5,strategy)
    with pytest.raises(ValueError): simulate(3,-10,2,5,strategy)
