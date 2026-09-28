#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "pymupdf", "python-docx"]
# ///
"""Collect and organize public comments on FDA docket FDA-2026-N-7874 for agentic analysis.

  API documentation - https://open.gsa.gov/api/regulationsgov/

  uv run collect_comments.py

"""
import os
import sys
import time
import json
import re
import html
import hashlib
import csv
from pathlib import Path
from urllib.parse import urlparse
from collections import Counter
from datetime import datetime

DOCKET = os.environ.get("DOCKET", "FDA-2026-N-7874")
PAPER_URL = "https://www.fda.gov/media/194242/download"
API = "https://api.regulations.gov/v4"
ROOT = Path(__file__).resolve().parent
DATA, CORPUS, ANALYSIS = ROOT / "data", ROOT / "corpus", ROOT / "analysis"
RAW, FILES, COMMENTS, MAPS = DATA / "raw", DATA / "files", CORPUS / "comments", ANALYSIS / "map"


ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus"

INDEX_FIELDS = ["comment_id", "received", "title", "category", "words", "cluster", "cluster_size",
                "fda_submissions", "flags"]

PAPER_TITLE = "Considerations for the Regulation of Generative AI-Enabled Medical Devices"

# ─── fetch (network) ────────────────────────────────────────────────────────────
def download(url, dest):
    import requests
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f'dest.name: {dest.name}')
    # Write to a temp file, to address the corner cases where download fails midstream
    tmp = dest.with_name(dest.name + ".part")
    err = None
    # Make a few attempts to download the file
    for attempt in range(3):
        try:
            # fda.gov answers the default python-requests agent with a 404 
            with requests.get(url, headers={"User-Agent": "Mozilla/5.0 (public comment research; collect_comments.py)"}, timeout=180, stream=True) as reply:
                reply.raise_for_status()
                if "html" in reply.headers.get("Content-Type", ""):
                    raise ValueError("server sent a web page instead of the file")

                # Fetch data in steps of 64 KB pieces
                with open(tmp, "wb") as fh:
                    for chunk in reply.iter_content(1 << 16):
                        fh.write(chunk)
            # Convert the tmp file into permanent file
            tmp.replace(dest)
            return True
        except Exception as e:
            err = e
            # Sleep a few seconds before retrying 
            time.sleep(5 * (attempt + 1))
    tmp.unlink(missing_ok=True)  # don't leave an unfinished download behind
    print(f"   ! download failed: {url} ({err})")
    return False


def api_get(path, params, key):
    import requests
    while True:
        reply = requests.get(API + path, params=params, headers={"X-Api-Key": key}, timeout=60)
        if reply.status_code == 429:  # hourly limit used up: the one error that waiting fixes
            print("   hourly API limit reached; waiting 1 hour", flush=True)
            time.sleep(3600)
            continue  # back to the top of the loop: ask again
        reply.raise_for_status()
        return reply # the whole reply: .json() for the data, .headers for the quota


def list_comments(key):
    """Headers of every comment in the docket, read page by page until the API says there are no more."""
    comments, page = {}, 1
    while True:
        params = {"filter[docketId]": DOCKET, "page[size]": 250, "page[number]": page, "sort": "lastModifiedDate,documentId"}
        reply = api_get("/comments", params, key)
        body = reply.json()
        print(f'metadata: {body["meta"]}')
        for comment in body["data"]:
            if not comment["id"].startswith(DOCKET + "-"):  # the docket filter is undocumented: check it held
                sys.exit(f"The API returned {comment['id']}, which is not in {DOCKET}: the docket filter was ignored.")
            comments[comment["id"]] = comment["attributes"]

        if not body["meta"].get("hasNextPage"):
            print(f"Docket {DOCKET}")
            print(f"  {'Comments listed':<24}{len(comments):>5}")
            for bucket in body["meta"].get("aggregations", {}).get("postedDate", []):
                print(f"  {'Posted ' + bucket.get('label', '?').lower():<24}{bucket.get('docCount', '?'):>5}")
            print(f"  {'API requests left':<24}{reply.headers.get('X-RateLimit-Remaining', '?'):>5}"
                  f"  (of {reply.headers.get('X-RateLimit-Limit', '?')} per hour)")
            return comments
        page += 1


def fetch_comments():
    # This is a sample key: XvFrJHH9Iaekxzr88qPhHK25YtdLgsTYJAg5sP4a
    key = os.environ.get("REGS_API_KEY") or "XvFrJHH9Iaekxzr88qPhHK25YtdLgsTYJAg5sP4a"
    for folder in (RAW, FILES, CORPUS):
        folder.mkdir(parents=True, exist_ok=True)

    # If the key is not found, it will be None and the download of comments is not possible.
    if not key:
        # Ideal thing to do, but I am hardcoding the key above
        sys.exit("Set REGS_API_KEY first (free key, emailed instantly: https://api.data.gov/signup/).")

    print(ROOT)
    # Acquire the discussion paper
    if not (CORPUS / "paper.pdf").exists() and not download(PAPER_URL, CORPUS / "paper.pdf"):
        print(f"   save the discussion paper manually as corpus/paper.pdf ({PAPER_URL})")

    listing = list_comments(key)
    (DATA / "listing.json").write_text(json.dumps(listing, indent=1), encoding="utf-8")

    # fetched.json records, for each comment fetched completely, the lastModifiedDate it had then
    progress_file = DATA / "fetched.json"
    progress = json.loads(progress_file.read_text(encoding="utf-8")) if progress_file.exists() else {}
    todo = [comment_id for comment_id, attributes in listing.items()
            if not attributes.get("withdrawn") and progress.get(comment_id) != attributes.get("lastModifiedDate")]
    print(f"{len(todo)} new or changed to download")

    # Fetch the comments which has not yet been fetched
    incomplete = [] # Something that is tried but failed
    for number, comment_id in enumerate(todo):
        detail = api_get(f"/comments/{comment_id}", {"include": "attachments"}, key).json()
        (RAW / f"{comment_id}.json").write_text(json.dumps(detail, indent=1), encoding="utf-8")

        all_downloaded = True
        for attachment in detail.get("included") or []:
            for file_format in attachment["attributes"]["fileFormats"] or []:  # may be null if the attachment is withheld
                url = file_format.get("fileUrl")
                dest = FILES / comment_id / Path(urlparse(url).path).name
                if not dest.exists() and not download(url, dest):
                    all_downloaded = False
        if all_downloaded:
            progress[comment_id] = listing[comment_id].get("lastModifiedDate")
            progress_file.write_text(json.dumps(progress, indent=1), encoding="utf-8")
        else:
            incomplete.append(comment_id)
        print(f"   [{number}/{len(todo)}] {comment_id}", flush=True)

    print(f"Done: {len(todo) - len(incomplete)} of {len(todo)} comments fetched completely.")
    if incomplete:
        print(f"   {len(incomplete)} had failed downloads; re-run fetch to retry them: {', '.join(incomplete)}")

    return


# ─── extract (offline) ──────────────────────────────────────────────────────────

def norm(t):
    t = re.sub(r"(?<=[a-z])-\n(?=[a-z])", "", t)  # re-join words hyphenated at line ends
    return re.sub(r"\s+", " ", t).strip()


def natural(s):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", str(s))]


PAGE_NO = re.compile(r"(?i)(page\s*)?\d{1,3}(\s*(of|/)\s*\d{1,3})?")
TERMINAL = re.compile(r"[.!?:;)\]\"”’]$")

PARA = re.compile(r"^\[p(\d+)\] \(([^)]*)\) (.*)$")

def read_pdf(path):
    """A PDF's text blocks as (page label, text), without running headers, footers and page numbers,
    plus the page count and a flag for scans that contain no text."""
    import pymupdf

    # 1. PyMuPDF splits each page into text blocks (roughly paragraphs), in reading order. A block is
    #    (x0, y0, x1, y1, text, block number, type): its position on the page, its text, and type 0 for text.
    pages = []  # one list per page of (text, in_margin)
    with pymupdf.open(path) as doc:
        for page in doc:
            height, texts = page.rect.height, []
            for x0, y0, x1, y1, text, number, kind in page.get_text("blocks", sort=True):
                text = norm(text)
                if kind == 0 and text:
                    in_margin = y1 < 0.1 * height or y0 > 0.9 * height  # in the top or bottom strip
                    texts.append((text, in_margin))
            pages.append(texts)

    # 2. Running headers and footers: text in the top or bottom strip that recurs on at least half the pages
    #    (and at least 3). Digits become "#" first, so "Page 2 of 9" and "Page 3 of 9" count as the same text.
    def without_digits(text):
        return re.sub(r"\d+", "#", text)

    counts = Counter()
    for texts in pages:
        counts.update({without_digits(text) for text, in_margin in texts if in_margin})  # once per page
    repeated = {text for text, count in counts.items() if count >= max(3, len(pages) / 2)}

    # 3. Keep everything else, labelled with its page. In the margin, also drop lone page numbers ("3", "Page 3 of 9").
    blocks = []
    for number, texts in enumerate(pages, 1):
        for text, in_margin in texts:
            if in_margin and (without_digits(text) in repeated or PAGE_NO.fullmatch(text)):
                continue
            blocks.append((f"p.{number}", text))

    # 4. A scanned PDF holds images of pages, so it yields little or no text: under 200 characters per page.
    characters = sum(len(text) for _, text in blocks)
    flag = "no_text_layer" if pages and characters / len(pages) < 200 else ""
    return blocks, len(pages), flag


def assemble(blocks):
    """Turn text blocks into paragraphs: re-join sentences broken across lines or pages, and attach short
    headings to the paragraph they introduce. Each block either continues the previous paragraph or starts a new one."""
    paragraphs = []  # (label of the page where the paragraph starts, text)
    for label, text in blocks:
        if paragraphs:
            previous_label, previous = paragraphs[-1]
            # A sentence broken across a line or page: no final punctuation before, lower case after.
            continues = not TERMINAL.search(previous) and re.match(r"[a-z(]", text)
            # A heading: up to 12 words that don't end like a sentence (no . ! ? ; ,).
            is_heading = len(previous.split()) <= 12 and not re.search(r"[.!?;,]$", previous)
            if continues or is_heading:
                joiner = " " if continues or previous.endswith(":") else " — "
                paragraphs[-1] = (previous_label, previous + joiner + text)
                continue
        paragraphs.append((label, text))
    return paragraphs

READERS = [".pdf", ".docx", ".txt"]  # the formats we can read, in order of preference


def pick_attachments(folder):
    """For each attachment in a comment's folder, the one file to read, plus the attachments we can't read.
    The same attachment can be downloaded in several formats (attachment_1.pdf, attachment_1.docx)."""
    chosen, unreadable = [], []
    if not folder.exists():  # a comment without attachments has no folder
        return chosen, unreadable
    # attachment_1, attachment_2, ...; a leftover .part file is an unfinished download, not an attachment
    names = sorted({file.stem for file in folder.iterdir() if file.suffix != ".part"}, key=natural)
    for name in names:
        # Try the formats in order of preference: is there a .pdf? a .docx? a .txt?
        readable = [folder / (name + extension) for extension in READERS if (folder / (name + extension)).exists()]
        if readable:
            chosen.append(readable[0])  # the first one found is the preferred format
        else:
            unreadable.append(sorted(folder.glob(name + ".*"))[0])  # e.g. attachment_2.xlsx
    return chosen, unreadable


def plain_text(comment):
    """The comment box's text as plain text. The API returns it with a little HTML in it: line breaks as
    <br/> tags and some characters as codes, such as &#39; for an apostrophe."""
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", comment)  # tags that end a line
    text = re.sub(r"<[^>]+>", "", text)                                # any other tag, e.g. <b> or <a href="…">
    text = html.unescape(text)                                         # &#39; -> '   &amp; -> &
    return text.replace("\r", "")                                      # stray Windows line-end characters


def read_docx(path):
    """A Word file's paragraphs and table rows, in reading order. Word files have no fixed pages, so the page
    label is empty. Running headers and footers are stored apart from the body and aren't read."""
    import docx
    blocks = []
    for item in docx.Document(path).iter_inner_content():  # paragraphs and tables, in document order
        if isinstance(item, docx.table.Table):
            for row in item.rows:  # one block per row: "cell | cell | cell"
                cells = []
                for cell in row.cells:
                    text = norm(cell.text)
                    if text and text not in cells[-1:]:  # a merged cell is returned once per column it spans
                        cells.append(text)
                if cells:
                    blocks.append(("", " | ".join(cells)))
        elif norm(item.text):
            blocks.append(("", norm(item.text)))
    return blocks, 0, ""


def read_text(path):
    """A plain-text file's paragraphs, separated by blank lines. Text files saved on older Windows systems aren't
    UTF-8, so if reading as UTF-8 fails, the Windows encoding is used instead of silently dropping characters."""
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")  # UTF-8, with or without the marker Windows Notepad puts at the start
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")  # the older Windows encoding
    paragraphs = re.split(r"\n\s*\n", text)  # a blank line separates paragraphs
    return [("", norm(paragraph)) for paragraph in paragraphs if norm(paragraph)], 0, ""


def duplicate_groups(texts):
    """Comments whose words are identical (ignoring case and punctuation) form one group, named after the
    lowest comment id. Only exact copies are grouped, so a group never hides anyone's words."""
    groups, first = {}, {}
    for comment_id in sorted(texts, key=natural):
        words = " ".join(re.findall(r"[a-z0-9]+", texts[comment_id].lower()))
        groups[comment_id] = first.setdefault(words, comment_id)  # the first comment with these exact words
    return groups


def text_hash(lines):
    """Short fingerprint of a comment's numbered paragraphs (header excluded). A mapping records the
    fingerprint it was made against, so 'the text changed since it was mapped' does not depend on
    file timestamps, which copies, git checkouts and zip extraction do not preserve."""
    return hashlib.sha1("\n".join(lines).encode("utf-8")).hexdigest()[:12]


def write_reading_pdf(entries, target):
    """The comments typeset as a PDF for reading: a title page, then each comment from a new page, with its
    paragraph numbers (so a citation such as [FDA-2026-N-7874-0003 ¶p012] can be looked up), a bookmark per
    comment, and the comment's id and a page number on every page."""
    import pymupdf
    css = ("body {font-family: sans-serif; font-size: 10.5pt; line-height: 1.4}"
           "h1 {font-size: 15pt; margin: 0} h2 {font-size: 11.5pt; font-weight: normal; margin: 3pt 0 4pt 0}"
           "p {margin: 0 0 7pt 0} .meta {font-size: 9pt; color: #555555; margin-bottom: 12pt}"
           ".number {font-size: 8pt; color: #888888}")
    page, margins = pymupdf.paper_rect("letter"), (54, 60, -54, -54)
    writer, owners, bookmarks = pymupdf.DocumentWriter(str(target)), [], []

    def typeset(body, owner):  # lay out one piece of HTML on as many new pages as it needs
        story, more = pymupdf.Story(html=body, user_css=css), True
        while more:
            device = writer.begin_page(page)
            more, _ = story.place(page + margins)
            story.draw(device)
            writer.end_page()
            owners.append(owner)  # which comment each page belongs to

    typeset(f"<h1>Public comments on docket {DOCKET}</h1><h2>{html.escape(PAPER_TITLE)}</h2>"
            f"<p class='meta'>{len(entries)} comments · generated {datetime.now():%d %B %Y}</p>"
            f"<p>{html.escape(READING_NOTE.replace('starts on a new page', 'starts on a new page and has a bookmark'))}</p>", "")
    for comment_id, title, details, paragraphs in entries:
        parts = [f"<h1>{comment_id}</h1><h2>{html.escape(title)}</h2><p class='meta'>{html.escape(details)}</p>"]
        for number, source, text in paragraphs:
            parts.append(f"<p><span class='number'>{number} · {html.escape(source)}</span>&nbsp; {html.escape(text)}</p>"
                         if number else f"<p><i>{html.escape(text)}</i></p>")
        bookmarks.append([1, f"{comment_id}  {title}", len(owners) + 1])
        typeset("".join(parts), comment_id)
    writer.close()

    doc = pymupdf.open(str(target))  # second pass: running header, page numbers, bookmarks
    for number, (pdf_page, owner) in enumerate(zip(doc, owners), 1):
        if owner:
            pdf_page.insert_text((54, 36), owner, fontsize=8, color=(0.45, 0.45, 0.45))
        pdf_page.insert_text((page.width - 116, page.height - 28), f"Page {number} of {len(owners)}",
                             fontsize=8, color=(0.45, 0.45, 0.45))
    doc.set_toc(bookmarks)
    finished = target.with_name(target.name + ".tmp")
    doc.save(str(finished))
    doc.close()
    finished.replace(target)

READING_NOTE = ("Each comment starts on a new page. A comment whose text is identical to an earlier one "
                "shows only its header.")

def reading_entries(source):
    """The comments in all_comments.md, for the PDF and Word copies: (id, title, details line, paragraphs).
    A paragraph is (number, source, text), or (None, None, text) for a line such as "Text identical to …"."""
    entries = []
    for block in source.read_text(encoding="utf-8").split("\n---\n\n"):
        if not block.strip():  # no comments yet: the document is empty
            continue
        header, _, body = block.partition("\n\n")
        first, *rest = header.splitlines()
        fields = dict(line.split(": ", 1) for line in rest if ": " in line)
        details = [fields.get("category", "-"), f"received {fields.get('received', '-')}",
                   f"attachments: {fields.get('attachments', '-')}", f"flags: {fields.get('flags', '-')}"]
        paragraphs = []
        for line in body.strip().splitlines():
            match = PARA.match(line)  # "[p012] (att1 p.3) text"
            paragraphs.append((f"p{match[1]}", match[2], match[3]) if match else (None, None, line))
        entries.append((first.lstrip("# "), fields.get("title", ""),
                        " · ".join(d for d in details if not d.endswith("-")), paragraphs))
    return entries


def write_reading_docx(entries, target):
    """The comments as a Word document for reading: a title page, then each comment from a new page under a
    Heading 1 (so Word's navigation pane lists them), with its paragraph numbers in small grey type."""
    import docx
    from docx.shared import Inches, Pt, RGBColor
    grey = RGBColor(0x77, 0x77, 0x77)
    document = docx.Document()
    section = document.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)  # US Letter
    section.left_margin = section.right_margin = Inches(0.75)
    document.styles["Normal"].font.name, document.styles["Normal"].font.size = "Arial", Pt(10.5)

    def small(paragraph, text, size):  # add text to a paragraph as a small grey run
        run = paragraph.add_run(text)
        run.font.size, run.font.color.rgb = Pt(size), grey

    document.add_heading(f"Public comments on docket {DOCKET}", level=0)
    document.add_paragraph(PAPER_TITLE)
    small(document.add_paragraph(), f"{len(entries)} comments · generated {datetime.now():%d %B %Y}", 9)
    document.add_paragraph(READING_NOTE.replace("starts on a new page", "starts on a new page under a heading "
                                                "(View > Navigation Pane lists them)"))
    for comment_id, title, details, paragraphs in entries:
        heading = document.add_heading(comment_id, level=1)
        heading.paragraph_format.page_break_before = True
        document.add_paragraph(title)
        small(document.add_paragraph(), details, 9)
        for number, source, text in paragraphs:
            paragraph = document.add_paragraph()
            if number:
                small(paragraph, f"{number} · {source}  ", 8)
                paragraph.add_run(text)
            else:
                paragraph.add_run(text).italic = True
    document.save(str(target))


def extract_data():
    if not (DATA / "listing.json").exists():
        sys.exit("Nothing to extract yet: run fetch first.")
    listing = json.loads((DATA / "listing.json").read_text(encoding="utf-8"))
    COMMENTS.mkdir(parents=True, exist_ok=True)
    if (CORPUS / "paper.pdf").exists() and not (CORPUS / "paper.md").exists():  # the paper, converted once
        blocks, _, _ = read_pdf(CORPUS / "paper.pdf")
        (CORPUS / "paper.md").write_text("# Discussion paper (FDA, August 2026)\n\n" + "\n\n".join(
            f"({label}) {text}" for label, text in assemble(blocks)) + "\n", encoding="utf-8")

    # 1. Read every comment that isn't withdrawn: its body text, then each attachment in order.
    comments = {}
    for comment_id in sorted(listing, key=natural):
        raw_file = RAW / f"{comment_id}.json"
        if listing[comment_id].get("withdrawn") or not raw_file.exists():
            continue
        raw = json.loads(raw_file.read_text(encoding="utf-8"))
        attributes = raw["data"]["attributes"]
        chosen, unreadable = pick_attachments(FILES / comment_id)

        # Flags mark a comment whose text is incomplete; each names the attachment concerned.
        attachments = raw.get("included", [])  # may be absent when a comment has no attachments
        listed = {Path(urlparse(file_format["fileUrl"]).path).stem  # attachment_1, attachment_2, ...
                  for attachment in attachments for file_format in attachment["attributes"]["fileFormats"] or []}
        flags = [f"missing:{name}" for name in sorted(listed - {file.stem for file in chosen + unreadable}, key=natural)]
        flags += [f"withheld:attachment_{attachment['attributes'].get('docOrder', '?')}"  # listed, but no file offered
                  for attachment in attachments if not attachment["attributes"]["fileFormats"]]
        flags += [f"unreadable:{file.name}" for file in unreadable]

        body = plain_text(attributes.get("comment") or "")
        lines = [("", norm(line)) for line in body.split("\n") if norm(line)]  # one block per non-empty line
        paragraphs = [("body", text) for _, text in assemble(lines)]

        files, page_count = [], 0
        for number, file in enumerate(chosen, 1):
            reader = {".pdf": read_pdf, ".docx": read_docx}.get(file.suffix.lower(), read_text)
            try:
                blocks, pages, flag = reader(file)
            except Exception:  # a damaged or unusual file: flag it and carry on with the rest
                blocks, pages, flag = [], 0, "read_error"
            if flag:
                flags.append(f"{flag}:{file.name}")
            files.append(file.name + (f" ({pages} pp)" if pages else ""))
            page_count += pages
            paragraphs += [(f"att{number} {label}".strip(), text) for label, text in assemble(blocks)]  # e.g. "att1 p.3"
        comments[comment_id] = dict(attributes=attributes, paragraphs=paragraphs, flags=flags,
                                    files=files, pages=page_count)

    # 2. Group exact copies. Only comments with complete text are grouped: a flagged comment's text is partial, so
    #    two different letters behind the same auto-filled "See attached file(s)" line would look identical.
    texts = {comment_id: " ".join(text for _, text in comment["paragraphs"])
             for comment_id, comment in comments.items() if comment["paragraphs"] and not comment["flags"]}
    cluster_of = duplicate_groups(texts)  # comment id -> the first comment with the same words
    cluster_size = Counter(cluster_of.values())

    # 3. Write one file per comment (a short header, then its numbered paragraphs) and collect its index row.
    rows, document = [], []  # document: every comment, for the single file all_comments.md
    for comment_id, comment in comments.items():
        attributes, paragraphs, flags = comment["attributes"], comment["paragraphs"], comment["flags"]
        if not paragraphs:
            flags.append("empty")
        words = sum(len(text.split()) for _, text in paragraphs)
        cluster = cluster_of.get(comment_id, comment_id)  # a comment left out of grouping is a group of one
        row = dict(comment_id=comment_id, received=(attributes.get("receiveDate") or "")[:10],
                   title=attributes.get("title") or "", category=attributes.get("category") or "",
                   words=words, cluster=cluster, cluster_size=cluster_size.get(cluster, 1),
                   fda_submissions=attributes.get("duplicateComments") or 1, flags=";".join(flags))
        rows.append(row)
        width = max(3, len(str(len(paragraphs))))  # p001; p0001 only for a comment with 1,000+ paragraphs
        lines = [f"[p{number:0{width}d}] ({label}) {text}" for number, (label, text) in enumerate(paragraphs, 1)]
        header = [f"# {comment_id}", f"title: {row['title']}", f"category: {row['category'] or '-'}",
                  f"received: {row['received']}", f"attachments: {', '.join(comment['files']) or '-'}", f"words: {words}",
                  f"text_hash: {text_hash(lines)}", f"flags: {row['flags'] or '-'}", ""]
        text = "\n".join(header + lines) + "\n"
        (COMMENTS / f"{comment_id}.md").write_text(text, encoding="utf-8")
        # In the single document, an exact copy shows its header and points to the first comment with the same words.
        document.append(text if cluster == comment_id else "\n".join(header) + f"\nText identical to {cluster}.\n")

    # 4. The index, one row per comment, and a summary.
    with open(CORPUS / "index.csv", "w", newline="", encoding="utf-8") as index_file:
        writer = csv.DictWriter(index_file, fieldnames=INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    unique = [row for row in rows if row["cluster"] == row["comment_id"] and row["words"]]
    sizes = Counter("L" if row["words"] >= 800 else "M" if row["words"] >= 150 else "S" for row in unique)
    flag_counts = Counter(flag.split(":")[0] for row in rows for flag in row["flags"].split(";") if flag)
    print(f"{len(rows)} comments -> corpus/comments/")
    print(f"  {'Unique after grouping':<26}{len(unique):>5}")
    for size, label in (("L", "Long (800+ words)"), ("M", "Medium (150-799 words)"), ("S", "Short (under 150)")):
        print(f"  {label:<26}{sizes[size]:>5}")
    for flag, count in sorted(flag_counts.items()):
        print(f"  {'Flagged ' + flag:<26}{count:>5}")

    (CORPUS / "all_comments.md").write_text("\n---\n\n".join(document), encoding="utf-8")
    entries = reading_entries(CORPUS / "all_comments.md")  # the same document, typeset for reading
    write_reading_pdf(entries, CORPUS / "all_comments.pdf")
    write_reading_docx(entries, CORPUS / "all_comments.docx")


if __name__ == "__main__":
    # Retrieve comments using the API
    fetch_comments()

    # Extract the contents of the comments
    extract_data()