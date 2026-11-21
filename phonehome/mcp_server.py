"""MCP server exposing the phonehome registry to AI assistants (Claude Desktop, Cursor, Zed, ...).

Run:  phonehome-mcp                      (stdio, for desktop clients)
      phonehome-mcp --transport streamable-http --port 8787   (remote, self-host it)
Data: the local data/apps/*.yaml if present, otherwise the published API
      (override with PHONEHOME_API=<url to apps.json>).
"""
import argparse, io, json, os, sys, yaml

from .registry import load_apps, status_of, env_optouts, block_hosts, STATUS_LABEL, STATUS_ORDER
from .cli import audit_compose, format_report, match_app

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ModuleNotFoundError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

INSTRUCTIONS = (
    "phonehome is a source-verified registry of what self-hosted apps send out of the network by default "
    "(telemetry, crash reports, update checks, external assets, cloud features), where it goes, and the exact "
    "env var / config / UI switch that disables it. Use lookup_app for one app, search_apps to find apps, "
    "audit_compose to check a docker-compose.yml, lookup_host to identify a domain seen in DNS logs, "
    "blocklist for safe-to-block hosts. 'clean' entries are based on source code search, not packet capture."
)

mcp = _Server("phonehome", instructions=INSTRUCTIONS)
_apps = []


def apps():
    global _apps
    if not _apps:
        _apps = load_apps()
    return _apps


def public(app):
    a = {k: v for k, v in app.items() if not k.startswith("_")}
    a["status"] = status_of(app)
    a["status_label"] = STATUS_LABEL[a["status"]]
    a["env_optouts"] = env_optouts(app)
    return a


def brief(app):
    return {"id": app["id"], "name": app["name"], "status": status_of(app), "status_label": STATUS_LABEL[status_of(app)],
            "category": app.get("category"), "destinations": sorted({h for c in app.get("calls") or [] for h in c.get("destinations") or []})}


@mcp.tool()
def lookup_app(app: str) -> dict:
    """Full registry record for one self-hosted app: every outbound call (type, default on/off/prompt,
    destinations, what is sent, frequency), opt-out env/config/UI/CLI, source URLs and verification date.
    `app` may be the registry id (e.g. 'grafana'), the display name, a GitHub repo URL, or a container image."""
    q = app.strip().lower()
    for a in apps():
        if q in (a["id"].lower(), a["name"].lower()) or (a.get("repo") and q.rstrip("/") == str(a["repo"]).lower().rstrip("/")):
            return public(a)
    m = match_app(q, apps())
    if m:
        return public(m)
    hits = [brief(a) for a in apps() if q in a["id"].lower() or q in a["name"].lower()]
    return {"error": f"no app matching {app!r}", "suggestions": hits[:10]}


@mcp.tool()
def search_apps(query: str = "", status: str = "", category: str = "", limit: int = 50) -> dict:
    """Search the registry. `query` matches id/name/category/notes/destination hosts (case-insensitive);
    `status` filters by one of telemetry-on, prompt, external, update-check, opt-in, clean;
    `category` filters by category (e.g. monitoring, media, database). Returns brief records; use lookup_app for detail."""
    q, st, cat = query.strip().lower(), status.strip().lower(), category.strip().lower()
    if st and st not in STATUS_ORDER:
        return {"error": f"unknown status {status!r}", "valid": STATUS_ORDER}
    out = []
    for a in apps():
        if st and status_of(a) != st:
            continue
        if cat and cat != str(a.get("category", "")).lower():
            continue
        hay = " ".join([a["id"], a["name"], str(a.get("category", "")), str(a.get("notes", "")),
                        " ".join(h for c in a.get("calls") or [] for h in c.get("destinations") or [])]).lower()
        if q and q not in hay:
            continue
        out.append(brief(a))
    return {"count": len(out), "apps": out[:max(1, limit)]}


@mcp.tool()
def lookup_host(host: str) -> dict:
    """Which registered apps contact this domain, for what (telemetry/crash_report/update_check/...), whether it is
    on by default, and whether blocking it is considered safe. Useful for a hostname seen in Pi-hole/AdGuard logs."""
    h = host.strip().lower().rstrip(".")
    hits = []
    for a in apps():
        for c in a.get("calls") or []:
            for d in c.get("destinations") or []:
                d = d.lower()
                if h == d or h.endswith("." + d) or d.endswith("." + h):
                    hits.append({"app": a["id"], "name": a["name"], "host": d, "type": c["type"], "default": c["default"],
                                 "sends": c.get("sends"), "optout": c.get("optout")})
    safe = set(block_hosts(apps(), include_update_checks=True))
    return {"host": h, "safe_to_block": h in safe, "matches": hits}


@mcp.tool()
def audit_compose(compose_yaml: str) -> dict:
    """Audit a docker-compose.yml (pass the file contents). Matches each service image against the registry and reports,
    per default-on call, whether the opt-out env var is set ([ok]), missing ([MISS], with the exact line to add),
    or only switchable via config/UI ([info]). exit_code 2 means at least one opt-out is missing."""
    try:
        compose = yaml.safe_load(io.StringIO(compose_yaml)) or {}
    except yaml.YAMLError as e:
        return {"error": f"invalid YAML: {e}"}
    report = audit_compose_report(compose)
    text, code = format_report(report)
    missing = [f"{r['service']}: {' or '.join(f['fix_env'])}" for r in report if r.get("app") for f in r["findings"] if f["fixed"] is False]
    return {"exit_code": code, "missing_optouts": missing, "report": report, "text": text}


def audit_compose_report(compose):
    from .cli import audit_compose as _audit
    return _audit(compose, apps(), os.getcwd())


@mcp.tool()
def blocklist(include_update_checks: bool = False, format: str = "domains") -> dict:
    """Hosts that can be blocked at the DNS level without breaking the apps (dedicated telemetry/crash hosts only;
    shared hosts like api.github.com are never included). `format`: domains | hosts | adguard. Set include_update_checks
    to also block version-check endpoints (you will stop seeing update notices)."""
    hosts = block_hosts(apps(), include_update_checks=include_update_checks)
    lines = []
    for h in sorted(hosts):
        if format == "hosts":
            lines.append(f"0.0.0.0 {h}")
        elif format == "adguard":
            lines.append(f"||{h}^")
        else:
            lines.append(h)
    return {"count": len(hosts), "format": format, "by_host": {h: sorted(v) for h, v in sorted(hosts.items())}, "text": "\n".join(lines) + "\n",
            "download": "https://12burb.github.io/phonehome/blocklists/" + ("telemetry-and-updates" if include_update_checks else "telemetry")
            + {"hosts": ".hosts", "adguard": ".adguard.txt"}.get(format, ".domains.txt")}


@mcp.tool()
def registry_summary() -> dict:
    """Counts per status, data source, and the list of all app ids with status. Call this first to see what is covered."""
    al = apps()
    counts = {s: sum(1 for a in al if status_of(a) == s) for s in STATUS_ORDER}
    return {"app_count": len(al), "counts": counts, "status_labels": STATUS_LABEL,
            "site": "https://12burb.github.io/phonehome/", "api": "https://12burb.github.io/phonehome/api/v1/index.json",
            "apps": [{"id": a["id"], "name": a["name"], "status": status_of(a)} for a in sorted(al, key=lambda x: x["name"].lower())]}


@mcp.tool()
def refresh_registry() -> dict:
    """Re-load the registry (picks up newly published entries without restarting the server)."""
    global _apps
    _apps = []
    return {"app_count": len(apps())}


def main(argv=None):
    p = argparse.ArgumentParser(prog="phonehome-mcp", description="MCP server for the phonehome registry")
    p.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8787)
    args = p.parse_args(argv)
    if args.transport == "stdio":
        mcp.run("stdio")
    elif hasattr(getattr(mcp, "settings", None), "host"):  # mcp 1.x (FastMCP)
        mcp.settings.host, mcp.settings.port = args.host, args.port
        mcp.run(args.transport)
    else:  # mcp 2.x (MCPServer)
        mcp.run(args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
