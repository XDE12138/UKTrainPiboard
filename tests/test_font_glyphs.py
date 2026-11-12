"""Small invariants for the native LED glyphs, independent of screenshots."""
import os
from pathlib import Path
import string
import sys
import unittest
import pygame

os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'piboard'))
from board.dot_font import (_FONT_5X7, _FONT_7X9, FontSize, _get_bitmap, measure_text,
                            _render_char, _inter_char_gap, render_text)


def components(bitmap,width):
    points={(x,y) for y,row in enumerate(bitmap) for x in range(width)
            if row&(1<<(width-1-x))}
    count=0
    while points:
        stack=[points.pop()];count+=1
        while stack:
            x,y=stack.pop()
            neighbours={(x+dx,y+dy) for dx in [-1,0,1] for dy in [-1,0,1]}&points
            points-=neighbours;stack.extend(neighbours)
    return count


class GlyphTests(unittest.TestCase):
    def test_all_ascii_cells_are_present_and_in_bounds(self):
        for ch in map(chr,range(32,127)):
            self.assertIn(ch,_FONT_5X7)
            for size,width,height in [(FontSize.SMALL,5,7),(FontSize.XLARGE,7,9)]:
                bitmap=_get_bitmap(ch,size)
                self.assertEqual(len(bitmap),height)
                self.assertTrue(all(0<=row<(1<<width) for row in bitmap))

    def test_uppercase_strokes_have_no_disconnected_fragments(self):
        for table,width in [(_FONT_5X7,5),(_FONT_7X9,7)]:
            for ch in string.ascii_uppercase:
                self.assertEqual(components(table[ch],width),1,(width,ch))

    def test_contextual_confusables_are_distinct(self):
        for size in [FontSize.SMALL,FontSize.XLARGE]:
            for a,b in [('0','O'),('S','5'),('Z','2'),('B','8'),('I','1'),('I','l')]:
                self.assertNotEqual(_get_bitmap(a,size),_get_bitmap(b,size),(size,a,b))

    def test_capital_cells_remain_fixed_width(self):
        for size in [FontSize.SMALL,FontSize.MEDIUM,FontSize.LARGE,FontSize.XLARGE]:
            expected=measure_text('A',size)
            for ch in string.ascii_uppercase+string.digits:
                self.assertEqual(measure_text(ch,size),expected)

    def test_v_finishes_at_a_point_and_w_at_two_valleys(self):
        self.assertEqual(_FONT_7X9['V'][-1],0x08)
        self.assertNotEqual(_FONT_7X9['V'][-2],0x08)
        self.assertEqual(_FONT_5X7['W'][-1],0x0A)
        self.assertEqual(_FONT_7X9['W'][-1],0x22)

    def test_neighbouring_glyphs_keep_three_clear_pixel_columns(self):
        pygame.font.init()
        chars=''.join(chr(code) for code in range(33,127))+'°日程项目进度会议天气北京'
        for size in [FontSize.SMALL,FontSize.MEDIUM,FontSize.LARGE,FontSize.XLARGE]:
            boxes={}
            for char in chars:
                surface=_render_char(char,size,(255,149,0))
                mask=pygame.mask.from_threshold(surface,(255,149,0,255),(1,1,1,1))
                rects=mask.get_bounding_rects()
                self.assertTrue(rects,(size,char))
                boxes[char]=(surface.get_width(),rects[0].unionall(rects))
            for a in chars:
                for b in chars:
                    width,box=boxes[a]
                    gap=width+_inter_char_gap(a,b,size)+boxes[b][1].left-box.right
                    self.assertGreaterEqual(gap,3,(size,a,b,gap))

    def test_whole_strings_fit_the_same_width_they_paint(self):
        for size in [FontSize.SMALL,FontSize.MEDIUM,FontSize.LARGE,FontSize.XLARGE]:
            for text in ['VVWW NNMM','rn m cl d III111','SWANSEA 08:35 UK','项目会议 09:30']:
                width,height=measure_text(text,size)
                surface=pygame.Surface((width,height))
                self.assertEqual(render_text(surface,text,0,0,size,(255,149,0)),width)


if __name__=='__main__':
    unittest.main()
