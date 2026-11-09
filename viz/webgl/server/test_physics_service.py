from viz.webgl.server.physics_service import build_physics_job, execute_physics


def test_outage_removes_source_and_routes_all_gross_mw_to_survivor():
    _, plan, snapshot = build_physics_job({'outage': 'northern', 'load': 100, 'storage': 60, 'curtailment': 10})
    assert len(plan['splits']) == 1
    assert plan['splits'][0]['mw'] == 100
    sid = plan['splits'][0]['substation_id']
    assert any(a['id'] == sid for a in snapshot['substations'])
    assert plan['flex']['storage_mw'] + plan['flex']['curtailment_mw'] == 70


def test_actual_ac_solver_returns_bus_and_branch_profiles():
    response = execute_physics({'load': 100, 'storage': 60, 'curtailment': 10, 'split': 50})
    assert response['engine'] == 'pandapower'
    assert response['result']['converged']
    assert response['nodes'] and response['edges']
    assert min(n['vm_pu'] for n in response['nodes']) == response['result']['v_min_pu'] or abs(min(n['vm_pu'] for n in response['nodes']) - response['result']['v_min_pu']) < .0001
    assert all(e['loading_pct'] is not None for e in response['edges'])
