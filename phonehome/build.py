"""Generate dist/: apps.json, blocklists and the static site."""
import os, sys, json, datetime
from .registry import load_apps, validate, status_of, env_optouts, block_hosts, STATUS_LABEL, STATUS_ORDER

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def public(app):
    a = {k: v for k, v in app.items() if not k.startswith("_")}
    a["status"] = status_of(app)
    a["status_label"] = STATUS_LABEL[a["status"]]
    a["env_optouts"] = env_optouts(app)
    return a

def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def hosts_file(hosts, title, fmt):
    today = datetime.date.today().isoformat()
    lines = [f"# phonehome - {title}", f"# generated {today} from https://github.com/12burb/phonehome", "#"]
    for h in sorted(hosts):
        apps = ",".join(sorted(hosts[h]))
        if fmt == "hosts":
            lines.append(f"0.0.0.0 {h}  # {apps}")
        elif fmt == "adguard":
            lines.append(f"||{h}^  # {apps}")
        else:  # plain domains (Pi-hole / Blocky / Technitium)
            lines.append(f"{h}")
    return "\n".join(lines) + "\n"

API_BASE = "https://12burb.github.io/phonehome/api/v1"

def write_api(out, pub, apps):
    """Static JSON API under /api/v1/. Every file is plain JSON on GitHub Pages (CORS: *), so anything can consume it."""
    api = os.path.join(out, "api", "v1")
    today = datetime.date.today().isoformat()
    dump = lambda o: json.dumps(o, indent=1, ensure_ascii=False)
    write(os.path.join(api, "apps.json"), dump(pub))
    for a in pub:
        write(os.path.join(api, "apps", a["id"] + ".json"), dump(a))
    hosts = {}
    for a in pub:
        for c in a.get("calls") or []:
            for h in c.get("destinations") or []:
                hosts.setdefault(h, []).append({"app": a["id"], "type": c["type"], "default": c["default"]})
    write(os.path.join(api, "hosts.json"), dump(dict(sorted(hosts.items()))))
    images = {}
    for a in pub:
        for img in a.get("images") or []:
            images[img] = a["id"]
    write(os.path.join(api, "images.json"), dump(dict(sorted(images.items()))))
    tele, tele_upd = block_hosts(apps), block_hosts(apps, include_update_checks=True)
    write(os.path.join(api, "blocklist.json"), dump({
        "telemetry": sorted(tele), "telemetry_and_updates": sorted(tele_upd),
        "by_host": {h: sorted(v) for h, v in sorted(tele_upd.items())}}))
    counts = {s: sum(1 for a in pub if a["status"] == s) for s in STATUS_ORDER}
    write(os.path.join(api, "index.json"), dump({
        "name": "phonehome", "version": 1, "generated": today, "base": API_BASE,
        "source": "https://github.com/12burb/phonehome", "app_count": len(pub), "counts": counts,
        "endpoints": {
            "apps": "apps.json", "app": "apps/{id}.json", "hosts": "hosts.json", "images": "images.json",
            "blocklist": "blocklist.json", "openapi": "openapi.json",
            "blocklists_text": "../../blocklists/telemetry.{hosts,adguard.txt,domains.txt}"},
        "apps": [{"id": a["id"], "name": a["name"], "status": a["status"], "category": a.get("category"), "verified": str(a.get("verified"))} for a in pub]}))
    write(os.path.join(api, "openapi.json"), dump(openapi(today)))

def openapi(today):
    j = lambda ref: {"content": {"application/json": {"schema": {"$ref": ref}}}}
    return {
        "openapi": "3.1.0",
        "info": {"title": "phonehome API", "version": "1." + today.replace("-", ""),
                 "description": "Static, read-only JSON API of the phonehome registry: what self-hosted apps send out by default and how to turn it off. "
                                "Files are regenerated on every push and served from GitHub Pages with CORS enabled. No auth, no rate limit beyond GitHub Pages'.",
                 "license": {"name": "MIT"}},
        "servers": [{"url": API_BASE}],
        "paths": {
            "/index.json": {"get": {"summary": "Registry summary: counts, endpoints, and id/name/status for every app", "responses": {"200": {"description": "OK"}}}},
            "/apps.json": {"get": {"summary": "All apps with calls, destinations, opt-outs and sources", "responses": {"200": {"description": "OK", **j("#/components/schemas/AppList")}}}},
            "/apps/{id}.json": {"get": {"summary": "One app by id (ids listed in index.json)", "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                                        "responses": {"200": {"description": "OK", **j("#/components/schemas/App")}, "404": {"description": "unknown id"}}}},
            "/hosts.json": {"get": {"summary": "Destination host -> list of {app, type, default}", "responses": {"200": {"description": "OK"}}}},
            "/images.json": {"get": {"summary": "Container image name -> app id", "responses": {"200": {"description": "OK"}}}},
            "/blocklist.json": {"get": {"summary": "Safe-to-block hosts (telemetry, telemetry_and_updates, by_host)", "responses": {"200": {"description": "OK"}}}},
        },
        "components": {"schemas": {
            "AppList": {"type": "array", "items": {"$ref": "#/components/schemas/App"}},
            "App": {"type": "object", "required": ["id", "name", "status", "calls", "sources"], "properties": {
                "id": {"type": "string"}, "name": {"type": "string"}, "category": {"type": "string"}, "repo": {"type": "string"},
                "images": {"type": "array", "items": {"type": "string"}}, "verified": {"type": "string", "format": "date"},
                "status": {"type": "string", "enum": STATUS_ORDER}, "status_label": {"type": "string"},
                "env_optouts": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "string"}, "type": {"type": "string"}}}},
                "calls": {"type": "array", "items": {"$ref": "#/components/schemas/Call"}},
                "sources": {"type": "array", "items": {"type": "string", "format": "uri"}}, "notes": {"type": "string"}}},
            "Call": {"type": "object", "properties": {
                "type": {"type": "string", "enum": ["telemetry", "crash_report", "update_check", "external_asset", "cloud_feature"]},
                "default": {"type": "string", "enum": ["on", "off", "prompt"]},
                "destinations": {"type": "array", "items": {"type": "string"}}, "sends": {"type": "string"}, "frequency": {"type": "string"},
                "optout": {"type": "object", "properties": {k: {"type": "array", "items": {"type": "string"}} if k == "env" else {"type": "string"} for k in ("env", "config", "ui", "cli")}},
                "sources": {"type": "array", "items": {"type": "string"}}, "block": {"type": "boolean"}}}}}}

def main(out=None):
    out = out or os.path.join(ROOT, "dist")
    apps = load_apps()
    errs = [e for a in apps for e in validate(a)]
    if errs:
        print("\n".join(errs)); sys.exit(1)
    pub = sorted((public(a) for a in apps), key=lambda a: (STATUS_ORDER.index(a["status"]), a["name"].lower()))
    write(os.path.join(out, "apps.json"), json.dumps(pub, indent=1, ensure_ascii=False))
    write_api(out, pub, apps)
    tele = block_hosts(apps)
    tele_upd = block_hosts(apps, include_update_checks=True)
    for name, hosts in (("telemetry", tele), ("telemetry-and-updates", tele_upd)):
        write(os.path.join(out, "blocklists", f"{name}.hosts"), hosts_file(hosts, name + " (hosts format)", "hosts"))
        write(os.path.join(out, "blocklists", f"{name}.adguard.txt"), hosts_file(hosts, name + " (AdGuard Home / uBlock)", "adguard"))
        write(os.path.join(out, "blocklists", f"{name}.domains.txt"), hosts_file(hosts, name + " (plain domains for Pi-hole, Blocky, Technitium)", "domains"))
    from .site import render
    write(os.path.join(out, "index.html"), render(pub))
    counts = {s: sum(1 for a in pub if a["status"] == s) for s in STATUS_ORDER}
    print(f"{len(pub)} apps, {len(tele)} telemetry hosts, {len(tele_upd)} incl. update hosts ->", out)
    print(counts)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
