"""Render an original synthetic localization story. No partner inputs are read."""
from pathlib import Path
import math
import argparse
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
NAVY = '#102C3A'
INK = '#163C4A'
GRID = '#244550'
WHITE = '#F1F5F4'
MUTED = '#A6BBC2'
TEAL = '#42D6C2'
AMBER = '#FFC471'


def font(size, bold=False):
    candidates = [Path('C:/Windows/Fonts') / ('segoeuib.ttf' if bold else 'segoeui.ttf'),
                  Path('/usr/share/fonts/truetype/dejavu') / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size=size)


def point(t):
    a = 2 * math.pi * t
    # An invented closed course, unrelated to any supplied map.
    return (450 + 265 * math.cos(a) + 42 * math.cos(3*a),
            354 + 158 * math.sin(a) - 38 * math.sin(2*a))


def polygon_car(draw, p, angle, fill):
    outline = [(-14,-8), (10,-8), (17,-4), (17,4), (10,8), (-14,8)]
    ca, sa = math.cos(angle), math.sin(angle)
    pts = [(p[0]+x*ca-y*sa, p[1]+x*sa+y*ca) for x,y in outline]
    draw.polygon(pts, fill=fill)
    draw.line((p[0]+4*ca-6*sa,p[1]+4*sa+6*ca,p[0]+4*ca+6*sa,p[1]+4*sa-6*ca),fill=NAVY,width=3)


def render(index, count):
    im = Image.new('RGB', (1280,720), NAVY)
    d = ImageDraw.Draw(im)
    d.text((48,32), 'TrackGuard', font=font(30, True), fill=WHITE)
    d.rounded_rectangle((907,34,1232,73), radius=19, outline=GRID, width=1)
    d.text((928,41), 'Illustrative simulation', font=font(20), fill=MUTED)
    d.text((48,92), 'A position feed with an explicit unavailable state.', font=font(25), fill=WHITE)
    d.line((48,142,1232,142), fill=GRID, width=1)
    for x in range(65,850,44):
        d.line((x,168,x,579),fill=GRID,width=1)
    for y in range(178,580,44):
        d.line((48,y,846,y),fill=GRID,width=1)
    course = [point(j/500) for j in range(501)]
    d.line(course, fill='#435C65', width=32, joint='curve')
    d.line(course, fill='#163541', width=26, joint='curve')
    for k in range(0,500,14):
        d.line(course[k:k+7], fill='#61777F', width=2)
    d.text((304,326), 'Synthetic mapped course', font=font(19), fill=MUTED)
    d.text((304,355), 'No partner map or trajectory', font=font(17), fill=MUTED)
    t = index / count
    lost = 0.42 <= t < 0.56
    segments, current = [], []
    for j in range(index+1):
        tj = j/count
        if 0.42 <= tj < 0.56:
            if current:
                segments.append(current)
                current=[]
            continue
        p = point(tj)
        current.append((p[0]+2*math.sin(j*.38),p[1]+2*math.cos(j*.28)))
    if current:
        segments.append(current)
    for seg in segments:
        if len(seg)>1:
            d.line(seg, fill=TEAL, width=4, joint='curve')
    p = point(t)
    pn = point(t+0.001)
    angle = math.atan2(pn[1]-p[1],pn[0]-p[0])
    polygon_car(d,p,angle,WHITE)
    if lost:
        last = point(.41)
        d.ellipse((last[0]-13,last[1]-13,last[0]+13,last[1]+13),outline=AMBER,width=3)
        d.line((last[0]+18,last[1]-10,last[0]+72,last[1]-45),fill=AMBER,width=2)
        d.text((last[0]+20,last[1]-72),'Last published pose',font=font(15),fill=AMBER)
    else:
        d.ellipse((p[0]-26,p[1]-26,p[0]+26,p[1]+26),outline='#247D7E',width=2)
        for delta in [-.4, .1, .6]:
            a=angle+delta
            d.line((p[0],p[1],p[0]+65*math.cos(a),p[1]+65*math.sin(a)),fill='#31706F',width=1)
        d.ellipse((p[0]-4,p[1]-4,p[0]+4,p[1]+4),fill=TEAL)
    d.rounded_rectangle((886,174,1232,573),radius=14,fill=INK)
    d.text((912,201),'Pose output',font=font(20),fill=MUTED)
    status_color = AMBER if lost else TEAL
    d.ellipse((913,250,925,262),fill=status_color)
    d.text((939,234),'Unavailable' if lost else 'Published',font=font(31,True),fill=status_color)
    d.text((912,296),'2 cameras agree' if lost else '5 cameras agree',font=font(21),fill=WHITE)
    d.text((912,331),'Minimum for a fix: 3',font=font(18),fill=MUTED)
    d.line((912,375,1205,375),fill='#42606C',width=1)
    explanation = ['Weak geometry detected.', 'Pose withheld for this frame.'] if lost else ['Shared vehicle pose solved.', 'Current output is available.']
    for k, line in enumerate(explanation):
        d.text((912,404+k*32),line,font=font(18),fill=WHITE)
    d.text((912,512),'Illustrative states and motion',font=font(16),fill=MUTED)
    d.line((48,609,1232,609),fill=GRID,width=1)
    legends=[('Vehicle',WHITE,48),('Published estimate',TEAL,225),('Unavailable interval',AMBER,518)]
    for label,color,x in legends:
        d.line((x,643,x+25,643),fill=color,width=5)
        d.text((x+36,628),label,font=font(18),fill=WHITE)
    d.text((48,679),'Synthetic demonstration. Measured performance is reported separately.',font=font(16),fill=MUTED)
    d.rounded_rectangle((894,635,1232,643),radius=4,fill=GRID)
    if index:
        d.rounded_rectangle((894,635,894+int(338*t),643),radius=4,fill=status_color)
    return im


def main(count):
    if not 24 <= count <= 120:
        raise ValueError('Choose24to120frames')
    out = ROOT/'assets'
    out.mkdir(exist_ok=True)
    frames=[render(i,count) for i in range(count)]
    frames[count//5].save(out/'localization-poster.png', optimize=True)
    # A shared palette avoids color flicker between frames.
    palette = frames[0].quantize(colors=128)
    indexed=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
    indexed[0].save(out/'localization.gif', save_all=True, append_images=indexed[1:],
                    duration=100, loop=0, disposal=2, optimize=False)
    small=[frame.resize((640,360),Image.Resampling.LANCZOS) for frame in frames[::2]]
    small_palette=small[0].quantize(colors=64)
    card=[frame.quantize(palette=small_palette,dither=Image.Dither.NONE) for frame in small]
    card[0].save(out/'localization-card.gif',save_all=True,append_images=card[1:],
                 duration=200,loop=0,disposal=2,optimize=True)
    frames[count//2].save(out/'localization-unavailable.png', optimize=True)
    print(f'Wrote {count} synthetic frames at1280x720; no source data read.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--frames',type=int,default=80)
    main(parser.parse_args().frames)
