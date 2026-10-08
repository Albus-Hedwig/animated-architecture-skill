// Installed before navigation; checks are invoked in one batch after demo is ready.
(() => {
  const errors = [];
  addEventListener('error', event => errors.push(event.message || 'resource failed: ' + (event.target.src || event.target.href || event.target.tagName)), true);
  addEventListener('unhandledrejection', event => errors.push(String(event.reason)));
  window.__architectureDiagnostics = () => ({
    errors: [...errors],
    externalRequests: performance.getEntriesByType('resource').map(r => r.name).filter(url => !/^(file:|data:)/.test(url))
  });
  window.__architectureChecks = async () => {
    const check = (ok, message) => { if (!ok) throw new Error(message); };
    const $ = id => document.getElementById(id);
    const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
    const visible = element => {
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility === 'visible' && Number(style.opacity) > 0;
    };
    const data = JSON.parse($('diagram-data').textContent);
    const state = () => window.demo.getState();
    const nodes = [...document.querySelectorAll('.node')];
    const routes = [...document.querySelectorAll('.route')];
    const starts = [];
    let duration = 0;
    for (const step of data.steps) { starts.push(duration); duration += step.duration; }
    check(nodes.length === data.nodes.length && routes.length === data.routes.length, 'missing nodes/routes');
    check(Math.abs(state().duration - duration) < 1e-6, 'wrong duration');
    const before = state().time;
    await delay(170);
    check(!state().paused && state().time !== before, 'autoplay did not advance');
    $('toggle').click();
    const frozen = state().time;
    await delay(150);
    check(state().paused && state().time === frozen, 'pause did not freeze');
    $('fit').click();
    const stableGeometry = JSON.stringify(window.demo.getGeometry());
    const signature = () => JSON.stringify([...document.querySelectorAll('.wire-base,.wire-active,.port,marker,marker path')].map(e =>
      [e.tagName, ...['d','marker-end','cx','cy','refX','refY','orient','viewBox','markerWidth','markerHeight','markerUnits'].map(k => e.getAttribute(k))]));
    const fixed = signature();
    const overlap = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
    for (const [index, step] of data.steps.entries()) {
      for (const progress of [0.25, 0.6, 0.8]) {
        window.demo.seek(starts[index] + step.duration * progress);
        check(state().id === step.id, 'wrong phase: ' + step.id);
        check(JSON.stringify(window.demo.getGeometry()) === stableGeometry && signature() === fixed, 'fixed geometry changed');
        check($('phase-label').textContent === step.label && $('trace-log').textContent === (step.description || ''), 'wrong phase text: ' + step.id);
        for (const node of nodes) {
          const id = node.dataset.node;
          const base = data.nodes.find(n => n.id === id);
          const override = step.nodeStates?.[id] || {};
          check(node.classList.contains('is-active') === (step.activeNodes || []).includes(id), 'wrong node highlight: ' + id);
          for (const [selector, key] of [['.state','state'],['.operation','operation'],['.node-footer','footer']]) {
            check(node.querySelector(selector).textContent === (override[key] ?? base[key] ?? ''), 'wrong text: ' + id + '/' + key);
          }
          for (const meter of base.meters || []) {
            const row = [...node.querySelectorAll('[data-meter]')].find(e => e.dataset.meter === meter.id);
            const value = override.meterValues?.[meter.id] ?? meter.value;
            check(row.querySelector('.meter-number').textContent === value.toFixed(2), 'wrong meter: ' + id + '/' + meter.id);
            check(Math.abs(parseFloat(row.querySelector('.meter-track i').style.width) - value * 100) < 0.01, 'wrong meter bar');
            check(row.classList.contains('is-selected') === (override.selectedMeter === meter.id), 'wrong selected meter');
            check(row.classList.contains('is-warning') === (meter.warningBelow !== undefined && value < meter.warningBelow), 'wrong meter warning');
          }
          const bounds = node.getBoundingClientRect();
          for (const child of node.querySelectorAll('.node-heading,.node-title,.state,.node-subtitle,.node-lines,.rows,.row-label,.row-value,.meter,.meter-label,.meter-number,.operation,.node-footer')) {
            const box = child.getBoundingClientRect();
            check(box.left >= bounds.left - 1 && box.right <= bounds.right + 1 && box.top >= bounds.top - 1 && box.bottom <= bounds.bottom + 1 && child.scrollWidth <= child.clientWidth + 1,
              'node content overflow: ' + step.id + '/' + id + '/' + child.className);
          }
        }
        for (const route of routes) {
          const id = route.dataset.route;
          const enabled = (step.activeRoutes || []).includes(id);
          check(route.classList.contains('is-active') === enabled, 'wrong route highlight: ' + id);
          check((Number(getComputedStyle(route.querySelector('.packet')).opacity) > 0) === enabled, 'wrong packet visibility: ' + id);
          if (enabled) {
            check(visible(route) && visible(route.querySelector('.packet')), 'packet invisible: ' + id);
            for (const dot of [...route.querySelectorAll('.packet circle')].slice(0, 3)) {
              check(visible(dot), 'packet invisible: ' + id);
            }
          }
          const caption = [...document.querySelectorAll('.route-caption')].find(e => e.dataset.routeCaption === id);
          if (caption) {
            const base = data.routes.find(r => r.id === id);
            check(caption.textContent === (step.routeLabels?.[id] ?? base.label), 'wrong caption: ' + id);
            check(caption.classList.contains('is-active') === enabled, 'wrong caption highlight: ' + id);
            const box = caption.getBoundingClientRect(), canvas = $('stage').getBoundingClientRect();
            check(box.left >= canvas.left - 1 && box.right <= canvas.right + 1 && box.top >= canvas.top - 1 && box.bottom <= canvas.bottom + 1, 'caption outside canvas: ' + id);
            for (const node of nodes) check(!overlap(box, node.getBoundingClientRect()), 'caption overlaps node: ' + step.id + '/' + id);
            for (const other of document.querySelectorAll('.route-caption')) {
              if (other !== caption) check(!overlap(box, other.getBoundingClientRect()), 'captions overlap: ' + step.id + '/' + id);
            }
          }
        }
      }
      const button = $('step-rail').querySelectorAll('button')[index];
      button.click();
      check(state().index === index && state().paused && button.getAttribute('aria-current') === 'step', 'step button failed');
    }
    const samples = {};
    const boundary = (p, b) => ((Math.abs(p.x-b[0]) < .01 || Math.abs(p.x-b[0]-b[2]) < .01) && p.y > b[1] && p.y < b[1]+b[3]) ||
      ((Math.abs(p.y-b[1]) < .01 || Math.abs(p.y-b[1]-b[3]) < .01) && p.x > b[0] && p.x < b[0]+b[2]);
    for (const route of routes) {
      const id = route.dataset.route, base = data.routes.find(r => r.id === id);
      const path = route.querySelector('.wire-base'), length = path.getTotalLength();
      check(length > 0 && route.querySelector('.wire-active').getAttribute('d') === path.getAttribute('d'), 'invalid route path: ' + id);
      const first = path.getPointAtLength(0), last = path.getPointAtLength(length);
      check(boundary(first, data.nodes.find(n => n.id === base.source).bounds) && boundary(last, data.nodes.find(n => n.id === base.target).bounds), 'route endpoint: ' + id);
      const ports = [...route.querySelectorAll('.port')];
      check(ports.length === 2, 'missing ports: ' + id);
      for (const [i, point] of [first, last].entries()) check(Math.hypot(Number(ports[i].getAttribute('cx'))-point.x, Number(ports[i].getAttribute('cy'))-point.y) < .01, 'port detached: ' + id);
      for (const wire of route.querySelectorAll('.wire-base,.wire-active')) {
        const match = wire.getAttribute('marker-end')?.match(/^url\(#(.+)\)$/), marker = match && $(match[1]);
        check(marker && marker.getAttribute('orient') === 'auto' && marker.getAttribute('refX') === '9' && marker.getAttribute('refY') === '5' && marker.querySelector('path').getAttribute('d') === 'M 1 1 L 9 5 L 1 9 Z', 'arrow not anchored: ' + id);
        const tip = marker.querySelector('path'), view = marker.viewBox.baseVal;
        check(marker.markerWidth.baseVal.value > 0 && marker.markerHeight.baseVal.value > 0 && view.width > 0 && view.height > 0 && visible(marker) && visible(tip) && !['none','transparent','rgba(0, 0, 0, 0)'].includes(getComputedStyle(tip).fill), 'arrow invisible: ' + id);
      }
      samples[id] = [];
      for (let at = 0; at <= Math.ceil(length); at++) {
        const point = path.getPointAtLength(Math.min(at, length));
        samples[id].push(point);
        for (const node of data.nodes) {
          const [x,y,w,h] = node.bounds;
          check(!(point.x > x+.01 && point.x < x+w-.01 && point.y > y+.01 && point.y < y+h-.01), 'rounded path inside node: ' + id + '/' + node.id);
        }
      }
    }
    let packets = 0;
    const frames = Math.min(1200, Math.ceil(duration * 20));
    // Sample each phase too: the bounded global grid may miss very short phases.
    const times = Array.from({length: frames}, (_, i) => duration*i/frames);
    data.steps.forEach((step, i) => [0.25,0.6,0.8].forEach(p => times.push(starts[i]+step.duration*p)));
    for (const time of times) {
      window.demo.seek(time);
      check(signature() === fixed, 'fixed arrow/path/port geometry changed');
      for (const id of state().activeRoutes) {
        const route = routes.find(r => r.dataset.route === id);
        for (const dot of route.querySelectorAll('.packet circle')) {
          if (getComputedStyle(dot).display === 'none') continue;
          const x = Number(dot.getAttribute('cx')), y = Number(dot.getAttribute('cy'));
          check(samples[id].some(p => Math.hypot(p.x-x,p.y-y) < 1.1), 'packet off route: ' + id);
          packets++;
        }
      }
    }
    // Check actual playback too: seeking alone can accept a frozen dot on the path.
    for (const [moving, step] of data.steps.entries()) {
      if (!step.activeRoutes?.length) continue;
      window.demo.setSpeed(Math.min(1, step.duration));
      window.demo.seek(starts[moving] + step.duration * .3);
      const positions = () => state().activeRoutes.map(id => {
        const dot = routes.find(r => r.dataset.route === id).querySelector('.packet circle:nth-child(2)');
        check(visible(dot) && visible(dot.parentElement), 'packet invisible: ' + id);
        return [Number(dot.getAttribute('cx')), Number(dot.getAttribute('cy'))];
      });
      const first = positions();
      window.demo.play(); await delay(90);
      check(state().index === moving, 'playback left sampled phase');
      const second = positions();
      second.forEach((p, i) => check(Math.hypot(p[0]-first[i][0], p[1]-first[i][1]) > .01, 'packet did not move: ' + step.activeRoutes[i]));
      for (const id of state().activeRoutes) {
        const index = data.routes.findIndex(r => r.id === id), route = routes[index], path = route.querySelector('.wire-base');
        const length = path.getTotalLength(), start = Math.min(7, length/4), end = Math.max(start, length-14);
        const point = path.getPointAtLength(start + ((state().progress*1.4 + index*.17)%1) * (end-start));
        const dot = route.querySelector('.packet circle:nth-child(2)');
        check(Math.hypot(Number(dot.getAttribute('cx'))-point.x, Number(dot.getAttribute('cy'))-point.y) < .02, 'packet disagrees with progress: ' + id);
      }
      window.demo.pause(); window.demo.setSpeed(1);
    }
    if (data.steps.length > 1) {
      window.demo.seek(starts[1]); $('previous').click(); check(state().index === 0, 'previous failed');
      $('next').click(); check(state().index === 1, 'next failed');
    }
    const target = duration * .4;
    $('scrubber').value = target; $('scrubber').dispatchEvent(new Event('input', {bubbles:true}));
    check(Math.abs(state().time-target) < .02 && state().paused, 'scrubber failed');
    $('speed').value = '2'; $('speed').dispatchEvent(new Event('change', {bubbles:true}));
    window.demo.seek(0); $('toggle').click();
    const clock = performance.now(); await delay(180);
    check(state().speed === 2 && Math.abs(state().time-((performance.now()-clock)/500)%duration) < .3, 'speed failed');
    $('loop').checked = false; $('loop').dispatchEvent(new Event('change', {bubbles:true}));
    window.demo.seek(Math.max(0,duration-.03)); window.demo.play(); await delay(120);
    check(state().paused && state().time === duration, 'end without loop failed');
    $('loop').checked = true; $('loop').dispatchEvent(new Event('change', {bubbles:true}));
    window.demo.seek(Math.max(0,duration-.03)); window.demo.play(); await delay(120);
    check(!state().paused && state().time < Math.min(duration,1), 'loop failed');
    $('restart').click(); check(!state().paused && state().time === 0, 'restart failed');
    window.demo.pause(); window.demo.setSpeed(1);
    const scale = state().scale; $('zoom-in').click(); check(state().scale > scale, 'zoom in failed');
    $('zoom-out').click(); check(Math.abs(state().scale-scale) < .001, 'zoom out failed'); $('fit').click();
    const app = $('app').getBoundingClientRect();
    check(innerWidth === 1400 && innerHeight === 1100 && app.top >= 0 && app.bottom <= innerHeight, 'desktop fit clips controls');
    return {phases:data.steps.length, duration_seconds:duration, starts, durations:data.steps.map(s => s.duration), geometry:{routes:routes.length,frames:times.length,packets},
      checked:['all phase states and meters','phase and route captions','node text bounds','caption bounds and overlaps','stable visible arrows/ports/paths','rounded route endpoints and node avoidance','all particle circles','all phase particle visibility and real motion','step buttons','previous/next','autoplay/pause','scrubber','speed','loop/end','restart','zoom/fit','desktop controls']};
  };
})();
