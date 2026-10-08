"""Safety configuration isolation tests; no browser is launched."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import verify_agent_browser


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cwd = Path(self.temporary.name)
        self.home = self.cwd / 'home'
        self.user = self.home / '.agent-browser/config.json'
        self.project = self.cwd / 'agent-browser.json'

    def write_config(self, path, values):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(values), encoding='utf-8')

    def settings(self, env=None):
        return verify_agent_browser.isolated_settings(env or {}, self.cwd, self.home)

    def test_env_safeguards_and_unrelated_settings_survive(self):
        safety = {
            'AGENT_BROWSER_ACTION_POLICY': './policy.json',
            'AGENT_BROWSER_ALLOWED_DOMAINS': 'example.com',
            'AGENT_BROWSER_CONFIRM_ACTIONS': 'eval,click',
            'AGENT_BROWSER_CONFIRM_INTERACTIVE': 'true',
            'AGENT_BROWSER_CONTENT_BOUNDARIES': 'true',
            'AGENT_BROWSER_MAX_OUTPUT': '1000',
            'AGENT_BROWSER_NO_AUTO_DIALOG': 'true',
            'AGENT_BROWSER_CA_CERT': './ca.pem',
            'AGENT_BROWSER_DEFAULT_TIMEOUT': '5000',
            'PATH': '/installed',
        }
        inherited = {name: 'inherited' for name in (
            'AGENT_BROWSER_SESSION', 'AGENT_BROWSER_NAMESPACE', 'AGENT_BROWSER_CDP',
            'AGENT_BROWSER_CDP_URL', 'AGENT_BROWSER_CDP_PORT', 'AGENT_BROWSER_AUTO_CONNECT',
            'AGENT_BROWSER_PIN_TAB', 'AGENT_BROWSER_PROFILE', 'AGENT_BROWSER_STATE',
            'AGENT_BROWSER_RESTORE', 'AGENT_BROWSER_RESTORE_SAVE', 'AGENT_BROWSER_SESSION_NAME',
            'AGENT_BROWSER_RESTORE_CHECK_URL', 'AGENT_BROWSER_RESTORE_CHECK_TEXT',
            'AGENT_BROWSER_RESTORE_CHECK_FN', 'AGENT_BROWSER_AUTOSAVE_INTERVAL_MS',
            'AGENT_BROWSER_PROVIDER', 'AGENT_BROWSER_PLUGINS', 'AGENT_BROWSER_IOS_DEVICE',
            'AGENT_BROWSER_IOS_UDID', 'BROWSERBASE_API_KEY', 'BROWSERLESS_API_KEY',
            'BROWSER_USE_PROFILE_ID', 'KERNEL_PROFILE_NAME', 'AGENTCORE_BROWSER_ID',
        )}
        original = {**safety, **inherited}
        env, config = self.settings(original)
        self.assertEqual(env, safety)
        self.assertEqual(config, {})
        self.assertEqual(original, {**safety, **inherited})

    def test_user_project_priority_and_safety_survive_isolation(self):
        self.write_config(self.user, {
            'actionPolicy': './policy.json', 'allowedDomains': ['user.example'],
            'confirmActions': ['eval'], 'confirmInteractive': True,
            'contentBoundaries': True, 'extensions': ['./user-extension'],
            'session': 'shared', 'namespace': 'shared', 'cdp': 9222,
            'autoConnect': True, 'pinTab': True, 'profile': 'Default', 'state': './state.json',
            'restore': 'shared', 'restoreSave': 'always', 'sessionName': 'shared',
            'restoreCheckUrl': '*', 'restoreCheckText': 'hi', 'restoreCheckFn': 'true',
            'autosaveIntervalMs': 1000, 'provider': 'kernel', 'plugins': [{'name': 'cloud'}],
            'iosDevice': 'phone', 'iosUdid': 'device',
        })
        self.write_config(self.project, {'allowedDomains': ['project.example'],
                                         'extensions': ['./project-extension']})
        env, config = self.settings({'AGENT_BROWSER_ALLOWED_DOMAINS': 'env.example'})
        self.assertEqual(env['AGENT_BROWSER_ALLOWED_DOMAINS'], 'env.example')
        self.assertEqual(config, {
            'actionPolicy': './policy.json', 'allowedDomains': ['project.example'],
            'confirmActions': ['eval'], 'confirmInteractive': True, 'contentBoundaries': True,
            'extensions': ['./user-extension', './project-extension'],
        })

    def test_explicit_config_replaces_defaults(self):
        self.user.parent.mkdir(parents=True)
        self.user.write_text('broken', encoding='utf-8')
        self.write_config(self.project, {'allowedDomains': ['project.example']})
        self.write_config(self.cwd / 'explicit.json', {
            'actionPolicy': './explicit-policy.json', 'allowedDomains': ['explicit.example'],
            'confirmActions': ['eval'], 'confirmInteractive': True, 'profile': 'Default',
        })
        for path in ('explicit.json', str(self.cwd / 'explicit.json')):
            with self.subTest(path=path):
                env, config = self.settings({'AGENT_BROWSER_CONFIG': path})
                self.assertNotIn('AGENT_BROWSER_CONFIG', env)
                self.assertEqual(config, {
                    'actionPolicy': './explicit-policy.json', 'allowedDomains': ['explicit.example'],
                    'confirmActions': ['eval'], 'confirmInteractive': True,
                })

    def test_bad_configs_fail_instead_of_discarding_safety(self):
        for content in ('invalid', '[]', 'null', '{"extensions":[]}'):
            with self.subTest(content=content):
                self.write_config(self.user, {'extensions': 'invalid'})
                self.project.write_text(content, encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'config|extensions'):
                    self.settings()
        with self.assertRaisesRegex(ValueError, 'missing.json'):
            self.settings({'AGENT_BROWSER_CONFIG': 'missing.json'})

    def test_config_error_is_reported_before_any_browser_command(self):
        source = self.cwd / 'input.html'
        source.write_text('<html></html>', encoding='utf-8')
        with patch.object(verify_agent_browser.Path, 'cwd', return_value=self.cwd), \
             patch.object(verify_agent_browser.Path, 'home', return_value=self.home), \
             patch.dict('os.environ', {'AGENT_BROWSER_CONFIG': 'missing.json'}, clear=True), \
             patch.object(verify_agent_browser.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'missing.json'):
                verify_agent_browser.verify(source, self.cwd / 'preview')
            run.assert_not_called()
        report = json.loads((self.cwd / 'preview/verification.json').read_text())
        self.assertEqual(report['result'], 'failed')
        self.assertIn('missing.json', report['error'])

    def test_cli_keeps_original_cwd_and_safety_without_browser(self):
        source = self.cwd / 'input.html'
        source.write_text('<html></html>', encoding='utf-8')
        self.write_config(self.project, {'actionPolicy': './policy.json', 'confirmInteractive': True})
        calls = []

        def rejected(command, **kwargs):
            calls.append(command)
            self.assertEqual(kwargs['cwd'], self.cwd)
            self.assertEqual(kwargs['env']['AGENT_BROWSER_ALLOWED_DOMAINS'], 'example.com')
            self.assertNotIn('AGENT_BROWSER_AUTO_CONNECT', kwargs['env'])
            config = json.loads(Path(command[command.index('--config') + 1]).read_text())
            self.assertEqual(config, {'actionPolicy': './policy.json', 'confirmInteractive': True})
            self.assertTrue(command[command.index('--session') + 1].startswith('animate-verify-'))
            raise RuntimeError('policy denied')

        with patch.object(verify_agent_browser.Path, 'cwd', return_value=self.cwd), \
             patch.object(verify_agent_browser.Path, 'home', return_value=self.home), \
             patch.dict('os.environ', {'AGENT_BROWSER_ALLOWED_DOMAINS': 'example.com',
                                      'AGENT_BROWSER_AUTO_CONNECT': 'true'}, clear=True), \
             patch.object(verify_agent_browser.shutil, 'which', return_value='/installed/browser'), \
             patch.object(verify_agent_browser.subprocess, 'run', side_effect=rejected):
            with self.assertRaisesRegex(RuntimeError, 'policy denied'):
                verify_agent_browser.verify(source, self.cwd / 'preview', browser_path='/installed/browser')
        self.assertEqual(calls[-1][-1], 'close')
        self.assertNotIn('confirm', [command[-1] for command in calls])
        report = json.loads((self.cwd / 'preview/verification.json').read_text())
        self.assertEqual(report['result'], 'failed')
        self.assertIn('policy denied', report['error'])


if __name__ == '__main__':
    unittest.main()
