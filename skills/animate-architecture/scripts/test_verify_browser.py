"""Backend selection and failure propagation; no browser or extra dependency needed."""
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import verify_browser


class VerifierTests(unittest.TestCase):
    available = {'agent_browser': '/installed/agent-browser', 'playwright': True, 'system_browser': None}

    def test_auto_reuses_agent_browser(self):
        self.assertEqual(verify_browser.select_engine('auto', False, self.available), 'agent-browser')

    def test_auto_uses_playwright_without_cli(self):
        self.assertEqual(verify_browser.select_engine('auto', False, {'agent_browser': None, 'playwright': True}), 'playwright')

    def test_gif_preserves_playwright_path(self):
        self.assertEqual(verify_browser.select_engine('auto', True, self.available), 'playwright')
        with self.assertRaises(ValueError):
            verify_browser.select_engine('agent-browser', True, self.available)

    def test_missing_dependency_fails(self):
        with self.assertRaises(RuntimeError):
            verify_browser.select_engine('auto', False, {'agent_browser': None, 'playwright': False})

    def test_macos_app_browser_is_discovered_without_path_entry(self):
        chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        with patch.object(verify_browser.shutil, 'which', return_value=None), \
             patch.object(verify_browser.os, 'access', side_effect=lambda path, mode: str(path) == chrome):
            self.assertEqual(verify_browser.installed_browser(), chrome)

    def test_native_reuses_installed_browser_unless_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'input.html'; source.write_text('<html></html>')
            explicit = Path(temporary) / 'chrome'; explicit.touch()
            available = dict(self.available, system_browser='/installed/chrome')
            for path, expected in ((None, '/installed/chrome'), (explicit, explicit)):
                with self.subTest(path=path), \
                     patch.object(verify_browser, 'environment', return_value=available), \
                     patch.object(verify_browser, 'verify_playwright', return_value={'result':'passed'}) as native:
                    verify_browser.verify(source, Path(temporary) / 'preview', engine='playwright', browser_path=path)
                    self.assertEqual(native.call_args.args[-1], expected)

    def test_failed_validation_is_not_retried_on_other_engine(self):
        def rejected(source, output, **options):
            (output / 'verification.json').write_text(json.dumps({'result':'failed', 'coverage':['phase check'], 'page_errors':['bad arrow']}), encoding='utf-8')
            raise AssertionError('bad arrow')
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'input.html'
            source.write_text('<html></html>', encoding='utf-8')
            output = Path(temporary) / 'preview'
            with patch.object(verify_browser, 'environment', return_value=self.available), \
                 patch.object(verify_browser, 'verify_playwright') as native, \
                 patch.dict('sys.modules', {'verify_agent_browser':types.SimpleNamespace(verify=rejected)}):
                with self.assertRaisesRegex(AssertionError, 'bad arrow'):
                    verify_browser.verify(source, output)
                native.assert_not_called()
            report = json.loads((output / 'verification.json').read_text(encoding='utf-8'))
            self.assertEqual(report['result'], 'failed')
            self.assertEqual(report['engine'], 'agent-browser')
            self.assertEqual(report['page_errors'], ['bad arrow'])

    def test_startup_failure_does_not_reuse_previous_report(self):
        def rejected(*args, **options):
            raise ImportError('missing adapter')
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'input.html'
            source.write_text('<html></html>', encoding='utf-8')
            output = Path(temporary) / 'preview'; output.mkdir()
            (output / 'verification.json').write_text(json.dumps({'result':'failed', 'session':'old', 'coverage':['old check']}), encoding='utf-8')
            with patch.object(verify_browser, 'environment', return_value=self.available), \
                 patch.dict('sys.modules', {'verify_agent_browser':types.SimpleNamespace(verify=rejected)}):
                with self.assertRaisesRegex(ImportError, 'missing adapter'):
                    verify_browser.verify(source, output)
            report = json.loads((output / 'verification.json').read_text(encoding='utf-8'))
            self.assertNotIn('session', report)
            self.assertNotIn('coverage', report)

    def test_corrupt_report_does_not_mask_original_error(self):
        def rejected(source, output, **options):
            (output / 'verification.json').write_text('invalid JSON', encoding='utf-8')
            raise AssertionError('real failure')
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'input.html'
            source.write_text('<html></html>', encoding='utf-8')
            output = Path(temporary) / 'preview'
            with patch.object(verify_browser, 'environment', return_value=self.available), \
                 patch.dict('sys.modules', {'verify_agent_browser':types.SimpleNamespace(verify=rejected)}):
                with self.assertRaisesRegex(AssertionError, 'real failure'):
                    verify_browser.verify(source, output)
            self.assertEqual(json.loads((output / 'verification.json').read_text(encoding='utf-8'))['error'], 'real failure')


if __name__ == '__main__':
    unittest.main()
