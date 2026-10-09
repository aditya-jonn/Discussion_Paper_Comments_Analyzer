# Adding a comment to the summary in Elsa

Every chat gets attachments and the message "Follow the instructions", and gives back one file to download.

## Once

- A folder on your computer, say `elsa`, holding `parts.py`, `subcodes.md`, `codebook.json`, `summary_pdf.py`, the seven summary files (`summary-title.md` and `summary-GENERAL.md`, `-RISK.md`, `-PREMARKET.md`, `-POSTMARKET.md`, `-MASTER_FILES.md`, `-AGENTIC.md`), and an empty subfolder `tags`.
- Two Elsa projects: **Tag**, with the text of `elsa-tag.md` as its instructions, and **Write**, with the text of `elsa-write.md`.

## For each comment

1. **A private comment that is a letter or an email**, not yet numbered: save its text as `private-NNNN.txt` and run `python parts.py number private-NNNN.txt`. That writes `private-NNNN.md`, numbered like the docket comment files. A docket comment file needs nothing.
2. **Tag chat**, a new chat in Tag. Attach `codebook.json` and the comment file. Say "Follow the instructions". Download `<comment id>.json` into `elsa/tags`. The reply's last lines name the codes with tags, for example RISK, PREMARKET, POSTMARKET.
3. **Write chats**, a new chat in Write for each code named. Attach that code's summary file, the comment file, the `.json` and `subcodes.md`. Say "Follow the instructions". Download the summary file it returns and save it over the old one in `elsa`. 
4. **Whenever you want the whole summary**: `python parts.py join summary.md`, then `python summary_pdf.py` as before. join writes `summary.md`.

Several short comments can go through one tag chat together, and a write chat can take all of them for its code: attach all their comment files and `.json` files.

## Rules

- Never run two write chats on the same summary file at once; each starts from the file the last one returned.
- The `tags` folder holds only the comments added since the summary was split.
- If a chat shows the file in a viewer instead of giving it to download, ask for it as a file. 
