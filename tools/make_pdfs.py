"""Build the PDFs of the lab manuals (one per lab + one combined book) with Microsoft Edge's headless printer.

Needs:  pip install markdown      (any Python 3)  and Microsoft Edge (or Chrome) on Windows.
Run:    python tools\\make_pdfs.py            ->  pdf\\*.pdf
Each lab's manual is labs\\<Lab>\\README.md; edit that, then rebuild.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "pdf"
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]

CSS = """
@page { size: A4; margin: 16mm 15mm 18mm 15mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.3pt; line-height: 1.42; color: #1b1b1b; }
h1 { font-size: 19pt; border-bottom: 2px solid #1f3a68; padding-bottom: 4px; margin: 0 0 10px; color: #1f3a68; }
h2 { font-size: 13.5pt; margin: 18px 0 6px; color: #1f3a68; border-bottom: 1px solid #c9d2e3; padding-bottom: 2px; }
h3 { font-size: 11.5pt; margin: 12px 0 4px; }
p, li { orphans: 3; widows: 3; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 9pt; background: #f1f3f6; padding: 0 3px; border-radius: 3px; }
pre { background: #f4f6f9; border: 1px solid #d5dbe6; border-left: 4px solid #1f3a68; padding: 7px 9px; margin: 6px 0 10px;
      white-space: pre-wrap; word-wrap: break-word; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.8pt; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 12px; font-size: 9.2pt; }
tr { page-break-inside: avoid; }
th { background: #1f3a68; color: #fff; text-align: left; }
th, td { border: 1px solid #b9c3d6; padding: 3px 6px; vertical-align: top; }
tr:nth-child(even) td { background: #f6f8fb; }
a { color: #1f3a68; text-decoration: none; }
.sec { page-break-before: always; }
.sec:first-child { page-break-before: auto; }
"""


def to_html(text):
    html = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    return re.sub(r'<a href="[^"#]+\.md">(.*?)</a>', r"\1", html)


def page(body, title):
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>"


def print_pdf(browser, html_path, pdf_path):
    # a private profile: otherwise an already open Edge window swallows the request and no PDF is written
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profile}",
                        f"--print-to-pdf={pdf_path}", html_path.as_uri()],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    if not pdf_path.exists() or pdf_path.stat().st_size < 2000:
        raise RuntimeError(f"no PDF produced for {html_path.name}")


def main():
    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if not browser:
        sys.exit("Microsoft Edge or Chrome not found")
    OUT.mkdir(exist_ok=True)
    skip = {s for s in os.environ.get("EXCLUDE", "").split(",") if s}      # labs not published yet
    sources = [ROOT / "README.md"] + sorted(p / "README.md" for p in (ROOT / "labs").iterdir() if (p / "README.md").exists() and p.name not in skip)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        sections = []
        for md in sources:
            name = "README" if md.parent == ROOT else md.parent.name
            text = md.read_text(encoding="utf-8")
            html = tmp / (name + ".html")
            html.write_text(page(to_html(text), name), encoding="utf-8")
            print_pdf(browser, html, OUT / (name + ".pdf"))
            print("wrote", name + ".pdf")
            sections.append(f"<div class='sec'>{to_html(text)}</div>")
        book = tmp / "book.html"
        book.write_text(page("".join(sections), "ROS 2 Labs"), encoding="utf-8")
        print_pdf(browser, book, OUT / "ROS2-Labs-All.pdf")
        print("wrote ROS2-Labs-All.pdf")


if __name__ == "__main__":
    main()
