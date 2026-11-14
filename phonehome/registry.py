import os, re, glob, yaml

CALL_TYPES = {"telemetry", "crash_report", "update_check", "external_asset", "cloud_feature"}
DEFAULTS = {"on", "off", "prompt"}
STATUS_ORDER = ["telemetry-on", "prompt", "external", "update-check", "opt-in", "clean"]
STATUS_LABEL = {
    "telemetry-on": "Telemetry on by default",
    "prompt": "Asks on first run",
    "external": "Third-party requests by default",
    "update-check": "Update check only",
    "opt-in": "Telemetry is opt-in",
    "clean": "No outbound calls found",
}
HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


def data_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "apps")


def load_apps(path=None):
    path = path or data_dir()
    apps = []
    for f in sorted(glob.glob(os.path.join(path, "*.yaml"))):
        with open(f, encoding="utf-8") as fh:
            app = yaml.safe_load(fh)
        app["_file"] = os.path.basename(f)
        apps.append(app)
    return apps


def validate(app):
    errs = []
    fid = app.get("_file", "?")
    for k in ("id", "name", "category", "repo", "verified", "calls"):
        if k not in app:
            errs.append(f"{fid}: missing '{k}'")
    if "id" in app and app.get("_file") and app["_file"] != app["id"] + ".yaml":
        errs.append(f"{fid}: file name must match id '{app['id']}'")
    if not (app.get("calls") or []) and not app.get("sources"):
        errs.append(f"{fid}: an app with no calls needs top-level 'sources' showing where you looked")
    if not isinstance(app.get("images", []), list):
        errs.append(f"{fid}: images must be a list")
    for i, c in enumerate(app.get("calls") or []):
        where = f"{fid} calls[{i}]"
        if c.get("type") not in CALL_TYPES:
            errs.append(f"{where}: type must be one of {sorted(CALL_TYPES)}")
        if c.get("default") not in DEFAULTS:
            errs.append(f"{where}: default must be one of {sorted(DEFAULTS)}")
        for h in c.get("destinations") or []:
            if not HOST_RE.match(h):
                errs.append(f"{where}: bad hostname '{h}'")
        if not c.get("sources"):
            errs.append(f"{where}: needs at least one source URL")
        if not c.get("sends"):
            errs.append(f"{where}: needs 'sends'")
        if "block" in c and not isinstance(c["block"], bool):
            errs.append(f"{where}: block must be true/false")
        oo = c.get("optout") or {}
        if c.get("default") != "off" and not any(oo.get(k) for k in ("env", "config", "ui", "cli")):
            errs.append(f"{where}: default-on/prompt call needs an optout (env/config/ui/cli)")
        for e in oo.get("env") or []:
            if "=" not in e:
                errs.append(f"{where}: env opt-out '{e}' must look like NAME=value")
    return errs


def status_of(app):
    calls = app.get("calls") or []
    types_on = {c["type"] for c in calls if c.get("default") == "on"}
    if "telemetry" in types_on or "crash_report" in types_on:
        return "telemetry-on"
    if any(c.get("default") == "prompt" and c["type"] in ("telemetry", "crash_report") for c in calls):
        return "prompt"
    if "external_asset" in types_on or "cloud_feature" in types_on:
        return "external"
    if "update_check" in types_on:
        return "update-check"
    if any(c["type"] in ("telemetry", "crash_report") for c in calls):
        return "opt-in"
    return "clean"


def env_optouts(app):
    """All NAME=value env opt-outs for calls that are on/prompt by default."""
    out = []
    for c in app.get("calls") or []:
        if c.get("default") == "off":
            continue
        for e in (c.get("optout") or {}).get("env") or []:
            name, _, value = e.partition("=")
            value = value.split(" (")[0].strip()
            out.append({"name": name.strip(), "value": value, "type": c["type"]})
    return out


def blockable(call, host):
    """A host goes on a blocklist only when blocking it cannot break unrelated things:
    an explicit `block: true` on the call, or a dedicated subdomain (3+ labels) unless `block: false`."""
    b = call.get("block")
    if b is False:
        return False
    if b is True:
        return True
    return host.count(".") >= 2


def block_hosts(apps, include_update_checks=False):
    hosts = {}
    for app in apps:
        for c in app.get("calls") or []:
            if c.get("default") == "off":
                continue
            if c["type"] in ("telemetry", "crash_report") or (include_update_checks and c["type"] == "update_check"):
                for h in c.get("destinations") or []:
                    if blockable(c, h):
                        hosts.setdefault(h, set()).add(app["id"])
    return hosts
