"""Optional browser regression tests: ANIMATE_BROWSER_TESTS=1 enables local Chrome."""
import os
import tempfile
import unittest
from pathlib import Path

import build
import verify_browser


@unittest.skipUnless(os.environ.get('ANIMATE_BROWSER_TESTS') == '1', 'opt-in local browser tests')
class BrowserNegativeTests(unittest.TestCase):
    def rejected(self, old, new, message):
        with tempfile.TemporaryDirectory(prefix='animate-negative-') as temporary:
            source = Path(temporary) / 'diagram.html'
            build.build(Path(__file__).resolve().parent.parent / 'assets/hub-feedback.json', source)
            html = source.read_text(encoding='utf-8')
            self.assertIn(old, html)
            source.write_text(html.replace(old, new), encoding='utf-8')
            with self.assertRaisesRegex(Exception, message):
                verify_browser.verify(source, Path(temporary) / 'preview',
                                      engine=os.environ.get('ANIMATE_BROWSER_ENGINE', 'auto'))

    def test_zero_sized_arrow_is_rejected(self):
        self.rejected('markerWidth:10', 'markerWidth:0', 'arrow invisible')

    def test_frozen_particle_on_route_is_rejected(self):
        self.rejected('point=r.base.getPointAtLength(distance)', 'point=r.base.getPointAtLength(start)', 'packet did not move')

    def test_hidden_particle_is_rejected(self):
        self.rejected('.packet{opacity:0}', '.packet circle{visibility:hidden}.packet{opacity:0}', 'packet invisible')

    def test_only_later_phase_hidden_particles_are_rejected(self):
        self.rejected('.packet{opacity:0}', '[data-route="prepare"] .packet circle{display:none!important}.packet{opacity:0}', 'packet invisible: prepare')

    def test_only_later_phase_frozen_particle_is_rejected(self):
        self.rejected('point=r.base.getPointAtLength(distance)', 'point=r.base.getPointAtLength(id==="prepare"?start:distance)', 'packet did not move: prepare')


if __name__ == '__main__':
    unittest.main()
