#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf"]
# ///
"""Typeset summary.md, the summary that `mini.py cites` puts together, as a PDF for reading.

  uv run summary_pdf.py                       summary.md in the current folder -> summary.pdf beside it
  uv run summary_pdf.py path/to/summary.md    another file -> path/to/summary.pdf

What changes on the way to the page, and what does not:
  - The words of every section are kept exactly as they are.
  - Each run of citations after a claim becomes one small number, such as [3]. The citations themselves are
    listed under the section as its sources, shortened: [FDA-2026-N-7874-0126 ¶p091] is written 0126 ¶p091,
    and several paragraphs of one comment share its number. Every citation stays; none is dropped.
  - Each code starts on a new page. The PDF has a bookmark for every code and every subcode, the code's name
    at the top of each page, and page numbers.

It uses PyMuPDF with the same page setup as the reading copy of the comments that collect_comments.py writes.
It is a script of its own, not a job of mini.py, because mini.py uses only Python's standard library.
"""
import html
import re
import sys
from datetime import datetime
from pathlib import Path

PAPER_TITLE = "Considerations for the Regulation of Generative AI-Enabled Medical Devices"
HEADING = re.compile(r"^(#{2,3}) ([A-Za-z0-9_-]+): (.*) \((\d+ comments?, \d+ tags?[^()]*)\)$")   # "## RISK: label (73 comments, ...)"
CITATION = re.compile(r"\[(FDA-\d{4}-N-\d{4})-(\d{4}) \u00b6(p\d{3,})\]")       # [FDA-2026-N-7874-0126 ¶p091]
CITATION_RUN = re.compile(r"(?:\s*" + CITATION.pattern + r")+")                 # one or more citations side by side
CSS = ("body {font-family: sans-serif; font-size: 10.5pt; line-height: 1.4}"
       "h1 {font-size: 16pt; margin: 0 0 2pt 0} h2 {font-size: 12pt; margin: 14pt 0 1pt 0}"
       "p {margin: 0 0 7pt 0} .meta {font-size: 9pt; color: #555555; margin: 0 0 8pt 0}"
       ".ref {font-size: 8pt; color: #23498F} .sources {font-size: 8pt; color: #666666; line-height: 1.35}"
       ".title {font-size: 20pt; margin: 0 0 4pt 0} .lead {font-size: 12pt; margin: 0 0 14pt 0}")


def parse_summary(text):
    """summary.md as (totals line, codes). A code is a dict: name, label, counts, sections and notes; a section is
    a dict: name, label, counts, paragraphs. Notes are a code's plain lines, such as "Not raised: X-SEC, X-IP"."""
    lines = text.replace("\r\n", "\n").split("\n")
    totals = next(line for line in lines[1:] if line.strip())      # the first line with text after the title
    codes, section = [], None
    for line in lines[lines.index(totals) + 1:]:
        heading = HEADING.match(line)
        if heading and heading[1] == "##":
            codes.append(dict(name=heading[2], label=heading[3], counts=heading[4], sections=[], notes=[]))
            section = None
        elif heading:
            section = dict(name=heading[2], label=heading[3], counts=heading[4], paragraphs=[])
            codes[-1]["sections"].append(section)
        elif line.startswith("#"):
            raise ValueError(f"a heading the summary's format doesn't have: {line[:80]}")
        elif line.strip() and line.startswith("Not raised: "):
            codes[-1]["notes"].append(line.strip())
            section = None
        elif line.strip() and section is not None:
            section["paragraphs"].append(line.strip())
        elif line.strip():
            codes[-1]["notes"].append(line.strip())                # for example "No commenter raised this."
    return totals, codes


def short_sources(run):
    """The citations of one run, shortened and grouped by comment: '0005 ¶p252, ¶p305; 0028 ¶p022'."""
    by_comment = {}
    for _, comment, paragraph in CITATION.findall(run):
        by_comment.setdefault(comment, [])
        if paragraph not in by_comment[comment]:
            by_comment[comment].append(paragraph)
    return "; ".join(f"{comment} " + ", ".join(f"\u00b6{p}" for p in paragraphs) for comment, paragraphs in by_comment.items())


def section_html(section):
    """One section as HTML: its heading, its counts, its paragraphs with a number for each run of citations, and
    the sources those numbers stand for. Returns (html, how many citations it lists)."""
    sources, listed = [], 0

    def numbered(run):
        nonlocal listed
        sources.append(short_sources(run.group()))
        listed += sources[-1].count("\u00b6")
        return f"<span class='ref'>&nbsp;[{len(sources)}]</span>"

    parts = [f"<h2 id='{section['name']}'>{html.escape(section['name'])}: {html.escape(section['label'])}</h2>",
             f"<p class='meta'>{html.escape(section['counts'])}</p>"]
    for paragraph in section["paragraphs"]:
        pieces, last = [], 0
        for run in CITATION_RUN.finditer(paragraph):               # the words are escaped; the runs become numbers
            pieces.append(html.escape(paragraph[last:run.start()]) + numbered(run))
            last = run.end()
        parts.append("<p>" + "".join(pieces) + html.escape(paragraph[last:]) + "</p>")
    if sources:
        parts.append("<p class='sources'><b>Sources.</b> " + " &nbsp; ".join(
            f"<b>[{number}]</b> {html.escape(source)}" for number, source in enumerate(sources, 1)) + "</p>")
    return "".join(parts), listed


def write_summary_pdf(source, target):
    """Typeset the summary at `source` as a PDF at `target`. Returns (pages, sections, citations listed)."""
    import pymupdf
    totals, codes = parse_summary(Path(source).read_text(encoding="utf-8"))
    docket = (CITATION.search(Path(source).read_text(encoding="utf-8")) or ["", "the docket"])[1]
    page, margins = pymupdf.paper_rect("letter"), (54, 60, -54, -54)
    writer, owners, bookmarks = pymupdf.DocumentWriter(str(target)), [], []
    titles = {section["name"]: f"{section['name']}: {section['label']}" for code in codes for section in code["sections"]}

    def typeset(body, owner):  # lay out one piece of HTML on as many new pages as it needs
        story, more = pymupdf.Story(html=body, user_css=CSS), True
        while more:
            device = writer.begin_page(page)
            more, _ = story.place(page + margins)
            # Note where each subcode's heading landed, for its bookmark. The title comes from the summary, by the
            # heading's id: the text the page reports loses a space where a long heading wraps.
            story.element_positions(lambda position: bookmarks.append([2, titles[position.id], len(owners) + 1])
                                    if position.heading == 2 and position.open_close & 1 and position.id in titles else None)
            story.draw(device)
            writer.end_page()
            owners.append(owner)  # which code each page belongs to

    section_total = sum(len(code["sections"]) for code in codes)
    typeset(f"<p class='title'><b>Summary of public comments</b></p>"
            f"<p class='lead'>{html.escape(PAPER_TITLE)}<br>Docket {html.escape(docket)}</p>"
            f"<p class='meta'>{html.escape(totals)} &middot; {section_total} sections &middot; generated {datetime.now():%d %B %Y}</p>"
            f"<p>Each section says what commenters wrote about one part of FDA\u2019s paper. The line under a section\u2019s "
            f"heading counts the comments and tags behind it, and the positions those tags take.</p>"
            f"<p>A number in brackets, such as <span class='ref'>[3]</span>, points to that section\u2019s sources, listed under "
            f"its text. A source names a comment and a paragraph: 0126 \u00b6p091 is paragraph p091 of comment {html.escape(docket)}-0126, "
            f"so every claim can be looked up in the commenter\u2019s own words.</p>", "")
    citations = 0
    for code in codes:
        parts = [f"<h1>{html.escape(code['name'])}: {html.escape(code['label'])}</h1><p class='meta'>{html.escape(code['counts'])}</p>"]
        for section in code["sections"]:
            body, listed = section_html(section)
            parts.append(body)
            citations += listed
        parts += [f"<p><i>{html.escape(note)}</i></p>" for note in code["notes"]]
        bookmarks.append([1, f"{code['name']}: {code['label']}", len(owners) + 1])
        typeset("".join(parts), f"{code['name']}: {code['label']}")
    writer.close()

    doc = pymupdf.open(str(target))  # second pass: running header, page numbers, bookmarks
    for number, (pdf_page, owner) in enumerate(zip(doc, owners), 1):
        if owner:
            pdf_page.insert_text((54, 36), owner, fontsize=8, color=(0.45, 0.45, 0.45))
        pdf_page.insert_text((page.width - 116, page.height - 28), f"Page {number} of {len(owners)}",
                             fontsize=8, color=(0.45, 0.45, 0.45))
    doc.set_toc(sorted(bookmarks, key=lambda entry: (entry[2], entry[0])))   # in page order, a code before its subcodes
    finished = Path(target).with_name(Path(target).name + ".tmp")
    doc.save(str(finished))
    doc.close()
    finished.replace(target)
    return len(owners), section_total, citations


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("summary.md")
    if not source.exists():
        sys.exit(f"There is no {source}. Run `python mini.py cites` until it writes summary.md, or give the file's path.")
    target = source.with_suffix(".pdf")
    pages, sections, citations = write_summary_pdf(source, target)
    print(f"wrote {target}: {pages} pages, {sections} sections, {citations} citations listed as sources")
