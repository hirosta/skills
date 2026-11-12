#!/usr/bin/env python3
"""会社のX原稿を点検する。入力の読み取りと標準出力だけを行う。"""

import argparse
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


# URLの厳密な抽出や絵文字データベースの代用ではない。範囲はREADMEを参照。
# 本文を飲み込まないよう、ホスト・パス・クエリの文字を明示する。
# 非ASCIIのURLは対象外。日本語のパスはパーセント符号化した原稿で確認する。
URL_PATH = r"[A-Za-z0-9!*';:=+,.$/%#\[\]_~@|&-]"
URL_QUERY = r"[A-Za-z0-9!?*'@();:&=+$/%#\[\]_.,~|-]"
URL = re.compile(
    r"(?:(?i:https?)://[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?"
    r"|(?<![\w@/])(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63})"
    r"(?::[0-9]+)?(?:/" + URL_PATH + r"*)?(?:\?" + URL_QUERY + r"*)?"
)
HASHTAG = re.compile(r"[#＃][\w]+")
PARENS = re.compile(r"（[^（）]*）|\([^()]*\)")
CAUTION = re.compile(r"結果|試作|検証|条件|場合|保証|異な|限[りる]|対象|時点|参考")
ASSERTION = re.compile(r"必ず|誰でも|[〇○\d０-９]+(?:[.．][\d０-９]+)?倍|が不要になる")
EMOJI_BASE = r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2300-\u23FF\u2B50\u2B55]"
EMOJI = re.compile(
    r"[0-9#*]\ufe0f?\u20e3|[\U0001F1E6-\U0001F1FF]{2}|"
    + EMOJI_BASE + r"[\ufe0e\ufe0f]?[\U0001F3FB-\U0001F3FF]?"
    + r"(?:\u200d" + EMOJI_BASE + r"[\ufe0e\ufe0f]?[\U0001F3FB-\U0001F3FF]?)*"
    + r"|[©®™]\ufe0f"
)
LIGHT_RANGES = ((0, 0x10FF), (0x2000, 0x200D), (0x2010, 0x201F), (0x2032, 0x2037))
FINAL_NOTE = "1行目で手が止まるか、事実が一次情報と合っているかは人が読んで確かめる"


class InputError(Exception):
    """公開可能な入力エラー。原文やローカルのパスは表示しない。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InputError("引数が不正です。--helpで使い方を確認してください。")


def read_text(filename):
    try:
        value = Path(filename).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError, ValueError):
        raise InputError("入力ファイルをUTF-8で読み取れません。") from None
    if not value.strip() or any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in value):
        raise InputError("入力が空か、使用できない制御文字を含んでいます。")
    return value


def urls_in(text):
    spans = []
    for match in URL.finditer(text):
        value = match.group().rstrip(".,!?。、！？:;)]}）")
        spans.append((match.start(), match.start() + len(value), value))
    return spans


def without_urls(text, urls):
    chars = list(text)
    for start, end, _ in urls:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def weighted_length(text):
    text = unicodedata.normalize("NFC", text)
    urls = urls_in(text)
    entities = {start: (end, 23) for start, end, _ in urls}
    for match in EMOJI.finditer(text):
        if not any(start <= match.start() < end for start, end, _ in urls):
            entities[match.start()] = (match.end(), 2)
    total = index = 0
    while index < len(text):
        if index in entities:
            index, weight = entities[index]
        else:
            codepoint = ord(text[index])
            weight = 1 if any(low <= codepoint <= high for low, high in LIGHT_RANGES) else 2
            index += 1
        total += weight
    return total


def inspect_post(text, terms):
    findings = []

    def add(level, label, detail):
        findings.append((level, label, detail))

    urls = urls_in(text)
    body = without_urls(text, urls)
    tags = list(HASHTAG.finditer(body))
    emojis = list(EMOJI.finditer(body))
    parens = list(PARENS.finditer(body))
    cautions = [m for m in parens if CAUTION.search(m.group())]
    marker_notes = [
        match for match in re.finditer(r"※[^\n]*", body)
        if not any(paren.start() <= match.start() < paren.end() for paren in parens)
    ]
    cautions.extend(marker_notes)
    weight = weighted_length(text)
    if weight > 280:
        add("×", "加重文字数", f"概算{weight}字で280字を超えています")
    if len(text) > 120:
        add("△", "長さの目安", f"改行・URLを含む原稿が{len(text)}文字です（目安120文字程度）")
    if len(urls) > 1:
        add("×", "リンク数", "最後の1つに絞ってください")
    for start, end, value in urls:
        if start and not text[start - 1].isspace():
            add("×", "URL前の空白", value)
        if text[end:].strip():
            add("×", "リンクの位置", "URLの後に本文や記号があります")
    if len(tags) > 1:
        add("×", "ハッシュタグ数", "0〜1個にしてください")
    for match in emojis:
        add("×", "絵文字", match.group())
    if len(cautions) > 1:
        add("×", "注意書き数", "結果・数字がある場合だけ末尾に1つにしてください")
    for match in cautions:
        tail = body[match.end():]
        if HASHTAG.sub("", tail).strip():
            add("×", "注意書きの位置", match.group())
    for match in parens:
        if match not in cautions:
            add("△", "括弧の補足", f"注意書きか、本文に戻せるか確認: {match.group()}")
    # 括弧なしの注記は条件の内容も人の確認へ回す。
    for match in marker_notes:
        add("△", "括弧外の注記", match.group())
    result_body = PARENS.sub("", body)
    result_body = re.sub(r"※[^\n]*", "", result_body)
    has_result = bool(re.search(r"結果|実績|[0-9０-９]+(?:件|人|分|秒|[%％]|倍)", result_body))
    if has_result and not cautions:
        add("△", "注意書きの不足候補", "結果・数字の条件を末尾の注意書き1つで示せるか確認")
    if cautions and not has_result:
        add("△", "注意書きの必要性", "結果・数字を書く投稿か確認")
    for match in ASSERTION.finditer(body):
        add("△", "効果・実績・保証の言い切り候補", match.group())
    for term in terms:
        for _ in re.finditer(re.escape(term), body):
            add("△", "社内の言葉", term)
    first = text.splitlines()[0]
    if re.match(r"(?:当社|弊社|株式会社|有限会社)", first):
        add("△", "1行目", "社名・当社の報告ではなく読み手の困りごと・事実・答えから始める")
    metrics = (
        f"原稿{len(text)}文字 / 加重概算{weight}字 / URL {len(urls)}個 / "
        f"ハッシュタグ{len(tags)}個 / 絵文字概算{len(emojis)}個 / "
        f"注意書き候補{len(cautions)}個（括弧全体{len(parens)}個）"
    )
    return first, metrics, findings


def main():
    parser = Parser(description="UTF-8の原稿を点検。1ファイル1投稿、複数ファイル指定可。")
    parser.add_argument("posts", nargs="+", help="原稿ファイル（本文内の改行可）")
    parser.add_argument("--internal-terms", help="社内語一覧のUTF-8ファイル（1行1語）")
    try:
        args = parser.parse_args()
        terms = []
        if args.internal_terms:
            terms = list(dict.fromkeys(
                line.strip() for line in read_text(args.internal_terms).splitlines() if line.strip()
            ))
        posts = [read_text(name).rstrip("\n") for name in args.posts]
        if any(not text.splitlines()[0].strip() for text in posts):
            raise InputError("原稿の1行目が空です。先頭の空行を除いてください。")
    except InputError as error:
        print(f"入力エラー: {error}")
        print(FINAL_NOTE)
        return 2

    results = [inspect_post(text, terms) for text in posts]
    groups = defaultdict(list)
    for index, (first, _, _) in enumerate(results):
        # 固定8文字と、よくある型を別々に照合。意味の近さは読んで確かめる。
        groups[("先頭8文字", first[:8])].append(index)
        for label, pattern in (("質問型", r"で困っていませんか[？?]"), ("紹介型", r"を紹介します")):
            if re.search(pattern, first):
                groups[(label, label)].append(index)
    for (kind, prefix), indices in groups.items():
        if len(indices) > 1:
            numbers = "・".join(str(i + 1) for i in indices)
            for index in indices:
                results[index][2].append(("△", "1行目の重なり", f"{kind}: {prefix}（投稿{numbers}）"))

    counts = Counter()
    print("社内語一覧: " + ("、".join(terms) if terms else "指定なし（社内語の自動推定はしません）"))
    for index, (first, metrics, findings) in enumerate(results, 1):
        print(f"\n投稿{index}: {metrics}\n1行目: {first}")
        for level, label, detail in findings:
            counts[level] += 1
            print(f"{level} {label}: {detail}")
        if not findings:
            print("機械検出なし（人の確認は必要）")
    print(f"\n合計: × {counts['×']}件 / △ {counts['△']}件")
    print(FINAL_NOTE)
    return 1 if counts else 0


if __name__ == "__main__":
    sys.exit(main())
