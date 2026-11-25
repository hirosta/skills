"""日本語の依頼文を行単位で点検し、候補を標準出力に表示する。"""

import argparse
import datetime
import re
import sys
import unicodedata
from pathlib import Path


SECTIONS = {
    "目的": ("目的", "作業の目的", "背景・目的"),
    "範囲": ("範囲", "作業範囲", "対象", "やること", "作業内容"),
    "やらないこと": ("やらないこと", "対象外", "範囲外", "除外", "禁止事項"),
    "受け入れ条件": ("受け入れ条件", "受入条件", "完了条件", "完了基準"),
}
CONTEXT_WORDS = re.compile(r"前に話した|前と同じ|いつもの|例の|さっきの|先ほどの")
VAGUE_WORDS = re.compile(r"いい感じに|適宜|よしなに|など|なるべく|できれば")
OPERATIONS = {
    "送信": re.compile(r"(?:メール|メッセージ)?(?:送信|送付)|メールを送|メッセージを送"),
    "公開": re.compile(r"(?<!非)公開(?!済み|されている|情報|資料)"),
    "本番反映": re.compile(r"本番.{0,12}(?:反映|適用|デプロイ)|デプロイ"),
    "削除": re.compile(r"削除|消去"),
    "支払い": re.compile(r"支払[いうえおっわ]|送金|振り?込"),
    "外部サービスへの登録": re.compile(
        r"外部.{0,15}(?:登録|アカウント作成)|(?:登録|アカウント作成).{0,15}外部"
    ),
}
# 操作の対象が同じ文節に現れる場合に限り、許可・禁止・確認の候補とみなす。
BOUNDARY_AFTER = re.compile(
    r"^.{0,8}(?:しない|しなくてよい|禁止|対象外|行わない|不要|は不可|せず|"
    r"して(?:も)?よい(?!か|のか)|を許可|は(?:担当者|利用者)が|は人が|は承認後|は確認後)"
)
BOUNDARY_BEFORE = re.compile(
    r"(?:承認|許可|確認)を(?:得て|受けて)から|(?:承認|許可|確認)後(?:に|のみ)?|"
    r"(?:担当者|利用者|人間)が"
)
CLAUSE_BREAK = re.compile(r"[。！？、；;\n]|(?:するが|しないが|する一方)")
PRIVATE_VALUE = re.compile(
    r"(?i)(?:パスワード|password|api[ _-]?キー|api[ _-]?key|"
    r"アクセストークン|access[ _-]?token|認証トークン|秘密鍵|氏名|本名|個人名|"
    r"住所|電話番号|生年月日|個人番号)\s*(?:[：=:]\s*|は\s+|は(?=[「\"a-z0-9]))\S"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\b(?:sk-[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9]{16,})\b"
    r"|[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+"
    r"|(?<!\d)(?:\+81[- ]?|0)\d{1,4}[- ]\d{1,4}[- ]\d{3,4}(?!\d)"
)
MARKUP = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
DATE_PLACEHOLDER = "YYYY-MM-DD"
DATE_VALUE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
FORMAT_ROW = re.compile(r"([^:：]+)([:：])\s*(\S.*)")


class InputError(Exception):
    """入力の内容やパスを含めずに報告できるエラー。"""


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stdout)
        print("引数エラー。指定方法は --help を参照してください。")
        self.exit(2)


def read_lines(path, label):
    try:
        if not path.is_file():
            raise InputError(f"{label}には通常のファイルを指定してください。")
        source = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError, ValueError):
        raise InputError(f"{label}を UTF-8 のテキストとして読めません。") from None
    if not source.strip() or "\x00" in source:
        raise InputError(f"{label}には空欄やバイナリではないテキストを指定してください。")
    return source.splitlines()


def unmark(line):
    return MARKUP.sub("", line.strip(), count=1).strip().replace("**", "")


def split_section(line):
    return re.split(r"[:：]", unmark(line), maxsplit=1)


def has_content(text):
    return any(character.isalnum() for character in text)


def read_formats(path):
    formats = {}
    for number, line in enumerate(read_lines(path, "書式一覧"), 1):
        if not line.strip():
            continue
        match = FORMAT_ROW.fullmatch(line)
        if not match or not match[1].strip() or line != line.strip():
            raise InputError(f"書式一覧の{number}行目は「項目名：値の形」で指定してください。")
        label = format_key(match[1])
        if label in formats:
            raise InputError(f"書式一覧の{number}行目の項目名が重複しています。")
        formats[label] = line
    return formats


def format_key(label):
    return "".join(unicodedata.normalize("NFKC", label).casefold().split())


def matches_format(line, template):
    if DATE_PLACEHOLDER not in template:
        return line == template
    pattern = re.escape(template).replace(re.escape(DATE_PLACEHOLDER), f"({DATE_VALUE.pattern})")
    match = re.fullmatch(pattern, line)
    if not match:
        return False
    try:
        for value in match.groups():
            datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def find_format(line, formats):
    label = split_section(line)[0]
    template = formats.get(format_key(label))
    if template is not None:
        return template
    label = re.split(r"[=＝\s]", label, maxsplit=1)[0]
    return formats.get(format_key(label))


def check_sections(lines):
    aliases = {alias: name for name, names in SECTIONS.items() for alias in names}
    present = set()
    section = None
    for line in lines:
        parts = split_section(line)
        heading = aliases.get(parts[0].strip())
        if heading:
            section = heading
            if len(parts) == 2 and has_content(parts[1]):
                present.add(section)
        elif line.lstrip().startswith("#"):
            section = None
        elif section and (len(parts) == 1 or LIST_ITEM.match(line)) and has_content(unmark(line)):
            present.add(section)
        elif len(parts) == 2:
            section = None
    for name in SECTIONS:
        if name not in present:
            yield f"× {name}の見出し・項目と内容を確認してください。"


def check_operations(lines):
    for name, pattern in OPERATIONS.items():
        unclear = set()
        bounded = set()
        for number, line in enumerate(lines, 1):
            for clause in CLAUSE_BREAK.split(line):
                for action in pattern.finditer(clause):
                    before = clause[:action.start()]
                    after = clause[action.end():]
                    if BOUNDARY_BEFORE.search(before) or BOUNDARY_AFTER.match(after):
                        bounded.add(number)
                    else:
                        unclear.add(number)
        for number in sorted(unclear):
            if bounded:
                yield f"△ {number}行目 {name}に別の記載があります。この操作にも適用されるか確認してください。"
            else:
                yield f"△ {number}行目 {name}の許可・禁止・人の確認の記載が見当たりません。"
        for number in sorted(bounded):
            yield f"参考 {number}行目 {name}の許可・禁止・人の確認を示す記載の候補があります。"


def quote_words(pattern, line):
    """見つかった語を出現順に重複なく「」で囲んで並べる。秘密の情報の候補には使わない。"""
    return "".join(f"「{word}」" for word in dict.fromkeys(pattern.findall(line)))


def check_brief(lines, formats):
    yield from check_sections(lines)
    for number, line in enumerate(lines, 1):
        if PRIVATE_VALUE.search(unicodedata.normalize("NFKC", line)):
            yield f"△ {number}行目 秘密の情報の候補"
        context = quote_words(CONTEXT_WORDS, line)
        if context:
            yield f"△ {number}行目 会話や記憶に頼る語の候補：{context}"
        vague = quote_words(VAGUE_WORDS, line)
        if vague:
            yield f"△ {number}行目 あいまいな語の候補：{vague}"
        template = find_format(line, formats)
        if template is not None and not matches_format(line, template):
            yield f"△ {number}行目 指定の書式と一致しません。"
    yield from check_operations(lines)


def main(argv=None):
    parser = ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("brief", nargs="+", type=Path, help="点検する UTF-8 の依頼文ファイル")
    parser.add_argument("--format-list", type=Path, help="任意の UTF-8 の書式一覧")
    args = parser.parse_args(argv)
    try:
        formats = read_formats(args.format_list) if args.format_list else {}
        briefs = [
            read_lines(path, f"依頼文 {number}")
            for number, path in enumerate(args.brief, 1)
        ]
    except InputError as error:
        print(error)
        return 2

    found = False
    for number, lines in enumerate(briefs, 1):
        print(f"依頼文 {number}")
        for finding in check_brief(lines, formats):
            print(finding)
            found |= finding.startswith(("×", "△"))
    print("目的と受け入れ条件が作業に合っているかは人が読んで確かめる")
    return int(found)


if __name__ == "__main__":
    sys.exit(main())
