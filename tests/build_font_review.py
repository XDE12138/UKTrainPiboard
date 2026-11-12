"""Build a portable human-review page from actual pygame-rendered glyphs.

Capture --before before editing the font. The normal build reuses that frozen
snapshot, so an existing working tree is never confused with Git HEAD.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'piboard'))
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
from jinja2 import Environment, FileSystemLoader, select_autoescape
from board import dot_font as font

SNAPSHOT = ROOT / '.visual-review/2026-11-11-fonts/before.json'
OUTPUT = ROOT / 'piboard/review_artifacts/font-review-2026-11-11'
SIZES = [font.FontSize.SMALL, font.FontSize.MEDIUM, font.FontSize.LARGE, font.FontSize.XLARGE]
CHARS = ''.join(chr(i) for i in range(32,127)) + '°' + '日程项目进度会议天气北京'
REASONS = {
    '0': '7×9：加入斜线，与字母 O 区分，并与小字号的 0 保持一致。',
    'S': '7×9：补上断开的中段，统一上下弧线，保留 5×7 字形。',
    'N': '5×7 / 7×9：让斜笔贯穿字高，避免笔画集中在上半部。',
    'V': '7×9：交点落在最后一行，去掉像 Y 的竖直尾巴。',
    'W': '5×7 / 7×9：底部收成两个谷点，避免折回两侧竖笔。',
}


def capture():
    pygame.display.init()
    pygame.display.set_mode((1,1))
    atlas = pygame.Surface((1024, 4096))
    atlas.fill((8,8,8))
    x = y = shelf = 0
    glyphs = {}
    for size in SIZES:
        glyphs[size] = {}
        for char in CHARS:
            w,h = font.measure_text(char,size)
            if x+w+4 > atlas.get_width():
                x=0; y+=shelf+4; shelf=0
            font.render_text(atlas,char,x,y,size,(255,149,0))
            bitmap=font._get_bitmap(char,size)
            glyphs[size][char] = {
                'rect':[x,y,w,h], 'bitmap':bitmap,
                'native':char in (font._FONT_7X9 if size in SIZES[2:] else font._FONT_5X7),
                'columns':7 if size in SIZES[2:] else 5,
            }
            x+=w+4; shelf=max(shelf,h)
    atlas=atlas.subsurface((0,0,1024,y+shelf+4)).copy()
    output=io.BytesIO()
    pygame.image.save(atlas,output,'atlas.png')
    result={
        'image':'data:image/png;base64,'+base64.b64encode(output.getvalue()).decode(),
        'glyphs':glyphs,
        'sha256':hashlib.sha256((ROOT/'piboard/board/dot_font.py').read_bytes()).hexdigest(),
        'tracking':dict(font._TRACKING_PX),
        'dot_spacing':{size:font._SIZE_CONFIG[size][2] for size in SIZES},
        'gap_strategy':'unicode_minimum' if hasattr(font,'_inter_char_gap') else 'uniform',
        'cjk_gap':{size:font._inter_char_gap('日','日',size) for size in SIZES},
    }
    pygame.quit()
    return result


def board_pair(before,after):
    from board.board_renderer import BoardRenderer
    from board.content import BoardContent,BoardRow
    from config import COLORS
    original5=dict(font._FONT_5X7);original7=dict(font._FONT_7X9)
    tracking=dict(font._TRACKING_PX);spacing_fn=font._inter_char_gap
    content=BoardContent(header_left='RAIL',header_right='08:35 UK',title='SWANSEA',
        subtitle='NEXT 08:35 UK',subtitle_color='amber',page_label='PLATFORM 11',
        rows=[BoardRow('DEPARTURES','FONT REVIEW',left_color='dim',right_color='dim'),
              BoardRow('SHEFFIELD','08:35 UK',highlight=True),BoardRow('NEW STREET','09:00 UK'),
              BoardRow('WORCESTER','09:30 UK'),BoardRow('SUSSEX EXPRESS','ON TIME'),
              BoardRow('VV W  VVWW','NNMM'),BoardRow('rn m  cl d','I1l 111'),
              BoardRow('SSSS S5S5','O0O0'),BoardRow('项目会议','09:30')],
        footer='LOCAL FONT REVIEW / DEMO',status_text='SYNTHETIC DATA',status_color='amber',template='info')
    result={}
    word_checks={}
    pygame.display.init();pygame.display.set_mode((1,1))
    try:
        for phase,snapshot in [('before',before),('after',after)]:
            font._FONT_5X7.clear();font._FONT_7X9.clear()
            font._FONT_5X7.update({ch:g['bitmap'] for ch,g in snapshot['glyphs']['SMALL'].items() if g['native']})
            font._FONT_7X9.update({ch:g['bitmap'] for ch,g in snapshot['glyphs']['XLARGE'].items() if g['native']})
            font._TRACKING_PX.update(snapshot['tracking'])
            font._inter_char_gap=(spacing_fn if phase=='after' else
                lambda a,b,size,char_gap=0:font._TRACKING_PX[size]+char_gap*font._SIZE_CONFIG[size][2])
            font.clear_cache()
            surface=pygame.Surface((600,1024));BoardRenderer(COLORS).render(surface,content,ticker_page=0)
            stream=io.BytesIO();pygame.image.save(surface,stream,'board.png')
            result[phase]='data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()
            word_checks[phase]=[]
            for size in SIZES:
                for text in ['SWANSEA 08:35 UK','rnrn clcl','项目日程 09:30']:
                    width,height=font.measure_text(text,size)
                    sample=pygame.Surface((width,height));sample.fill((8,8,8))
                    font.render_text(sample,text,0,0,size,(255,149,0))
                    word_checks[phase].append({'size':size,'text':text,'width':width,'height':height,
                        'rgb_sha256':hashlib.sha256(pygame.image.tostring(sample,'RGB')).hexdigest()})
    finally:
        font._FONT_5X7.clear();font._FONT_5X7.update(original5)
        font._FONT_7X9.clear();font._FONT_7X9.update(original7)
        font._TRACKING_PX.update(tracking);font._inter_char_gap=spacing_fn
        font.clear_cache();pygame.quit()
    result['word_checks']=word_checks
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', action='store_true')
    args=parser.parse_args()
    current=capture()
    if args.before:
        if SNAPSHOT.exists() or (OUTPUT/'before.json').exists():
            parser.error('before snapshot already exists; preserve it instead of recapturing')
        SNAPSHOT.parent.mkdir(parents=True,exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current,ensure_ascii=False),encoding='utf-8')
        print('Saved actual pre-edit pygame raster snapshot')
        return
    before_path=OUTPUT/'before.json' if (OUTPUT/'before.json').exists() else SNAPSHOT
    if not before_path.exists():
        parser.error('missing original snapshot; use --before before editing the font')
    before=json.loads(before_path.read_text(encoding='utf-8'))
    before.setdefault('tracking',current['tracking'])
    changed=[]
    for char in CHARS:
        sizes=[size for size in SIZES if before['glyphs'][size][char]['bitmap'] != current['glyphs'][size][char]['bitmap']]
        if sizes: changed.append({'char':char,'sizes':sizes,'reason':REASONS.get(char,'字形调整')})
    manifest={
        'before':before,'after':current,'characters':list(CHARS),'sizes':SIZES,
        'changed':changed,'date':'2026-11-11','runtime':'pygame raster / local candidate',
        'samples':['S SERVICES STATUS','SUSSEX EXPRESS','SHEFFIELD TO SWANSEA',
                   'NEW STREET / NEWPORT','WALSALL VIA WORCESTER',
                   'ON TIME 08:35 UK','CANCELLED / DELAYED','O0 QG C S5 Z2 B8 I1l',
                   'VV W  VVWW  MWMW  NNMM','rn m  cl d  il li  III  111',
                   'SSSS  S5S5  0000  O0O0','08:35  11:11  23°C  10 / 12',
                   'abcdefghijklmnopqrstuvwxyz','项目进度 / 会议日程 09:30'],
        'boards':board_pair(before,current),
    }
    deployment_path=OUTPUT/'deployment.json'
    if deployment_path.exists():
        deployment=json.loads(deployment_path.read_text(encoding='utf-8'))
        if deployment.get('font_sha256')==current['sha256']:
            manifest['deployment']=deployment
    env=Environment(loader=FileSystemLoader(str(ROOT/'tests')),autoescape=select_autoescape(['html']))
    html=env.get_template('font_review.template.html').render(data=manifest)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    frozen=OUTPUT/'before.json'
    if frozen.exists() and json.loads(frozen.read_text(encoding='utf-8'))!=before:
        parser.error('tracked baseline differs; preserve the original snapshot')
    if not frozen.exists():
        frozen.write_text(json.dumps(before,ensure_ascii=False),encoding='utf-8')
    (OUTPUT/'index.html').write_text(html,encoding='utf-8')
    (OUTPUT/'changes.json').write_text(json.dumps({
        'date':manifest['date'],'before_sha256':before['sha256'],
        'after_sha256':current['sha256'],'changed':changed,
        'spacing':{'before_tracking':before['tracking'],'after_tracking':current['tracking'],
                   'before_cjk_gap':before['tracking'],'after_cjk_gap':current['cjk_gap']},
    },ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Changed characters:', ', '.join(item['char'] for item in changed))
    print(OUTPUT/'index.html')
    from PIL import Image, ImageDraw
    atlases={phase:Image.open(io.BytesIO(base64.b64decode(snapshot['image'].split(',',1)[1])))
             for phase,snapshot in [('before',before),('after',current)]}
    audit_dir=ROOT/'.visual-review/2026-11-11-fonts'
    for phase,snapshot in [('before',before),('after',current)]:
        for size in [font.FontSize.SMALL,font.FontSize.XLARGE]:
            scale=4 if size==font.FontSize.SMALL else 2
            chars=list(CHARS); cell_w,cell_h=158,172
            sheet=Image.new('RGB',(8*cell_w,((len(chars)+7)//8)*cell_h),(24,24,24))
            draw=ImageDraw.Draw(sheet)
            for i,char in enumerate(chars):
                x,y,w,h=snapshot['glyphs'][size][char]['rect']
                glyph=atlases[phase].crop((x,y,x+w,y+h)).resize((w*scale,h*scale),Image.Resampling.NEAREST)
                px,py=(i%8)*cell_w,(i//8)*cell_h
                draw.text((px+6,py+4),f'U+{ord(char):04X}',fill='white')
                sheet.paste(glyph,(px+6,py+24))
            sheet.save(audit_dir/f'{phase}-{size}-all.png')
    rows=[(font.FontSize.XLARGE,ch,3) for ch in ['S','0','N','V','W']]
    sheet=Image.new('RGB',(1050,520),(24,24,24)); draw=ImageDraw.Draw(sheet)
    for i,(size,char,scale) in enumerate(rows):
        px,py=(i%3)*350,(i//3)*260
        draw.text((px+10,py+6),f'{char} / 7x9   BEFORE         AFTER',fill='white')
        for j,phase in enumerate(['before','after']):
            x,y,w,h=manifest[phase]['glyphs'][size][char]['rect']
            glyph=atlases[phase].crop((x,y,x+w,y+h)).resize((w*scale,h*scale),Image.Resampling.NEAREST)
            sheet.paste(glyph,(px+10+j*170,py+32))
    sheet.save(OUTPUT/'changes.png')


if __name__=='__main__':
    main()
