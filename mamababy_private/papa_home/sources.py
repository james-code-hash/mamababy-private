"""官方來源：抓網頁或 PDF → 一句一句。第二幕的知識點只能引用這裡切出來的原句（企劃 §8）。"""
from __future__ import annotations

import io
import re
import ssl
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

# 白名單（業主 2026-11-05 定）：台灣政府（國健署、衛福部、疾管署、食藥署、農業部動保網、防檢署…都在 .gov.tw）、
# 台灣兒科醫學會、獸醫師公會全聯會、AAP、WHO；台灣找不到才用國外寵物權威 AVMA、International Cat Care、康乃爾貓健康中心。
# 熱門網站只能找靈感，不能當步驟字卡的出處。其他網域要業主核准後加進來。
ALLOWED_SUFFIXES = (".gov.tw", "pediatr.org.tw", "tw-tvma.org", "tvma.org.tw", "tpnhfs.org.tw",
                    "healthychildren.org", "aap.org", "who.int", "avma.org", "icatcare.org", "vet.cornell.edu")
SENTENCE_MIN, SENTENCE_MAX = 8, 160
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in (x.lstrip(".") for x in ALLOWED_SUFFIXES))


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "form", "svg"}
    BLOCK = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr", "td", "section", "article"}

    def __init__(self) -> None:
        super().__init__()
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.out.append(data)


def html_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    return "".join(p.out)


BULLETS = "‧•●⚫・▪■□◆◇"


def join_wrapped(text: str) -> str:
    """PDF 每行會被版面切斷：行尾不是句末標點、下一行也不是項目符號開頭，就接回同一句。"""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            out.append("")
            continue
        starts_item = line[0] in BULLETS or re.match(r"^(\d+[.、)]|[（(]\d+[）)])", line)
        if out and out[-1] and not starts_item and not re.search(r"[。！？；!?：:]$", out[-1]):
            out[-1] += line
        else:
            out.append(line)
    return "\n".join(out)


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    return join_wrapped("\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(data)).pages))


def sentences(text: str) -> list[str]:
    """切成句子：以句號、驚嘆號、問號、分號與換行斷句；去掉太短（選單）或太長（整段沒標點）的。"""
    text = re.sub(r"[ \t　\xa0]+", " ", text)
    out, seen = [], set()
    for line in text.splitlines():
        for s in re.split(r"(?<=[。！？；!?])|(?<=\.)\s+(?=[A-Z])", line):  # 英文（國外寵物權威）句點後接大寫才斷
            s = s.strip(" -–" + BULLETS)
            cjk = re.search(r"[一-鿿]", s)
            latin = not cjk and len(re.findall(r"[A-Za-z]+", s)) >= 5
            if SENTENCE_MIN <= len(s) <= (SENTENCE_MAX if cjk else SENTENCE_MAX * 2) and (cjk or latin) and s not in seen:
                seen.add(s)
                out.append(s)
    return out


def fetch(url: str, timeout: int = 25) -> bytes:
    ctx = ssl.create_default_context()
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT  # 政府網站憑證缺 SKI（同 news_roundup）；仍驗證憑證鏈
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        final = resp.geturl()
        if not allowed(final):  # urlopen 會自動跟著重新導向走，最後的網址也要在白名單內
            raise ValueError(f"重新導向到白名單外：{final}")
        return resp.read()


def decode_html(data: bytes) -> str:
    """網頁解碼：先試 UTF-8，不行就照 <meta charset> 宣告，最後退回 cp950（台灣政府網站常見 Big5）。"""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    m = re.search(rb"""charset=["']?([A-Za-z0-9_-]+)""", data[:4096])
    for enc in ([m.group(1).decode("ascii", "ignore")] if m else []) + ["cp950", "big5"]:
        try:
            return data.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def load(url: str, get=fetch) -> list[str]:
    """網址 → 句子清單；不在白名單或切不出任何句子 raise ValueError。"""
    if not allowed(url):
        raise ValueError(f"來源不在白名單：{url}")
    data = get(url)
    is_pdf = data[:5] == b"%PDF-" or url.lower().endswith(".pdf")
    out = sentences(pdf_text(data) if is_pdf else html_text(decode_html(data)))
    if not out:
        raise ValueError(f"來源切不出任何句子（編碼或格式不對，或是掃描檔）：{url}")
    return out


def topic_sources(topic: dict, get=fetch) -> dict:
    """題目的來源網址 → {S1: {url, quotes}}；有 keywords 時只留含關鍵字的句子（每個來源最多 40 句）。"""
    out = {}
    for k, url in enumerate(topic.get("source_urls") or [], 1):
        rows = load(url, get=get)
        kws = topic.get("keywords") or []
        if kws:
            rows = [r for r in rows if any(w in r for w in kws)]
        if rows:
            out[f"S{k}"] = {"url": url, "quotes": rows[:40]}
    return out
