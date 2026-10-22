#!/usr/bin/env python3
"""HTML・CSSを読み取り、DADSを参考にした静的な点検候補を出す。"""

import argparse
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
import re


CATEGORIES = ("文字サイズ", "行間", "下線", "フォーカス", "ラベル", "説明", "斜体", "コントラスト", "要確認")
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
VOID = set("area base br col embed hr img input link meta param source track wbr".split())
HEADINGS = {f"h{i}" for i in range(1, 7)}


@dataclass
class Node:
    tag: str
    attrs: dict
    line: int
    parents: list
    text: str = ""


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self.stack = []
        self.styles = []

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.getpos()[0], list(self.stack))
        self.nodes.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.stack and self.stack[-1].tag == "style":
            self.styles.append((data, self.getpos()[0]))
        elif not any(n.tag in {"script", "style", "title"} for n in self.stack):
            for node in self.stack:
                node.text += data


def split_css(text, separator):
    """引用符、括弧の内側を分割しない。開始位置も返す。"""
    start = depth = 0
    quote = None
    escaped = False
    for i, char in enumerate(text):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == separator and depth == 0:
            yield text[start:i], start
            start = i + 1
    yield text[start:], start


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m[0]), css, flags=re.S)


@dataclass
class Rule:
    selector: str
    declarations: dict
    line: int
    scope: tuple = field(default_factory=tuple)
    node: object = None


def declarations(text, first_line):
    result = {}
    for part, offset in split_css(text, ";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        line = first_line + text[:offset + len(part) - len(part.lstrip())].count("\n")
        result[key.strip().lower()] = (re.sub(r"\s*!important\s*$", "", value.strip(), flags=re.I), line)
    return result


def css_rules(css, first_line=1, scope=()):
    """通常の規則と@media等の内側を読む。CSSの完全な構文解析ではない。"""
    css = strip_comments(css)
    # 引用符内の波括弧を境界として数えない。
    masked = re.sub(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' ''',
                    lambda m: " " * len(m[0]), css, flags=re.X)
    pos = 0
    while (opening := masked.find("{", pos)) >= 0:
        depth = 1
        closing = opening + 1
        while closing < len(masked) and depth:
            depth += (masked[closing] == "{") - (masked[closing] == "}")
            closing += 1
        if depth:
            break
        selector = list(split_css(css[pos:opening], ";"))[-1][0].strip()
        body = css[opening + 1:closing - 1]
        line = first_line + css[:opening + 1].count("\n")
        if selector.startswith("@"):
            if re.match(r"@(media|supports|layer|container)\b", selector):
                yield from css_rules(body, line, scope + (selector,))
        elif "{" not in masked[opening + 1:closing - 1]:
            for item, _ in split_css(selector, ","):
                yield Rule(item.strip(), declarations(body, line), line, scope)
        pos = closing


def color(value):
    value = value.strip().lower()
    named = {"black": "#000000", "white": "#ffffff"}
    value = named.get(value, value)
    if re.fullmatch(r"#[0-9a-f]{3}", value):
        return tuple(int(c * 2, 16) / 255 for c in value[1:])
    if re.fullmatch(r"#[0-9a-f]{6}", value):
        return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))
    match = re.fullmatch(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", value)
    if match and all(int(c) <= 255 for c in match.groups()):
        return tuple(int(c) / 255 for c in match.groups())
    raise ValueError("色は #RGB、#RRGGBB、rgb(0, 0, 0)、black、white の不透明色で指定してください")


def luminance(rgb):
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return sum(c * w for c, w in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(foreground, background):
    a, b = sorted((luminance(color(foreground)), luminance(color(background))))
    return (b + 0.05) / (a + 0.05)


def pixels(value):
    match = re.fullmatch(r"(\d*\.?\d+)(px|rem)", value.lower())
    if match:
        return float(match[1]) * (16 if match[2] == "rem" else 1)
    return None


def line_ratio(value, size=None):
    match = re.fullmatch(r"(\d*\.?\d+)(%|em|px|rem)?", value.lower())
    if not match:
        return None
    number, unit = float(match[1]), match[2]
    if unit == "%":
        return number / 100
    if unit in {None, "em"}:
        return number
    return pixels(value) / size if size else None


def heading(selector):
    # h1 p のように見出しの子孫を指すものは除外しない。
    return bool(re.fullmatch(r"h[1-6](?:[.#][\w-]+|:[\w-]+)*", selector.strip().lower()))


def matches(node, selector):
    """斜体の適用先候補用。単純なタグ・class・idだけを照合する。"""
    if not re.fullmatch(r"(?:[a-zA-Z][\w-]*|\*)?(?:[.#][\w-]+)*", selector):
        return False
    tag = re.match(r"^[\w*-]+", selector)
    if tag and tag[0] not in {"*", node.tag}:
        return False
    return all((name in (node.attrs.get("class") or "").split() if kind == "."
                else node.attrs.get("id") == name)
               for kind, name in re.findall(r"([.#])([\w-]+)", selector))


def outline_removed(value):
    return bool(re.search(r"\bnone\b", value, re.I) or re.fullmatch(r"0(?:px)?", value.strip()))


def visible_replacement(props):
    outline = props.get("outline", ("", 0))[0].lower()
    shadow = props.get("box-shadow", ("", 0))[0].lower()
    # 色関数の内部は分割せず、寸法はトークン全体で読む。
    def tokens(value):
        return [part for part, _ in split_css(re.sub(r"\s+", " ", value.strip()), " ") if part]

    def length(token):
        match = re.fullmatch(r"([+-]?(?:\d*\.\d+|\d+))(px|rem|em|ex|ch|cap|ic|lh|rlh|vw|vh|vmin|vmax|cm|mm|q|in|pt|pc)?", token)
        if match and (match[2] or float(match[1]) == 0):
            return float(match[1])
        return None

    def opaque_color(token):
        try:
            color(token)
        except ValueError:
            return False
        return True

    parts = tokens(outline)
    styles = {"solid", "dashed", "dotted", "double", "groove", "ridge", "inset", "outset", "auto"}
    widths = [length(part) for part in parts if length(part) is not None]
    # 幅省略時はmedium。未対応の色・変数・透過は推定しない。
    if (any(part in styles for part in parts)
            and all(part in styles | {"thin", "medium", "thick"}
                    or length(part) is not None or opaque_color(part) for part in parts)
            and all(width > 0 for width in widths)):
        return True
    for item, _ in split_css(shadow, ","):
        parts = tokens(item)
        lengths = [length(part) for part in parts if length(part) is not None]
        if (not 2 <= len(lengths) <= 4
                or not all(part == "inset" or length(part) is not None or opaque_color(part) for part in parts)):
            continue
        x, y, blur, spread = (lengths + [0, 0])[:4]
        if blur >= 0 and (x != 0 or y != 0 or blur > 0 or spread > 0):
            return True
    return False


def check_rules(rules, nodes, emit):
    for rule in rules:
        props = rule.declarations
        size = pixels(props.get("font-size", ("", 0))[0])
        for key, (value, line) in props.items():
            value = value.lower()
            context = f"{rule.selector}: {key}: {value}"
            if key == "font-size" and size is not None and size < 14:
                emit(line, "文字サイズ", context + "（remは16px換算）")
            if key == "line-height":
                ratio = line_ratio(value, size)
                if ratio is not None and ratio < 1.5 and not (heading(rule.selector) or rule.node and rule.node.tag in HEADINGS):
                    emit(line, "行間", context + "。読み物本文に効くか確認（見出し・単行UIは別判断）")
                elif ratio is None and value != "normal":
                    emit(line, "要確認", context + "。行高の比率を静的に算出できない")
            if key in {"text-decoration", "text-decoration-line"} and value == "none":
                emit(line, "下線", context + "。本文リンクに効くか確認")
            if key in {"outline", "outline-width", "outline-style"} and outline_removed(value):
                base = re.sub(r":focus(?:-visible|-within)?", "", rule.selector)
                alternatives = [r for r in rules if r.scope == rule.scope
                                and ":focus" in r.selector
                                and re.sub(r":focus(?:-visible|-within)?", "", r.selector) == base]
                if not visible_replacement(props) and not any(visible_replacement(r.declarations) for r in alternatives):
                    emit(line, "フォーカス", context + "。同じ対象・条件で代替表示を確認できない")
            if key == "font-style" and value.startswith(("italic", "oblique")):
                targets = [rule.node] if rule.node else [n for n in nodes if matches(n, rule.selector)]
                if any(JAPANESE.search(n.text) for n in targets):
                    emit(line, "斜体", context + "。日本語を含む適用先候補あり")
                elif not targets:
                    emit(line, "要確認", context + "。日本語への適用を照合できない")
        if "color" in props and ("background-color" in props or "background" in props):
            foreground, line = props["color"]
            background = props.get("background-color", props.get("background"))[0]
            try:
                ratio = contrast(foreground, background)
            except ValueError:
                emit(line, "要確認", f"{rule.selector}: 色の組を計算できない（変数・画像・透過等）")
            else:
                if ratio < 4.5:
                    emit(line, "コントラスト", f"{rule.selector}: {ratio:.3f}:1、文字の4.5:1未満、非文字の3:1は{'充足' if ratio >= 3 else '未達'}")


def check_classes(node, emit):
    classes = (node.attrs.get("class") or "").split()
    bases = [item.rsplit(":", 1)[-1] for item in classes]
    for raw, base in zip(classes, bases):
        conditions = [p for p in raw.split(":")[:-1] if p not in {"focus", "focus-visible"}]
        replacement = any(
            re.search(r"(?:^|:)focus(?:-visible)?:(?:ring|outline)-[1-9]\d*$", c)
            and [p for p in c.split(":")[:-1] if p not in {"focus", "focus-visible"}] == conditions
            for c in classes
        )
        arbitrary = re.fullmatch(r"text-\[(\d*\.?\d+(?:px|rem))\]", base)
        if base == "text-xs" or arbitrary and pixels(arbitrary[1]) < 14:
            emit(node.line, "文字サイズ", f"class={raw}（標準値を仮定。独自設定は未解決）")
        leading = {"leading-none": 1, "leading-tight": 1.25, "leading-snug": 1.375}.get(base)
        arbitrary = re.fullmatch(r"leading-\[([^]]+)\]", base)
        if arbitrary:
            leading = line_ratio(arbitrary[1])
        if leading is not None and leading < 1.5 and node.tag not in HEADINGS:
            emit(node.line, "行間", f"class={raw}。読み物本文への適用を確認")
        if base == "no-underline":
            emit(node.line, "下線", f"class={raw}。本文リンクへの適用を確認")
        if base in {"outline-none", "outline-0", "outline-hidden"} and not replacement:
            emit(node.line, "フォーカス", f"class={raw}。同じ要素の代替クラスを確認できない")
        if base == "italic" and JAPANESE.search(node.text):
            emit(node.line, "斜体", f"class={raw}。日本語を含む（継承先も含む）")


def check_page(page, emit):
    ids = {n.attrs["id"]: n for n in page.nodes if n.attrs.get("id")}
    labels = [n for n in page.nodes if n.tag == "label" and n.text.strip()]
    for node in page.nodes:
        check_classes(node, emit)
        if node.tag in {"i", "em"} and JAPANESE.search(node.text):
            emit(node.line, "斜体", f"{node.tag}要素に日本語。既定の斜体が解除されているか確認")
        if node.tag not in {"input", "textarea", "select"}:
            continue
        if node.tag == "input" and (node.attrs.get("type") or "text").lower() in {"hidden", "submit", "button", "reset", "image"}:
            continue
        associated = any((n.attrs.get("for") == node.attrs.get("id") and node.attrs.get("id"))
                         or (not n.attrs.get("for") and any(p is n for p in node.parents)) for n in labels)
        if not associated:
            emit(node.line, "ラベル", f"{node.tag}に空でないlabelとの結び付きがない。ariaの名前だけでは可視ラベルを保証しない")
        described = any(ids.get(i) and ids[i].text.strip() for i in (node.attrs.get("aria-describedby") or "").split())
        if node.attrs.get("placeholder") and not described:
            emit(node.line, "説明", f"{node.tag}にplaceholderがあるが説明文との関連付けを確認できない。近くの可視説明も確認")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", nargs="?", type=Path, help="UTF-8のHTMLファイル")
    parser.add_argument("--css", action="append", default=[], type=Path, help="CSSファイル（繰り返し可）")
    parser.add_argument("--contrast", nargs=2, metavar=("前景色", "背景色"))
    args = parser.parse_args()
    if args.contrast:
        if args.html or args.css:
            parser.error("--contrastはファイル指定と併用できません")
        try:
            ratio = contrast(*args.contrast)
        except ValueError as error:
            parser.error(str(error))
        print(f"コントラスト比: {ratio:.6f}:1")
        print(f"4.5:1以上: {'はい' if ratio >= 4.5 else 'いいえ'} / 3:1以上: {'はい' if ratio >= 3 else 'いいえ'}")
        print("指定した不透明な2色のみの計算であり、ページの適合を保証しません。")
        return
    if not args.html:
        parser.error("HTMLファイル、または--contrastを指定してください")
    # 全入力を先に読み、読取失敗を候補0件として出さない。
    try:
        html = args.html.read_text(encoding="utf-8-sig")
        sheets = [(p.name, p.read_text(encoding="utf-8-sig")) for p in args.css]
    except (OSError, UnicodeError):
        parser.error("入力を読み取れません。ファイルの存在・読取権限・UTF-8を確認してください")
    page = Page()
    page.feed(html)
    page.close()
    findings = []

    def emitter(source):
        def emit(line, category, message):
            findings.append((source, line, category, message))
        return emit

    check_page(page, emitter(args.html.name))
    embedded = []
    for css, line in page.styles:
        embedded.extend(css_rules(css, line))
    for node in page.nodes:
        if node.attrs.get("style"):
            embedded.append(Rule(f"<{node.tag}>", declarations(node.attrs["style"], node.line), node.line, node=node))
    check_rules(embedded, page.nodes, emitter(args.html.name))
    # 明示したCSSだけを読む。link・@import・URLはたどらない。
    for source, css in sheets:
        check_rules(list(css_rules(css)), page.nodes, emitter(source))
    counts = Counter()
    # 同一規則のセレクター列挙で同じ宣言を数える場合も内容が異なる候補として出す。
    for source, line, category, message in sorted(set(findings)):
        print(f"{line}:{category}:{source}: {message}")
        counts[category] += 1
    for category in CATEGORIES:
        print(f"件数:{category}:{counts[category]}")
    print(f"合計:{sum(counts.values())}")
    print("件数は点検の候補です。アクセシビリティの適合を保証しません。")
    print("継承・詳細度・動的状態・背景画像・計算後の表示は未判定です。ブラウザで確認してください。")


if __name__ == "__main__":
    main()
