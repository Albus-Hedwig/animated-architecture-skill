#!/usr/bin/env python3
"""Verify an actual generated HTML in an isolated browser; optionally export GIF."""
import argparse
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


def verify(source, output, export_gif=False, preview_step=None):
    source = source.resolve(); output.mkdir(parents=True, exist_ok=True)
    if export_gif:
        from PIL import Image
    errors = []; requests = []; phases = []
    def check(ok, message):
        if not ok:
            raise AssertionError(message)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width':1400, 'height':1100}, device_scale_factor=1)
        def offline(route):
            if route.request.url.startswith(('file:', 'data:')):
                route.continue_()
            else:
                requests.append(route.request.url); route.abort()
        context.route('**/*', offline)
        page = context.new_page(); page.on('pageerror', lambda err: errors.append(str(err)))
        page.goto(source.as_uri()); page.wait_for_function('window.demo !== undefined')
        data = page.evaluate('JSON.parse(document.querySelector("#diagram-data").textContent)')
        state = lambda: page.evaluate('demo.getState()')
        duration = state()['duration']; starts = []; total = 0
        for step in data['steps']:
            starts.append(total); total += step['duration']
        before = state()['time']; page.wait_for_timeout(170)
        check(not state()['paused'] and state()['time'] > before, 'autoplay did not advance')
        page.locator('#toggle').click(); frozen = state()['time']; page.wait_for_timeout(150)
        check(state()['paused'] and state()['time'] == frozen, 'pause did not freeze')
        node_data = {n['id']:n for n in data['nodes']}
        for index, step in enumerate(data['steps']):
            page.evaluate('(t)=>demo.seek(t)', starts[index]+step['duration']*.6)
            check(state()['id'] == step['id'], 'wrong phase')
            check(set(page.locator('.node.is-active').evaluate_all('(es)=>es.map(e=>e.dataset.node)')) == set(step.get('activeNodes',[])), 'wrong active node')
            check(set(page.locator('.route.is-active').evaluate_all('(es)=>es.map(e=>e.dataset.route)')) == set(step.get('activeRoutes',[])), 'wrong active routes')
            for nid, node in node_data.items():
                expected = step.get('nodeStates', {}).get(nid, {})
                for cls, key in (('state','state'), ('operation','operation'), ('node-footer','footer')):
                    check(page.locator('#node-'+nid+' .'+cls).text_content() == expected.get(key,node.get(key,'')), 'wrong '+nid+' '+key)
                for meter in node.get('meters', []):
                    value = expected.get('meterValues', {}).get(meter['id'],meter['value'])
                    actual = page.locator('#node-'+nid+' [data-meter="'+meter['id']+'"] .meter-number').text_content()
                    check(float(actual) == round(value,2), 'wrong meter value')
            overflow = page.locator('.node').evaluate_all('''es=>es.flatMap(n=>{const b=n.getBoundingClientRect();return [...n.querySelectorAll('.node-heading,.node-title,.state,.node-subtitle,.node-lines,.rows,.row-label,.row-value,.meter,.meter-label,.operation,.node-footer')].filter(e=>{const r=e.getBoundingClientRect();return r.left<b.left-1||r.right>b.right+1||r.bottom>b.bottom+1||e.scrollWidth>e.clientWidth+1;}).map(e=>n.dataset.node+':'+e.className);})''')
            check(not overflow, 'node content overflow: '+str(overflow))
            path = output / ('step-%02d.png' % (index+1)); page.locator('#app').screenshot(path=str(path)); phases.append(path)
        print('PASS %d complete phase snapshots and text bounds' % len(phases), flush=True)
        geometry = page.evaluate('''() => {
            const g=demo.getGeometry(),issues=[],samples={};
            for(const r of g.routes){const path=document.querySelector(`[data-route="${r.id}"] .wire-base`);samples[r.id]=[];
              const src=g.nodes.find(n=>n.id===r.source).bounds,tgt=g.nodes.find(n=>n.id===r.target).bounds;
              const boundary=(p,b)=>((Math.abs(p.x-b[0])<.01||Math.abs(p.x-b[0]-b[2])<.01)&&p.y>b[1]&&p.y<b[1]+b[3])||((Math.abs(p.y-b[1])<.01||Math.abs(p.y-b[1]-b[3])<.01)&&p.x>b[0]&&p.x<b[0]+b[2]);
              if(!boundary(path.getPointAtLength(0),src)||!boundary(path.getPointAtLength(r.length),tgt))issues.push(r.id+':endpoint');
              for(let d=0;d<=r.length;d++){const p=path.getPointAtLength(d);samples[r.id].push([p.x,p.y]);for(const n of g.nodes){const [x,y,w,h]=n.bounds;if(p.x>x+.01&&p.x<x+w-.01&&p.y>y+.01&&p.y<y+h-.01)issues.push(r.id+':inside '+n.id);}}
            }
            const sig=()=>JSON.stringify([...document.querySelectorAll('.wire-base,.wire-active,.port,marker')].map(e=>[e.tagName,...['d','marker-end','cx','cy','refX','refY','orient'].map(k=>e.getAttribute(k))]));
            const before=sig(),duration=demo.getState().duration,frames=Math.min(1200,Math.ceil(duration*20));let packets=0;
            for(let i=0;i<frames;i++){demo.seek(duration*i/frames);if(sig()!==before)issues.push('fixed geometry changed');
              for(const rid of demo.getState().activeRoutes){const c=document.querySelector(`[data-route="${rid}"] .packet circle:nth-child(2)`),x=Number(c.getAttribute('cx')),y=Number(c.getAttribute('cy'));if(!samples[rid].some(p=>Math.hypot(p[0]-x,p[1]-y)<1.1))issues.push(rid+':packet off route');packets++;}}
            return{issues:[...new Set(issues)],routes:g.routes.length,frames,packets};
        }''')
        check(not geometry['issues'], 'geometry failed: '+str(geometry['issues']))
        print('PASS %d routes and %d animation positions' % (geometry['routes'],geometry['frames']), flush=True)
        for index in range(len(data['steps'])):
            page.locator('#step-rail button').nth(index).click()
            check(state()['index'] == index and state()['paused'], 'step button failed')
        if len(data['steps']) > 1:
            page.keyboard.press('ArrowLeft'); check(state()['index'] == len(data['steps'])-2, 'focused-button keyboard failed')
            page.locator('#next').click(); check(state()['index'] == len(data['steps'])-1, 'next failed')
            page.locator('#previous').click(); check(state()['index'] == len(data['steps'])-2, 'previous failed')
        target=round(duration*.4,2); page.locator('#scrubber').fill(str(target)); check(abs(state()['time']-target)<.02 and state()['paused'], 'scrubber failed')
        page.locator('#speed').select_option('2'); page.locator('#toggle').click(); before=state()['time']; page.wait_for_timeout(180)
        expected = (before+.36) % duration
        check(state()['speed']==2 and abs(state()['time']-expected)<.3, 'speed failed')
        page.locator('#loop').uncheck(); page.evaluate('(t)=>{demo.seek(t);demo.play()}', max(0,duration-.1)); page.wait_for_timeout(200)
        check(state()['paused'] and state()['time']==duration, 'end without loop failed')
        page.locator('#loop').check(); page.evaluate('(t)=>{demo.seek(t);demo.play()}', max(0,duration-.1)); page.wait_for_timeout(200)
        check(not state()['paused'] and state()['time']<min(duration,1), 'loop failed')
        page.locator('#restart').click(); check(state()['time']<.4 and not state()['paused'], 'restart failed')
        page.evaluate('document.activeElement.blur()'); page.keyboard.press('Space'); check(state()['paused'], 'space failed')
        page.keyboard.press('r'); check(not state()['paused'], 'keyboard restart failed'); page.evaluate('demo.pause()')
        before=state()['scale']; page.locator('#zoom-in').click(); check(state()['scale']>before, 'zoom failed'); page.locator('#zoom-out').click(); page.locator('#fit').click()
        rect=page.locator('#app').bounding_box(); check(rect['y']+rect['height']<=1100, 'desktop fit clips controls')
        page.locator('#fullscreen').click(); page.wait_for_function('document.fullscreenElement!==null'); page.locator('#fullscreen').click(); page.wait_for_function('document.fullscreenElement===null')
        page.set_viewport_size({'width':390,'height':844}); page.wait_for_timeout(100)
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'mobile document overflow')
        for _ in range(3): page.locator('#zoom-in').click()
        check(page.locator('#viewport').evaluate('(e)=>{e.scrollLeft=300;return e.scrollLeft>0}'), 'mobile scroll failed')
        page.locator('#fit').click(); check(page.locator('#viewport').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'), 'mobile fit failed')
        page.screenshot(path=str(output/'mobile.png'),full_page=True)
        reduced=browser.new_context(reduced_motion='reduce'); reduced.route('**/*',offline); rp=reduced.new_page(); rp.goto(source.as_uri()); check(rp.evaluate('demo.getState().paused'), 'reduced motion failed'); reduced.close()
        check(not errors and not requests, 'browser errors or external requests')
        report={'result':'passed','checked_at':datetime.now(timezone.utc).isoformat(),'browser':'isolated Playwright Chromium','browser_version':browser.version,'phases':len(phases),'duration_seconds':duration,'geometry':geometry,'node_content_bounds':'all phases passed','controls':['autoplay','pause','step buttons','previous','next','keyboard','scrubber','speed','end','loop','restart','zoom','fit','fullscreen'],'viewports':[[1400,1100],[390,844]],'reduced_motion':'starts paused','page_errors':errors,'external_requests':requests}
        print('PASS playback controls, fullscreen and desktop/mobile layout',flush=True)
        if preview_step is not None:
            check(1<=preview_step<=len(phases),'preview-step out of range')
        chosen=(preview_step-1) if preview_step else len(phases)//2
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
        (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        browser.close()
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html',type=Path);parser.add_argument('--output-dir',type=Path,default=Path('preview'));parser.add_argument('--gif',action='store_true');parser.add_argument('--preview-step',type=int,help='1-based phase for preview.png')
    args=parser.parse_args()
    verify(args.html,args.output_dir,args.gif,args.preview_step)
