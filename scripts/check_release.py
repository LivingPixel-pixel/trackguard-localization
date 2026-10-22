"""Check the public aggregate contract, links and release data boundary."""
from pathlib import Path
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT/'data/metrics.json').read_text(encoding='utf-8'))
    js = (ROOT/'assets/dashboard.js').read_text(encoding='utf-8')
    at = js.index('EMBEDDED_METRICS')
    start = js.index('{', at)
    embedded, _ = json.JSONDecoder().raw_decode(js[start:])
    assert embedded == data, 'Dashboard fallback differs from metric source'
    windows = {w['id']: w for w in data['windows']}
    assert set(windows) == {'later_laps','lap6','lap7','stress','day'}
    for window in windows.values():
        assert window['published'] + window['unavailable'] == window['planned']
        assert 0 <= window['coverage_percent'] <= 100
    combined = windows['later_laps']
    assert combined['within20cm_count'] / combined['scored_planned_excluding_seed'] * 100 == combined['within20cm_all_planned_percent']
    assert combined['scored_planned_excluding_seed'] == combined['planned'] - combined['seed_count']
    assert windows['day']['position_rmse_m'] is None and windows['day']['lateral_rmse_m'] is None
    assert not windows['stress']['qualified'] and not windows['day']['qualified']
    required = ('README.md','docs/ENGINE.md','docs/EVIDENCE.md','index.html',
                'assets/localization.gif','assets/localization-card.gif','assets/localization-poster.png',
                'slides/slides.html','slides/trackguard-pitch.pdf','slides/trackguard-pitch.pptx')
    for name in required:
        assert (ROOT/name).is_file(), 'Missing public artifact: '+name
    for filename in ('index.html','README.md'):
        text = (ROOT/filename).read_text(encoding='utf-8')
        targets = re.findall(r'(?:href|src)="([^"]+)"',text) if filename.endswith('.html') else re.findall(r'\]\(([^)]+)\)',text)
        for target in targets:
            if target.startswith(('https:','http:','#','mailto:','data:')):
                continue
            assert (ROOT/target.split('#',1)[0]).is_file(), 'Broken local link: '+target
    forbidden = {'.mcap','.bag','.db3','.npz','.npy','.pickle','.pkl','.pt','.pth','.onnx','.zip','.mp4','.webm','.mov'}
    secrets = [r'gh[pousr]_[A-Za-z0-9]{25,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
               r'C:[/\\](?:Users[/\\][^/\\]+[/\\]\.codex|CodexLocal[/\\](?:schubKI|Hackathons[/\\]output))']
    for path in ROOT.rglob('*'):
        if not path.is_file() or any(part in {'.git','__pycache__','build','dist'} or part.endswith('.egg-info') for part in path.relative_to(ROOT).parts):
            continue
        assert path.suffix.lower() not in forbidden, 'Restricted/binary data extension: '+str(path.relative_to(ROOT))
        if path.suffix.lower() in {'.py','.md','.json','.html','.js','.css','.yml','.toml','.txt','.ps1'}:
            text = path.read_text(encoding='utf-8')
            assert chr(0x2014) not in text, 'Em dash: '+str(path.relative_to(ROOT))
            for pattern in secrets:
                assert not re.search(pattern,text), 'Private material pattern: '+str(path.relative_to(ROOT))
    with zipfile.ZipFile(ROOT/'slides/trackguard-pitch.pptx') as deck:
        slides = [n for n in deck.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)]
        assert len(slides) == 6, 'Expected six-slide editable deck'
    print('Public release checks passed: aggregate parity, denominators, links, six slides and data boundary.')


if __name__ == '__main__':
    main()
