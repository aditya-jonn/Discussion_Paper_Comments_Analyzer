#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf", "matplotlib"]
# ///
"""Typeset summary.md, the summary that `mini.py cites` puts together, as a PDF for reading.

  uv run summary_pdf.py                       summary.md in the current folder -> summary.pdf beside it
  uv run summary_pdf.py path/to/summary.md    another file -> path/to/summary.pdf

It also draws summary_figure.png beside the PDF: the tags per stance as bars, for each code and for each of FDA's
numbered questions. Every number in the figure is read from the summary's headings, so it shows what the PDF says.

What changes on the way to the page, and what does not:
  - The words of every section are kept exactly as they are.
  - Each run of citations after a claim becomes one small number, such as [3]. The citations themselves are
    listed under the section as its sources, shortened: [FDA-2026-N-7874-0126 ¶p091] is written 0126 ¶p091,
    and several paragraphs of one comment share its number. Every citation stays; none is dropped.
  - Each code starts on a new page. The PDF has a bookmark for every code and every subcode, the code's name
    at the top of each page, and page numbers.

It uses PyMuPDF with the same page setup as the reading copy of the comments that collect_comments.py writes.
It is a script of its own, not a job of mini.py, because mini.py uses only Python's standard library. The figure is
drawn with matplotlib, which is loaded only when the figure is drawn: the PDF does not need it.
"""
import html
import re
import sys
from datetime import datetime
from pathlib import Path

PAPER_TITLE = "Considerations for the Regulation of Generative AI-Enabled Medical Devices"
HEADING = re.compile(r"^(#{2,3}) ([A-Za-z0-9_-]+): (.*) \((\d+ comments?, \d+ tags?[^()]*)\)$")   # "## RISK: label (73 comments, ...)"
DOCKET = re.compile(r"(FDA-\d{4}-N-\d{4})-(\d{4})")                             # a docket comment's id: the docket, then the comment's number
CITATION = re.compile(r"\[(?:" + DOCKET.pattern + r"|(private-\d{4})) \u00b6(p\d{3,})\]")   # [FDA-2026-N-7874-0126 ¶p091]; [private-0001 ¶p003] for a comment received privately
CITATION_RUN = re.compile(r"(?:\s*" + CITATION.pattern + r")+")                 # one or more citations side by side
STANCE_COUNT = re.compile(r"(\d+) ([a-z]+(?:-[a-z]+)*)")                        # "382 conditional", in a heading's counts
QUESTION = re.compile(r"^Q(\d+)$")                                             # a subcode that is one of FDA's numbered questions
FIGURE_WORD = "Sentiment"                                                      # what the figure calls a stance, in its titles and legend
STANCE_COLORS = {"support": "#28a745", "conditional": "#ffc107", "conditional-minor": "#ffd54f", "conditional-major": "#fb8c00",
                 "oppose": "#dc3545", "neutral": "#000000"}                    # in the order the bars are stacked; any other stance is grey
DARK_ON = {"conditional", "conditional-minor", "conditional-major"}            # stances whose colour is light: their labels are black
LABEL_FROM = 0.125      # a part of a bar gets a label if it is at least this share of the panel's longest bar: shorter, the label wouldn't fit
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
    """The citations of one run, shortened and grouped by comment: '0005 ¶p252, ¶p305; 0028 ¶p022'. A docket comment
    is named by its number alone; a comment received privately keeps its whole name, private-0001."""
    by_comment = {}
    for _, number, private, paragraph in CITATION.findall(run):
        comment = number or private
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
    text = Path(source).read_text(encoding="utf-8")
    docket = (DOCKET.search(text) or ["", "the docket"])[1]
    private = any(private for _, _, private, _ in CITATION.findall(text))   # does the summary cite a comment received privately?
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
            f"so every claim can be looked up in the commenter\u2019s own words.</p>"
            + (f"<p>A comment received privately rather than through the docket keeps its own name, such as private-0001. "
               f"It is not on regulations.gov.</p>" if private else ""), "")
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


def stance_counts(counts):
    """The tags per stance in a heading's counts: '73 comments, 428 tags: 36 support, 382 conditional' gives
    {'support': 36, 'conditional': 382}. A heading with no tags gives an empty dict."""
    return {stance: int(number) for number, stance in STANCE_COUNT.findall(counts.partition(": ")[2])}


def figure_rows(codes):
    """What the figure shows, read from the summary's headings: (the stances, one row per code, one row per numbered
    question). A row is (name, {stance: tags}). A question nobody raised is listed with no tags, so it is not left out."""
    per_code = [(code["name"], stance_counts(code["counts"])) for code in codes]
    questions = {section["name"]: stance_counts(section["counts"]) for code in codes for section in code["sections"]
                 if QUESTION.match(section["name"])}
    for code in codes:
        for note in code["notes"]:
            if note.startswith("Not raised: "):
                questions.update({name: {} for name in note[len("Not raised: "):].split(", ") if QUESTION.match(name)})
    per_question = sorted(questions.items(), key=lambda row: int(QUESTION.match(row[0])[1]))
    found = {stance for _, taken in per_code + per_question for stance in taken}
    stances = [stance for stance in STANCE_COLORS if stance in found] + sorted(found - set(STANCE_COLORS))
    return stances, per_code, per_question


def bar_labels(rows):
    """The labels inside the bars of one panel: {(name, stance): '71%  (202)'}, the stance's share of its bar and its
    tags. Only a part that is at least LABEL_FROM of the panel's longest bar gets one."""
    longest = max((sum(taken.values()) for _, taken in rows), default=0)
    return {(name, stance): f"{100 * tags / sum(taken.values()):.0f}%  ({tags})"
            for name, taken in rows for stance, tags in taken.items() if tags >= LABEL_FROM * longest}


def write_stance_figure(source, target, dpi=150):
    """Draw the figure for the summary at `source` and save it at `target` (a .png, or a .pdf or .svg): on the left
    the tags per stance for each code, on the right for each numbered question. Returns (codes, questions) drawn."""
    import matplotlib
    matplotlib.use("Agg")                                          # draw to a file; no window is needed
    import matplotlib.pyplot as plt
    _, codes = parse_summary(Path(source).read_text(encoding="utf-8"))
    stances, per_code, per_question = figure_rows(codes)
    span = f" (Q{QUESTION.match(per_question[0][0])[1]}\u2013Q{QUESTION.match(per_question[-1][0])[1]})" if per_question else ""
    panels = [(f"{FIGURE_WORD} per Section", per_code, 30, 22), (f"{FIGURE_WORD} per Question{span}", per_question, 24, 15)]

    figure, axes = plt.subplots(1, 2, figsize=(26, 12.5))
    drawn, legends = [], []                                        # drawn: (axis, the label, where its part of the bar starts, how wide that part is)
    for axis, (title, rows, name_size, label_size) in zip(axes, panels):
        labels, left = bar_labels(rows), [0] * len(rows)
        names = [name.replace("_", " ") for name, _ in rows]
        for stance in stances:
            widths = [taken.get(stance, 0) for _, taken in rows]
            axis.barh(names, widths, left=left, height=0.74, color=STANCE_COLORS.get(stance, "#888888"),
                      label=stance.replace("-", ", ").capitalize())
            for position, ((name, _), width, start) in enumerate(zip(rows, widths, left)):
                if (name, stance) in labels:
                    drawn.append((axis, axis.text(start + width / 2, position, labels[(name, stance)], ha="center", va="center",
                                                  fontsize=label_size, fontweight="bold",
                                                  color="black" if stance in DARK_ON else "white"), start, width))
            left = [start + width for start, width in zip(left, widths)]
        axis.invert_yaxis()                                        # the first code, or Q1, at the top
        axis.set_ylim(len(rows) - 0.5, -0.5)
        axis.set_xlim(0, max(left, default=0) * 1.05 or 1)
        axis.set_title(title, fontsize=34, fontweight="bold")
        axis.set_xlabel("Number of Tags", fontsize=28)
        axis.tick_params(axis="x", labelsize=24)
        axis.tick_params(axis="y", labelsize=name_size, length=0)
        for side in axis.spines.values():
            side.set_color("#b0b0b0")
        legends.append(axis.legend(title=FIGURE_WORD, loc="lower right", fontsize=22, title_fontsize=26))
    figure.tight_layout(w_pad=6)
    renderer = figure.canvas.get_renderer()
    # The legend sits bottom right. If a bar reaches under it there, it moves to where it covers the least.
    for axis, legend in zip(axes, legends):
        box = legend.get_window_extent(renderer)
        if any(box.overlaps(bar.get_window_extent(renderer)) for bar in axis.patches if bar.get_width() > 0):
            legend.remove()
            axis.legend(title=FIGURE_WORD, loc="best", fontsize=22, title_fontsize=26)
    # A label must stay inside its part of the bar. One that is too wide is set smaller, down to two thirds of its
    # size; if it still does not fit, it is left out rather than drawn over its neighbours.
    for axis, label, start, width in drawn:
        room = 0.94 * (axis.transData.transform((start + width, 0))[0] - axis.transData.transform((start, 0))[0])
        smallest = label.get_fontsize() * 2 / 3
        while label.get_window_extent(renderer).width > room and label.get_fontsize() > smallest:
            label.set_fontsize(label.get_fontsize() - 1)
        if label.get_window_extent(renderer).width > room:
            label.remove()
    figure.savefig(str(target), dpi=dpi)
    plt.close(figure)
    return len(per_code), len(per_question)


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("summary.md")
    if not source.exists():
        sys.exit(f"There is no {source}. Run `python mini.py cites` until it writes summary.md, or give the file's path.")
    target = source.with_suffix(".pdf")
    pages, sections, citations = write_summary_pdf(source, target)
    print(f"wrote {target}: {pages} pages, {sections} sections, {citations} citations listed as sources")
    figure = source.with_name(source.stem + "_figure.png")
    try:
        drawn_codes, drawn_questions = write_stance_figure(source, figure)
        print(f"wrote {figure}: the tags per stance for {drawn_codes} codes and {drawn_questions} questions")
    except ImportError:            # the PDF is written either way; the figure needs one more package
        print(f"did not write {figure}: matplotlib is not installed. Run with `uv run summary_pdf.py`, or install matplotlib.")
