"""Run the repository's pandapower model on a bounded browser scenario."""
import json
import math
import time
import uuid
from datetime import datetime, timezone
from .search_service import ROOT, validate_settings


def build_physics_job(settings):
    s = validate_settings(settings)
    run = json.loads((ROOT / 'viz/webgl/public/data/run.json').read_text(encoding='utf-8'))
    snapshot = run['grid_snapshot']
    ids = [p['substation_id'] for p in run['candidate_plan']['splits']]
    shares = [s['split'] / 100, 1 - s['split'] / 100]
    offline = ids[0] if s['outage'] == 'northern' else ids[1] if s['outage'] == 'esteros' else None
    if offline:
        shares = [0, 1] if offline == ids[0] else [1, 0]
        snapshot['substations'] = [a for a in snapshot['substations'] if a['id'] != offline]
        snapshot['lines'] = [a for a in snapshot['lines'] if offline not in (a['from'], a['to'])]
    for sub in snapshot['substations']:
        sub['headroom_mw'] *= (100 - s['utilization']) / 35 / (1 + max(0, s['temperature'] - 25) * .008)
    snapshot['dlr_uplift_pct'] = s['dlr']
    gross = s['load'] * (1 + s['growth'] / 100)
    curtailed = gross * s['curtailment'] / 100
    plan = {'site_id': run['site']['id'], 'splits': [{'substation_id': sid, 'mw': gross * share} for sid, share in zip(ids, shares) if share > 0],
            'flex': {'storage_mw': min(s['storage'], gross - curtailed), 'curtailment_mw': curtailed,
                     'dlr': s['dlr'] > 0, 'reconductor': s['reconductor']}}
    return s, plan, snapshot


def execute_physics(settings):
    from grid.physics import check, build_net, _solve
    s, plan, snapshot = build_physics_job(settings)
    start = time.monotonic()
    result = check(plan, snapshot)
    nodes, edges = [], []
    if result['converged']:
        net, unknown = build_net(plan, snapshot)
        if unknown or not _solve(net):
            raise RuntimeError('Base-case profile could not be reproduced')
        names = {a['id']: a['name'] for a in snapshot['substations']}
        for i, row in net.bus.iterrows():
            value = float(net.res_bus.at[i, 'vm_pu'])
            nodes.append({'id': int(i), 'name': names.get(row['name'], row['name']), 'kv': float(row['vn_kv']), 'vm_pu': value if math.isfinite(value) else None})
        for table, res, kind, a, b, power in [(net.line, net.res_line, 'line', 'from_bus', 'to_bus', 'p_from_mw'), (net.trafo, net.res_trafo, 'transformer', 'hv_bus', 'lv_bus', 'p_hv_mw')]:
            for i, row in table.iterrows():
                loading, mw = float(res.at[i, 'loading_percent']), float(res.at[i, power])
                edges.append({'name': row['name'], 'kind': kind, 'from': int(row[a]), 'to': int(row[b]), 'loading_pct': loading if math.isfinite(loading) else None, 'p_mw': mw if math.isfinite(mw) else None})
    return {'engine': 'pandapower', 'job_id': uuid.uuid4().hex, 'completed_utc': datetime.now(timezone.utc).isoformat(),
            'input_settings': s, 'result': result, 'nodes': nodes, 'edges': edges, 'wall_s': round(time.monotonic() - start, 3),
            'scope': 'Actual AC power flow and each model line-out contingency on assumed snapshot topology and ratings. Transformer-bank N-1 is a firm-capacity check, not a re-solved bank outage. Temperature alters assumed background headroom; no conductor-temperature solver is used. Not a utility study or a Lean certificate.'}
