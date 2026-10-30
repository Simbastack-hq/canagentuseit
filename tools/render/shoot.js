// Screenshot a timeline: shoot.js <timeline.json> <out-dir> <wide|tall> [clean|cards]
// clean (default): no captions, no full-screen cards; same timing, so markers.csv and captions.srt line up.
// cards: one PNG per card (title, each attempt, verdict) for the edit, no video frames.
// Writes <out-dir>/f00000.png… at 2x device scale (3840x2160 or 2160x3840) and concat.txt for ffmpeg,
// holding each frame for its duration. Playwright module path: $CAUI_PLAYWRIGHT (or `playwright`).
const fs = require('fs'), path = require('path');
const { chromium } = require(process.env.CAUI_PLAYWRIGHT || 'playwright');
(async () => {
  const [tlPath, out, aspect, mode = 'clean'] = process.argv.slice(2);
  const tl = JSON.parse(fs.readFileSync(tlPath, 'utf8'));
  fs.mkdirSync(out, { recursive: true });
  const vp = aspect === 'tall' ? { width: 1080, height: 1920 } : { width: 1920, height: 1080 };
  const b = await chromium.launch();
  const page = await (await b.newContext({ viewport: vp, deviceScaleFactor: 2 })).newPage();
  await page.goto('file://' + path.join(__dirname, 'page.html'));
  if (mode === 'cards') {
    let n = 0;
    for (const f of tl.frames) {
      if (!f.state.overlay || f.state.overlay.kind === 'skip') continue;
      await page.evaluate(s => window.show(s), f.state);
      const name = f.state.overlay.kind === 'attempt' ? `card-attempt-${++n}` : `card-${f.state.overlay.kind}`;
      await page.screenshot({ path: path.join(out, `${name}.png`) });
    }
    await b.close(); console.log(`${aspect}: cards`); return;
  }
  const lines = [];
  let last = null, lastFile = null;
  for (let i = 0; i < tl.frames.length; i++) {
    const f = tl.frames[i], next = tl.frames[i + 1];
    const dur = Math.max(1 / 30, (next ? next.v : tl.duration) - f.v);
    const st = { ...f.state, overlay: null, clean: true };
    const key = JSON.stringify(st);
    if (key !== last) {
      await page.evaluate(s => window.show(s), st);
      lastFile = `f${String(i).padStart(5, '0')}.png`;
      await page.screenshot({ path: path.join(out, lastFile) });
      last = key;
      lines.push(`file '${lastFile}'`, `duration ${dur.toFixed(3)}`);
    } else {
      // same picture: extend the previous frame's hold
      const d = parseFloat(lines.pop().split(' ')[1]);
      lines.push(`duration ${(d + dur).toFixed(3)}`);
    }
  }
  lines.push(`file '${lastFile}'`);   // concat demuxer needs the last file repeated for its duration to count
  fs.writeFileSync(path.join(out, 'concat.txt'), lines.join('\n') + '\n');
  await b.close();
  console.log(`${aspect}: ${lines.filter(l => l.startsWith('file')).length - 1} unique frames`);
})().catch(e => { console.error(e); process.exit(1); });
