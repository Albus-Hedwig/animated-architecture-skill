#!/usr/bin/env python3
"""Verify offline architecture HTML with installed agent-browser and Chrome (no GIF)."""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from verify_browser import installed_browser


def isolated_settings(environ, cwd: Path, home: Path):
    """Keep CLI defaults and safeguards, excluding inherited browser ownership."""
    isolated = {
        'session', 'namespace', 'sessionName', 'cdp', 'cdpUrl', 'cdpPort',
        'autoConnect', 'pinTab', 'profile', 'state', 'restore', 'restoreSave',
        'restoreCheckUrl', 'restoreCheckText', 'restoreCheckFn', 'autosaveIntervalMs',
        'provider', 'plugins', 'iosDevice', 'iosUdid', 'device', 'udid',
    }
    isolated_env = {'AGENT_BROWSER_' + name for name in (
        'CONFIG', 'SESSION', 'NAMESPACE', 'SESSION_NAME', 'CDP', 'CDP_URL', 'CDP_PORT',
        'AUTO_CONNECT', 'PIN_TAB', 'PROFILE', 'STATE', 'RESTORE', 'RESTORE_SAVE',
        'RESTORE_CHECK_URL', 'RESTORE_CHECK_TEXT', 'RESTORE_CHECK_FN', 'AUTOSAVE_INTERVAL_MS',
        'PROVIDER', 'PLUGINS', 'IOS_DEVICE', 'IOS_UDID',
    )}
    explicit = environ.get('AGENT_BROWSER_CONFIG')
    paths = [cwd / explicit] if explicit else [home / '.agent-browser/config.json', cwd / 'agent-browser.json']
    config = {}
    for path in paths:
        try:
            values = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError as error:
            if not explicit and not path.is_symlink():
                continue
            raise ValueError(f'Cannot read agent-browser config: {path}') from error
        except (OSError, ValueError) as error:
            raise ValueError(f'Cannot read agent-browser config: {path}') from error
        if not isinstance(values, dict):
            raise ValueError(f'agent-browser config must be an object: {path}')
        if 'extensions' in config and 'extensions' in values:
            if not isinstance(config['extensions'], list) or not isinstance(values['extensions'], list):
                raise ValueError(f'agent-browser extensions must be an array: {path}')
            values['extensions'] = config['extensions'] + values['extensions']
        config.update(values)
    env = {key: value for key, value in environ.items()
           if key not in isolated_env
           and not key.startswith(('BROWSERBASE_', 'BROWSERLESS_', 'BROWSER_USE_', 'KERNEL_', 'AGENTCORE_'))}
    return env, {key: value for key, value in config.items() if key not in isolated}


def verify(source: Path, output: Path, preview_step=None, all_steps=False, browser_path=None) -> dict:
    source = source.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    session = 'animate-verify-' + uuid.uuid4().hex
    report = {'result': 'failed', 'backend': 'agent-browser', 'browser': 'isolated local Chrome via CDP',
              'session': session, 'checked_at': datetime.now(timezone.utc).isoformat(),
              'coverage': [], 'page_errors': [], 'external_requests': [], 'gif': 'unsupported; use Playwright entry point'}
    cwd = Path.cwd()
    started = False
    failure = None
    with tempfile.TemporaryDirectory(prefix='animate-agent-browser-') as temporary:
        config = Path(temporary) / 'config.json'
        command = []

        def cli(*args, script=None):
            result = subprocess.run(command + list(args), input=script, text=True, capture_output=True,
                                    env=env, cwd=cwd, timeout=60)
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError as error:
                raise RuntimeError(f'agent-browser {args[0]} returned invalid JSON: {result.stdout[:1000]} {result.stderr[:1000]}') from error
            if result.returncode or not payload.get('success'):
                raise RuntimeError(f'agent-browser {args[0]} failed: {payload.get("error", payload)} {result.stderr[:1000]}')
            return payload.get('data', {})

        def evaluate(script):
            return cli('eval', '--stdin', script=script)['result']

        def check(expression, message):
            if not evaluate(expression):
                raise AssertionError(message)

        def diagnostics():
            browser_errors = cli('errors').get('errors', [])
            logs = cli('console').get('messages', [])
            requests = cli('network', 'requests').get('requests', [])
            observed = evaluate('window.__architectureDiagnostics()')
            report['page_errors'].extend(browser_errors + observed['errors'])
            report['page_errors'].extend(item for item in logs if item.get('type') == 'error')
            report['external_requests'].extend(item for item in requests if not item.get('url', '').startswith(('file:', 'data:', 'about:')))
            report['external_requests'].extend(observed['externalRequests'])

        try:
            if not source.is_file():
                raise FileNotFoundError(source)
            env, settings = isolated_settings(os.environ, cwd, Path.home())
            # Keep the caller's cwd so relative policy paths retain CLI semantics.
            config.write_text(json.dumps(settings), encoding='utf-8')
            executable = browser_path or os.environ.get('AGENT_BROWSER_EXECUTABLE_PATH')
            if not executable:
                executable = installed_browser()
            if not executable:
                cached = sorted((Path.home() / '.cache' / 'ms-playwright').glob('chromium-*/chrome-linux*/chrome'))
                executable = next((str(path) for path in reversed(cached) if os.access(path, os.X_OK)), None)
            executable = shutil.which(str(executable)) if executable else None
            if not executable:
                raise RuntimeError('Installed Chrome not found; pass --browser-path (no browser will be installed)')
            if not shutil.which('agent-browser'):
                raise RuntimeError('Installed agent-browser is required')
            report['browser_path'] = executable
            command = ['agent-browser', '--config', str(config), '--session', session, '--json',
                       '--executable-path', executable, '--headed', 'false', '--allow-file-access', '--init-script',
                       str(Path(__file__).with_name('browser_checks.js')), '--args', '--disable-background-networking']
            started = True
            cli('set', 'offline', 'on')
            cli('set', 'viewport', '1400', '1100', '1')
            cli('network', 'route', 'http*://*', '--abort')
            cli('network', 'requests', '--clear')
            cli('open', source.as_uri())
            cli('wait', '--fn', 'window.demo !== undefined && window.__architectureChecks !== undefined')
            report['browser_version'] = evaluate('navigator.userAgent')
            batch = evaluate('window.__architectureChecks()')
            report.update({key: value for key, value in batch.items() if key not in ('starts', 'durations', 'checked')})
            report['coverage'].extend(batch['checked'])
            count = batch['phases']
            if preview_step is not None and not 1 <= preview_step <= count:
                raise ValueError('preview-step out of range')
            chosen = preview_step - 1 if preview_step is not None else count // 2
            evaluate(f'demo.seek({batch["starts"][chosen] + batch["durations"][chosen] * .6})')
            cli('screenshot', str(output / 'preview.png'))
            if all_steps:
                for index, (start, duration) in enumerate(zip(batch['starts'], batch['durations'])):
                    evaluate(f'demo.seek({start + duration * .6})')
                    cli('screenshot', str(output / f'step-{index+1:02d}.png'))
            report['screenshots'] = ['preview.png', 'mobile.png'] + ([f'step-{i+1:02d}.png' for i in range(count)] if all_steps else [])
            evaluate('demo.seek(0); document.activeElement.blur()')
            cli('press', 'Space')
            check('!demo.getState().paused', 'Space did not play')
            cli('press', 'Space')
            check('demo.getState().paused', 'Space did not pause')
            cli('press', 'r')
            check('!demo.getState().paused', 'keyboard restart failed')
            evaluate('demo.seek(0)')
            if count > 1:
                cli('focus', '#step-rail button:first-child')
                cli('press', 'ArrowRight')
                check('demo.getState().index === 1', 'focused-button ArrowRight failed')
                cli('press', 'ArrowLeft')
                check('demo.getState().index === 0', 'focused-button ArrowLeft failed')
            report['coverage'].append('real keyboard Space/r/ArrowLeft/ArrowRight')
            cli('click', '#fullscreen')
            cli('wait', '--fn', 'document.fullscreenElement === document.getElementById("app")')
            cli('click', '#fullscreen')
            cli('wait', '--fn', 'document.fullscreenElement === null')
            report['coverage'].append('real fullscreen enter/exit clicks')
            cli('set', 'viewport', '390', '844', '1')
            cli('wait', '--fn', 'innerWidth === 390 && innerHeight === 844')
            check('document.documentElement.scrollWidth <= innerWidth', 'mobile document overflow')
            evaluate('for(let i=0;i<3;i++)document.getElementById("zoom-in").click()')
            check('(()=>{const v=document.getElementById("viewport");v.scrollLeft=300;return v.scrollLeft>0})()', 'mobile horizontal scroll failed')
            evaluate('document.getElementById("fit").click()')
            evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
            fit = evaluate('(()=>{const v=document.getElementById("viewport");return {width:v.clientWidth, scrollWidth:v.scrollWidth, scale:demo.getState().scale}})()')
            if fit['scrollWidth'] > fit['width'] + 1:
                raise AssertionError('mobile fit failed: ' + json.dumps(fit))
            check('(()=>{const r=document.querySelector(".controls").getBoundingClientRect();return r.left>=0 && r.right<=innerWidth && r.bottom<=innerHeight})()', 'mobile controls clipped')
            cli('screenshot', str(output / 'mobile.png'), '--full')
            report['viewports'] = [[1400, 1100], [390, 844]]
            report['coverage'].append('mobile document bounds, horizontal scroll, fit and controls')
            diagnostics()
            cli('set', 'media', 'dark', 'reduced-motion')
            cli('reload')
            cli('wait', '--fn', 'window.demo !== undefined')
            check('matchMedia("(prefers-reduced-motion: reduce)").matches && demo.getState().paused', 'reduced motion did not start paused')
            report['reduced_motion'] = 'starts paused with actual browser media emulation'
            report['coverage'].append('reduced-motion preference before reload')
            diagnostics()
            if report['page_errors'] or report['external_requests']:
                raise AssertionError('browser errors or external requests; see verification.json')
            report['coverage'].append('offline, request log, resource timing, page errors and console errors')
            report['result'] = 'passed'
        except Exception as error:
            failure = error
            report['error'] = f'{type(error).__name__}: {error}'
            if started:
                try:
                    diagnostics()
                except Exception as diagnostic_error:
                    report['diagnostics_error'] = str(diagnostic_error)
        finally:
            if started:
                try:
                    cli('close')
                except Exception as error:
                    report['cleanup_error'] = str(error)
                    if failure is None:
                        failure = error
                        report['result'] = 'failed'
                        report['error'] = f'Could not close owned session: {error}'
            (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if failure is not None:
        raise failure
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('preview'))
    parser.add_argument('--preview-step', type=int, help='1-based phase for preview.png')
    parser.add_argument('--all-steps', action='store_true', help='also capture every phase')
    parser.add_argument('--browser-path', type=Path, help='installed Chrome executable')
    args = parser.parse_args()
    verify(args.html, args.output_dir, args.preview_step, args.all_steps, args.browser_path)
