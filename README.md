# Analyzer: three ways to turn the docket's comments into the cited summary

| Method | Where it runs | What does the work | Use it for |
|---|---|---|---|
| **Pipeline** | ChatGPT or Claude Code | `mini.py` checks every step by code and builds the summary from the tags | the whole corpus |
| **Parts** | Elsa | one tagging chat, then one writing chat per code; the summary is kept as one file per code and `parts.py` joins them | late and private comments, at any summary size |
| **Single** | Elsa | one prompt, one chat, the whole summary attached | the same, while the summary fits in a chat (about 5,000 words) |

All three use the same `codebook.json`, produce the same `summary.md`, and end with `python summary_pdf.py`.

## Pipeline/

`CLAUDE.md` (the instructions), `mini.py` (check, map, build, cites; start and finish for chats), `codebook.json`, `collect_comments.py` (fetches the docket and builds the corpus), and the pipeline's own `README.md`. The three limits near the top of `mini.py` (`BATCH_WORDS`, `PART_WORDS`, `MAP_WORDS`) are 100,000 words for ChatGPT/Claude Code; set them to 20,000 for elsa.

## Parts/

`elsa-tag.md` (the Tag project's instructions), `elsa-write.md` (the Write project's), `elsa-steps.md` (the procedure, one page), `parts.py` (split, join, number), `subcodes.md` (attached to writing chats), `codebook.json` (attached to tagging chats). The working files, `summary-title.md`, the six `summary-<CODE>.md` and the `tags/` folder, will be in the working folder, not here.

## Single/

`elsa-prompt.md` (the project's instructions) and `codebook.json`; attach both with `summary.md` and the comment.
