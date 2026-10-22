"""Check the public aggregate contract, links and release data boundary."""
from pathlib import Path
import json
import math
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
    replay = json.loads((ROOT/'data/replay.json').read_text(encoding='utf-8'))
    replay_js = (ROOT/'assets/replay.js').read_text(encoding='utf-8')
    replay_start = replay_js.index('{',replay_js.index('EMBEDDED_REPLAY'))
    replay_embedded, _ = json.JSONDecoder().raw_decode(replay_js[replay_start:])
    assert replay_embedded == replay, 'Offline replay snapshot differs from source'
    assert replay['schema'] == 'trackguard-measured-replay-v1'
    rows, meta = replay['rows'], replay['metadata']
    assert len(rows) == meta['frames'] == combined['planned'] == 460
    assert sum(row['published'] for row in rows) == meta['published'] == 411
    assert sum(not row['published'] for row in rows) == meta['unavailable'] == 49
    assert sum(row['seed'] for row in rows) == meta['seed_count'] == 1
    assert rows[0]['seed'] and rows[0]['t_s'] == 0
    keys = {'frame','t_s','lap','published','seed','reference_px','estimate_px',
            'position_error_m','lateral_error_m','longitudinal_error_m','yaw_error_deg',
            'rolling_position_rmse_m','rolling_frame_publication_percent'}
    errors = ('position_error_m','lateral_error_m','longitudinal_error_m','yaw_error_deg')
    for i,row in enumerate(rows):
        assert set(row) == keys, 'Unexpected replay field'
        assert row['frame'] == i and row['lap'] in (6,7)
        assert i == 0 or row['t_s'] > rows[i-1]['t_s']
        for key in ('reference_px','estimate_px'):
            px = row[key]
            if px is not None:
                assert len(px) == 2 and all(type(v) is int for v in px)
                assert 0 <= px[0] < meta['track_width'] and 0 <= px[1] < meta['track_height']
        if not row['published']:
            assert row['estimate_px'] is None
        if row['seed'] or not row['published']:
            assert all(row[key] is None for key in errors)
        if row['position_error_m'] is not None:
            assert math.isclose(row['position_error_m']**2,
                                row['lateral_error_m']**2 + row['longitudinal_error_m']**2,
                                abs_tol=2e-9)
            assert -180 <= row['yaw_error_deg'] <= 180
        assert 0 <= row['rolling_frame_publication_percent'] <= 100
    for field,metric in [('position_error_m','position_rmse_m'),('lateral_error_m','lateral_rmse_m'),
                         ('longitudinal_error_m','longitudinal_rmse_m'),('yaw_error_deg','yaw_rmse_deg')]:
        values = [row[field] for row in rows if row[field] is not None]
        assert len(values) == 410
        assert math.isclose(math.sqrt(sum(v*v for v in values)/len(values)),combined[metric],abs_tol=1e-9)
    required = ('README.md','docs/ENGINE.md','docs/EVIDENCE.md','index.html',
                'assets/track-replay.gif','assets/track-replay-card.gif','assets/track-replay-poster.png',
                'assets/track-replay-background.png','docs/REPLAY.md',
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
    print('Public release checks passed: real replay, error parity, denominators, links, six slides and data boundary.')


if __name__ == '__main__':
    main()
