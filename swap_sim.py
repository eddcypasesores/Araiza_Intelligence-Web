import streamlit as st

data = {
    'top_origen_data': {'description': 'A'},
    'top_origen_query': 'A',
    'top_destino_data': {'description': 'C'},
    'top_destino_query': 'C',
    'top_parada_data': {'description': 'B'},
    'top_parada_query': 'B',
    'show_intermediate_stop': True,
}

POINT_SUFFIXES = ("_data", "_query", "_options", "_selection")
pending_swap_key = "_pending_route_swaps"
stop_state_key = "show_intermediate_stop"

class Session(dict):
    pass

st_session = Session(data)

def capture(prefix):
    return {suffix: st_session.get(f"{prefix}{suffix}") for suffix in POINT_SUFFIXES}

role_prefix = {
    "origin": "top_origen",
    "destination": "top_destino",
    "stop": "top_parada",
}

snapshot = {role: capture(prefix) for role, prefix in role_prefix.items()}

role_a, role_b = 'origin', 'stop'

snapshot[role_a], snapshot[role_b] = snapshot.get(role_b, {}), snapshot.get(role_a, {})

pending = {}
for role, prefix in role_prefix.items():
    pending[prefix] = snapshot.get(role, {})
stop_active_now = bool(st_session.get(stop_state_key))
stop_has_data = bool(snapshot.get('stop', {}).get('_data'))
pending['_stop_state'] = stop_active_now or stop_has_data

st_session[pending_swap_key] = pending

pending_swaps = st_session.pop(pending_swap_key, None)
if isinstance(pending_swaps, dict):
    for prefix, payload in pending_swaps.items():
        if prefix == '_stop_state':
            st_session[stop_state_key] = bool(payload)
            continue
        for suffix in POINT_SUFFIXES:
            key = f"{prefix}{suffix}"
            value = payload.get(suffix)
            if value is None:
                st_session.pop(key, None)
            else:
                st_session[key] = value

print('origin data', st_session['top_origen_data'])
print('stop data', st_session['top_parada_data'])
print('stop state', st_session[stop_state_key])
