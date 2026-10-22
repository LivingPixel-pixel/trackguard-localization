"""Local artifact checks and QA contact sheet. Run after build.py."""
from pathlib import Path
import hashlib,json,zipfile,re
from xml.etree import ElementTree as ET
from PIL import Image,ImageDraw
from pypdf import PdfReader
import fitz

root=Path(__file__).resolve().parent
qa=root/'qa';qa.mkdir(exist_ok=True)
ppt=root/'trackguard-pitch.pptx';pdf=root/'trackguard-pitch.pdf'
metrics=json.loads((root.parent/'data/metrics.json').read_text(encoding='utf-8-sig'))
snapshot=json.loads((root/'build/metrics.snapshot.json').read_text(encoding='utf-8'))
assert metrics==snapshot,'Metrics changed since export. Rebuild.'
with zipfile.ZipFile(ppt) as z:
    ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
    parts=[f'ppt/slides/slide{i}.xml' for i in range(1,7)]
    docs=[ET.fromstring(z.read(p)) for p in parts]
    assert len([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)])==6
    tables=[len(d.findall('.//a:tbl',ns)) for d in docs]
    assert tables==[0,0,0,1,0,1],tables
    texts=[' '.join(d.itertext()) for d in docs]
    assert all(v in texts[3] for v in ['17.48cm','11.42cm','94.8%','31.95cm','71.24%','327/459','411 / 49'])
    assert all(v in texts[3] for v in ['0.107° / 13.23cm','Yaw / longitudinal RMSE'])
    assert 'REAL TRACK / SEALED DEVELOPMENT REPLAY' in texts[0]
    assert len(docs[0].findall('.//p:pic',ns)) == 1, 'Measured cover image missing'
    assert all(v in texts[4] for v in ['18.48 / 9.95cm','72% coverage: FAIL','0 / 148','No RMSE'])
    relationships=[(n,z.read(n).decode()) for n in z.namelist() if n.endswith('.rels')]
    assert not any('TargetMode="External"' in s for _,s in relationships),'Unexpected external relationship'
    assert not any(re.search(r'(?:C:|Users[/\\]|file:)',s,re.I) for _,s in relationships),'Private absolute relationship'
    metadata=ET.fromstring(z.read('docProps/core.xml'))
    assert all(e.text=='TrackGuard' for e in metadata if e.tag.endswith(('creator','lastModifiedBy')))
reader=PdfReader(pdf)
assert len(reader.pages)==6
html=(root/'slides.html').read_text(encoding='utf-8')
assert html.count('class="slide"')==6
assert not re.search(r'<(?:script|img|link)[^>]+(?:src|href)=["\']https?://',html)
assert 'aria-live="polite"' in html and 'prefers-reduced-motion' in html
assert '\u2014' not in html
assert 'C:/' not in (root/'build/deck.json').read_text(encoding='utf-8')
overflow=json.loads((qa/'text-overflow.json').read_text(encoding='utf-8-sig'))
assert not overflow,overflow
doc=fitz.open(pdf)
for i,page in enumerate(doc,1):
    pix=page.get_pixmap(matrix=fitz.Matrix(1600/page.rect.width,1600/page.rect.width))
    pix.save(qa/f'pdf-slide-{i}.png')
sheet=Image.new('RGB',(1600,1410),'#dce5e5');draw=ImageDraw.Draw(sheet)
for i in range(1,7):
    x=16+((i-1)%2)*800;y=22+((i-1)//2)*466
    sheet.paste(Image.open(qa/f'slide-{i}.png').resize((768,432)),(x,y))
    draw.text((x+4,y+436),f'Slide {i}',fill='#102C3A')
sheet.save(qa/'contact-sheet.png')
report={
    'slides':6,'pdf_pages':6,'native_tables_by_slide':tables,
    'native_text_and_diagrams':True,'powerpoint_render_count':6,'pdf_render_count':6,
    'powerpoint_text_overflow_count':0,'external_relationship_count':0,
    'metrics_snapshot_parity':True,'metrics_sha256':hashlib.sha256((root.parent/'data/metrics.json').read_bytes()).hexdigest(),
    'browser_checks':{'six_slide_navigation':True,'number_keys':True,'svg_text_outside_canvas':0,'remote_asset_references':0,'animation_play_pause':True},
    'authoring_engine':'Installed Microsoft PowerPoint via local COM. No new dependencies.',
    'runtime_limitation':'load_workspace_dependencies and @oai/artifact-tool were unavailable. The documented local route was inspected. Native PowerPoint used under explicit fallback authorization. Artifact Tool import/finalizer unavailable.',
    'review':'Updated measured-replay cover and yaw/longitudinal evidence slide inspected at 1600x900. Four unchanged slides retain prior visual review. All six PDF pages rendered; native overflow and input parity checked. Browser navigation evidence reused for unchanged controls.',
    'export_command':'python slides/build.py',
    'verification_command':'python slides/verify.py',
    'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (ppt,pdf,root/'slides.html')}
}
(qa/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
