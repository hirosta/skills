"""HTMLのメッセージを読み取り、推敲の候補を標準出力に示す。"""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import re


class Messages(HTMLParser):
    """class=message の要素を文書順に収集する。"""

    def __init__(self):
        super().__init__()
        self.messages = []
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if self.depth:
            if tag not in {"br", "img", "hr", "input", "meta", "link"}:
                self.depth += 1
        elif "message" in (dict(attrs).get("class") or "").split():
            self.depth = 1
            self.parts = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in {"br", "img", "hr", "input", "meta", "link"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.depth and tag not in {"br", "img", "hr", "input", "meta", "link"}:
            self.depth -= 1
            if not self.depth:
                self.messages.append("".join(self.parts).strip())

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    args = parser.parse_args()
    try:
        document = Messages()
        document.feed(args.html.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        parser.exit(2, "HTMLをUTF-8で読み取れませんでした\n")
    endings = []
    for number, message in enumerate(document.messages, 1):
        flags = []
        rules = [
            ("句点", r"[。．]"),
            ("二段構え", r"[。！？!?：:]|一方[、,]|しかし[、,]"),
            ("ダッシュ", r"[—―–ー]{2,}|[—―–]|-{2,}|\s-\s"),
            ("数え上げ", r"[123１２３一二三四五六七八九十]+[つ点項]|①|②|③|第一|第二"),
            ("自己言及", r"本(?:資料|提案|スライド)|この(?:資料|提案|ページ)|ご紹介|説明します"),
        ]
        for label, pattern in rules:
            if re.search(pattern, message):
                flags.append(label)
        if len(message) > 42:
            flags.append(f"長さ（{len(message)}字、まず1行に収める目安42字超）")
        ending = message[-4:]
        endings.append(ending)
        if len(endings) >= 3 and len(set(endings[-3:])) == 1:
            flags.append("文末の繰り返し（隣接3枚）")
        print(f"{number:02d} {message}\n   {'／'.join(flags) or '機械的な指摘なし'}")
    if not document.messages:
        print("メッセージが見つかりません（class=message を確認）")
    print("候補の表示であり合否判定ではありません。事実と判断が入っているか、文型・根拠・縦のつながりは人が確かめてください。")


if __name__ == "__main__":
    main()
