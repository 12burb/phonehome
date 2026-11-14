# phonehome project status (scratch for Devin)
- Project at ~/research/phonehome (git initialized on main, 1 commit). Remote not yet created: waiting for user to click the propose_new_repo card "phonehome" (owner 12burb). After creation: git remote add origin, push main, enable Pages (Settings > Pages > Source: GitHub Actions).
- Build: python3 -m phonehome.build ; tests: python3 -m pytest -q ; CLI: python3 -m phonehome.cli audit <compose>
- Data: data/apps/*.yaml (67 apps). Validator in phonehome/registry.py. Site in phonehome/site.py (vanilla JS). Blocklists only include hosts with >=2 dots unless block: true.
- Research helpers: src/probe.py (curl+grep), src/batch.sh (stdin URL|||pattern), src/ghs.py (GitHub code search, 10/min limit).
- Still unverified/not added: GitLab service ping, Synapse report_stats, Portainer telemetry default, Ghost update check, Plausible/Pi-hole/AdGuard clean entries, memos/miniflux/audiobookshelf.
