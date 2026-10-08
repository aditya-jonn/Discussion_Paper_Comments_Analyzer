# Adding a comment to the summary in Elsa

Every chat gets attachments and the message "Follow the instructions", and gives back one file to download. Nothing is typed or edited by hand.

## Once

- A folder on your computer, say `elsa`, holding `parts.py`, `subcodes.md`, `codebook.json`, `summary_pdf.py`, the seven summary files (`summary-title.md` and `summary-GENERAL.md`, `-RISK.md`, `-PREMARKET.md`, `-POSTMARKET.md`, `-MASTER_FILES.md`, `-AGENTIC.md`), and an empty subfolder `tags`.
- Two Elsa projects: **Tag**, with the text of `elsa-tag.md` as its instructions, and **Write**, with the text of `elsa-write.md`.

## For each comment

1. **A private comment that is a letter or an email**, not yet numbered: save its text as `private-NNNN.txt` and run `python parts.py number private-NNNN.txt`. That writes `private-NNNN.md`, numbered like the docket comment files. A docket comment file needs nothing.
2. **Tag chat**, a new chat in Tag. Attach `codebook.json` and the comment file. Say "Follow the instructions". Read the tag table against the comment, as you do now; this is the only step with judgment in it. Download `<comment id>.json` into `elsa/tags`. The reply's last lines name the codes with tags, for example RISK, PREMARKET, POSTMARKET.
3. **Write chats**, a new chat in Write for each code named. Attach that code's summary file, the comment file, the `.json` and `subcodes.md`. Say "Follow the instructions". Download the summary file it returns and save it over the old one in `elsa`. Glance at its old → new arithmetic.
4. **Whenever you want the whole summary**: `python parts.py join summary.md`, then `python summary_pdf.py` as before. join writes `summary.md`, brings the title line up to date from the files in `tags`, and warns if the sections' tag counts and the tags files disagree, which means a write chat is still to be done or miscounted.

Several short comments can go through one tag chat together, and a write chat can take all of them for its code: attach all their comment files and `.json` files.

## Rules

- Never run two write chats on the same summary file at once; each starts from the file the last one returned.
- The `tags` folder holds only the comments added since the summary was split; the 124 comments of the pipeline run are already in the title line's numbers.
- If a chat shows the file in a viewer instead of giving it to download, ask for it as a file. If a write chat says a tag looks wrong, decide it yourself; if it is wrong, fix the `.json` and rerun that write chat from the old summary file.
- A section's text is capped at 500 words, so a summary file can grow to about 600 words per section; PREMARKET (12 sections) could reach 7,000. If a write chat starts failing on it, say so: `parts.py` can then split that code by subcode.
