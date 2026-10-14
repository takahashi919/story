import re,pathlib
D=pathlib.Path('/home/user/story/notes/第0部骨組み案/解説')
log=[]
def load(n): return (D/f'script_{n}.md').read_text(encoding='utf-8').split('\n')
def save(n,lines): (D/f'script_{n}.md').write_text('\n'.join(lines),encoding='utf-8')
def bounds(lines):
    hs=[i for i,l in enumerate(lines) if re.match(r'^## S\d+｜',l)]
    out={}
    for k,h in enumerate(hs):
        n=int(re.match(r'^## S(\d+)',lines[h]).group(1))
        end=hs[k+1] if k+1<len(hs) else len(lines)
        nar=next(i for i in range(h,end) if lines[i].startswith('【ナレーション】'))
        out[n]=(h,nar+1,end)
    return out
def quotes(s):
    a=s.find('「');b=s.rfind('」')
    return s[a+1:b] if a>=0 and b>a else None

def bullets(chk,sec_pat):
    t=(D/chk).read_text(encoding='utf-8')
    m=re.search(sec_pat,t,re.S|re.M)
    return t[m.start():] if m else ''

# ---------- A
lines=load('A');chk=bullets('check_A.md',r'^## 追記すべき文')
# (1) line replacements
reps=[]
for l in chk.split('\n'):
    m=re.match(r'^- S(\d+) L(\d+)(?:〜(\d+))?[:：]\s*(.*)$',l)
    if m and '「' in l and '削除' not in l:
        new=quotes(m.group(4));
        if new: reps.append((int(m.group(2)),int(m.group(3) or m.group(2)),new))
    m2=re.match(r'^- S(\d+) L(\d+)／S(\d+) L(\d+)[:：]',l)
    if m2:
        new=quotes(l.split('：',1)[1] if '：' in l else l)
        if new: reps.append((int(m2.group(2)),int(m2.group(2)),new));reps.append((int(m2.group(4)),int(m2.group(4)),new))
for a,b,new in reps:
    if lines[a-1].strip() and not lines[a-1].startswith(('#','【','-')):
        lines[a-1]=new
        for k in range(a,b): lines[k]=''
    else: log.append(f'A line {a} not narration: {lines[a-1][:30]}')
# (2) appends
bd=bounds(lines);app={}
for l in chk.split('\n'):
    m=re.match(r'^- S(\d+)[^「]*[:：]\s*「(.+)」\s*$',l)
    if m and not re.search(r'L\d+',l.split('「')[0]): app.setdefault(int(m.group(1)),[]).append(m.group(2))
    elif l.startswith('- S') and 'L' not in l.split('：')[0]: log.append('A skip: '+l[:60])
for n in sorted(app,reverse=True):
    if n not in bd: log.append(f'A no section {n}');continue
    h,ns,e=bd[n]
    k=e
    while k>ns and not lines[k-1].strip(): k-=1
    lines[k:k]=['']+['\n'.join(app[n])] if False else ['']+app[n]
save('A',lines)

# ---------- B
lines=load('B');chk=bullets('check_B.md',r'^## 追記すべき文')
def sent_replace(lines,n,kw,new,all_=False):
    bd=bounds(lines);h,ns,e=bd[n];done=False
    for i in range(ns,e):
        if kw in lines[i]:
            parts=re.split(r'(?<=[。])',lines[i]);out=[];hit=False
            for p in parts:
                if kw in p and not (hit and not all_): out.append(new if not hit else '');hit=True
                else: out.append(p)
            lines[i]=''.join(out);done=True
            if not all_: break
    if not done: log.append(f'B sent_replace miss S{n} {kw}')
sent_replace(lines,6,'伏せたまま','第十五話では、陽子が一度、写真立てを起こして集合写真を差し込みます。そのあと博之が夜中に倒し、朝は伏せたままです。第十六話で、博之が自分の手で起こします。')
lines=[x.replace('起こされたままの写真立て','伏せたままの写真立て') for x in lines] if False else lines
bd=bounds(lines)
h,ns,e=bd[39]
for i in range(ns,e): lines[i]=lines[i].replace('起こされたままの写真立て','伏せたままの写真立て')
sent_replace(lines,46,'起こされたまま','二つ目は、夜中に博之が倒して、伏せたままの写真立てです。')
sent_replace(lines,22,'露見','陽子は九話から知っています。ここで起きるのは、博之の嘘が、陽子の前で声に出されることです。')
for n in (25,26):
    h,ns,e=bounds(lines)[n]
    for i in range(ns,e): lines[i]=lines[i].replace('陽子の側に露見','陽子の前で言葉になる').replace('陽子に露見','陽子の前で言葉になる')
sent_replace(lines,46,'朝のタッパー','第十六話は八月二日。雨の中の大規模戦で、午後三時十二分に陽子の信号が消えます。引きは、超巨大の接近警報です。朝のタッパー十個と、いない陽子は、この第十五話の引きです。')
sent_replace(lines,46,'第0部のヤマト','第0部のヤマトは、試作を一発撃つことと、試験場跡の裂け目をどう扱うかが未決です。第1部八月五日の断層と同じものかも、決まっていません。')
sent_replace(lines,12,'救えなかった','囮部隊は十一人で、生きて戻るのは白石を含めて三人です。壕の中で返事をしなかった二人の扱いは、骨組みでも数字を言わない書き方で、死者か生存者かは本文にするときに決めます。')
app={}
for l in chk.split('\n'):
    if re.search(r'置き換え|直す|置換|→',l) : continue
    m=re.match(r'^\s*- (?:[A-Z]\d*\s+)?(?:F\d+\s+)?S(\d+)[^「]*[:：]?\s*「(.+)」\s*$',l)
    if m: app.setdefault(int(m.group(1)),[]).append(m.group(2))
# multi-line bullets: head line then quote on next line
txt=chk.split('\n')
for i,l in enumerate(txt[:-1]):
    m=re.match(r'^- ([A-Z]\d+) (?:S(\d+))[^「]*[:：]\s*$',l)
    if m and '置き換え' not in l and '直す' not in l and txt[i+1].strip().startswith('「'):
        app.setdefault(int(m.group(2)),[]).append(quotes(txt[i+1]))
bd=bounds(lines)
for n in sorted(app,reverse=True):
    if n not in bd: log.append(f'B no section {n}');continue
    h,ns,e=bd[n];k=e
    while k>ns and not lines[k-1].strip(): k-=1
    lines[k:k]=['']+app[n]
save('B',lines)

# ---------- C
lines=load('C');chk=bullets('check_C.md',r'^## 追記すべき文')
bd=bounds(lines)
sec=chk.split('### ★の抜け')[0]
for l in sec.split('\n'):
    m=re.match(r'^- (S\d+)[^「]*「(.+?)」→「(.+)」',l)
    if not m: continue
    n=int(m.group(1)[1:]);old=m.group(2);new=m.group(3)
    pat='.*?'.join(re.escape(x) for x in old.replace('...','…').split('…') if x)
    h,ns,e=bounds(lines)[n];blk='\n'.join(lines[ns:e])
    if re.search(pat,blk,re.S):
        blk=re.sub(pat,lambda _:new,blk,count=1,flags=re.S);lines[ns:e]=blk.split('\n')
    else: log.append(f'C miss S{n}: {old[:30]}')
app={}
rest=chk.split('### ★の抜け')[1].split('### 音声合成')[0]
for l in rest.split('\n'):
    m=re.match(r'^- S(\d+)[^「]*[:：]\s*「(.+)」',l)
    if m: app.setdefault(int(m.group(1)),[]).append(m.group(2))
bd=bounds(lines)
for n in sorted(app,reverse=True):
    if n not in bd: log.append(f'C no section {n}');continue
    h,ns,e=bd[n];k=e
    while k>ns and not lines[k-1].strip(): k-=1
    lines[k:k]=['']+app[n]
save('C',lines)
print('\n'.join(log) or 'no skips')
