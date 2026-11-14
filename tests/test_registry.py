import os, sys, subprocess, textwrap
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from phonehome.registry import load_apps, validate, status_of, env_optouts, block_hosts, blockable
from phonehome.cli import norm_image, match_app, audit

APPS = load_apps()

def test_dataset_is_valid():
    errs = [e for a in APPS for e in validate(a)]
    assert errs == [], "\n".join(errs)

def test_ids_unique():
    ids = [a["id"] for a in APPS]
    assert len(ids) == len(set(ids))

def test_status_rules():
    assert status_of({"calls": [{"type": "telemetry", "default": "on"}]}) == "telemetry-on"
    assert status_of({"calls": [{"type": "telemetry", "default": "prompt"}]}) == "prompt"
    assert status_of({"calls": [{"type": "update_check", "default": "on"}, {"type": "telemetry", "default": "off"}]}) == "update-check"
    assert status_of({"calls": [{"type": "external_asset", "default": "on"}]}) == "external"
    assert status_of({"calls": [{"type": "telemetry", "default": "off"}]}) == "opt-in"
    assert status_of({"calls": []}) == "clean"

def test_env_optouts_strip_comments():
    app = {"calls": [{"type": "telemetry", "default": "on", "optout": {"env": ["FOO=bar (only on first start)"]}}]}
    assert env_optouts(app) == [{"name": "FOO", "value": "bar", "type": "telemetry"}]

def test_blockable_rules():
    assert blockable({}, "telemetry.example.com")
    assert not blockable({}, "example.com")
    assert blockable({"block": True}, "example.com")
    assert not blockable({"block": False}, "telemetry.example.com")

def test_blocklist_never_contains_apex_domains_without_optin():
    for host in block_hosts(APPS, include_update_checks=True):
        assert host.count(".") >= 2 or any(
            c.get("block") is True and host in (c.get("destinations") or []) for a in APPS for c in a["calls"])

def test_norm_image():
    assert norm_image("docker.io/library/postgres:16") == "postgres"
    assert norm_image("ghcr.io/immich-app/immich-server:release") == "ghcr.io/immich-app/immich-server"
    assert norm_image("localhost:5000/grafana/grafana:10") == "localhost:5000/grafana/grafana"

def test_match_app():
    assert match_app("grafana/grafana:11.0.0", APPS)["id"] == "grafana"
    assert match_app("docker.io/grafana/grafana", APPS)["id"] == "grafana"
    assert match_app("postgres:16", APPS) is None

def test_audit_exit_codes(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(textwrap.dedent("""
        services:
          search:
            image: getmeili/meilisearch:v1.10
    """))
    assert audit(str(compose), APPS) == 2
    compose.write_text(textwrap.dedent("""
        services:
          search:
            image: getmeili/meilisearch:v1.10
            environment:
              MEILI_NO_ANALYTICS: "true"
    """))
    assert audit(str(compose), APPS) == 0

def test_audit_reads_env_file(tmp_path):
    (tmp_path / ".env").write_text("MEILI_NO_ANALYTICS=true\n")
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services:\n  s:\n    image: getmeili/meilisearch\n    env_file: .env\n")
    assert audit(str(compose), APPS) == 0

def test_build_runs(tmp_path):
    r = subprocess.run([sys.executable, "-m", "phonehome.build", str(tmp_path)], capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "index.html").exists() and (tmp_path / "apps.json").exists()
    assert (tmp_path / "blocklists" / "telemetry.hosts").exists()
