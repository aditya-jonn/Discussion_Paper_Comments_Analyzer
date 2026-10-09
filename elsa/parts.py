#!/usr/bin/env python3
"""parts.py: keep the summary as one part per code, so that a chat only ever handles one part.

  python parts.py split summary.md         writes summary-title.md and summary-<CODE>.md for each code, beside summary.md
  python parts.py join summary.md          writes summary.md from those files, with the title line brought up to date
  python parts.py number private-0001.txt  writes private-0001.md: the text of a letter or an email as a numbered comment file

The parts are plain Markdown: summary-title.md holds the title and its counts line as they were when the summary was
split, and each summary-<CODE>.md holds that code's `## ` heading and everything under it, to the next code. join puts
them back in the codebook's order and rewrites the counts line: to the numbers in summary-title.md it adds the comments,
tags and skips of every tag file in tags/ beside the parts (the <comment id>.json files the tagging chats made), so
that nothing in the title is kept by hand; it prints the old and new numbers, and warns when the tags in the files and
the tags in the sections' headings disagree, which means a part was not updated or a chat miscounted. Uses only
Python's standard library.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

CODES = ["GENERAL", "RISK", "PREMARKET", "POSTMARKET", "MASTER_FILES", "AGENTIC"]   # the codebook's order
HEADING = re.compile(r"^### \S+: .*\((\d+) comments?, (\d+) tags?\b", re.M)          # a section heading's two counts
TITLE = re.compile(r"^(\d+) tagged comments?, (\d+) tags?, (\d+) skips?(.*)$", re.M)  # the counts line under the title


def sizes(folder, names):
    for name in names:
        text = (folder / name).read_text(encoding="utf-8-sig")
        print(f"  {name}: {len(text.split())} words, {len(HEADING.findall(text))} sections")


def split(summary):
    text = summary.read_text(encoding="utf-8-sig")
    pieces = re.split(r"^(?=## )", text, flags=re.M)
    folder = summary.resolve().parent
    (folder / "summary-title.md").write_text(pieces[0].rstrip("\n") + "\n", encoding="utf-8")
    written = ["summary-title.md"]
    for piece in pieces[1:]:
        code = re.match(r"## (\S+):", piece)
        if not code or code[1] not in CODES:
            sys.exit(f"unexpected heading: {piece.splitlines()[0]}")
        (folder / f"summary-{code[1]}.md").write_text(piece.rstrip("\n") + "\n", encoding="utf-8")
        written.append(f"summary-{code[1]}.md")
    print(f"wrote {len(written)} parts beside {summary.name}:")
    sizes(folder, written)


def join(summary):
    folder = summary.resolve().parent
    names = ["summary-title.md"] + [f"summary-{code}.md" for code in CODES]
    missing = [name for name in names if not (folder / name).is_file()]
    if missing:
        sys.exit("missing: " + ", ".join(missing))
    parts = [(folder / name).read_text(encoding="utf-8-sig").rstrip("\n") for name in names]
    title = TITLE.search(parts[0])
    if not title:
        sys.exit("summary-title.md has no counts line (N tagged comments, M tags, S skips)")
    comments, tags, skips = (int(title[i]) for i in (1, 2, 3))
    files = sorted((folder / "tags").glob("*.json")) if (folder / "tags").is_dir() else []
    if not files:
        strays = [path.name for path in folder.glob("*.json") if path.name != "codebook.json"]
        print(f"no tag files found in {folder / 'tags'}" + (f"; {', '.join(strays)} in {folder} would be one: move it into tags/"
                                                             if strays else ""))
    for file in files:                                  # the comments added since the split, one tag file each
        made = json.loads(file.read_text(encoding="utf-8-sig"))
        comments += 1 if made.get("tags") else 0
        tags += len(made.get("tags", []))
        skips += len(made.get("skipped", []))
    line = f"{comments} tagged comment{'s' if comments != 1 else ''}, {tags} tag{'s' if tags != 1 else ''}, {skips} skip{'s' if skips != 1 else ''}{title[4]}"
    parts[0] = parts[0][:title.start()] + line + parts[0][title.end():]
    text = "\n\n".join(parts) + "\n"
    summary.write_text(text, encoding="utf-8")
    print(f"wrote {summary} from {len(names)} parts, {len(text.split())} words, {len(HEADING.findall(text))} sections:")
    sizes(folder, names)
    print(f"title line: {title[1]} → {comments} tagged comments, {title[2]} → {tags} tags, {title[3]} → {skips} skips, "
          f"from {len(files)} tag file{'s' if len(files) != 1 else ''} in tags/")
    in_headings = sum(int(found[1]) for found in HEADING.findall(text))
    if in_headings != tags:
        print(f"warning: the sections' headings add up to {in_headings} tags, not {tags}: a part was not updated after a tag "
              f"file was added, or a chat miscounted")


def number(source):
    """A letter or an email as a numbered comment file: one paragraph per block of text separated by a blank line."""
    found = re.search(r"private-\d{4}", source.stem)
    if not found:
        sys.exit(f"name the file after the comment's id, private-NNNN (for example private-0001.txt), not {source.name}")
    comment_id = found.group()
    text = source.read_text(encoding="utf-8-sig")
    blocks = [" ".join(line.strip() for line in block.splitlines() if line.strip()) for block in re.split(r"\n\s*\n", text)]
    blocks = [block for block in blocks if block]
    header = [f"# {comment_id}", "title: Comment received privately", "category: -", "received: -", "attachments: -",
              f"words: {len(text.split())}", f"text_hash: {hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}", "flags: private", ""]
    target = source.with_name(comment_id + ".md")
    target.write_text("\n".join(header + [f"[p{i:03d}] (body) {block}" for i, block in enumerate(blocks, 1)]) + "\n", encoding="utf-8")
    print(f"wrote {target.name}: {len(blocks)} paragraphs, {len(text.split())} words")


if __name__ == "__main__":
    jobs = dict(split=split, join=join, number=number)
    if len(sys.argv) != 3 or sys.argv[1] not in jobs:
        sys.exit("usage: python parts.py split summary.md | python parts.py join summary.md | python parts.py number private-NNNN.txt")
    jobs[sys.argv[1]](Path(sys.argv[2]))
