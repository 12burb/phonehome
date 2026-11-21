"""phonehome CLI: audit a docker-compose file, list apps, show one app."""
import argparse, os, sys, json, re, yaml
from .registry import load_apps, validate, status_of, env_optouts, STATUS_LABEL

def norm_image(img):
    img = str(img).strip().lower()
    img = img.split("@")[0]
    # strip tag (but not registry port)
    name, _, tag = img.rpartition(":")
    if name and "/" not in tag:
        img = name
    if img.startswith("docker.io/"):
        img = img[len("docker.io/"):]
    if img.startswith("library/"):
        img = img[len("library/"):]
    return img

def match_app(image, apps):
    n = norm_image(image)
    for app in apps:
        for pat in app.get("images") or []:
            p = norm_image(pat)
            if n == p or n.endswith("/" + p) or (p.startswith("docker.io/") and n == p[10:]):
                return app
    return None

def env_of(service, compose_dir):
    env = {}
    files = service.get("env_file") or []
    if isinstance(files, (str, dict)):
        files = [files]
    for f in files:
        path = f["path"] if isinstance(f, dict) else f
        path = os.path.join(compose_dir, path)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip().strip('"').strip("'")
    e = service.get("environment") or {}
    if isinstance(e, list):
        for item in e:
            k, _, v = str(item).partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    else:
        for k, v in e.items():
            env[str(k).strip()] = "" if v is None else str(v).strip()
    return env

def same_value(actual, wanted):
    a, w = actual.strip().lower(), wanted.strip().lower()
    truthy = {"true", "1", "yes", "on"}
    falsy = {"false", "0", "no", "off"}
    if a == w:
        return True
    if a in truthy and w in truthy:
        return True
    if a in falsy and w in falsy:
        return True
    return False

def audit_compose(compose, apps, compose_dir="."):
    """Audit a parsed docker-compose mapping; returns a JSON-able report (one entry per service with an image)."""
    services = (compose or {}).get("services") or {}
    report = []
    for sname, svc in services.items():
        image = (svc or {}).get("image")
        if not image:
            continue
        app = match_app(image, apps)
        if not app:
            report.append({"service": sname, "image": image, "app": None})
            continue
        env = env_of(svc, compose_dir)
        findings = []
        for call in app.get("calls") or []:
            if call.get("default") == "off":
                continue
            oo = call.get("optout") or {}
            envs = oo.get("env") or []
            fixable = [e for e in envs if "=" in e]
            if fixable:
                ok = False
                for e in fixable:
                    name, _, value = e.partition("=")
                    value = value.split(" (")[0].strip()
                    if name.strip() in env and same_value(env[name.strip()], value):
                        ok = True
                findings.append({"type": call["type"], "default": call["default"], "destinations": call.get("destinations") or [],
                                 "fixed": ok, "fix_env": [f.split(" (")[0] for f in fixable]})
            else:
                findings.append({"type": call["type"], "default": call["default"], "destinations": call.get("destinations") or [],
                                 "fixed": None, "fix_config": oo.get("config"), "fix_ui": oo.get("ui"), "fix_cli": oo.get("cli")})
        report.append({"service": sname, "image": image, "app": app["id"], "name": app["name"], "status": status_of(app), "findings": findings})
    return report

def format_report(report):
    """Human-readable audit text and exit code (2 = a default-on call has no opt-out set)."""
    exit_code, lines = 0, []
    for r in report:
        if not r["app"]:
            lines.append(f"  {r['service']:<22} {r['image']}  (not in registry)")
            continue
        lines.append(f"\n{r['service']}  ({r['name']}, {STATUS_LABEL[r['status']]})")
        if not r["findings"]:
            lines.append("   no default-on outbound calls recorded")
        for f in r["findings"]:
            dest = ", ".join(f["destinations"]) or "-"
            if f["fixed"] is True:
                lines.append(f"   [ok]   {f['type']:<14} -> {dest}  (opt-out env present)")
            elif f["fixed"] is False:
                exit_code = 2
                lines.append(f"   [MISS] {f['type']:<14} -> {dest}")
                lines.append(f"          add: {' or '.join(f['fix_env'])}")
            else:
                lines.append(f"   [info] {f['type']:<14} -> {dest}  (no env switch; " + "; ".join(x for x in (f.get('fix_config'), f.get('fix_ui'), f.get('fix_cli')) if x) + ")")
    return "\n".join(lines) + "\n", exit_code

def audit(path, apps, as_json=False):
    with open(path, encoding="utf-8") as fh:
        compose = yaml.safe_load(fh) or {}
    report = audit_compose(compose, apps, os.path.dirname(os.path.abspath(path)))
    if as_json:
        print(json.dumps(report, indent=1))
        return 0
    text, code = format_report(report)
    print(text)
    return code

def main(argv=None):
    p = argparse.ArgumentParser(prog="phonehome", description="Does your self-hosted stack phone home?")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audit", help="check a docker-compose.yml for missing telemetry opt-outs")
    a.add_argument("compose", nargs="?", default="docker-compose.yml")
    a.add_argument("--json", action="store_true")
    sub.add_parser("list", help="list all apps in the registry")
    s = sub.add_parser("show", help="show one app")
    s.add_argument("id")
    sub.add_parser("validate", help="validate the dataset")
    args = p.parse_args(argv)
    apps = load_apps()
    if args.cmd == "validate":
        errs = [e for app in apps for e in validate(app)]
        print("\n".join(errs) if errs else f"{len(apps)} apps OK")
        return 1 if errs else 0
    if args.cmd == "list":
        for app in sorted(apps, key=lambda x: x["name"].lower()):
            print(f"{app['id']:<16} {STATUS_LABEL[status_of(app)]:<34} {app['name']}")
        return 0
    if args.cmd == "show":
        for app in apps:
            if app["id"] == args.id:
                print(yaml.safe_dump({k: v for k, v in app.items() if not k.startswith('_')}, sort_keys=False, allow_unicode=True, width=100))
                return 0
        print("unknown app", args.id); return 1
    if args.cmd == "audit":
        return audit(args.compose, apps, args.json)

if __name__ == "__main__":
    sys.exit(main())
