Tag the attached comments.

Attached: `codebook.json` (the codes, subcodes, stances and the skip rule) and the comments to tag, each as `FDA-2026-N-7874-NNNN.md` or `private-NNNN.md`: the comment's id on the first line, a short header, and then the comment's paragraphs, numbered `[p001]`, `[p002]`, and so on. If a comment is not numbered, number it yourself, `p001` onward in order, one paragraph for each block of text separated by a blank line, every block counted (a mail header, a salutation, a heading, a list item and a signature block are each one), and give the numbering in your reply and in the file described below. Use only what I gave you: the codebook decides every code, subcode, stance and skip. If you were shown only parts of the codebook or of a comment, say which parts you saw and work from those: never fill in a part you did not see.

Your tags are written into the summary by other chats, one for each code, which see your file and the comment and nothing else of this chat: the file must be complete. Work through the three steps below in order and show the work of each in your reply, so that I can check it.

## 1. Read

Read all of `codebook.json`. Each code and subcode has a `label`, a `covers` text and `cues`, and codes, stances and the skip rule have `excludes`, which draw the borders between them. In your reply, note in two or three sentences per code the borders its `excludes` draw (the stances and the skip rule need no note). Then read each comment from start to end before tagging any of it.

## 2. Tag

For each paragraph of each comment, decide one of two things:

- A tag: the code and subcode whose `covers` fit the point (when two fit, the codebook's `excludes` and `priority` decide); the stance, by the codebook's definitions; and a gist of at most 25 words, in your own words, saying what the paragraph asks or states. A paragraph gets one tag per point it makes; a second tag only when it makes two separable points under different subcodes. A heading that introduces a paragraph is tagged with that paragraph, not on its own. A paragraph that only repeats a point made earlier in the comment, in an introduction, a list or a conclusion, gets its own tag with the subcode and stance of the point it repeats, so that its citation can join that claim.
- A skip, with its reason: text that makes no point (greetings, signatures, a table of contents), or a point on a topic the paper does not address, written as `Outside the paper: <topic>`. A worry about such a topic that is tied to a part of FDA's proposal is tagged with that part's subcode instead; the skip rule's `excludes` gives examples of these cases, not a complete list.

On stances: the size of the change decides, not how firmly it is asked for. Asking FDA to define, spell out, clarify or add detail to something, or to weigh further factors, leaves the approach working the same way (conditional-minor). A core element added, replaced or removed, or a defining feature reversed, makes it work differently (conditional-major). When it is unclear whether the approach would work differently, use conditional-minor. Agreement that asks for nothing is support; agreement that also asks for something, even "the framework should include…", is conditional-minor, not support; rejecting the approach itself is oppose; information that takes no position is neutral.

If two of the comments I gave you are identical, tag the first and say that the second is its duplicate, which gets no tags.

## 3. Count

For each comment: the codes that have tags, with the number of tags under each by stance (`RISK: 1 tag, 1 conditional-minor; PREMARKET: 2 tags, 2 conditional-minor`), and one line `adds 1 comment, 4 tags, 6 skips` (a comment counts as tagged when it has at least one tag), with the arithmetic on the line after it.

## What to give me

In your reply, in this order: the borders note (step 1), and the numbering of any comment that came without it (the number and the first few words of each paragraph); the tag table (step 2), with the columns paragraph, code, subcode, stance and gist, in the order of the paragraphs, then the skipped paragraphs with their reasons, then the decisions that were hard to call (a stance, a subcode, a skip) with your reason for each; the counts (step 3). Then the tags as a file named after the comment, `<comment id>.json`, as `{"comment_id": "...", "tags": [{"code": "...", "subcode": "...", "paragraph": "p001", "stance": "...", "gist": "..."}], "skipped": [{"paragraph": "p002", "reason": "..."}]}`, the tags in the order of the paragraphs, the stance as its key (`conditional-minor`), one file per comment, as a file to download, not in a viewer and not printed in the reply. A heading tagged with its paragraph is one tag whose paragraph is the range, `"p003-p004"`, with one gist; a paragraph with two points is two tags. For a comment you numbered yourself, add `"paragraphs": {"p001": "<its first five words>", "p002": "...", ...}`, every paragraph, so that the other chats find them.

Before you finish, check three things: every paragraph of every comment is either in the tag table or in your skipped list; the stance of every tag follows the codebook's definitions and the rule on agreement that asks for something; and the file holds the same tags and skips as the table. Do not add anything that no comment I gave you says.
