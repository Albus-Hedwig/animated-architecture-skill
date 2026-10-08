#!/usr/bin/env python3
"""Verify an actual generated HTML in an isolated browser; optionally export GIF."""
import argparse
import importlib.util
import io
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

def verify_playwright(source, output, export_gif=False, preview_step=None, all_steps=False, browser_path=None):
    from playwright.sync_api import sync_playwright
    source = source.resolve(); output.mkdir(parents=True, exist_ok=True)
    if export_gif:
        from PIL import Image
    errors = []; requests = []
    def check(ok, message):
        if not ok:
            raise AssertionError(message)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, **({'executable_path': str(browser_path)} if browser_path else {}))
        context = browser.new_context(viewport={'width':1400, 'height':1100}, device_scale_factor=1)
        def offline(route):
            if route.request.url.startswith(('file:', 'data:')):
                route.continue_()
            else:
                requests.append(route.request.url); route.abort()
        context.route('**/*', offline)
        context.add_init_script(path=str(Path(__file__).with_name('browser_checks.js')))
        page = context.new_page(); page.on('pageerror', lambda err: errors.append(str(err)))
        page.goto(source.as_uri()); page.wait_for_function('window.demo !== undefined')
        batch = page.evaluate('window.__architectureChecks()')
        count = batch['phases']; duration = batch['duration_seconds']
        if preview_step is not None:
            check(1 <= preview_step <= count, 'preview-step out of range')
        chosen = preview_step - 1 if preview_step else count // 2
        phases = [output / ('step-%02d.png' % (i+1)) for i in range(count)]
        for index, (start, step_duration) in enumerate(zip(batch['starts'], batch['durations'])):
            if all_steps or export_gif or index == chosen:
                page.evaluate('(t)=>demo.seek(t)', start + step_duration*.6)
                page.locator('#app').screenshot(path=str(phases[index] if all_steps or export_gif else output/'preview.png'))
        page.evaluate('demo.seek(0); document.activeElement.blur()')
        page.keyboard.press('Space'); check(not page.evaluate('demo.getState().paused'), 'Space did not play')
        page.keyboard.press('Space'); check(page.evaluate('demo.getState().paused'), 'Space did not pause')
        page.keyboard.press('r'); check(not page.evaluate('demo.getState().paused'), 'keyboard restart failed')
        page.evaluate('demo.seek(0)')
        if count > 1:
            page.locator('#step-rail button').first.focus()
            page.keyboard.press('ArrowRight'); check(page.evaluate('demo.getState().index === 1'), 'ArrowRight failed')
            page.keyboard.press('ArrowLeft'); check(page.evaluate('demo.getState().index === 0'), 'ArrowLeft failed')
        page.locator('#fullscreen').click(); page.wait_for_function('document.fullscreenElement!==null')
        page.locator('#fullscreen').click(); page.wait_for_function('document.fullscreenElement===null')
        page.set_viewport_size({'width':390, 'height':844})
        page.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'mobile document overflow')
        page.evaluate('for(let i=0;i<3;i++)document.getElementById("zoom-in").click()')
        check(page.locator('#viewport').evaluate('(e)=>{e.scrollLeft=300;return e.scrollLeft>0}'), 'mobile scroll failed')
        page.evaluate('document.getElementById("fit").click()')
        page.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
        check(page.locator('#viewport').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'), 'mobile fit failed')
        check(page.locator('.controls').evaluate('(e)=>{const r=e.getBoundingClientRect();return r.left>=0 && r.right<=innerWidth && r.bottom<=innerHeight}'), 'mobile controls clipped')
        page.screenshot(path=str(output/'mobile.png'),full_page=True)
        observed = page.evaluate('window.__architectureDiagnostics()')
        errors.extend(observed['errors']); requests.extend(observed['externalRequests'])
        reduced=browser.new_context(reduced_motion='reduce')
        reduced.route('**/*',offline); reduced.add_init_script(path=str(Path(__file__).with_name('browser_checks.js')))
        rp=reduced.new_page(); rp.goto(source.as_uri()); rp.wait_for_function('window.demo !== undefined')
        check(rp.evaluate('demo.getState().paused'), 'reduced motion failed')
        observed = rp.evaluate('window.__architectureDiagnostics()')
        errors.extend(observed['errors']); requests.extend(observed['externalRequests']); reduced.close()
        check(not errors and not requests, 'browser errors or external requests: '+str(errors+requests))
        report={key:value for key,value in batch.items() if key not in ('starts','durations','checked')}
        report.update(result='passed', checked_at=datetime.now(timezone.utc).isoformat(),
                      browser='isolated Playwright Chromium', browser_version=browser.version,
                      coverage=batch['checked']+['real keyboard','real fullscreen','mobile fit and controls','reduced motion','offline/page errors'],
                      viewports=[[1400,1100],[390,844]], reduced_motion='starts paused',
                      page_errors=errors, external_requests=requests)
        print('PASS %d phases, %d routes, playback controls and desktop/mobile layout' % (count, batch['geometry']['routes']), flush=True)
        if all_steps or export_gif:
            (output/'preview.png').write_bytes(phases[chosen].read_bytes())
        if export_gif:
            page.set_viewport_size({'width':1400,'height':1100}); page.locator('#fit').click(); page.locator('#speed').select_option('1'); page.evaluate('document.activeElement.blur()')
            palette_samples=Image.new('RGB',(600,450))
            for i,index in enumerate((0,len(phases)//2,len(phases)-1)):
                image=Image.open(phases[index]).convert('RGB'); image.thumbnail((600,150)); palette_samples.paste(image,(0,i*150))
            palette=palette_samples.quantize(colors=256); frames=[]
            # Keep preview exports bounded for long walkthroughs; HTML retains full duration.
            fps=min(10,600/duration); count=max(1,int(duration*fps)); delay=max(10,round(duration*1000/count/10)*10)
            for i in range(count):
                page.evaluate('(t)=>demo.seek(t)',duration*i/count)
                shot=Image.open(io.BytesIO(page.locator('#app').screenshot())).convert('RGB'); shot=shot.resize((1000,round(shot.height*1000/shot.width)),Image.Resampling.LANCZOS)
                frames.append(shot.quantize(palette=palette,dither=Image.Dither.NONE))
                if i%100==0: print('GIF %d / %d' % (i,count),flush=True)
            frames[0].save(output/'demo.gif',save_all=True,append_images=frames[1:],duration=delay,loop=0,optimize=True)
            report['gif']={'source':'actual browser screenshots','frames':count,'frame_duration_ms':delay,'duration_ms':count*delay}
        (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
        browser.close()
    return report


def installed_browser():
    executable = next((path for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'microsoft-edge') if (path := shutil.which(name))), None)
    if executable:
        return executable
    for directory in (Path('/Applications'), Path.home() / 'Applications'):
        for app in ('Google Chrome', 'Chromium', 'Microsoft Edge'):
            executable = directory / (app + '.app') / 'Contents/MacOS' / app
            if os.access(executable, os.X_OK):
                return str(executable)
    return None


def environment():
    return {
        'agent_browser': shutil.which('agent-browser'),
        'playwright': importlib.util.find_spec('playwright') is not None,
        'system_browser': installed_browser(),
    }


def select_engine(requested, export_gif, available):
    if requested != 'auto':
        engine = requested
    elif export_gif:
        engine = 'playwright'
    elif available['agent_browser']:
        engine = 'agent-browser'
    else:
        engine = 'playwright'
    if engine == 'agent-browser' and export_gif:
        raise ValueError('GIF export requires --engine playwright; agent-browser verifies HTML and PNG only')
    if engine == 'agent-browser' and not available['agent_browser']:
        raise RuntimeError('agent-browser is not installed; no dependencies were installed')
    if engine == 'playwright' and not available['playwright']:
        raise RuntimeError('Playwright is not installed; use the installed agent-browser for HTML/PNG verification')
    return engine


def verify(source, output, export_gif=False, preview_step=None, engine='auto', all_steps=False, browser_path=None):
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    selected = None
    try:
        source = source.resolve(strict=True)
        if browser_path and not Path(browser_path).is_file():
            raise ValueError('browser executable does not exist: ' + str(browser_path))
        available = environment()
        selected = select_engine(engine, export_gif, available)
        (output / 'verification.json').write_text('{"result":"running"}\n', encoding='utf-8')
        if selected == 'agent-browser':
            from verify_agent_browser import verify as verify_agent
            report = verify_agent(source, output, preview_step=preview_step, all_steps=all_steps,
                                  browser_path=browser_path)
        else:
            report = verify_playwright(source, output, export_gif, preview_step, all_steps,
                                       browser_path or available['system_browser'])
        report['engine'] = selected
        report['elapsed_seconds'] = round(time.perf_counter() - started, 3)
        (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return report
    except Exception as error:
        failure = {}
        report_file = output / 'verification.json'
        if selected == 'agent-browser' and report_file.is_file():
            try:
                candidate = json.loads(report_file.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                candidate = {}
            if isinstance(candidate, dict) and candidate.get('result') == 'failed':
                failure = candidate
        failure.update(result='failed', engine=selected, error=str(error),
                       elapsed_seconds=round(time.perf_counter() - started, 3))
        report_file.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html',type=Path,nargs='?');parser.add_argument('--output-dir',type=Path,default=Path('preview'));parser.add_argument('--gif',action='store_true');parser.add_argument('--preview-step',type=int,help='1-based phase for preview.png')
    parser.add_argument('--engine', choices=['auto', 'playwright', 'agent-browser'], default='auto')
    parser.add_argument('--browser-path', type=Path, help='use an already-installed browser executable')
    parser.add_argument('--all-steps', action='store_true', help='also export a PNG for every checked phase')
    parser.add_argument('--doctor', action='store_true', help='report available engines without launching or installing a browser')
    args=parser.parse_args()
    if args.doctor:
        print(json.dumps(environment(), ensure_ascii=False))
    elif args.html is None:
        parser.error('html is required unless --doctor is used')
    else:
        try:
            report = verify(args.html,args.output_dir,args.gif,args.preview_step,args.engine,args.all_steps,args.browser_path)
            print(json.dumps({'result':report['result'], 'engine':report['engine'], 'elapsed_seconds':report['elapsed_seconds']}, ensure_ascii=False))
        except Exception as error:
            parser.exit(1, 'Verification failed: ' + str(error) + '\n')
