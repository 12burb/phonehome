import os, sys, json, subprocess, textwrap
import pytest
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


def test_build_writes_api(tmp_path):
    from phonehome import build
    build.main(str(tmp_path))
    api = tmp_path / "api" / "v1"
    idx = json.loads((api / "index.json").read_text())
    assert idx["app_count"] == len(json.loads((api / "apps.json").read_text()))
    assert (api / "apps" / "grafana.json").exists()
    assert "stats.grafana.org" in json.loads((api / "hosts.json").read_text())
    assert json.loads((api / "openapi.json").read_text())["openapi"].startswith("3.")
    bl = json.loads((api / "blocklist.json").read_text())
    assert set(bl["telemetry"]) <= set(bl["telemetry_and_updates"])


def test_audit_compose_dict():
    from phonehome.cli import audit_compose, format_report
    apps = load_apps()
    compose = {"services": {"m": {"image": "getmeili/meilisearch:v1.10"}, "x": {"image": "nobody/unknown"}}}
    report = audit_compose(compose, apps)
    assert report[1]["app"] is None
    text, code = format_report(report)
    assert code == 2 and "MEILI_NO_ANALYTICS=true" in text
    compose["services"]["m"]["environment"] = {"MEILI_NO_ANALYTICS": "true"}
    assert format_report(audit_compose(compose, apps))[1] == 0


def test_load_apps_falls_back_to_api(tmp_path, monkeypatch):
    from phonehome import registry, build
    build.main(str(tmp_path))
    monkeypatch.setattr(registry, "API_URL", (tmp_path / "api" / "v1" / "apps.json").as_uri())
    apps = registry.load_apps(str(tmp_path / "missing"))
    assert len(apps) == len(load_apps()) and apps[0]["_file"].endswith(".yaml")


def test_mcp_tools():
    pytest.importorskip("mcp")
    from phonehome import mcp_server as m
    assert m.lookup_app("grafana/grafana")["id"] == "grafana"
    assert m.lookup_app("nope-nope").get("error")
    assert m.search_apps(status="clean")["count"] > 50
    assert m.lookup_host("udc.neo4j.com")["matches"][0]["app"] == "neo4j"
    assert "api.github.com" not in m.blocklist(include_update_checks=True)["by_host"]
    assert m.audit_compose("services:\n  g:\n    image: grafana/grafana\n")["exit_code"] == 2
    assert m.audit_compose("services: [")["error"]
