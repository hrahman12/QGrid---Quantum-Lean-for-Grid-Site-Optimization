import math
import pytest
from viz.webgl.server.search_service import build_job, validate_settings


@pytest.mark.parametrize('value', [math.nan, math.inf, '150', True, -1, 501])
def test_api_rejects_invalid_or_unbounded_load(value):
    with pytest.raises(ValueError):
        validate_settings({'load': value})


def test_baseline_has_no_marked_plan_under_firm_caps():
    _, _, space, _, marked = build_job({})
    assert space.size == 5
    assert space.n_qubits == 7
    assert space.padded_size == 128
    assert marked == []


def test_flexibility_budgets_create_real_feasible_candidates_and_keep_firm_caps():
    _, _, space, oracle, marked = build_job({'load': 100, 'storage': 60, 'curtailment': 10, 'dlr': 15})
    assert space.size == 120
    assert space.n_qubits == 7
    assert len(marked) == 4
    for index in marked:
        plan = space.decode(index)
        assert plan.storage_mw <= 60 and plan.curtail_pct <= 10
        assert oracle(plan)
        assert all(q == 2 for q in plan.quarters)
    assert all(oracle.limit_mw(sub) == 19.9 for sub in space.substations)


def test_job_spaces_do_not_mutate_shared_global_search_options():
    _, _, first, _, _ = build_job({'storage': 60, 'curtailment': 10, 'dlr': 15})
    _, _, second, _, _ = build_job({})
    assert len(first.storage_options) == 4
    assert second.storage_options == (0.0,)
    assert second.curtail_options == (0.0,)


def test_outage_removes_the_failed_source_from_the_quantum_space():
    _, _, space, _, _ = build_job({'outage': 'northern'})
    assert len(space.substations) == 1
    assert space.substations[0]['name'] == 'Los Esteros Substation'


@pytest.mark.parametrize('settings', [{}, {'outage': 'northern'},
    {'storage': 100, 'curtailment': 20, 'dlr': 30},
    {'storage': 60, 'curtailment': 7, 'dlr': 15}])
def test_browser_register_is_always_seven_qubits_and_padding_is_never_marked(settings):
    _, _, space, oracle, marked = build_job(settings)
    assert space.n_qubits == 7
    assert space.padded_size == 128
    assert 0 < space.size <= 128
    assert all(i < space.size for i in marked)
    for index in range(space.size, 128):
        with pytest.raises(IndexError):
            space.decode(index)
