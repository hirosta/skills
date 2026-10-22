# hirosta skills

日本語の文章の見直しやWebページの点検など、日本の業務で使えるAIエージェント向けのスキル集です。株式会社hirostaが公開し、Claude Code などで利用できます。

日本語・日本の業務で使えることを重視しています。各スキルは架空の素材で試し、その結果を各スキルの README と、hirostaの検証ラボの記事で公開します。

## スキル一覧

| スキル | 内容 |
| --- | --- |
| [ai-smell-ja](skills/ai-smell-ja/) | 日本語の決まり文句や文型の繰り返しを確認し、意味を保って書き直す。 |
| [dads-page-check](skills/dads-page-check/) | DADS β版を参考にWebページの読みやすさと操作を点検し、修正案を出す。 |

## 使い方

### CLIで入れる

Node.js 22.20以上とnpxが使える環境で、導入先のプロジェクトから次を実行します。リポジトリのスキルをまとめて入れるには、対話画面ですべてのスキルを選び、利用するAIエージェントと導入先を確認してください。

```bash
npx skills add hirosta/skills
```

CLIには匿名の利用集計（テレメトリー）があり、環境変数 `DISABLE_TELEMETRY=1` で無効にできます。たとえば、`DISABLE_TELEMETRY=1 npx skills add hirosta/skills` と実行します。詳しくは[公式ドキュメント](https://www.skills.sh/docs)と[FAQ](https://www.skills.sh/docs/faq)を参照してください。

### 手でコピーする

Claude Code向けにコピーする場合は、次を実行します。同名のフォルダーがある場合は内容を確認し、上書きするか決めてからコピーしてください。

```bash
git clone https://github.com/hirosta/skills.git
mkdir -p ~/.claude/skills/
cp -r skills/skills/<スキル名> ~/.claude/skills/
```

## 方針

- 公開するスキルは、架空の素材で試してから公開します。効果を保証するものではありません。
- ほかのスキルを参考にした場合は、着想元を各スキルの README に書きます。
- 認証情報・お客様の情報は含めません。

## ライセンス

[MIT](LICENSE)

## 運営

[株式会社hirosta](https://hirosta.com)
