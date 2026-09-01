#!/usr/bin/env python3
from pathlib import Path
import json
import re
import sys
ROOT=Path(__file__).resolve().parents[1]
errors=[]
try:
    cfg=json.loads((ROOT/'.claude/automation/model-routing.json').read_text(encoding='utf-8'))
except Exception as exc:
    errors.append(f"routing JSON: {exc}"); cfg={}
valid={"fable","opus","sonnet","haiku","inherit"}
for p in sorted((ROOT/'.claude/agents').rglob('*.md')):
    text=p.read_text(encoding='utf-8')
    m=re.search(r'^model:\s*(\S+)',text,re.M)
    if not m: errors.append(f"missing model: {p.relative_to(ROOT)}")
    elif m.group(1) not in valid and not m.group(1).startswith('claude-'): errors.append(f"invalid model {m.group(1)}: {p.relative_to(ROOT)}")
for route in cfg.get('routes',[]):
    agent=route.get('primary_agent')
    if not any(re.search(rf'^name:\s*{re.escape(agent)}\s*$', p.read_text(encoding='utf-8'), re.M) for p in (ROOT/'.claude/agents').rglob('*.md')):
        errors.append(f"unknown primary agent: {agent}")
settings=json.loads((ROOT/'.claude/settings.json').read_text(encoding='utf-8'))
# El hook UserPromptSubmit se RETIRO el 2026-09-01 (decision del operador):
# nunca estuvo cableado y, aun cableado, solo inyectaba texto consultivo -- no
# asigna modelo. El mecanismo real es el parametro `model` del Agent tool
# (REGLA DE DESPACHO en .claude/automation/MODEL_ROUTING.md). La logica de
# clasificacion sobrevive como modulo, consumido bajo demanda por /route-task.
# Se validan las dos mitades de la retirada para que no se deshaga a medias.
if not (ROOT/'.claude/automation/route_classifier.py').is_file(): errors.append('route_classifier.py missing')
if (ROOT/'.claude/hooks/route-model.py').is_file(): errors.append('el hook retirado el 2026-09-01 reaparecio en .claude/hooks/')
if settings.get('model')!='claude-opus-5': errors.append(f"settings model {settings.get('model')!r} != claude-opus-5 (politica 2026-08-30)")
if errors:
    print('Claude model routing configuration: FAILED')
    print('\n'.join(f'- {e}' for e in errors)); sys.exit(1)
print('Claude model routing configuration: OK')
