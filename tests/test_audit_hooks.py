"""AUD-009/010: exercise actual hooks using Git Bash on Windows."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _bash():
    executable = ("C:/Program Files/Git/bin/bash.exe" if os.name == "nt"
                  else shutil.which("bash"))
    if not executable or not Path(executable).exists():
        pytest.skip("Git Bash/native bash unavailable")
    return executable


def _run(root, script, payload=None):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    return subprocess.run([_bash(), str(root / script)], cwd=root,
                          input=json.dumps(payload or {}), text=True,
                          # Guarda contra cuelgues, no rendimiento: con 30 s fallaba
                          # de forma intermitente con la maquina cargada (KI-062).
                          capture_output=True, env=env, timeout=120)


@pytest.mark.parametrize("assignment", [
    'ODDS_API_KEY="ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"',
    'set ODDS_API_KEY=ABCDEFGHIJKLMNOPQRSTUVWXYZ012345',
    'api_key: ABCDEFGHIJKLMNOPQRSTUVWXYZ012345',
])
@pytest.mark.parametrize("comment", ["", " # replaces the example key"])
def test_comments_do_not_hide_literal(tmp_path, assignment, comment):
    shutil.copytree(ROOT / ".claude/hooks", tmp_path / ".claude/hooks")
    target = tmp_path / "fixture.txt"
    target.write_text(assignment + comment, encoding="utf-8")
    result = _run(tmp_path, ".claude/hooks/check-secrets.sh",
                  {"tool_input": {"file_path": str(target)}})
    assert result.returncode == 2
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345" not in result.stderr


@pytest.mark.parametrize("value", ['"TU_CLAVE"', '"your_placeholder"',
                                   'os.environ["ODDS_API_KEY"]', '%ODDS_API_KEY%'])
def test_placeholders_remain_allowed(tmp_path, value):
    shutil.copytree(ROOT / ".claude/hooks", tmp_path / ".claude/hooks")
    target = tmp_path / "fixture.txt"
    target.write_text("ODDS_API_KEY=" + value, encoding="utf-8")
    assert _run(tmp_path, ".claude/hooks/check-secrets.sh",
                {"tool_input": {"file_path": str(target)}}).returncode == 0


def test_reinstall_preserves_runtime_hooks_and_bash_targets(tmp_path):
    shutil.copytree(ROOT / ".claude/hooks", tmp_path / ".claude/hooks")
    shutil.copy2(ROOT / "instalar-candados.sh", tmp_path)
    hooks = [tmp_path / ".claude/hooks" / f"{name}.sh" for name in
             ("require-dispatch-model", "mark-crossreview-pending", "crossreview-on-stop")]
    before = [p.read_bytes() for p in hooks]
    result = _run(tmp_path, "instalar-candados.sh")
    assert result.returncode == 0, result.stderr
    assert "Edit|Write|Bash" in result.stdout
    assert [p.read_bytes() for p in hooks] == before
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/test.yaml").write_text("x", encoding="utf-8")
    result = _run(tmp_path, ".claude/hooks/mark-crossreview-pending.sh",
                  {"tool_name": "Bash", "tool_input": {"command": "echo x > configs/test.yaml"}})
    assert result.returncode == 0
    assert (tmp_path / ".claude/.crossreview-pending").exists()


# AUD-007 (ronda audit-2026-09-18): el detector marcaba como secreto una
# asignacion REFLEXIVA (`self.api_key = api_key`) seguida de `\r\n` escapado
# dentro de una cadena JSON (codigo fuente citado en un EVIDENCE.json): el
# "valor" capturado era el propio identificador mas los 4 caracteres de
# escape. Y `check-secrets.sh` re-escaneaba ese fichero, ajeno al turno, en
# cada comando Bash con operador de escritura: >15 avisos identicos por sesion.
def _suspicious_lines():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "secret_literals", ROOT / ".claude/hooks/_secret_literals.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.suspicious_lines


@pytest.mark.parametrize("line", [
    # asignacion reflexiva citada dentro de una cadena JSON (escape literal)
    '"output": "        self.api_key = api_key\r\n        self.regions = regions"',
    # asignacion reflexiva en codigo fuente
    "        self.api_key = api_key",
    "settings.odds_api_key = odds_api_key  # inyectada",
    # el valor es una llamada / atributo, no un literal
    "api_key = settings.odds_api_key",
    "token = read_token_from(path)",
])
def test_reflexive_or_symbolic_assignments_are_not_secrets(line):
    assert _suspicious_lines()(line) == []


@pytest.mark.parametrize("line", [
    'ODDS_API_KEY="ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"',
    "api_key = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ012345'",
    "TOKEN: ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    '"api_key": "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"',
])
def test_real_literals_still_detected(line):
    assert _suspicious_lines()(line) == [1]


def test_audit_reports_are_scanned_too(tmp_path):
    """AUD-006 (ronda audit-2026-10-18): `audit/` y `audits/` se excluian del
    escaneo por carpeta (AUD-007, audit-2026-09-18) y quedaban 325 ficheros
    rastreados de un repo PUBLICO sin ninguna barrera. Ahora se escanean: un
    literal bloquea igual que en el codigo, y la asignacion reflexiva citada que
    motivo la exclusion sigue sin dar aviso porque `_symbolic` la descarta por
    el valor."""
    shutil.copytree(ROOT / ".claude/hooks", tmp_path / ".claude/hooks")
    for rel in ("audit/latest/openai/EVIDENCE.json", "audits/x/REPORT.md",
                "src/x.py", "src/sqp/audit/html_report.py", "scripts/audit_team_names.py"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('ODDS_API_KEY="ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"',
                          encoding="utf-8")
        result = _run(tmp_path, ".claude/hooks/check-secrets.sh",
                      {"tool_input": {"file_path": str(target)}})
        assert result.returncode == 2, rel
        assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345" not in result.stderr
    citado = tmp_path / "audit/latest/claude/EVIDENCE.json"
    citado.parent.mkdir(parents=True, exist_ok=True)
    citado.write_text('{"output": "        self.api_key = api_key\\r\\n        x = 1"}',
                      encoding="utf-8")
    assert _run(tmp_path, ".claude/hooks/check-secrets.sh",
                {"tool_input": {"file_path": str(citado)}}).returncode == 0


# AUD-012 (ronda audit-2026-10-18): formatos que el detector no veia. El valor se
# construye en tiempo de ejecucion para no dejar mas literales en este fichero.
_HEX = "a1b2c3d4" * 4
_GH = "A1b2C3d4E5f6G7h8I9j0" * 2


@pytest.mark.parametrize("line", [
    f'key="{_HEX}"',
    f'ODDS_KEY="{_HEX}"',
    '{"x-api-key": "' + _HEX + '"}',
    f"headers = {{'X-Api-Key': '{_HEX}'}}",
    "ghp_" + _GH,
    "github_pat_" + _GH + "_" + _GH,
])
def test_aud012_new_formats_are_detected(line):
    assert _suspicious_lines()(line) == [1]


@pytest.mark.parametrize("line", [
    'key="home_team_name_long_value"',
    "rows.sort(key=lambda r: r.start_time)",
    'cache_key = "2026-10-18_nba_h2h_home_team"',
    'secret = tmp_path / ".env"',
    "| `secret_scanning: disabled` |",
    "grep -rlE 'apiKey=[A-Za-z0-9]{8,}' logs",
])
def test_aud012_common_code_is_not_a_secret(line):
    assert _suspicious_lines()(line) == []


# AUD-011 (ronda audit-2026-09-23, OPENAI-008 reproducido): `[ -z "$out" ] &&
# exit 0` iba ANTES de mirar el codigo de salida. Un `codex review` que fallaba
# sin escribir nada salia con exito, sin aviso y con el centinela ya borrado:
# la revision pendiente se perdia en silencio. `codex` es un doble en PATH; no
# se llama a ningun servicio.
def _crossreview(tmp_path, rc: int, salida: str, espera_s: int = 0,
                 env_extra: dict | None = None):
    shutil.copytree(ROOT / ".claude/hooks", tmp_path / ".claude/hooks")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True,
                   capture_output=True)
    marker = tmp_path / ".claude/.crossreview-pending"
    marker.write_text("", encoding="utf-8")
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    fake = bin_dir / "codex"
    fake.write_text("#!/usr/bin/env bash\n"
                    + (f"sleep {espera_s}\n" if espera_s else "")
                    + (f"printf '%s\n' {json.dumps(salida)}\n" if salida else "")
                    + f"exit {rc}\n", encoding="utf-8", newline="\n")
    fake.chmod(0o755)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path),
           "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
           **(env_extra or {})}
    res = subprocess.run([_bash(), "-c",
                          f'export PATH="$(cygpath -u "{bin_dir}" 2>/dev/null '
                          f'|| echo "{bin_dir}"):$PATH"; '
                          f'bash "{(tmp_path / ".claude/hooks/crossreview-on-stop.sh").as_posix()}"'],
                         cwd=tmp_path, input=json.dumps({}), text=True,
                         capture_output=True, env=env, timeout=60)
    return res, marker


def test_crossreview_fallo_sin_salida_avisa_y_conserva_el_marcador(tmp_path):
    res, marker = _crossreview(tmp_path, 7, "")
    assert res.returncode == 0
    assert "NO SE EJECUTO" in res.stderr
    assert marker.exists()


def test_crossreview_salida_vacia_con_rc0_no_es_un_veredicto(tmp_path):
    res, marker = _crossreview(tmp_path, 0, "")
    assert res.returncode == 0
    assert "NO SE EJECUTO" in res.stderr
    assert marker.exists()


def test_crossreview_fallo_con_texto_sigue_igual(tmp_path):
    res, marker = _crossreview(tmp_path, 1, "You've hit your usage limit")
    assert res.returncode == 0
    assert "NO SE EJECUTO" in res.stderr
    assert marker.exists()


def test_crossreview_veredicto_valido_bloquea_y_consume_el_marcador(tmp_path):
    res, marker = _crossreview(tmp_path, 0, "Finding: algo")
    assert res.returncode == 2
    assert "REVISION CRUZADA AUTOMATICA" in res.stderr
    assert not marker.exists()

# AUD-007 (ronda audit-2026-10-18): `codex review` no tenia presupuesto propio.
# Si se pasaba de los 600 s del harness, el hook moria con el centinela ya
# borrado. Con un presupuesto de 1 s y un doble que tarda 5, debe cortarse,
# avisar y conservar el centinela.
def test_crossreview_lento_se_corta_avisa_y_conserva_el_marcador(tmp_path):
    res, marker = _crossreview(tmp_path, 0, "Finding: tarde", espera_s=5,
                               env_extra={"SQP_CROSSREVIEW_TIMEOUT_S": "1"})
    assert res.returncode == 0
    assert "NO SE EJECUTO" in res.stderr
    assert "presupuesto" in res.stderr
    assert marker.exists()


# AUD-010 (ronda audit-2026-10-15): sin `codex` en el PATH el hook BORRABA el
# centinela y salia en silencio; la revision cruzada se perdia sin reintento.
# PATH reducido a /usr/bin (cat, rm, bash; ningun `codex`) para simular su
# ausencia sin depender de lo que tenga instalado la maquina.
def test_crossreview_sin_codex_avisa_y_conserva_el_marcador(tmp_path):
    shutil.copytree(ROOT / ".claude/hooks", tmp_path / ".claude/hooks")
    marker = tmp_path / ".claude/.crossreview-pending"
    marker.write_text("", encoding="utf-8")
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    hook = (tmp_path / ".claude/hooks/crossreview-on-stop.sh").as_posix()
    res = subprocess.run([_bash(), "-c", f'PATH=/usr/bin; bash "{hook}"'],
                         cwd=tmp_path, input=json.dumps({}), text=True,
                         capture_output=True, env=env, timeout=60)
    assert res.returncode == 0, "la ausencia de codex no debe bloquear el turno"
    assert "NO SE EJECUTO" in res.stderr, "la revision perdida no se avisa"
    assert marker.exists(), "el centinela se borro: la revision no se reintentara"


# AUD-013 (ronda audit-2026-10-18): el guard de despacho ejecutado de verdad. Un
# fork ignora `model`, asi que pasa con aviso; un subagente sin `model`, no.
def test_dispatch_guard_lets_fork_through_but_not_a_plain_subagent(tmp_path):
    shutil.copytree(ROOT / ".claude/hooks", tmp_path / ".claude/hooks")
    hook = ".claude/hooks/require-dispatch-model.sh"
    fork = _run(tmp_path, hook, {"tool_name": "Agent",
                                 "tool_input": {"subagent_type": "fork", "prompt": "x"}})
    assert fork.returncode == 0, fork.stderr
    assert "modelo de la sesion" in fork.stderr
    plano = _run(tmp_path, hook, {"tool_name": "Agent",
                                  "tool_input": {"subagent_type": "Explore", "prompt": "x"}})
    assert plano.returncode == 2
    assert "DESPACHO BLOQUEADO" in plano.stderr
