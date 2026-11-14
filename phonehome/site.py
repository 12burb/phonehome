"""Render the single-page static site (no build tools, no external requests)."""
import json, html, datetime
from .registry import STATUS_ORDER, STATUS_LABEL

CSS = """
:root{--bg:#0f1115;--fg:#e6e6e6;--mut:#9aa0a6;--card:#171a21;--line:#2a2f3a;--on:#ff6b6b;--prompt:#ffb347;--ext:#c084fc;--upd:#4fc3f7;--optin:#9ccc65;--clean:#66bb6a;--link:#8ab4f8}
@media (prefers-color-scheme: light){:root{--bg:#fafafa;--fg:#1b1b1b;--mut:#5f6368;--card:#fff;--line:#e0e0e0;--link:#1a56db}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg)}
a{color:var(--link)}main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
header h1{margin:0 0 4px;font-size:28px}header p{margin:0;color:var(--mut)}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;cursor:pointer}
.stat b{display:block;font-size:22px}.stat.active{outline:2px solid var(--link)}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 18px}input,select{font:inherit;padding:8px 10px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
input{flex:1;min-width:220px}
.card{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--line);border-radius:8px;padding:14px 16px;margin:10px 0}
.card.telemetry-on{border-left-color:var(--on)}.card.prompt{border-left-color:var(--prompt)}.card.external{border-left-color:var(--ext)}.card.update-check{border-left-color:var(--upd)}.card.opt-in{border-left-color:var(--optin)}.card.clean{border-left-color:var(--clean)}
.card h2{margin:0;font-size:18px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}.card h2 small{color:var(--mut);font-weight:normal;font-size:13px}
.badge{display:inline-block;font-size:12px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--mut)}
.badge.telemetry-on{color:var(--on);border-color:var(--on)}.badge.prompt{color:var(--prompt);border-color:var(--prompt)}.badge.external{color:var(--ext);border-color:var(--ext)}.badge.update-check{color:var(--upd);border-color:var(--upd)}.badge.opt-in,.badge.clean{color:var(--clean);border-color:var(--clean)}
.call{margin:10px 0 0;padding:10px 12px;border:1px solid var(--line);border-radius:6px}.call .t{font-weight:600}.call .d{color:var(--mut);font-size:13px}
code,pre{font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:rgba(127,127,127,.12);border-radius:4px}code{padding:1px 5px}pre{padding:8px 10px;overflow:auto;margin:6px 0 0;white-space:pre-wrap}
.row{display:flex;gap:16px;flex-wrap:wrap;margin-top:6px}.row>div{flex:1;min-width:240px}
.srcs{font-size:12px;color:var(--mut);margin-top:6px;word-break:break-all}.notes{color:var(--mut);font-size:13px;margin-top:8px}
.dl{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 0}.dl a{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 10px;text-decoration:none;font-size:13px}
footer{color:var(--mut);font-size:13px;margin-top:40px;border-top:1px solid var(--line);padding-top:12px}
.hidden{display:none}.empty{color:var(--mut);padding:20px;text-align:center}
.copy{font-size:12px;cursor:pointer;margin-left:6px;background:none;border:1px solid var(--line);color:var(--mut);border-radius:4px;padding:1px 6px}
"""

JS = r"""
const apps = JSON.parse(document.getElementById('data').textContent);
const LABEL = __LABELS__;
const TYPE = {telemetry:'Usage telemetry',crash_report:'Crash / error reports',update_check:'Update check',external_asset:'Third-party asset',cloud_feature:'Vendor cloud feature'};
const DEF = {on:'on by default',off:'off by default (opt-in)',prompt:'asked on first run'};
const esc = s => String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let status='all', q='', cat='all';
function optout(o){ if(!o) return ''; let h='';
  if(o.env&&o.env.length) h+='<div><div class="d">Environment</div><pre>'+o.env.map(esc).join('\n')+'</pre></div>';
  if(o.config) h+='<div><div class="d">Config</div><pre>'+esc(o.config)+'</pre></div>';
  if(o.cli) h+='<div><div class="d">CLI</div><pre>'+esc(o.cli)+'</pre></div>';
  if(o.ui) h+='<div><div class="d">UI</div><div>'+esc(o.ui)+'</div></div>';
  return '<div class="row">'+h+'</div>'; }
function card(a){
  const calls=(a.calls||[]).map(c=>`<div class="call"><span class="t">${esc(TYPE[c.type]||c.type)}</span> <span class="badge ${c.default==='on'?(c.type==='telemetry'||c.type==='crash_report'?'telemetry-on':'external'):(c.default==='prompt'?'prompt':'opt-in')}">${esc(DEF[c.default]||c.default)}</span>
    ${c.destinations&&c.destinations.length?'<span class="d"> → '+c.destinations.map(esc).join(', ')+'</span>':''}
    <div>${esc(c.sends)}${c.frequency?' <span class="d">('+esc(c.frequency)+')</span>':''}</div>
    ${c.default==='off'?'':optout(c.optout)}
    <div class="srcs">Sources: ${(c.sources||[]).map(s=>'<a href="'+esc(s)+'" target="_blank" rel="noopener">'+esc(s.replace(/^https?:\/\//,''))+'</a>').join(' · ')}</div></div>`).join('');
  const envs=(a.env_optouts||[]).map(e=>e.name+'='+e.value);
  return `<article class="card ${a.status}" id="${esc(a.id)}"><h2>${esc(a.name)} <span class="badge ${a.status}">${esc(a.status_label)}</span> <small>${esc(a.category)} · <a href="${esc(a.repo)}" target="_blank" rel="noopener">repo</a> · verified ${esc(a.verified)}</small></h2>
    ${envs.length?'<div class="d" style="margin-top:6px">Quick opt-out: <code>'+envs.map(esc).join('</code> <code>')+'</code><button class="copy" data-c="'+esc(envs.join('\n'))+'">copy</button></div>':''}
    ${calls||'<div class="notes">No outbound calls recorded.'+((a.sources&&a.sources.length)?' Checked: '+a.sources.map(s=>'<a href="'+esc(s)+'" target="_blank" rel="noopener">'+esc(decodeURIComponent(s).replace(/^https?:\/\//,''))+'</a>').join(' · '):'')+'</div>'}
    ${a.notes?'<div class="notes">'+esc(a.notes)+'</div>':''}</article>`; }
function render(){
  const list=document.getElementById('list'); const qq=q.trim().toLowerCase();
  const shown=apps.filter(a=>(status==='all'||a.status===status)&&(cat==='all'||a.category===cat)&&(!qq||(a.name+' '+a.id+' '+(a.images||[]).join(' ')+' '+a.category).toLowerCase().includes(qq)));
  list.innerHTML=shown.map(card).join('')||'<div class="empty">No apps match. Missing one? Open an issue or PR.</div>';
  document.getElementById('count').textContent=shown.length+' of '+apps.length+' apps';
  document.querySelectorAll('.stat').forEach(s=>s.classList.toggle('active',s.dataset.s===status));
  list.querySelectorAll('.copy').forEach(b=>b.onclick=()=>{navigator.clipboard.writeText(b.dataset.c);b.textContent='copied';setTimeout(()=>b.textContent='copy',1200);});
}
document.querySelectorAll('.stat').forEach(s=>s.onclick=()=>{status=s.dataset.s;render();});
document.getElementById('q').oninput=e=>{q=e.target.value;render();};
document.getElementById('cat').onchange=e=>{cat=e.target.value;render();};
render();
if(location.hash){const el=document.querySelector(location.hash);if(el)el.scrollIntoView();}
"""

def render(apps):
    today = datetime.date.today().isoformat()
    counts = {s: sum(1 for a in apps if a["status"] == s) for s in STATUS_ORDER}
    cats = sorted({a["category"] for a in apps})
    stats = f'<div class="stat" data-s="all"><b>{len(apps)}</b>apps</div>' + "".join(
        f'<div class="stat" data-s="{s}"><b>{counts[s]}</b>{html.escape(STATUS_LABEL[s])}</div>' for s in STATUS_ORDER if counts[s])
    opts = '<option value="all">All categories</option>' + "".join(f'<option>{html.escape(c)}</option>' for c in cats)
    data = json.dumps(apps, ensure_ascii=False).replace("</", "<\\/")
    js = JS.replace("__LABELS__", json.dumps(STATUS_LABEL))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>phonehome - does your self-hosted app phone home?</title><meta name="description" content="Verified registry of telemetry, update checks and third-party requests in self-hosted apps, with the exact opt-out for each."><style>{CSS}</style></head>
<body><main><header><h1>Does it phone home?</h1><p>What each self-hosted app sends out of your network by default, and the exact switch that turns it off. Every entry links to the source code or documentation it was verified against. Generated {today}.</p></header>
<div class="stats">{stats}</div>
<div class="controls"><input id="q" type="search" placeholder="Search apps, images, categories…" aria-label="Search"><select id="cat" aria-label="Category">{opts}</select><span id="count" style="align-self:center;color:var(--mut)"></span></div>
<div class="dl"><span style="align-self:center;color:var(--mut)">Blocklists:</span>
<a href="blocklists/telemetry.hosts">telemetry.hosts</a><a href="blocklists/telemetry.adguard.txt">telemetry.adguard.txt</a><a href="blocklists/telemetry.domains.txt">telemetry.domains.txt (Pi-hole)</a>
<a href="blocklists/telemetry-and-updates.hosts">+update checks (hosts)</a><a href="blocklists/telemetry-and-updates.adguard.txt">+update checks (AdGuard)</a><a href="blocklists/telemetry-and-updates.domains.txt">+update checks (domains)</a><a href="apps.json">apps.json</a></div>
<p style="color:var(--mut);font-size:13px">Audit your own stack: <code>pipx run phonehome audit docker-compose.yml</code> prints the opt-out variables your services are missing. Blocking telemetry hosts at DNS is a second layer; some apps retry or log errors when blocked, so prefer the opt-out switch.</p>
<div id="list"></div>
<footer>Status is derived from the recorded calls: anything that sends usage or crash data without being asked is “telemetry on by default”; apps that only fetch version information are “update check only”; “third-party requests” covers things like Gravatar or vendor-hosted map tiles that leak metadata but are not usage telemetry. Entries describe defaults in the upstream Docker image or default config at the verified date; your distribution or Helm chart may differ. Corrections and additions: open a pull request against <code>data/apps/</code>. Not affiliated with any listed project.</footer>
</main><script id="data" type="application/json">{data}</script><script>{js}</script></body></html>"""
