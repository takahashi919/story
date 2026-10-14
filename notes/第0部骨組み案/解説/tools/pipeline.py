import re,sys,os,json,hashlib,subprocess,time,html,pathlib,concurrent.futures as cf,urllib.request,urllib.error
SC=pathlib.Path('/home/user/story/notes/第0部骨組み案/解説')
W=pathlib.Path(__file__).parent
VOICE=os.environ.get('VOICE','bfd988b9cf6a45b1a9fcaf915cedb558')
CACHE=W/'cache';CACHE.mkdir(exist_ok=True)
CHROME='/opt/pw-browsers/chromium-1194/chrome-linux/chrome'

def parse():
    secs=[]
    for f in ['script_A.md','script_B.md','script_C.md']:
        t=(SC/f).read_text(encoding='utf-8')
        for m in re.finditer(r'^## S(\d+)｜(.+?)\n【スライド】\n(.*?)【ナレーション】\n(.*?)(?=^## S|\Z)',t,re.S|re.M):
            slide=[l[2:].strip() for l in m.group(3).strip().split('\n') if l.startswith('- ')]
            narr=m.group(4).strip()
            secs.append(dict(src=f,num=m.group(1),title=m.group(2).strip(),slide=slide,narr=narr))
    # groups
    g='00_全体概要';gs=[]
    for s in secs:
        m=re.match(r'第(\d+)話[ 　]',s['title'])
        if m: g=f"{int(m.group(1)):02d}"
        elif s['title'].startswith('結末の総ざらい'): g='91_総括1_結末'
        elif s['title'].startswith('フラグ台帳の総ざらい') and not g.startswith('92'): g='92_総括2_フラグ台帳'
        elif s['title'].startswith('canonに入れる案'): g='93_総括3_canonと要決定'
        s['group']=g
    return secs


KANA=[('斑鳩巌','いかるがいわお'),('斑鳩','いかるが'),('成瀬','なるせ'),('白石','しらいし'),('博之','ひろゆき'),('陽子','ようこ'),('海魔','かいま'),('東雲','しののめ'),('三枝','さえぐさ'),('皇征弦','すめらぎせいげん'),('征弦','せいげん'),('皇さん','すめらぎさん'),('皇','すめらぎ'),('川崎慶一郎','かわさきけいいちろう'),('慶一郎','けいいちろう'),('洋一','よういち'),('黒田','くろだ'),('勝浦','かつうら'),('砥石','といし'),('泥纏い','どろまとい'),('涵洞','かんどう'),('荒砥','あらと'),('尺骨','しゃっこつ'),('頸椎','けいつい'),('胸椎','きょうつい'),('掌紋','しょうもん'),('縫合','ほうごう'),('檻','おり'),('嘔吐','おうと'),('canon','カノン'),('Canon','カノン')]
def kan(n):
    d='零一二三四五六七八九';u=['','十','百','千']
    def f4(x):
        r=''
        for i,c in enumerate(str(x).zfill(4)):
            v=int(c);pos=3-i
            if v==0: continue
            r+=('' if (v==1 and pos>0) else d[v])+u[pos]
        return r
    if n==0: return '零'
    parts=[];units=['','万','億']
    k=0
    while n>0:
        q=n%10000;n//=10000
        if q: parts.append(f4(q)+units[k])
        k+=1
    return ''.join(reversed(parts))
def norm(t):
    t=t.replace('★','').replace('☆','').replace('【','「').replace('】','」')
    t=re.sub(r'[—―─－ー]{2,}|——','、',t); t=t.replace('……','、').replace('…','、')
    t=re.sub(r'(\d{1,2})/(\d{1,2})',r'\1月\2日',t)
    t=re.sub(r'(\d{1,2}):(\d{2})',lambda m:f'{int(m.group(1))}時{int(m.group(2))}分',t)
    t=t.replace('%','パーセント').replace('％','パーセント')
    t=re.sub(r'\d{1,3}(?:,\d{3})+',lambda m:kan(int(m.group(0).replace(',',''))),t)
    t=re.sub(r'(?<![\d.])(\d{5,})(?![\d.])',lambda m:kan(int(m.group(0))),t)
    for a,b in KANA: t=t.replace(a,b)
    return t

def split_chunks(text,limit=230):
    text=norm(text)
    sents=[x for x in re.split(r'(?<=[。！？])',re.sub(r'\n+','\n',text)) if x.strip()]
    chunks=[];cur=''
    for s in sents:
        s=s.strip()
        if len(cur)+len(s)>limit and cur:
            chunks.append(cur);cur=s
        else: cur+=('' if not cur or cur.endswith('\n') else '')+s
    if cur: chunks.append(cur)
    return [c.replace('\n','、') if False else c.replace('\n','') for c in chunks]

def key(): return os.environ.get('FISH_KEY')
def tts(text):
    h=hashlib.sha1((VOICE+text).encode()).hexdigest()
    p=CACHE/f'{h}.mp3'
    if p.exists() and p.stat().st_size>1000: return p
    body=json.dumps({'text':text,'reference_id':VOICE,'format':'mp3','mp3_bitrate':64,'latency':'normal'}).encode()
    for att in range(6):
        try:
            r=urllib.request.Request('https://api.fish.audio/v1/tts',data=body,headers={'Content-Type':'application/json','model':'s2.1-pro-free'})
            with urllib.request.urlopen(r,timeout=180) as resp: data=resp.read()
            if len(data)>1000: p.write_bytes(data);return p
        except urllib.error.HTTPError as e:
            msg=e.read()[:200]
            if e.code==402: raise SystemExit('402 credit! '+str(msg))
            if e.code in (429,500,502,503,504): time.sleep(4*(att+1));continue
            raise SystemExit(f'HTTP {e.code} {msg}')
        except Exception as e:
            time.sleep(4*(att+1))
    raise SystemExit('tts failed: '+text[:30])

def dur(p): return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)]).decode().strip())

def silence(sec,path):
    if not path.exists(): subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','anullsrc=r=44100:cl=mono','-t',str(sec),'-c:a','libmp3lame','-b:a','64k',str(path)],check=True)

def concat(files,out):
    lst=out.with_suffix('.txt');lst.write_text(''.join(f"file '{f}'\n" for f in files))
    subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(lst),'-c:a','libmp3lame','-b:a','64k','-ar','44100','-ac','1',str(out)],check=True)

def audio_section(s,idx):
    out=W/'sec'/f'{idx:03d}.mp3';out.parent.mkdir(exist_ok=True)
    chunks=split_chunks(s['narr'])
    with cf.ThreadPoolExecutor(2) as ex: ps=list(ex.map(tts,chunks))
    sil=W/'sil_0.35.mp3';silence(0.35,sil)
    files=[]
    for i,p in enumerate(ps):
        files.append(p)
        if i<len(ps)-1: files.append(sil)
    concat(files,out)
    return out

def slide_html(s,gtitle,idx,total):
    li=''.join(f'<li>{html.escape(x)}</li>' for x in s['slide'])
    return f'''<!doctype html><meta charset=utf-8><style>
body{{margin:0;width:1280px;height:720px;background:#14161b;color:#e9e9ee;font-family:"IPAPGothic","IPAGothic",sans-serif;position:relative;overflow:hidden}}
.top{{position:absolute;top:28px;left:56px;right:56px;font-size:22px;color:#9aa3b5;display:flex;justify-content:space-between}}
h1{{position:absolute;top:80px;left:56px;right:56px;margin:0;font-size:44px;line-height:1.25;border-left:10px solid #c0503c;padding-left:22px}}
ul{{position:absolute;top:240px;left:80px;right:80px;margin:0;padding:0;list-style:none}}
li{{font-size:34px;line-height:1.5;margin-bottom:10px;padding-left:34px;position:relative}}
li:before{{content:"";position:absolute;left:0;top:20px;width:12px;height:12px;background:#c0503c}}
.bar{{position:absolute;bottom:0;left:0;height:8px;background:#c0503c;width:{100*idx/total:.1f}%}}
</style><div class=top><span>報復のツァラトゥストラ 第0部 骨組み③（齊藤統合案）解説</span><span>{html.escape(gtitle)}　{idx}/{total}</span></div>
<h1>{html.escape(s['title'])}</h1><ul>{li}</ul><div class=bar></div>'''

def render_slide(s,gtitle,idx,total):
    png=W/'slides'/f'{idx:03d}.png';png.parent.mkdir(exist_ok=True)
    h=W/'slides'/f'{idx:03d}.html';h.write_text(slide_html(s,gtitle,idx,total),encoding='utf-8')
    subprocess.run([CHROME,'--headless','--no-sandbox','--disable-gpu','--hide-scrollbars','--window-size=1280,720',f'--screenshot={png}',f'file://{h}'],capture_output=True)
    return png

def gtitle(g,secs):
    first=next(s for s in secs if s['group']==g)
    return first['title'] if re.match(r'第\d+話',first['title']) else {'00_全体概要':'全体概要','91_総括1_結末':'総括 結末','92_総括2_フラグ台帳':'総括 フラグ台帳','93_総括3_canonと要決定':'総括 canonと要決定'}.get(g,g)

if __name__=='__main__':
    secs=parse()
    only=sys.argv[1] if len(sys.argv)>1 else None
    print(len(secs),'sections',sum(len(s['narr']) for s in secs),'chars')
    groups=sorted({s['group'] for s in secs})
    print(groups)
    if only=='parse': sys.exit()
    sel=[(i,s) for i,s in enumerate(secs) if (only in (None,'all') or s['group'] in only.split(',') or only=='first1' and i==0)]
    meta=[]
    for i,s in sel:
        a=audio_section(s,i);d=dur(a)
        png=render_slide(s,gtitle(s['group'],secs),i+1,len(secs))
        meta.append(dict(i=i,group=s['group'],title=s['title'],audio=str(a),png=str(png),dur=d))
        print(i,s['title'],round(d,1),flush=True)
    (W/f'meta_{(only or "all")[:20].replace(",","_")}.json').write_text(json.dumps(meta,ensure_ascii=False,indent=1))
