"""Evaluator-only display export of sealed predictions. Never runs inference.

Inputs are private and supplied by CLI. Requires NumPy, Pillow, mcap and
mcap_ros2 already installed. Run under the local resource guard.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from mcap.reader import make_reader
from mcap_ros2.decoder import DecoderFactory

TOPICS = tuple('/constructor0/map_paths/rr/' + n for n in
               ('track_left', 'track_right', 'pitlane_left', 'pitlane_right'))
BG = '#0b111c'
TEXT = '#e9f0f7'
MUTED = '#92a4ba'
CYAN = '#43e5d2'
AMBER = '#ffbf69'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def track_paths(path):
    """Decode only four indexed ROS2 Path topics, at most 8 MiB total payload."""
    paths, used, frames = {}, 0, set()
    decoder = DecoderFactory()
    with Path(path).open('rb') as stream:
        reader = make_reader(stream)
        summary = reader.get_summary()
        if summary is None or not summary.chunk_indexes:
            raise ValueError('Indexed map MCAP required; no whole-file fallback')
        selected = [c for c in summary.channels.values() if c.topic in TOPICS]
        assert {c.topic for c in selected} == set(TOPICS), 'Four map paths required'
        for channel in selected:
            assert summary.schemas[channel.schema_id].name == 'nav_msgs/msg/Path'
        for schema, channel, message in reader.iter_messages(topics=TOPICS, log_time_order=False):
            used += len(message.data)
            assert used <= 8 * 1024 * 1024, 'Selected map payload cap exceeded'
            assert schema.name == 'nav_msgs/msg/Path' and channel.topic in TOPICS
            obj = decoder.decoder_for(channel.message_encoding, schema)(message.data)
            frame = obj.header.frame_id.lstrip('/')
            assert frame == 'map', 'Expected map frame; no inferred transform allowed'
            frames.add(frame)
            assert all(p.header.frame_id.lstrip('/') in ('', 'map') for p in obj.poses)
            xy = np.array([(p.pose.position.x, p.pose.position.y) for p in obj.poses])
            assert xy.ndim == 2 and xy.shape[0] >= 2 and np.isfinite(xy).all()
            paths.setdefault(channel.topic, xy)
            if len(paths) == 4:
                break
    assert len(paths) == 4 and frames == {'map'}
    return paths, used


def aggregates(errors, mask):
    pos, lat, lon, yaw = (errors[k][mask] for k in ('position', 'lateral', 'longitudinal', 'yaw'))
    assert len(pos)
    return {
        'paired_scored_frames': int(mask.sum()),
        'position_rmse_m': float(np.sqrt(np.mean(pos ** 2))),
        'lateral_rmse_m': float(np.sqrt(np.mean(lat ** 2))),
        'longitudinal_rmse_m': float(np.sqrt(np.mean(lon ** 2))),
        'yaw_rmse_deg': float(np.sqrt(np.mean(yaw ** 2))),
        'position_median_m': float(np.median(pos)),
        'position_p95_m': float(np.percentile(pos, 95)),
        'position_max_m': float(pos.max()),
        'absolute_lateral_p95_m': float(np.percentile(np.abs(lat), 95)),
        'absolute_lateral_max_m': float(np.abs(lat).max()),
        'absolute_longitudinal_p95_m': float(np.percentile(np.abs(lon), 95)),
        'absolute_longitudinal_max_m': float(np.abs(lon).max()),
        'absolute_yaw_p95_deg': float(np.percentile(np.abs(yaw), 95)),
        'absolute_yaw_max_deg': float(np.abs(yaw).max()),
    }


def font(size):
    # Pillow's bundled font is portable; no private font or system dependency.
    return ImageFont.load_default(size=size)


def line_segments(draw, rows, end, key, project, fill, width=2, start=0):
    prev = None
    for row in rows[start:end + 1]:
        value = row[key]
        point = None if value is None else project(row, value)
        if point is not None and prev is not None:
            draw.line((prev, point), fill=fill, width=width)
        prev = point


def render(replay, background, assets, count=72):
    rows, meta = replay['rows'], replay['metadata']
    duration = meta['duration_s']
    indices = np.rint(np.linspace(0, len(rows) - 1, count)).astype(int).tolist()
    # Preserve both endpoints and deliberately show a missing estimate.
    missing = next(i for i, row in enumerate(rows) if not row['published'])
    indices[1] = missing
    indices = sorted(set(indices))
    assert 60 <= len(indices) <= 80 and indices[0] == 0 and indices[-1] == len(rows) - 1
    frame_ms = 100
    acceleration = duration / (len(indices) * frame_ms / 1000)
    static = Image.new('RGB', (960, 540), BG)
    d = ImageDraw.Draw(static)
    d.text((20, 14), 'TRACKGUARD / RECORDED DEVELOPMENT REPLAY', font=font(19), fill=TEXT)
    d.text((20, 42), f'R16 laps 6 + 7  |  {duration:.1f}s recorded in {len(indices)/10:.1f}s  |  {acceleration:.1f}x accelerated', font=font(13), fill=MUTED)
    track_box = (18, 88)
    track_size = (576, 384)
    static.paste(background.resize(track_size, Image.Resampling.LANCZOS), track_box)
    d.text((26, 93), 'REAL TRACK / EVALUATION REFERENCE', font=font(12), fill=MUTED)
    d.line((29, 453, 47, 453), fill=AMBER, width=2)
    d.text((53, 446), 'Reference: evaluation only', font=font(11), fill=AMBER)
    d.line((300, 453, 318, 453), fill=CYAN, width=2)
    d.text((324, 446), 'Published estimate', font=font(11), fill=CYAN)
    d.text((20, 486), 'Overview cannot resolve centimetres. Read the measured error charts.', font=font(13), fill=TEXT)
    d.text((20, 509), 'First truth seed not scored. Missing estimates stay missing. No inference rerun.', font=font(12), fill=MUTED)
    charts = [('position_error_m', 'POSITION ERROR / m', 0, 0.65, 238, CYAN),
              ('yaw_error_deg', 'SIGNED YAW ERROR / deg', -0.45, 0.45, 357, AMBER)]
    for key, title, low, high, y, color in charts:
        d.text((620, y - 23), title, font=font(12), fill=color)
        d.rectangle((620, y, 937, y + 78), outline='#28394d')
        for value in (low, (low + high) / 2, high):
            py = y + 78 - (value - low) / (high - low) * 78
            d.line((620, py, 937, py), fill='#1f3042')
        def project(row, val, y=y, low=low, high=high):
            return (620 + row['t_s'] / duration * 317,
                    y + 78 - (max(low, min(high, val)) - low) / (high - low) * 78)
        line_segments(d, rows, len(rows) - 1, key, project, '#375166', width=1)
        d.text((620, y + 82), f'{low:g} to {high:g}  |  time 0 to {duration:.1f}s', font=font(10), fill=MUTED)
    full_frames, card_frames = [], []
    palette = None
    for index in indices:
        row = rows[index]
        im = static.copy()
        d = ImageDraw.Draw(im)
        project_track = lambda r, p: (18 + p[0] * .6, 88 + p[1] * .6)
        line_segments(d, rows, index, 'estimate_px', project_track, CYAN, width=2,
                      start=max(0, index - 45))
        for key, color, radius in [('reference_px', AMBER, 6), ('estimate_px', CYAN, 3)]:
            if row[key] is not None:
                x, y = project_track(row, row[key])
                if key == 'reference_px':
                    d.ellipse((x-radius, y-radius, x+radius, y+radius), outline=color, width=2)
                else:
                    d.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color)
        status = 'SEED / NOT SCORED' if row['seed'] else ('PUBLISHED' if row['published'] else 'ESTIMATE UNAVAILABLE')
        d.text((620, 82), f"{row['t_s']:6.1f}s / LAP {row['lap']}", font=font(18), fill=TEXT)
        d.text((620, 110), status, font=font(13), fill=CYAN if row['published'] else AMBER)
        def show(key, unit, signed=False):
            v = row[key]
            return 'unavailable' if v is None else (f'{v:+.3f}' if signed else f'{v:.3f}') + unit
        d.text((620, 140), 'Position  ' + show('position_error_m', ' m'), font=font(16), fill=CYAN)
        d.text((620, 166), 'Yaw       ' + show('yaw_error_deg', ' deg', True), font=font(16), fill=AMBER)
        d.text((620, 194), 'Lat ' + show('lateral_error_m', ' m', True) + ' / Long ' + show('longitudinal_error_m', ' m', True), font=font(11), fill=TEXT)
        for key, title, low, high, y, color in charts:
            def project(row, val, y=y, low=low, high=high):
                return (620 + row['t_s'] / duration * 317,
                        y + 78 - (max(low, min(high, val)) - low) / (high - low) * 78)
            line_segments(d, rows, index, key, project, color, width=2)
            x = 620 + row['t_s'] / duration * 317
            d.line((x, y, x, y + 78), fill=TEXT, width=1)
            if row[key] is not None:
                px, py = project(row, row[key])
                d.ellipse((px-3, py-3, px+3, py+3), fill=color)
        d.text((620, 464), '10s RMSE: ' + show('rolling_position_rmse_m', ' m'), font=font(13), fill=TEXT)
        d.text((620, 486), f"10s frame publication: {row['rolling_frame_publication_percent']:.1f}%", font=font(12), fill=MUTED)
        if palette is None:
            palette = im.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
        quantized = im.quantize(palette=palette, dither=Image.Dither.NONE)
        full_frames.append(quantized)
        card_frames.append(im.resize((640, 360), Image.Resampling.LANCZOS).quantize(palette=palette, dither=Image.Dither.NONE))
        if index == indices[len(indices) // 2]:
            im.save(assets / 'track-replay-poster.png')
    for frames, name in [(full_frames, 'track-replay.gif'), (card_frames, 'track-replay-card.gif')]:
        frames[0].save(assets / name, save_all=True, append_images=frames[1:],
                       duration=frame_ms, loop=0, optimize=False, disposal=1)
    # Decode the actual saved GIFs, not only in-memory source frames.
    sizes = {}
    for name, limit in [('track-replay.gif', 6_000_000), ('track-replay-card.gif', 2_000_000)]:
        p = assets / name
        with Image.open(p) as saved:
            assert saved.n_frames == len(indices)
            elapsed = 0
            for i in range(saved.n_frames):
                saved.seek(i)
                saved.load()
                elapsed += saved.info['duration']
            assert elapsed == len(indices) * frame_ms
            sizes[name] = {'bytes': p.stat().st_size, 'frames': saved.n_frames,
                           'width': saved.width, 'height': saved.height, 'duration_ms': elapsed,
                           'within_target_bytes': p.stat().st_size < limit}
    return {'sampled_frames': len(indices), 'source_frame_indices': indices,
            'duration_s': len(indices) * frame_ms / 1000, 'acceleration': acceleration,
            'assets': sizes}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('predictions', 'inference-receipt', 'inference-complete', 'scored-metrics',
                 'scored-laps', 'query', 'labels', 'labels-valid', 'map', 'output', 'private-receipt'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--prediction-sha256', required=True)
    args = p.parse_args()
    started = time.monotonic()
    scores, laps = read_json(args.scored_metrics), read_json(args.scored_laps)
    pred_sha = sha(args.predictions)
    assert pred_sha == args.prediction_sha256 == laps['input_sha256']
    for evidence in (read_json(args.inference_receipt), read_json(args.inference_complete)):
        assert evidence['complete'] is True
        assert evidence['output_pins']['predictions.npz']['sha256'] == pred_sha
    allowed_pins = {Path(pin['path']).name: pin['sha256'] for pin in laps['evaluator_input_pins']}
    for path in (args.query, args.labels, args.labels_valid):
        assert sha(path) == allowed_pins[path.name], 'Evaluator input pin mismatch'
    with np.load(args.predictions, allow_pickle=False) as data:
        ts, pose, status = data['timestamps_ns'], data['poses'], data['status']
    with np.load(args.query, allow_pickle=False) as data:
        query_ts = data['timestamps_ns']  # Do not load camera paths or any image payload.
    truth = np.load(args.labels, allow_pickle=False)
    valid = np.load(args.labels_valid, allow_pickle=False)
    assert np.array_equal(ts, query_ts), 'Exact timestamp alignment required'
    assert len(ts) == 460 and pose.shape == truth.shape == (460, 3)
    assert valid.shape == (460,) and valid.dtype == np.bool_
    assert np.all(np.diff(ts) > 0) and valid.all() and np.isfinite(truth).all()
    published = np.isfinite(pose).all(axis=1)
    seed = status == 'fusion_seed'
    assert published.sum() == 411 and (~published).sum() == 49
    assert seed.sum() == 1 and seed[0] and published[0]
    assert all(np.isnan(pose[~published]).all(axis=1)), 'Partial poses forbidden'
    delta = pose[:, :2] - truth[:, :2]
    yaw_delta = pose[:, 2] - truth[:, 2]
    errors = {
        'position': np.linalg.norm(delta, axis=1),
        'lateral': -delta[:, 0] * np.sin(truth[:, 2]) + delta[:, 1] * np.cos(truth[:, 2]),
        'longitudinal': delta[:, 0] * np.cos(truth[:, 2]) + delta[:, 1] * np.sin(truth[:, 2]),
        'yaw': np.degrees(np.arctan2(np.sin(yaw_delta), np.cos(yaw_delta))),
    }
    eligible = published & valid & ~seed
    lap_masks = {}
    for name, info in laps['laps'].items():
        start, end = int(info['start_ns']), int(info['end_ns'])
        mask = (ts >= start) & ((ts <= end) if info['end_inclusive'] else (ts < end))
        assert mask.sum() == info['total_frames'] and published[mask].sum() == info['finite_frames']
        lap_masks[name] = mask
    assert np.all(lap_masks['lap6'] ^ lap_masks['lap7'])
    measured = {'later_laps': aggregates(errors, eligible)}
    measured.update({name: aggregates(errors, mask & eligible) for name, mask in lap_masks.items()})
    for name, result in measured.items():
        expected = scores if name == 'later_laps' else laps['laps'][name]
        for key in ('position_rmse_m', 'lateral_rmse_m'):
            assert abs(result[key] - expected[key]) <= 1e-9, (name, key, result[key], expected[key])
    paths, map_bytes = track_paths(args.map)
    bounds = np.concatenate(list(paths.values()))
    lo, hi = bounds.min(axis=0), bounds.max(axis=0)
    assert np.all(truth[:, :2] >= lo - 5) and np.all(truth[:, :2] <= hi + 5), 'Reference/map bounds mismatch'
    # A map-frame plausibility check, never an estimated coordinate transform.
    nearest = np.full(460, np.inf)
    for offset in range(0, len(bounds), 512):
        block = bounds[offset:offset + 512]
        nearest = np.minimum(nearest, np.sqrt(((truth[:, None, :2] - block[None, :, :]) ** 2).sum(axis=2)).min(axis=1))
    assert np.percentile(nearest, 95) < 20, 'Reference not near supplied track bounds'
    extent = hi - lo
    scale = min(856 / extent[0], 536 / extent[1])
    center = (lo + hi) / 2
    def pixels(xy):
        xy = (xy - center) * scale
        return np.rint(np.column_stack((xy[:, 0] + 480, 320 - xy[:, 1]))).astype(int)
    ref_px = pixels(truth[:, :2])
    estimate_px = np.zeros((460, 2), dtype=int)
    estimate_px[published] = pixels(pose[published, :2])
    background = Image.new('RGB', (960, 640), BG)
    draw = ImageDraw.Draw(background)
    for topic, xy in paths.items():
        draw.line([tuple(p) for p in pixels(xy)], fill='#43566d' if 'track_' in topic else '#273950', width=3 if 'track_' in topic else 2)
    draw.line([tuple(p) for p in ref_px], fill='#a87845', width=2)
    elapsed = (ts - ts[0]) / 1e9
    rows = []
    fields = {'position': 'position_error_m', 'lateral': 'lateral_error_m',
              'longitudinal': 'longitudinal_error_m', 'yaw': 'yaw_error_deg'}
    for i in range(460):
        trailing = (elapsed > elapsed[i] - 10) & (elapsed <= elapsed[i])
        paired_window = trailing & eligible
        row = {'frame': i, 't_s': round(float(elapsed[i]), 6),
               'lap': 6 if lap_masks['lap6'][i] else 7,
               'published': bool(published[i]), 'seed': bool(seed[i]),
               'reference_px': ref_px[i].tolist(),
               'estimate_px': estimate_px[i].tolist() if published[i] else None}
        row.update({field: round(float(errors[key][i]), 9) if eligible[i] else None for key, field in fields.items()})
        row['rolling_position_rmse_m'] = round(float(np.sqrt(np.mean(errors['position'][paired_window] ** 2))), 9) if paired_window.any() else None
        row['rolling_frame_publication_percent'] = round(float(published[trailing].mean() * 100), 6)
        rows.append(row)
    metadata = {'run': 'R16 continuous development laps 6 + 7', 'frames': 460,
                'published': 411, 'unavailable': 49, 'seed_count': 1,
                'duration_s': float(elapsed[-1]), 'sampling_hz': 2, 'rolling_window_s': 10,
                'rolling_window_interval': '(current time - 10s, current time]',
                'track_image': 'assets/track-replay-background.png', 'track_width': 960, 'track_height': 640,
                'reference_scope': 'Evaluation-only reference after sealed inference',
                'coordinate_scope': 'Rounded display pixels only; no world poses or raw labels',
                'overview_limit': 'Overview cannot resolve centimetre accuracy; read error charts.',
                'accuracy_scope': 'Published eligible non-seed observations; no lap 7 reseed',
                'unavailable_policy': 'Null estimate and errors; no interpolation or connecting trail',
                'map_scope': 'Four supplied map-frame track and pitlane bounds, rendered only'}
    replay = {'schema': 'trackguard-measured-replay-v1', 'metadata': metadata, 'rows': rows}
    output = args.output
    assets = output / 'assets'
    assets.mkdir(exist_ok=True)
    (output / 'data').mkdir(exist_ok=True)
    background.save(assets / 'track-replay-background.png')
    write_json(output / 'data/replay.json', replay)
    metrics_path = output / 'data/metrics.json'
    metrics = read_json(metrics_path)
    original = json.loads(json.dumps(metrics))
    for window in metrics['windows']:
        if window['id'] not in measured:
            continue
        for key, value in measured[window['id']].items():
            if key in window:
                assert abs(window[key] - value) <= 1e-9
            else:
                window[key] = value
    metrics['measured_replay'] = {'schema': replay['schema'], 'path': 'data/replay.json',
                                 'reference_scope': metadata['reference_scope'],
                                 'accuracy_scope': metadata['accuracy_scope'],
                                 'supersedes_synthetic_graphics_note_for': 'assets/track-replay* only',
                                 'yaw_definition': 'Wrapped signed estimate minus reference degrees',
                                 'longitudinal_definition': 'Signed error along reference heading',
                                 'tail_definition': 'Linear-interpolated 95th percentile of absolute errors',
                                 'new_aggregates_computed_before_rounding': True}
    metrics['methodology'] = [
        'The track-replay graphics show the real sealed R16 development run as derived display pixels and errors. The reference is evaluator-only. All 460 rows and 49 unavailable estimates remain represented; raw world poses and labels stay local.'
        if item.startswith('All graphics showing a course, vehicle or trajectory') else item
        for item in metrics['methodology']]
    for old, new in zip(original['windows'], metrics['windows']):
        assert all(new[k] == v for k, v in old.items())
    assert all(metrics[k] == v for k, v in original.items() if k not in ('windows', 'methodology'))
    render_info = render(replay, background, assets)
    write_json(metrics_path, metrics)
    receipt = {'schema': 'trackguard-private-replay-export-v1', 'success': True,
               'predictions_sha256': pred_sha, 'input_pins_verified': True,
               'sealed_receipts_verified': True, 'exact_timestamp_alignment': True,
               'existing_metrics_verified_tolerance': 1e-9, 'existing_public_metrics_preserved': True,
               'selected_map_payload_bytes': map_bytes, 'map_frame': 'map',
               'reference_to_bounds_nearest_p95_m': float(np.percentile(nearest, 95)),
               'frames': 460, 'published': 411, 'unavailable': 49, 'seed_excluded': 1,
               'measured': measured, 'render': render_info,
               'elapsed_seconds': time.monotonic() - started,
               'outputs': {str(p.relative_to(output)): {'bytes': p.stat().st_size, 'sha256': sha(p)}
                           for p in [output / 'data/replay.json', metrics_path, *assets.glob('track-replay*')]}}
    with args.private_receipt.open('x', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2, allow_nan=False)
    print(json.dumps(receipt, allow_nan=False))


if __name__ == '__main__':
    main()
