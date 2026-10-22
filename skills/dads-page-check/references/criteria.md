# 点検基準

デジタル庁デザインシステム（DADS）β版を参考に、点検用に言い換えて整理した一覧。公式文書の転載ではない。参照日は要件指定の2026-10-21、実装時の公式ページ再確認日は2026-10-22。DADSは行政機関や公共性の高い組織のサイト・サービスを想定している。このスキルでは中小企業や団体のサイトを見直す際の参考として使い、公式の認証や適合判断には使わない。

| 項目 | 点検の目安・方法 | 参照URL | 参照日 |
| --- | --- | --- | --- |
| 文字の大きさ | 本文・操作部品は原則16 CSS px以上。14pxは付随情報や領域の制約がある場合に限り、14px未満は原則避ける。計算後の値で調べる。 | https://design.digital.go.jp/dads/foundations/typography/ | 2026-10-21 |
| 行高 | 読み物本文は文字サイズの1.5倍以上、1.5〜1.75が目安。見出しは1.4も使える。本文と見出しを分け、pxの行高は文字サイズで割る。 | https://design.digital.go.jp/dads/foundations/typography/ | 2026-10-21 |
| 書体 | 日本語のitalic・obliqueは、特別な理由がなければ避ける。欧文の慣習によるイタリックとは区別する。 | https://design.digital.go.jp/dads/foundations/typography/ | 2026-10-21 |
| 文字色 | DADSでは大きい文字も含め背景との4.5:1以上を確保する。 | https://design.digital.go.jp/dads/foundations/color/ 、 https://design.digital.go.jp/dads/foundations/color/accessibility/ | 2026-10-21 |
| 枠線・アイコン | 操作や理解に必要な非文字要素は隣接色と3:1以上。入力欄の境界も調べる。 | https://design.digital.go.jp/dads/foundations/color/accessibility/ | 2026-10-21 |
| リンク | 本文中は下線を残すのを基本に、色以外でも区別する。新規タブはアイコンと代替テキスト等で知らせる。外部リンクはサイトの方針と行先を明確にし、必ず別タブにするとは決めない。PDF等は形式・容量の併記を勧める。ホバーの太さ・サイズ変更は原則避け、他要素へ影響しない場合のみ検討する。 | https://design.digital.go.jp/dads/foundations/link-text/ | 2026-10-21 |
| フォーカス | Tab移動中の位置を可視化する。枠等は隣接色と3:1以上を調べる。outlineの削除だけではなく代替表示も見る。 | https://design.digital.go.jp/dads/foundations/color/accessibility/ | 2026-10-21 |
| ボタンの領域 | 重なりのない44×44 CSS px以上を確保する。見た目が小さくても周囲の余白を含む領域で確認する。 | https://design.digital.go.jp/dads/components/button/usage/ 、 https://design.digital.go.jp/dads/components/button/accessibility/ | 2026-10-21 |
| リンクの領域 | 44×44 CSS pxが望ましい。難しい場合は24×24 CSS pxを目安に周囲の間隔と重なりも調べる。細則はWCAGを参照する。 | https://design.digital.go.jp/dads/foundations/link-text/accessibility/ | 2026-10-21 |
| ボタンの階層 | 塗り・枠・文字など形でも重要度を区別する。主ボタンは原則1画面1つ。主ボタンに枠の表現を使う選択肢もある。無効化を避ける設計を検討し、必要なら操作可能になる条件を近くに書く。 | https://design.digital.go.jp/dads/components/button/usage/ 、 https://design.digital.go.jp/dads/components/button/accessibility/ | 2026-10-21 |
| フォーム | ラベル→具体的な条件→入力欄→原因と訂正方法を伝えるエラー文の順を基本とする。要否は「※必須」「※任意」等で示す。placeholderを条件説明の代わりにしない。枠線は3:1以上。 | https://design.digital.go.jp/dads/components/input-text/usage/ 、 https://design.digital.go.jp/dads/foundations/color/ | 2026-10-21 |
| 余白 | 8 CSS pxを基準に3〜5段階ほどの規則を持つ例を参考に、同種の要素のばらつきを確認する。8の倍数以外を一律に不適合とはしない。 | https://design.digital.go.jp/dads/foundations/spacing/ | 2026-10-21 |
| 角丸 | 5段階を目安に部品ごとの値を定める。同じ半径でも大きさで見え方が変わるため、数値の同一性ではなく同種の部品のばらつきを指摘する。 | https://design.digital.go.jp/dads/foundations/corner-shapes/ | 2026-10-21 |

## 例外と判断の残し方

- ロゴ・ブランド名、意味も機能も持たない純粋な装飾文字、写真の中で読む必要がない文字、無効化された操作部品などは、コントラスト要件の例外になり得る。通常の説明文や操作に必要な文字まで例外にしない。スクリプトはこれらを自動で除外しない。参照： https://design.digital.go.jp/dads/foundations/color/accessibility/ （参照日2026-10-21）。
- WCAGの大きな文字の3:1という扱いを、DADSの文字の4.5:1へそのまま持ち込まない。参照： https://design.digital.go.jp/dads/foundations/color/accessibility/ （参照日2026-10-21）。
- 単行のボタンや情報密度を優先する管理画面には、本文より狭い行高がある。本文1.5を全要素へ一律に当てない。日本語斜体にも必要な理由がある場合の留保がある。参照： https://design.digital.go.jp/dads/foundations/typography/ （参照日2026-10-21）。
- フォームは縦積みを基本案にするが、公式にはラベルと条件をひとまとまりにした横並びの良い例もある。配置だけで違反と断定せず、関連が明確か、狭い幅でも使えるかを確かめる。要否表示はステート表示等の選択肢もある。参照： https://design.digital.go.jp/dads/components/input-text/usage/ （参照日2026-10-21）。

## 静的点検で分かる範囲

`check.py` はHTMLParserと簡易CSS解析を使う。一般的な単純規則、@media・@supports・@layer・@container内の規則、style要素・style属性が対象。CSSの宣言は規則ごと、Tailwind風クラスは要素ごとに数える。HTMLのクラスとCSSの宣言で同じ問題を重複して拾う場合もある。候補の件数を、問題のある要素の数とは見なさない。

- サイズはpxとrem（ルート16pxと仮定）、クラスは標準のtext-xsとtext-[数値px/rem]を拾う。独自のTailwind設定、em、calc、変数、font短縮指定は解決しない。
- 行高は数値・%・em、または同じ規則にfont-sizeがあるpx・remを比率にする。leading-none/tight/snug、leading-[数値/%/em]を拾う。単純なh1〜h6指定や見出し要素のクラスは除外する。クラス名から見出しと分からないものは本文への適用を要確認とする。
- 下線の削除指定は適用先がリンクでなくても候補にする。フォーカスの代替は同じセレクター・条件内のoutlineやbox-shadow、同じ要素のfocus系ring・outline幅指定の存在から推定する。別ファイルの代替や複雑なセレクターは関連付けられず候補が残る。代替の色や十分な可視性は実表示で確認する。
- CSSの代替フォーカス表示では、色関数をひとまとまりに保って寸法だけを調べる。幅0のoutlineや寸法がすべて0の影は代替としない。色は下記の不透明色のみ扱い、未対応色・変数・透過は推定しない。outlineの個別プロパティや宣言の上書き、影の寸法の相殺は解決しない。
- ラベルは空でないlabelのfor/idまたは内包関係を調べる。aria-labelだけでは可視ラベルの代わりとしない。placeholderがあり、文字を持つaria-describedby参照先がないものは説明の候補とする。近くにあるが関連付けのない説明も拾うため読み直す。CSSでラベルが隠れていないかは未判定。
- 斜体は日本語を含む要素（子孫の文字を含む）のクラス、i/em、単純なタグ・class・idのCSS指定を調べる。複雑なセレクターは要確認とする。CSSの上書きによる斜体解除は判定しない。
- 色は#RGB、#RRGGBB、整数のrgb(r, g, b)、black、whiteのみ。同じ規則にcolorとbackground-color（または単色background）がある場合だけ計算し、4.5:1未満を候補にする。未対応色は「要確認」。枠線の比は自動抽出しないので、隣接する2色を `--contrast` へ渡す。
- 継承・詳細度・条件の有効性・CSSネスト・JavaScript・疑似要素・グラデーション・透過・背景画像・ルート文字サイズの変化は解決しない。未検出を合格としない。style属性は要素の開始行を目安にする。

## コントラストの計算

sRGBの各成分を0〜1にし、0.04045以下なら12.92で割り、それ以外は `((成分 + 0.055) / 1.055) ** 2.4` に変換する。相対輝度はR・G・Bに0.2126、0.7152、0.0722を掛けて足す。比は `(明るい側 + 0.05) / (暗い側 + 0.05)`。表示用に丸める前の値で閾値と比較する。

参照： [WCAG 2.2 相対輝度](https://www.w3.org/TR/WCAG22/#dfn-relative-luminance)・[コントラスト比](https://www.w3.org/TR/WCAG22/#dfn-contrast-ratio)（参照日2026-10-21、再確認2026-10-22）。
