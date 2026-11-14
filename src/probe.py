import sys,re,html,subprocess
def fetch(u):
    b=subprocess.run(['curl','-sL','-m','30','-A','Mozilla/5.0 (phonehome-research)',u],capture_output=True).stdout.decode('utf-8','ignore')
    if not b or len(b)<40: raise Exception('empty/short '+str(len(b)))
    if re.match(r'\s*(404|Not Found)',b): raise Exception('404')
    b=re.sub(r'<script.*?</script>|<style.*?</style>','',b,flags=re.S)
    t=re.sub(r'<[^>]+>',' ',b); t=html.unescape(t); t=re.sub(r'[ \t]+',' ',t); t=re.sub(r'\n\s*\n+','\n',t)
    return t
def grep(t,pat,ctx=200,maxn=6):
    out=[];last=-10**9
    for m in re.finditer(pat,t,re.I):
        if m.start()-last<ctx: continue
        last=m.start()
        s=max(0,m.start()-ctx); e=min(len(t),m.end()+ctx)
        out.append(' '.join(t[s:e].split()))
        if len(out)>=maxn: break
    return out
if __name__=='__main__':
    u=sys.argv[1]; pat=None
    if '|||' in u: u,pat=u.split('|||',1)
    if pat is None: pat=r'telemetry|analytics|anonymous|usage (data|statistic|report)|phone home|opt[- ]?out|DO_NOT_TRACK|update check|check for update'
    try: t=fetch(u)
    except Exception as e: print('ERR',u,e); sys.exit()
    print('==',u,len(t))
    for g in grep(t,pat): print(' *',g[:420])
