// 2 つのディレクトリのサイトを同条件で撮影し、見た目・Tab 順・ページ高さが同じかを比べる。
//   node tools/verify/visual.cjs <基準ディレクトリ> <比較ディレクトリ> [回数=3]
// 海の WebGL は ?nosea で止め、アニメーションは reducedMotion で止める。
// 注意: スマホ幅は変更が無くても稀に描画が揺らぐ（同じページ同士でも差分が出る）。複数回の多数決で判断する。
const { chromium } = require('playwright');
const http = require('node:http'), fs = require('node:fs'), path = require('node:path');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2', '.woff': 'font/woff' };
function serve(dir) {
  return new Promise(res => { const s = http.createServer((q, r) => {
    let f = path.join(dir, decodeURIComponent(new URL(q.url, 'http://x').pathname));
    if (f.endsWith('/')) f += 'index.html';
    fs.readFile(f, (e, b) => { if (e) { r.writeHead(404); r.end(); return; }
      r.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' }); r.end(b); });
  }).listen(0, () => res(s)); });
}
(async () => {
  const [a, b, n = '3'] = process.argv.slice(2);
  const servers = await Promise.all([serve(path.resolve(a)), serve(path.resolve(b))]);
  const ports = servers.map(s => s.address().port);
  const browser = await chromium.launch(); let ng = 0;
  for (const [w, h, tag] of [[1440, 900, 'desktop'], [390, 844, 'mobile']]) {
    let same = 0;
    for (let i = 0; i < Number(n); i++) {
      const shots = [], meta = [];
      for (const port of ports) {
        const ctx = await browser.newContext({ viewport: { width: w, height: h }, reducedMotion: 'reduce' });
        const pg = await ctx.newPage();
        await pg.route(/github\.com\/.*\.png/, r => r.abort());   // アバターは外部取得なので固定（avatar.png にフォールバック）
        await pg.goto(`http://localhost:${port}/?nosea`); await pg.waitForTimeout(2500);
        await pg.evaluate(() => document.querySelectorAll('.page').forEach(e => e.classList.add('seen')));
        await pg.waitForTimeout(800);
        shots.push(await pg.screenshot({ fullPage: true }));
        const tabs = []; for (let t = 0; t < 8; t++) { await pg.keyboard.press('Tab');
          tabs.push(await pg.evaluate(() => document.activeElement.outerHTML.slice(0, 60))); }
        meta.push(JSON.stringify({ h: await pg.evaluate(() => document.documentElement.scrollHeight), tabs }));
        await ctx.close();
      }
      if (meta[0] !== meta[1]) { console.log(`NG  ${tag}: Tab 順またはページ高さが違う`); ng++; }
      if (Buffer.compare(shots[0], shots[1]) === 0) same++;
    }
    console.log(`${same * 2 > Number(n) ? 'OK ' : 'NG '} ${tag}: 画素一致 ${same}/${n} 回`);
    if (same * 2 <= Number(n)) ng++;
  }
  await browser.close(); servers.forEach(s => s.close()); process.exit(ng ? 1 : 0);
})();
