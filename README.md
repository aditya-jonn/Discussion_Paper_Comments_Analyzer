# Analyzer: three ways to turn the docket's comments into the cited summary

| Method | Where it runs | What does the work | Use it for |
|---|---|---|---|
| **Pipeline** | Claude Code (or ChatGPT, with the state round trip) | `mini.py` checks every step by code and builds the summary from the tags and the concept layer | the whole corpus |
| **Parts** | Elsa | one tagging chat, then one writing chat per code; the summary is kept as one file per code and `parts.py` joins them | late and private comments, at any summary size |
| **Single** | Elsa | one prompt, one chat, the whole summary attached | the same, while the summary fits in a chat (about 4,000 words) |

All three use the same `codebook.json`, produce the same `summary.md`, and end with `python summary_pdf.py` (kept here, once) to typeset it.

## Pipeline/

`CLAUDE.md` (the instructions), `mini.py` (check, map, build, cites; start and finish for chats), `codebook.json`, `seed_concepts.py` (starts the concept layer from a summary written before it existed), `collect_comments.py` (fetches the docket and builds the corpus; needs `requests`, `pymupdf`, `python-docx`), and the pipeline's own `README.md`. The three limits near the top of `mini.py` (`BATCH_WORDS`, `PART_WORDS`, `MAP_WORDS`) are 100,000 words for Claude Code; set them to 20,000 for a chat.

## Parts/

`elsa-tag.md` (the Tag project's instructions), `elsa-write.md` (the Write project's), `elsa-steps.md` (the procedure, one page), `parts.py` (split, join, number), `subcodes.md` (attached to writing chats), `codebook.json` (attached to tagging chats). The working files, `summary-title.md`, the six `summary-<CODE>.md` and the `tags/` folder, live in your working folder, not here.

## Single/

`elsa-prompt.md` (the project's instructions) and `codebook.json`; attach both with `summary.md` and the comment.
