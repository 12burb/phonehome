import sys,json,subprocess,time,urllib.parse
tok=subprocess.run(['gh','auth','token'],capture_output=True,text=True).stdout.strip()
def search(q,n=3):
    u='https://api.github.com/search/code?per_page=%d&q=%s'%(n,urllib.parse.quote(q))
    r=subprocess.run(['curl','-s','-H','Authorization: Bearer '+tok,'-H','Accept: application/vnd.github.text-match+json',u],capture_output=True,text=True).stdout
    try: d=json.loads(r)
    except Exception: print('ERR',q,r[:200]); return
    print('\n##',q,d.get('total_count'))
    for it in d.get('items',[]):
        print(' -',it['repository']['full_name'],it['path'])
        for m in it.get('text_matches',[])[:2]: print('    >',' '.join(m['fragment'].split())[:300])
    if 'message' in d: print('  MSG',d['message'])
for q in sys.argv[1:]:
    search(q); time.sleep(7)
