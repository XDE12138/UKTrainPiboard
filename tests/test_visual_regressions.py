"""Geometry and animation checks for the railway display presentation layer."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "piboard"))
import pygame
from board.board_renderer import BoardRenderer
from board.dot_font import FontSize, measure_text, render_text, normalize_text, fit_text
from board.animations import TickerAnimation, PageFlipAnimation, ContentTransitionAnimation
from config import COLORS
from visual_review import specimens


class VisualRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((1, 1))
        cls.pages = specimens()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_title_and_header_stay_inside_their_regions(self):
        renderer = BoardRenderer(COLORS)
        for w, h in [(600,1024), (1024,600), (600,512), (512,600)]:
            for name, content in self.pages.items():
                surface = pygame.Surface((w,h))
                hh, th, fh = renderer._region_heights(w,h,content)
                self.assertGreater(h-hh-th-fh, 0, name)
                for label, y, height, draw in [
                    ('header', 0, hh, renderer._draw_header),
                    ('title', hh, th, renderer._draw_title),
                ]:
                    rects = []
                    def left(s, text, x, ty, size, color):
                        tw, tall = measure_text(text, size)
                        rects.append(pygame.Rect(x, ty, tw, tall))
                    def right(s, text, edge, ty, size, color):
                        tw, tall = measure_text(text, size)
                        rects.append(pygame.Rect(edge-tw, ty, tw, tall))
                    with patch('board.board_renderer.render_text', left), patch(
                            'board.board_renderer.render_text_right_aligned', right):
                        draw(surface, content, 0, y, w, height)
                    region = pygame.Rect(0,y,w,height)
                    for rect in rects:
                        self.assertTrue(region.contains(rect), (name, label, (w,h), region, rect))

    def test_mixed_glyphs_are_centered_without_resizing(self):
        from board.dot_font import _render_char
        for size in [FontSize.SMALL, FontSize.MEDIUM, FontSize.LARGE, FontSize.XLARGE]:
            text = 'A项目B'
            width, height = measure_text(text, size)
            target = pygame.Surface((width,height), pygame.SRCALPHA)
            self.assertEqual(render_text(target,text,0,0,size,COLORS['amber']),width)
            latin = _render_char('A',size,COLORS['amber'])
            expected = pygame.Surface((width,height),pygame.SRCALPHA)
            expected.blit(latin,(0,(height-latin.get_height())//2))
            self.assertEqual(pygame.image.tostring(target.subsurface((0,0,latin.get_width(),height)),'RGBA'),
                             pygame.image.tostring(expected.subsurface((0,0,latin.get_width(),height)),'RGBA'))

    def test_punctuation_and_fitting_use_same_width_as_rendering(self):
        for size in [FontSize.SMALL, FontSize.MEDIUM, FontSize.LARGE, FontSize.XLARGE]:
            text = 'King’s Cross – 北京 • 08:30…'
            self.assertEqual(measure_text(text,size), measure_text(normalize_text(text),size))
            for width in [100,260,488,576]:
                fitted = fit_text(text,size,width)
                self.assertLessEqual(measure_text(fitted,size)[0],width)

    def test_static_ticker_pages_preserve_unicode_without_overflow(self):
        text = 'Platform information 项目进度说明及下一班车时间 '*4
        renderer = BoardRenderer(COLORS)
        for width in [260,488,576,1000]:
            pages = renderer.ticker_pages(text,width)
            self.assertEqual(''.join(''.join(pages).split()),''.join(text.split()))
            for page in pages:
                self.assertLessEqual(measure_text(page,FontSize.SMALL)[0],width-24)

    def test_ticker_does_not_jump_after_idle(self):
        ticker = TickerAnimation(60)
        ticker.set_text('First announcement')
        with patch('pygame.time.get_ticks',return_value=100): ticker.update()
        ticker.set_text(None)
        ticker.set_text('Second announcement')
        with patch('pygame.time.get_ticks',return_value=100000):
            self.assertEqual(ticker.update(),0)

    def test_page_wrap_does_not_scroll_back_through_intermediate_pages(self):
        flip = PageFlipAnimation()
        flip.configure(30,100,30)
        flip._page = flip._total_pages-1
        with patch('pygame.time.get_ticks',return_value=flip._last_page_time+flip.interval_ms+1):
            self.assertEqual(flip.update(),0)
        self.assertFalse(flip._flipping)

    def test_transition_clears_pixels_outside_sliding_content(self):
        transition = ContentTransitionAnimation(500)
        old = pygame.Surface((100,100)); old.fill((20,20,20))
        new = pygame.Surface((100,100)); new.fill((30,30,30))
        target = pygame.Surface((100,100)); target.fill((255,0,255))
        second = pygame.Surface((100,100)); second.fill((0,0,0))
        with patch('pygame.time.get_ticks',return_value=100): transition.trigger(old)
        with patch('pygame.time.get_ticks',return_value=350):
            transition.update(new,target)
            transition.update(new,second)
        self.assertEqual(pygame.image.tostring(target,'RGB'),pygame.image.tostring(second,'RGB'))

    def test_static_mode_reaches_every_row_page_without_continuous_animation(self):
        from apps.uk_station.app import UKStationApp
        from layouts.single import SingleLayout
        from layouts.dual import DualLayout
        from layouts.carousel import CarouselLayout
        from providers.custom import CustomProvider
        for cls in [SingleLayout, DualLayout, CarouselLayout]:
            provider = CustomProvider({})
            provider._cached_content = self.pages['dense']
            app = UKStationApp({cls.layout_id: cls(COLORS)}, {'custom':provider},
                               cls.layout_id, ['custom'], {'animations_enabled':False})
            surface = pygame.Surface((600,1024))
            with patch('pygame.time.get_ticks',return_value=100): app.render(surface,0)
            layout = app._current_layout
            controller = layout._anims[0] if hasattr(layout,'_anims') else layout._anim
            page = controller.page_flip
            self.assertGreater(page._total_pages,1)
            for expected in range(1,page._total_pages):
                due = page._last_page_time + page.interval_ms + 1
                self.assertEqual(app.next_render_ms(due-1),due)
                with patch('pygame.time.get_ticks',return_value=due): app.render(surface,0)
                self.assertEqual(page._page,expected)
                self.assertFalse(page._flipping)
                self.assertFalse(app.is_animating())

    def test_same_count_glyph_changes_recalculate_pagination(self):
        from board.content import BoardContent, BoardRow
        from providers.custom import CustomProvider
        from layouts.single import SingleLayout
        from layouts.dual import DualLayout
        from layouts.carousel import CarouselLayout
        for cls in [SingleLayout,DualLayout,CarouselLayout]:
            provider = CustomProvider({})
            provider._cached_content = BoardContent(title='LIST',provider_id='custom',
                                                     rows=[BoardRow('Row') for _ in range(30)])
            layout = cls(COLORS,animations_enabled=False)
            screen = pygame.Surface((600,1024) if cls is DualLayout else (600,512))
            layout.render(screen,[provider])
            anim = layout._anims[0] if hasattr(layout,'_anims') else layout._anim
            self.assertEqual(anim.page_flip._row_height,29)
            provider._cached_content.rows[0] = BoardRow('项目')
            layout.render(screen,[provider])
            self.assertEqual(anim.page_flip._row_height,32)


if __name__ == '__main__':
    unittest.main()
