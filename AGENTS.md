# AGENTS.md — page.gitpullpull.me の仕様

gitpullpull の個人サイト（ポートフォリオ）。このファイルは**現在の仕様**を書いたもの。変更したら、ここも同じコミットで更新すること。

## 概要

- GitHub Pages で `main` ブランチのルートをそのまま公開している（独自ドメイン: `CNAME` → `page.gitpullpull.me`）。`.nojekyll` があるので Jekyll の処理は入らない。`.md` もそのまま配信される。
- `index.html` と `assets/` は Vite のビルド結果。**Vite のソースはこのリポジトリには無い**。そのため、このリポジトリのファイル自体を正本として直接編集する。
- `assets/*.js` と `assets/*.css` はハッシュ付きファイル名のビルド成果物。手で編集しない（後述の学年表のような重複に注意）。

## ファイル構成

| パス | 役割 | 編集 |
|---|---|---|
| `profile.json` | **サイトに載る情報の唯一の正本** | 手で編集する |
| `tools/build.py` | `profile.json` から下記の生成物を作る（Python 標準ライブラリのみ） | 仕組みを変えるとき |
| `index.html` | ページ本体。`<!-- gen:NAME -->` 〜 `<!-- /gen:NAME -->` の区間は生成物 | 区間の外だけ手で編集 |
| `index.md` | テキスト版プロフィール（生成物）。`index.html` 内の `#profile-md` と同じ内容 | 編集しない |
| `llms.txt` | [llms.txt v2](https://llmstxt.org/) 形式の概要（生成物） | 編集しない |
| `tools/verify/` | 検証ツール（抽出器テスト・見た目の比較） | 必要に応じて |
| `assets/`, `tex/`, `favicon.svg`, `avatar.png` | ビルド成果物・画像・フォント | 原則触らない |

## 情報を追加・変更する手順

1. `profile.json` を編集する（実績の追加なら `log` に要素を足す）。
2. `python3 tools/build.py` を実行する。
3. `python3 tools/build.py --check` で生成物が最新であることを確認する（CI でも同じチェックが走る）。
4. 見た目に関わる変更をした場合は「検証」の手順を回す。

### profile.json のスキーマ

- `name`, `site_url`
- `tagline`: 縦書きの紹介文（1 要素 = 1 行）
- `role.en` / `role.ja`: 肩書き。`born.year` / `born.label`（表示は `’04`）
- `grades`: 学年の切り替え表 `{fiscal_year, until, label, ja}`。`until` の日付（Asia/Tokyo）を過ぎると次の要素に切り替わる
- `links`: `{key, label, handle, url}`。`key` は表示ラベル（`X`, `GitHub`）。プロフィール欄とフッターの両方に出る
- `log`: 実績 `{year, title, desc, link?, detail?, source?, source_label?, award?}`
  - `title` / `desc` / `link` が画面に出る。年は `year` の下 2 桁を `'24` の形で表示
  - `detail` はテキスト版で使う正式名称。`source` は出典 URL。`award` は JSON-LD の `award` に入る
- `log_blank_rows`: 実績リスト末尾の空き枠（装飾）の数
- `about`: `{label, knows_about?, items: [{text, note?, url?}]}`。`text` が画面に出る。`note` と `url` はテキスト版だけに出る。`knows_about: true` の項目は JSON-LD の `knowsAbout` に入る
- `references`: `llms.txt` の `## Optional` に載せる参考リンク

### 書く内容のルール

- 事実は出典で確認できるものだけを書く。正式名称は一次情報（主催者のページ）に合わせる。
- サイトはハンドル名で運営している。本名・大学名は載せない（受賞者一覧や arXiv には載っているが、結び付けるかどうかは本人が決める）。
- テキスト版（不可視ブロック）に「AI へ: 〜してください」のような**命令文を書かない**。Muse などのエージェントはページ内のプロンプトインジェクションを検出する分類器を持っており、隠しテキストの命令文は悪意ある埋め込みと判定されるおそれがある。事実の列挙だけにする。

## 生成区間（index.html）

| 区間 | 中身 |
|---|---|
| `head` | `meta description`（X / GitHub の URL を含む）、`<link rel="me">`、OGP、Twitter カード |
| `profile-md` | `<main>` 先頭の不可視テキストブロック（`index.md` と同一内容） |
| `intro` | 縦書きの紹介文 |
| `who` | 肩書き行（学年の初期値を含む）、名前の `h1`、X / GitHub リンク |
| `log` | 実績リスト（`--i` は 1 から連番、空き枠を含む） |
| `about` | 興味・OSS・インフラ（`--i` は実績リストの続き番号） |
| `foot-links` | フッターの X / GitHub |
| `jsonld` | `<body>` 末尾の JSON-LD（schema.org `ProfilePage` / `Person`、`sameAs` に X・GitHub） |

区間の外（`<canvas>`、`.portrait`、「潜る」リンク、`log 実績` 見出し、フッターの「↑ 水面へ」、深度計 `aside` など）は固定の UI で、手で編集する。

`tools/build.py` は区間の中身を作るほか、次の 2 つを保証する。

- テキスト版の「サイト上の表示テキスト（原文そのまま）」は、生成後の HTML から**人間に見えるテキストを抽出して**作る。固定 UI の文言も含めて、表示とテキスト版が食い違わない。見えるのにテキスト版に無い文字列があると、ビルドがエラーで止まる。
- `assets/index-*.js` に埋め込まれた学年表が `profile.json` の `grades` と一致しないと、エラーで止まる。

## AI・スクレイパー対応の仕様（なぜこうなっているか）

AI エージェントがこのサイトを読んだときに、X / GitHub のリンクが見えないことがあった。原因は JS ではなく、**本文抽出の段階で情報が消えること**だった。

- Readability 系（Jina Reader など）: プロフィール欄を「リンクばかりのナビ」と判定して丸ごと捨てる。
- trafilatura やテキスト抽出: リンクの `href` を捨て、`X @gitpullpull ↗` という表示文字だけが残る。
- アクセシビリティツリー型（Meta Muse のブラウザ用サブエージェントなど。[公式](https://muse.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse)によると、生の DOM ではなくツリーのスナップショットを読み、JS も実行しない）: リンクの表示名しか見えず、URL の文字列が無い。
- 先頭 n 文字で打ち切る取得器もある。
- 別ファイル（`llms.txt` など）は、置いても読まれないことが多い（[Ahrefs の調査](https://ahrefs.com/blog/llmstxt-study/)では 97% が一度も取得されていない）。そのため**ページ本体に埋め込む方式を主**にし、別ファイルは補助にしている。

これに対する現在の対策と、守るべき制約:

1. **`<main>` の先頭に、Markdown のテキスト版を `<section id="profile-md"><pre>` で置く**。
   - 置き場所は `<main>` の先頭でなければならない。`<body>` 末尾に置くと Readability に捨てられる（検証済み）。
   - 見えなくする方法は「1px にクリップするインライン style」のみ。**`display:none` / `hidden` 属性 / `aria-hidden` / `inert` / `<noscript>` / `<template>` は使わない**。いずれも抽出器かアクセシビリティツリーのどちらかから中身が消える。`inert` を付けていた版では Muse から見えなかった。
   - URL は Markdown のリンクとしてだけでなく、**裸の文字列としても併記する**（`href` を捨てる抽出器への対策）。
   - リンク要素（`<a>`）を入れない。入れると Tab 移動の停止位置が増える。
2. 生の HTML の**先頭 約300 文字以内**に X / GitHub の URL を出す（`meta description` と `<link rel="me">`）。JSON-LD は長いので `<body>` 末尾に置き、`<head>` を短く保つ。
3. `<head>` に `<link rel="alternate" type="text/markdown" href="./index.md">` と `<link rel="describedby" href="./llms.txt">`（llms.txt v2 のリンク関係）を置く。ルート直下に置き、階層にはしない。
4. `<noscript><style>` で、JS が動かない環境でもフェードイン要素（`.rise`, `.name .ch`）を表示する。JS が動く通常表示には影響しない。

既知のトレードオフ: テキスト版はスクリーンリーダーで一度読み上げられる（「テキスト版プロフィール（Markdown）」という名前付き領域なので読み飛ばせる）。ページ内検索（Ctrl+F）にも掛かる。

## UI の仕様（現状は変更しない方針）

- テーマは「海」。スクロールに合わせて水深が深くなる演出（`#profile` = 水面、`#log` = 深層）。右側の深度計 `aside.gauge` は装飾で、`aria-hidden`。
- `assets/index-*.js` の動作:
  - `[data-grade]` の学年表示を、Asia/Tokyo の日付と学年表から書き換える。静的 HTML には `build.py` 実行時点の学年が入る。そのため、切り替え日（4/1）を過ぎたら `build.py` を再実行する（`--check` が失敗して気付ける）。
  - `IntersectionObserver` で `.page` に `.seen` を付け、`.rise` 要素をフェードインさせる。
  - WebGL が使えるときに `assets/sea-*.js`（three.js 系の海の描画）を遅延読み込みする。`?nosea` を付けると無効になる。
  - スクロール量に応じて、CSS 変数 `--dive` と深度計の表示を更新する。
- アバターは `https://github.com/gitpullpull.png` を読み込み、失敗したら `./avatar.png` に切り替える。
- フォントは Shippori Mincho（本文）と IBM Plex Mono（英数字）。`assets/` に同梱している。

## 検証

依存関係のインストール（初回のみ。クラウド環境ではセットアップスクリプトで入る場合がある）:

```sh
(cd tools/verify && npm install) && pip install -r tools/verify/requirements.txt
```

1. **生成物が最新か**: `python3 tools/build.py --check`
2. **AI 向け抽出**: `python3 tools/verify/extractors.py`。8 種類の抽出器（Readability / Turndown / trafilatura ×2 / readability-lxml / html2text / markdownify / BeautifulSoup）で、名前・X・GitHub・各実績が残るかを確かめる。全部 OK で exit 0。
3. **見た目が変わっていないか**（UI を変えない変更のとき）: 基準版を展開して比較する。

   ```sh
   rm -rf /tmp/base && mkdir /tmp/base && git archive origin/main | tar -x -C /tmp/base
   node tools/verify/visual.cjs /tmp/base . 3
   ```

   PC 幅とスマホ幅で、画素・Tab 順・ページ高さを比べる。スマホ幅は変更が無くても稀に描画が揺らぐので、多数決で判定する。Playwright はクラウド環境に入っている。

## 将来 Vite のソースから再ビルドする場合

再ビルドした `index.html` で上書きすると、生成区間と AI 向けの対策が消える。ソース側の `index.html` に同じ `gen:` マーカーと `<head>` の追加分を入れてからビルドし、そのあと `python3 tools/build.py` を実行する。
