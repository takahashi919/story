import json,glob,subprocess,pathlib,re,sys
W=pathlib.Path(__file__).parent
metas=[]
for f in glob.glob(str(W/'meta_*.json')):
    if 'first1' in f: continue
    metas+=json.load(open(f))
metas.sort(key=lambda m:m['i'])
assert [m['i'] for m in metas]==list(range(161)),len(metas)
out=W/'out';out.mkdir(exist_ok=True)
sil=W/'sil_0.8.mp3'
if not sil.exists(): subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','anullsrc=r=44100:cl=mono','-t','0.8','-c:a','libmp3lame','-b:a','64k',str(sil)],check=True)
names={'00_全体概要':'00_全体概要','91_総括1_結末':'91_総括1_結末','92_総括2_フラグ台帳':'92_総括2_フラグ台帳','93_総括3_canonと要決定':'93_総括3_canonと要決定'}
groups={}
for m in metas: groups.setdefault(m['group'],[]).append(m)
def title(g):
    if re.fullmatch(r'\d\d',g):
        t=groups[g][0]['title'];return f'第{int(g):02d}話_'+re.sub(r'^第\d+話[ 　]*','',t).replace('/','・')
    return names[g]
allfiles=[]
for g in sorted(groups):
    ms=groups[g];name=title(g)
    # audio
    lst=out/f'{g}.txt'
    lst.write_text(''.join(f"file '{m['audio']}'\nfile '{sil}'\n" for m in ms))
    mp3=out/f'解説_{name}.mp3'
    subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(lst),'-c:a','libmp3lame','-b:a','64k','-ar','44100','-ac','1',str(mp3)],check=True)
    # video
    vl=out/f'{g}_v.txt'
    vl.write_text(''.join(f"file '{m['png']}'\nduration {m['dur']+0.8:.3f}\n" for m in ms)+f"file '{ms[-1]['png']}'\n")
    mp4=out/f'解説_{name}.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(vl),'-i',str(mp3),'-c:v','libx264','-tune','stillimage','-pix_fmt','yuv420p','-r','2','-c:a','aac','-b:a','64k','-shortest','-movflags','+faststart',str(mp4)],check=True)
    d=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(mp3)]))
    print(name,round(d/60,1),'min',mp3.stat().st_size//1024,'KB',mp4.stat().st_size//1024,'KB',flush=True)
    allfiles.append(mp3)
