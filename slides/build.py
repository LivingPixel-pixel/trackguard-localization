"""TrackGuard local deck source. Run: python slides/build.py

Writes editable PowerPoint drawing instructions and a self-contained accessible
HTML deck. export.ps1 uses installed PowerPoint for the PPTX, PDF and slide PNGs.
Only slides/ is writable. All metrics come from ../data/metrics.json.
"""
from pathlib import Path
import json, html, math, subprocess, base64, shutil

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / 'build'
QA = ROOT / 'qa'
for d in (BUILD, QA): d.mkdir(exist_ok=True)
M = json.loads((ROOT.parent / 'data/metrics.json').read_text(encoding='utf-8-sig'))
W = {w['id']:w for w in M['windows']}
C = dict(marine='#102C3A',mist='#F1F5F4',white='#FFFFFF',teal='#007D7D',amber='#A45B00',slate='#4D626B',line='#D1DEDE',light='#B4CBCF',pale='#E0EEEE')
slides=[]
def slide(title,bg='mist'):
    s={'title':title,'bg':C.get(bg,bg),'objects':[],'notes':'Source: data/metrics.json and data/replay.json (approved derived evaluation display, 2026-10-22). The cover shows the real sealed R16 development replay. Architecture diagrams are illustrative. Raw recordings, world-coordinate poses and labels remain local.'}
    slides.append(s);return s
def add(s,t,**kw):
    o={'type':t,**kw};s['objects'].append(o);return o
def box(s,x,y,w,h,fill='white',stroke=None,sw=1):return add(s,'rect',x=x,y=y,w=w,h=h,fill=C.get(fill,fill),stroke=C.get(stroke,stroke),sw=sw)
def text(s,x,y,w,h,t,size=28,color='marine',bold=False,font='Segoe UI',align='left'):
    return add(s,'text',x=x,y=y,w=w,h=h,text=t,size=size,color=C.get(color,color),bold=bold,font=font,align=align)
def line(s,x,y,x2,y2,color='line',sw=2,dash=False):return add(s,'line',x=x,y=y,x2=x2,y2=y2,color=C.get(color,color),sw=sw,dash=dash)
def ellipse(s,x,y,w,h,fill='teal',stroke=None,sw=2):return add(s,'ellipse',x=x,y=y,w=w,h=h,fill=C.get(fill,fill),stroke=C.get(stroke,stroke),sw=sw)
def path(s,points,color='teal',sw=4,dash=False):return add(s,'path',points=points,color=C.get(color,color),sw=sw,dash=dash)

def image(s,x,y,w,h,src,alt):return add(s,'image',x=x,y=y,w=w,h=h,src=src,alt=alt)
def header(s,kicker,title):
    text(s,72,43,1300,30,kicker.upper(),19,'teal',True)
    text(s,72,90,1450,112,title,52,'marine',True)
def footer(s,n,dark=False):
    col='light' if dark else 'slate'
    text(s,72,844,1380,28,'TRACKGUARD   /   CUSTOMER PILOT BRIEF   /   22 OCT 2026',17,col)
    text(s,1460,839,68,34,f'{n:02}',22,col,font='Consolas',align='right')
def table(s,x,y,width,widths,rows,rowh=58):
    return add(s,'table',x=x,y=y,w=width,h=rowh*len(rows),widths=widths,rows=rows,rowh=rowh)
# 1. Actual solution and explicit output states in the first ten seconds.
s=slide('Vehicle localization from the cameras you already run','marine')
box(s,815,0,785,900,'mist')
text(s,72,48,640,44,'TRACKGUARD',30,'white',True)
text(s,72,148,710,285,'Vehicle localization\nfrom the cameras\nyou already run',66,'white',True)
text(s,75,470,658,155,'Seven calibrated cameras, a reference map and motion signals produce one shared vehicle pose.',30,'white')
line(s,75,678,720,678,'slate',2)
text(s,75,712,650,84,'When geometric evidence is insufficient, the output is unavailable.',28,'light')
text(s,857,60,680,55,'REAL TRACK / SEALED DEVELOPMENT REPLAY',21,'slate',True)
image(s,840,175,720,405,'assets/track-replay-poster.png','Measured R16 track replay with position and yaw error. Reference is evaluation-only; missing outputs remain gaps.')
text(s,875,612,645,40,'Laps 6 + 7. One seed. 49 unavailable outputs.',24,'marine',True)
box(s,875,670,280,122,'white')
line(s,875,670,1155,670,'teal',6)
text(s,897,689,240,40,'POSE AVAILABLE',22,'teal',True)
text(s,897,733,245,38,'x   y   heading',23,'marine',font='Consolas')
box(s,1180,670,340,122,'white')
line(s,1180,670,1520,670,'amber',6)
text(s,1202,689,300,40,'UNAVAILABLE',22,'amber',True)
text(s,1202,733,290,38,'No pose published',23,'slate')
footer(s,1,True)
# Cover footer on light half needs dark ink.
s['objects'][-1]['color']=C['slate']
s['notes']+=' Recorded real-track replay of the selected R16 run; its reference is evaluator-only after sealed inference. Animation is accelerated and does not measure live throughput. The interactive dashboard retains all 460 rows.'

# 2. Customer and decision. The potential value remains a hypothesis.
s=slide('The customer decision: evaluate an additional position signal')
header(s,'Customer decision','An additional position signal for a mapped course')
text(s,73,224,570,95,'Vehicle autonomy leads\nand track operators',37,'marine',True)
text(s,73,351,540,140,'When the existing position signal weakens, can camera evidence provide a useful second input?',31,'slate')
box(s,688,232,840,324,'marine')
text(s,730,267,740,50,'THE PILOT DECISION',22,'light',True)
text(s,730,337,730,149,'Is the signal accurate and available often enough for our course and operating conditions?',38,'white',True)
line(s,72,611,1528,611,'line',2)
text(s,72,648,355,50,'Existing inputs',27,'teal',True)
text(s,72,712,400,84,'Compatible calibrated cameras and a reference map',27,'marine')
text(s,572,648,355,50,'Proposed integration',27,'teal',True)
text(s,572,712,400,84,'A timestamped pose and explicit availability status',27,'marine')
text(s,1072,648,400,50,'Value to test',27,'teal',True)
text(s,1072,712,430,84,'Useful supplementary coverage within the existing stack',27,'marine')
footer(s,2)
s['notes']+=' Customer value and integration fit are hypotheses for a pilot. No customer deployment, ROI or hardware saving has been measured. This is a supplementary signal, with no actuator authority in the proposed pilot.'

# 3. Editable architecture and shared-body diagram.
s=slide('One vehicle pose from map geometry, cameras and motion')
header(s,'Solution','One vehicle pose from map geometry and motion')
text(s,73,222,720,43,'SYNTHETIC ILLUSTRATIVE GEOMETRY',20,'slate',True)
box(s,72,289,365,282,'marine')
text(s,100,314,310,55,'Reference map',29,'white',True)
for i,(xx,yy) in enumerate([(130,405),(230,380),(335,435),(173,503),(340,510)]):
    ellipse(s,xx,yy,10,10,'light')
    line(s,xx+5,yy+5,610,430,'light',1)
text(s,100,599,337,75,'Map correspondences constrain camera poses.',26,'slate')
box(s,530,358,174,142,'marine')
text(s,551,403,135,50,'BODY',29,'white',True)
for i,(xx,yy) in enumerate([(514,337),(574,331),(640,331),(706,361),(706,454),(613,508),(514,470)]):
    ellipse(s,xx,yy,20,20,'white','teal',3)
text(s,502,548,284,88,'7 calibrated cameras\n1 shared body pose',27,'marine',True)
text(s,77,715,690,99,'Calibration ties cameras to one vehicle frame.\nThe quality threshold remains uncalibrated.',26,'marine')
line(s,800,280,800,782,'line',2)
text(s,857,238,663,48,'CAUSAL ESTIMATION',21,'teal',True)
for i,(a,b) in enumerate([
    ('01  Geometry','Match the map and solve a consistent body pose.'),
    ('02  Motion','Fuse motion signals with current and past evidence.'),
    ('03  Quality gate','Publish an accepted pose or mark it unavailable.')]):
    yy=316+i*153
    text(s,857,yy,650,43,a,30,'marine',True)
    text(s,857,yy+56,650,79,b,27,'slate')
footer(s,3)
s['notes']+=' Architecture is a conceptual explanation from the task and design contract. It does not specify unsupported sensor rates or production interfaces. Publication uncertainty threshold is uncalibrated, not an actual-error bound.'

# 4. Evidence. Metrics are formatted only from the current JSON, with no fallback constants.
d=W['later_laps']
s=slide('Same-session development meets aggregate targets')
header(s,'Verified aggregate evidence','Same-session development meets aggregate targets')
text(s,73,208,1430,55,'Laps 6 + 7   /   One continuous run   /   One initial truth seed   /   No lap 7 reset',25,'slate')
for x,key,label,unit in [(72,'position_rmse_m','Position RMSE','cm'),(574,'lateral_rmse_m','Lateral RMSE','cm'),(1076,'coverage_percent','One-second coverage','%')]:
    v=d[key]*(100 if key.endswith('_m') else 1)
    val=f'{v:.2f}' if unit=='cm' else f'{v:.1f}'
    text(s,x,283,430,100,val+unit,73,'teal',True,font='Consolas')
    text(s,x,389,440,45,label,28,'marine',True)
    text(s,x,441,440,36,'Target ≤20cm' if unit=='cm' else 'Target ≥90%',24,'slate')
line(s,72,510,1528,510,'line',2)
table(s,72,532,1456,[.34,.25,.41],[
    ['Metric','Observed','How to read it'],
    ['Position error, p95',f"{100*d['position_p95_m']:.2f}cm",'RMSE is not a per-output guarantee'],
    ['Yaw / longitudinal RMSE',f"{d['yaw_rmse_deg']:.3f}° / {100*d['longitudinal_rmse_m']:.2f}cm",'Wrapped heading / along-track position'],
    ['Within 20cm, all planned',f"{d['within20cm_all_planned_percent']:.2f}%",f"{d['within20cm_count']}/{d['scored_planned_excluding_seed']} non-seed frames, unavailable = miss"],
    ['Published / unavailable',f"{d['published']} / {d['unavailable']}",f"{d['planned']} planned, {100*d['published']/d['planned']:.2f}% publication fraction"],
],rowh=48)
text(s,73,788,1448,46,'Coverage counts occupied one-second bins. Development data is consumed, not untouched validation.',23,'slate')
footer(s,4)
s['notes']+=' Position RMSE sqrt(mean(dx^2+dy^2)) on finite published estimates, excluding initial truth seed. Lateral error projects across ground-truth heading. One-second coverage differs from publication fraction. '+json.dumps(d,separators=(',',':'))

# 5. Failures are shown as operational evidence, never merged into the headline.
t=W['stress'];day=W['day']
s=slide('Coverage and cold start remain the deployment blockers','marine')
text(s,72,43,1430,30,'OPERATIONAL BOUNDARIES',19,'light',True)
text(s,72,91,1456,119,'Coverage and cold start remain\nthe deployment blockers',51,'white',True)
line(s,72,265,1528,265,'slate',2)
text(s,72,304,690,50,'Original 131-second stress window',32,'white',True)
text(s,72,378,650,84,f"{100*t['position_rmse_m']:.2f} / {100*t['lateral_rmse_m']:.2f}cm",52,'white',True,font='Consolas')
text(s,72,465,640,48,'Position / lateral RMSE on published poses',24,'light')
text(s,72,532,680,60,f"{t['coverage_percent']:.0f}% coverage: FAIL",40,'#FFC17A',True)
text(s,72,609,651,86,f"{t['published']}/{t['planned']} published, {t['unavailable']} unavailable.\nSeparate seeded window. Below 90% target.",26,'white')
line(s,795,303,795,708,'slate',2)
text(s,847,304,682,50,'Blind day replay',32,'white',True)
text(s,847,378,655,84,f"{day['published']} / {day['planned']}",62,'white',True,font='Consolas')
text(s,847,465,650,48,'Published / planned groups, all unavailable',24,'light')
text(s,847,532,675,60,'Never initialized',40,'#FFC17A',True)
text(s,847,609,670,86,'No truth labels or initial seed. No RMSE.\nNo approved three-camera fix.',26,'white')
box(s,72,738,1456,85,'#1D3B48')
text(s,96,747,1406,72,'Next proof: independent day/night runs, reliable cold starts and calibrated confidence.\nEnd-to-end latency is unproven. No production deployment or safety certification.',24,'white')
footer(s,5,True)
s['notes']+=' Stress is not ranked. Day: 73.9s, 148 complete groups at 2 Hz, 145 geometry rejects, 3 single-camera results. Day coverage uses 74 camera-time bins without ground-truth interval. No independent-session 20cm result, live 10Hz measurement, GPU speed result, deployment or safety certification. Nominal 0.20m publication uncertainty threshold is uncalibrated and cannot guarantee actual error. Earlier R14 raw geometry timing is not R16 end-to-end latency.'

# 6. Proposed scoped customer pilot and acceptance targets.
s=slide('A scoped pilot to decide whether this signal earns integration')
header(s,'Proposed customer pilot','One vehicle. One mapped course. A decision in four weeks.')
text(s,72,224,455,92,'Offline replay, then\nshadow operation',36,'marine',True)
text(s,72,348,435,185,'Use compatible existing cameras and recorded motion signals. Keep the output outside vehicle control.',29,'slate')
text(s,72,574,435,50,'Customer contribution',26,'teal',True)
text(s,72,637,440,125,'Course access, calibration, an independent evaluation capture and an agreed latency budget.',27,'marine')
table(s,565,225,963,[.41,.59],[
    ['Acceptance item','Proposed target'],
    ['Independent day + night','Freeze map and parameters before capture'],
    ['Position / lateral RMSE','≤20cm each on published non-seed poses'],
    ['One-second coverage','≥90% in each agreed test condition'],
    ['Cold start, no truth seed','≥95% of agreed starts within 30s'],
    ['Tail error + missing poses','Report p95 and all-planned within 20cm'],
    ['Signal integrity + latency','100% explicit unavailable states, measure p95'],
],rowh=72)
box(s,565,750,963,68,'marine')
text(s,590,764,910,46,'Decision: extend the pilot only if the agreed gates pass.',27,'white',True)
footer(s,6)
s['notes']+=' Proposed pilot, scope and acceptance targets, not measured achievements or committed delivery dates. Week 1 calibrate/freeze/evaluation design, week 2 independent capture, week 3 replay and cold-start evaluation, week 4 shadow integration only if earlier gates pass. Agree denominator and trial count for cold-start target before capture. No truth seed enters the proposed deployment signal. Independent ground truth is evaluation only and must remain separate from map construction. Timing target requires customer stack budget agreed before evaluation. Report failures and unavailable outputs. No safety certification or ROI claim.'

assert len(slides)==6
# Persist inputs for deterministic, portable build and evidence traceability.
(BUILD/'deck.json').write_text(json.dumps({'width':1600,'height':900,'slides':slides},indent=2),encoding='utf-8')
(BUILD/'metrics.snapshot.json').write_text(json.dumps(M,indent=2),encoding='utf-8')

def svg_obj(o):
    t=o['type'];f=o.get('fill') or 'none';st=o.get('stroke') or 'none'
    if t=='image':
        p=ROOT.parent/o['src']
        encoded=base64.b64encode(p.read_bytes()).decode()
        return f'<image x="{o["x"]}" y="{o["y"]}" width="{o["w"]}" height="{o["h"]}" href="data:image/png;base64,{encoded}" preserveAspectRatio="xMidYMid meet"><title>{html.escape(o["alt"])}</title></image>'
    if t in ('rect','ellipse'):
        if t=='rect':a=f'x="{o["x"]}" y="{o["y"]}" width="{o["w"]}" height="{o["h"]}"'
        else:a=f'cx="{o["x"]+o["w"]/2}" cy="{o["y"]+o["h"]/2}" rx="{o["w"]/2}" ry="{o["h"]/2}"'
        return f'<{t} {a} fill="{f}" stroke="{st}" stroke-width="{o.get("sw",1)}"/>'
    if t in ('line','path'):
        pts=o.get('points',[[o.get('x'),o.get('y')],[o.get('x2'),o.get('y2')]])
        p=' '.join(','.join(map(str,v)) for v in pts)
        return f'<polyline points="{p}" fill="none" stroke="{o["color"]}" stroke-width="{o["sw"]}" stroke-linejoin="round" stroke-linecap="round"'+(' stroke-dasharray="10 9"' if o.get('dash') else '')+'/>'
    if t=='text':
        sz=o['size'];lh=sz*1.2;x=o['x'];y=o['y']+sz
        anchor='start'
        if o['align']=='right':x+=o['w'];anchor='end'
        # Wrap text with font metrics matched approximately to Segoe UI.
        from PIL import ImageFont
        fp='C:/Windows/Fonts/'+('consola.ttf' if o['font']=='Consolas' else ('segoeuib.ttf' if o['bold'] else 'segoeui.ttf'))
        font=ImageFont.truetype(fp,int(sz))
        lines=[]
        for para in o['text'].split('\n'):
            line_=''
            for word in para.split(' '):
                c=(line_+' '+word).strip()
                if line_ and font.getlength(c)>o['w']-2:lines.append(line_);line_=word
                else:line_=c
            lines.append(line_)
        spans=''.join(f'<tspan x="{x}" y="{y+i*lh}">{html.escape(v)}</tspan>' for i,v in enumerate(lines))
        return f'<text font-family="{o["font"]},sans-serif" font-size="{sz}" fill="{o["color"]}" font-weight="{700 if o["bold"] else 400}" text-anchor="{anchor}">{spans}</text>'
    if t=='table':
        pieces=[]; yy=o['y']
        for ri,row in enumerate(o['rows']):
            pieces.append(svg_obj(dict(type='rect',x=o['x'],y=yy,w=o['w'],h=o['rowh'],fill=C['marine'] if ri==0 else (C['white'] if ri%2 else '#E7EFEE'))))
            xx=o['x']
            for ci,cell in enumerate(row):
                ww=o['w']*o['widths'][ci]
                pieces.append(svg_obj(dict(type='text',x=xx+16,y=yy+10,w=ww-28,h=o['rowh']-12,text=cell,size=23 if len(o['rows'])<6 else 22,color=C['white'] if ri==0 else C['marine'],bold=ri==0,font='Segoe UI',align='left')))
                xx+=ww
            yy+=o['rowh']
        return ''.join(pieces)
    raise ValueError(t)

svgs=[]
for i,s in enumerate(slides,1):
    a=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" role="img" aria-labelledby="title{i} desc{i}"><title id="title{i}">{html.escape(s["title"])}</title><desc id="desc{i}">Slide {i} of 6. '+html.escape(' '.join(o.get('text','') for o in s['objects']))+'</desc>'
    a+=f'<rect width="1600" height="900" fill="{s["bg"]}"/>'+''.join(svg_obj(o) for o in s['objects'])+'</svg>'
    svgs.append(a)
    (BUILD/f'slide-{i}.svg').write_text(a,encoding='utf-8')

# Use the derived real-track replay. No raw recording or video is embedded.
gif=ROOT.parent/'assets/track-replay-card.gif';poster=ROOT.parent/'assets/track-replay-poster.png'
media=''
if gif.exists() and poster.exists():
    gd=base64.b64encode(gif.read_bytes()).decode();pd=base64.b64encode(poster.read_bytes()).decode()
    media=f'<aside class="demo" aria-label="Measured track replay"><h2>The real track, with synchronized errors</h2><p>Accelerated R16 development replay. Reference is evaluation-only. Missing outputs remain gaps.</p><img id="animation" src="data:image/png;base64,{pd}" alt="Real track with the recorded estimate, reference and synchronized position and yaw errors." data-poster="data:image/png;base64,{pd}" data-motion="data:image/gif;base64,{gd}"><button id="motion" type="button" aria-pressed="false">Play measured replay</button></aside>'
sections=''.join(f'<section class="slide" id="slide-{i}" aria-label="Slide {i} of 6" tabindex="-1">{a}</section>' for i,a in enumerate(svgs,1))
transcript=''.join('<details><summary>Slide '+str(i)+': '+html.escape(s['title'])+'</summary><div>'+''.join('<p>'+html.escape(o['text']).replace('\n','<br>')+'</p>' for o in s['objects'] if o['type']=='text')+(''.join('<table>'+''.join('<tr>'+''.join(('<th>' if j==0 else '<td>')+html.escape(c)+('</th>' if j==0 else '</td>') for c in row)+'</tr>' for j,row in enumerate(o['rows']))+'</table>' for o in s['objects'] if o['type']=='table'))+'<p>'+html.escape(s['notes'])+'</p></div></details>' for i,s in enumerate(slides,1))
doc='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TrackGuard | Customer pilot brief</title><style>
*{box-sizing:border-box}body{margin:0;background:#F1F5F4;color:#102C3A;font:18px 'Segoe UI',sans-serif}a{color:#007D7D}nav{display:flex;gap:12px;align-items:center;justify-content:center;padding:16px;flex-wrap:wrap}button,a.control{border:1px solid #4D626B;background:white;color:#102C3A;padding:10px 18px;border-radius:3px;font:inherit;cursor:pointer}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #A45B00;outline-offset:3px}main{max-width:1600px;margin:auto}.slide{display:none}.slide.active{display:block}.slide svg{display:block;width:100%;height:auto}.help{text-align:center;color:#4D626B;font-size:15px;padding:0 12px}#transcript{max-width:1000px;margin:25px auto;padding:20px}summary{cursor:pointer;font-weight:600;padding:15px 0}details div{padding:0 10px 20px}table{border-collapse:collapse;width:100%}td,th{padding:9px;border:1px solid #D1DEDE;text-align:left}aside.demo{max-width:900px;margin:30px auto;padding:24px;background:#fff}aside.demo img{width:100%;display:block;margin-bottom:15px}h2{font-size:24px}.skip{position:absolute;left:-10000px}.skip:focus{left:10px;top:10px;background:white;padding:12px;z-index:3}@media(max-width:650px){nav{gap:6px;padding:10px}button,a.control{font-size:15px;padding:9px}#transcript{margin-top:5px;padding:16px}.help{font-size:14px}}@media print{@page{size:landscape;margin:0}body{background:white}nav,.help,#transcript,.demo,.skip{display:none!important}main{max-width:none}.slide{display:block!important;break-after:page;page-break-after:always}.slide:last-child{break-after:auto}.slide svg{width:100%;max-height:100%;aspect-ratio:16/9}}
</style></head><body><a href="#transcript" class="skip">Skip to accessible slide text</a><nav aria-label="Presentation controls"><button id="prev" aria-label="Previous slide">Previous</button><span id="status" role="status" aria-live="polite">Slide 1 of 6</span><button id="next" aria-label="Next slide">Next</button><button id="print">Print / save PDF</button><a class="control" href="#transcript">Accessible text</a></nav><p class="help">Left / Right arrows or Page Up / Down. Home / End. Keys 1–6. P to print. No network required.</p><main>'''+sections+'''</main>'''+media+'''<section id="transcript" aria-label="Accessible slide text"><h2>Slide text and evidence notes</h2>'''+transcript+'''</section><script>
const slides=[...document.querySelectorAll('.slide')];let current=0;function show(n){current=Math.max(0,Math.min(5,n));slides.forEach((s,i)=>{s.classList.toggle('active',i===current);s.setAttribute('aria-hidden',i!==current)});document.getElementById('status').textContent=`Slide ${current+1} of 6`;document.getElementById('prev').disabled=current===0;document.getElementById('next').disabled=current===5;history.replaceState(null,'','#'+(current+1))}document.getElementById('prev').onclick=()=>show(current-1);document.getElementById('next').onclick=()=>show(current+1);document.getElementById('print').onclick=()=>window.print();document.addEventListener('keydown',e=>{if(/input|textarea|select/i.test(e.target.tagName))return;if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(current+1)}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(current-1)}if(e.key==='Home'){e.preventDefault();show(0)}if(e.key==='End'){e.preventDefault();show(5)}if(/^[1-6]$/.test(e.key))show(+e.key-1);if(e.key.toLowerCase()==='p')window.print()});const animation=document.getElementById('animation'),motion=document.getElementById('motion');if(motion){motion.onclick=()=>{const play=motion.getAttribute('aria-pressed')!=='true';motion.setAttribute('aria-pressed',play);animation.src=play?animation.dataset.motion:animation.dataset.poster;motion.textContent=play?'Pause measured replay':'Play measured replay'};matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',()=>{animation.src=animation.dataset.poster;motion.setAttribute('aria-pressed','false')})}show((+location.hash.slice(1)||1)-1);console.log('TrackGuard offline deck: '+slides.length+' slides, controls initialized');
</script></body></html>'''
(ROOT/'slides.html').write_text(doc,encoding='utf-8')
print('Built six slide sources and offline HTML from current metrics.json')
if __name__=='__main__':
    subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'export.ps1')],check=True)
    # Remove workstation author identity from the public presentation package.
    import zipfile, re
    ppt=ROOT/'trackguard-pitch.pptx'
    clean=BUILD/'metadata-clean.pptx'
    with zipfile.ZipFile(ppt) as src,zipfile.ZipFile(clean,'w',zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data=src.read(info.filename)
            if info.filename=='docProps/core.xml':
                xml=data.decode('utf-8')
                for tag,value in [('dc:title','TrackGuard customer pilot brief'),('dc:creator','TrackGuard'),('cp:lastModifiedBy','TrackGuard')]:
                    xml=re.sub(f'<{tag}>.*?</{tag}>',f'<{tag}>{value}</{tag}>',xml,flags=re.S)
                data=xml.encode('utf-8')
            dst.writestr(info,data)
    clean.replace(ppt)
    from pypdf import PdfReader,PdfWriter
    reader=PdfReader(ROOT/'trackguard-pitch.pdf');writer=PdfWriter()
    for page in reader.pages:writer.add_page(page)
    writer.add_metadata({'/Title':'TrackGuard customer pilot brief','/Author':'TrackGuard','/Subject':'Local camera localization pilot proposal'})
    with (BUILD/'metadata-clean.pdf').open('wb') as f:writer.write(f)
    (BUILD/'metadata-clean.pdf').replace(ROOT/'trackguard-pitch.pdf')
    print('Public file metadata normalized to TrackGuard')
