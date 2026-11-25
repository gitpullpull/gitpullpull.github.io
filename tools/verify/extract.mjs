// Readability（Jina Reader 等の方式）と Turndown（HTML→Markdown 全体変換）の出力を JSON で返す
import fs from 'node:fs';
import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';
import TurndownService from 'turndown';

const html = fs.readFileSync(process.argv[2], 'utf8');
const td = new TurndownService({ headingStyle: 'atx' });
const art = new Readability(new JSDOM(html, { url: 'https://page.gitpullpull.me/' }).window.document).parse();
process.stdout.write(JSON.stringify({
  turndown_full: td.turndown(new JSDOM(html).window.document.body.innerHTML),
  readability: art ? td.turndown(art.content) : '',
}));
