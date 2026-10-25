"""外部参照のないローカルHTMLをChrome系ブラウザでPDFにする。"""
import argparse
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


class LocalHTML(HTMLParser):
    """印刷対象は静的HTMLと同じディレクトリ内のSVGだけに限定する。"""

    def __init__(self, folder):
        super().__init__()
        self.folder = folder
        self.images = set()
        self.slides = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"script", "iframe", "object", "embed", "link", "base", "video", "audio", "source", "svg", "math"}:
            raise ValueError("スクリプト・埋め込み・外部スタイルは使えません")
        if tag == "meta" and "http-equiv" in values:
            raise ValueError("http-equivは入力に指定できません")
        for key, value in attrs:
            if key.startswith("on") or key in {"srcset", "background", "action", "formaction", "ping"}:
                raise ValueError("動的な処理・追加の参照は使えません")
            if key in {"src", "href"}:
                if tag != "img" or key != "src" or not value:
                    raise ValueError("参照はローカルSVG画像だけ使えます")
                parts = urlsplit(value)
                name = unquote(parts.path)
                if parts.scheme or parts.netloc or parts.query or parts.fragment or Path(name).name != name:
                    raise ValueError("画像はHTMLと同じフォルダーのSVGを指定してください")
                image = self.folder / name
                if image.suffix.lower() != ".svg" or image.is_symlink():
                    raise ValueError("画像は通常のSVGファイルにしてください")
                svg = image.read_text(encoding="utf-8")
                root = ET.fromstring(svg)
                for element in root.iter():
                    if element.tag.split("}")[-1] not in {"svg", "text", "tspan", "g", "path", "rect", "circle", "line", "title", "desc"}:
                        raise ValueError("SVGに許可していない要素があります")
                    if any(k.split("}")[-1] in {"href", "src", "style"} or k.startswith("on") for k in element.attrib):
                        raise ValueError("SVGに追加の参照・処理があります")
                if re.search(r"url\s*\(|<!DOCTYPE|<!ENTITY", svg, re.I):
                    raise ValueError("SVGに追加の参照があります")
                self.images.add(image)
        if "slide" in (values.get("class") or "").split():
            self.slides += 1

    handle_startendtag = handle_starttag


def find_browser(explicit):
    if explicit:
        path = Path(explicit).expanduser()
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge", "chrome", "msedge"):
        if found := shutil.which(name):
            return found
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ]
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if base := os.environ.get(variable):
            candidates.extend(Path(base) / item for item in (
                "Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe"))
    return next((str(p) for p in candidates if p.is_file()), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--browser")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    source = args.html.resolve()
    output = (args.out or source.with_suffix(".pdf")).absolute()
    if output.suffix.lower() != ".pdf" or output.resolve() == source or output.is_symlink():
        parser.exit(2, "出力先は入力と異なる通常のPDFファイルを指定してください\n")
    if output.exists() and not args.force:
        parser.exit(2, "同名のPDFがあります。上書きの了承後に--forceを指定してください\n")
    browser = find_browser(args.browser)
    if not browser:
        parser.exit(2, "Chrome・Chromium・Microsoft Edgeが見つかりません。--browserで実行ファイルを指定してください\n")
    try:
        html = source.read_text(encoding="utf-8")
        # CSSのエスケープやコメントによる参照の隠蔽も許可しない。
        if re.search(r"url\s*\(|@import|\\|/\*", html, re.I):
            raise ValueError("CSSのURL・import・エスケープ・コメントは使えません")
        document = LocalHTML(source.parent)
        document.feed(html)
        if not document.slides:
            raise ValueError("class=slide のスライドがありません")
        with tempfile.TemporaryDirectory(prefix="proposal-deck-") as temporary:
            folder = Path(temporary)
            policy = '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; img-src file:; font-src &#39;none&#39;">'
            staged = folder / "deck.html"
            secured, inserted = re.subn(r"(<head\b[^>]*>)", lambda match: match[0] + policy, html, count=1, flags=re.I)
            if not inserted:
                raise ValueError("HTMLにhead要素がありません")
            staged.write_text(secured, encoding="utf-8")
            for image in document.images:
                shutil.copyfile(image, folder / image.name)
            pdf = folder / "deck.pdf"
            command = [browser, "--headless", "--no-pdf-header-footer", "--disable-background-networking",
                       "--disable-component-update", "--disable-sync", "--no-first-run", "--no-default-browser-check",
                       "--disable-extensions", "--disable-default-apps", "--disable-domain-reliability",
                       "--host-resolver-rules=MAP * ~NOTFOUND", "--proxy-server=http://127.0.0.1:9",
                       "--proxy-bypass-list=<-loopback>", f"--user-data-dir={folder / 'profile'}",
                       f"--print-to-pdf={pdf}", staged.as_uri()]
            result = subprocess.run(command, capture_output=True, timeout=90, check=False)
            if result.returncode or not pdf.is_file():
                raise ValueError("ブラウザのPDF出力に失敗しました")
            content = pdf.read_bytes()
            pages = len(re.findall(rb"/Type\s*/Page\b", content))
            print(f"HTML: {document.slides}枚 / PDF: {pages}ページ")
            if pages != document.slides:
                raise ValueError("ページ数が一致しません。出力を保存せず終了します")
            # xモードにより並行実行でも既存ファイルを上書きしない。
            with output.open("wb" if args.force else "xb") as stream:
                stream.write(content)
        print("PDFを保存しました。固定高による文字の欠落はページ数では検出できません。全ページを画像で確認してください。")
    except (OSError, UnicodeError, ValueError, ET.ParseError, subprocess.TimeoutExpired):
        parser.exit(2, "印刷できませんでした。入力・ローカルSVG・出力先・ブラウザを確認してください（外部参照や動的処理は非対応）\n")


if __name__ == "__main__":
    main()
