"""
mini.py: the tools for the mini tagging pipeline.

    python mini.py check     check Claude's tag files (described below)
    python mini.py build     count the comments and tags for every code and subcode, and write the evidence
    python mini.py cites     check the summary sections, and put them together as summary.md

For every tag file in tags/, it asks five questions:
    1. Is every code real, and every stance and subcode?  (all must be in codebook.json, and each
       subcode must belong to its tag's code)
    2. Does every tag and skip point to a real paragraph?  (it must exist in the comment; a tag may cover a
       range such as p003-p004, and then every paragraph in the range must exist)
    3. Is every paragraph either tagged or skipped, never both, and skipped at most once?
    4. Is every gist between 1 and 25 words long?
    5. Does the file name its own comment, and does every skip give a reason?
    6. Does every file, tag and skip have exactly the fields the format defines, and nothing else?
A "no" to any of them is an ERROR: definitely wrong, and must be fixed. So is a tag file in tags/ that is named
after no comment in comments/, such as a leftover from an earlier session or a sync program's "conflicted copy":
it can't be checked, and build would trip over it.

It also looks for things that might be wrong, and reports them as a WARNING:
    - a gist that repeats 6 words in a row from its paragraph (it may be copied, not paraphrased)
    - a paragraph with the same code twice (it may be one point tagged twice)
    - a skip reason that points to a paragraph with no tag (a heading's point may have been lost)
A warning is a question, not a verdict: fix it, or explain why it's fine.

It also plans the work, for runs that take many sessions:
    duplicates     a comment is not tagged when at least 80% of its substantive paragraphs appear in one other
                   comment; nothing is deleted. Of two comments that contain each other (a resubmission), the
                   later is kept; if only one contains the other, the larger is kept, so no content is lost
    next batch     the comments still to tag, in id order, up to 100,000 words: what one session tags
    next part      once every comment is tagged, build names the summary sections still to write, in order, up to
                   100,000 words of evidence: what one session reviews and summarizes

Where the results go:
    the terminal   the findings (at most 15) and, last, a one-line summary
    check.md       the full report, replaced on every run
    log.md         one line per run, in the tool's own words
    exit code      0 when every comment is tagged and there are no errors, otherwise 1;
                   2 when the check could not run at all, because codebook.json is broken
"""
import json
import re
from collections import Counter
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent        # the mini/ folder, wherever the script is run from
PARAGRAPH = re.compile(r"^\[(p\d+)\] \([^)]*\) (.*)$")   # "[p003] (body) text"  ->  "p003", "text"
MAX_GIST_WORDS = 25                           # the limit set in the instructions (CLAUDE.md)
SECTION_WORDS = 150                           # a summary section may have this many words...
SECTION_WORDS_PER_TAG = 3                     # ...plus this many for every tag it has to cover...
MAX_SECTION_WORDS = 500                       # ...up to this many. build states each section's budget in its part file
WORD = re.compile(r"[A-Za-z0-9]+(?:['\u2019-][A-Za-z0-9]+)*")   # a word: letters or digits, joined by ' or -
COPIED_RUN = 6                                # this many words in a row, identical to the paragraph, suggests copying
BATCH_WORDS = 100000                          # one session tags at most this many words; a longer comment is a batch alone
PART_WORDS = 100000                           # one session summarizes at most this many words of evidence
DUPLICATE_SHARE = 0.8                         # a comment is a duplicate if this share of its substantive paragraphs...
SUBSTANTIVE_WORDS = 5                         # ...appears in one other comment; a paragraph needs this many words to count
REPORT = HERE / "check.md"                    # the full report
LOG = HERE / "log.md"                         # Claude's work log; each tool adds one line per run
EVIDENCE = HERE / "evidence.md"               # the overview: every code's and subcode's heading, with its counts
PARTS = HERE / "evidence"                     # the evidence itself, one part file per subcode: every tag next to its source text
SECTIONS = HERE / "summary"                   # Claude's summary, one section file per subcode, named like its part file
SUMMARY = HERE / "summary.md"                 # the sections put together; cites writes it when all are there and clean
CITES = HERE / "cites.md"                     # the full report of the cites job
CLAIMS = HERE / "cites"                       # for each section, every claim next to the paragraphs it cites
CITATION = re.compile(r"\[(FDA-\d{4}-N-\d{4}-\d{4}) \u00b6(p\d{3})\]")   # [FDA-2026-N-7874-0039 ¶p003], as build writes them
CITATION_RUN = re.compile(r"(?:\s*" + CITATION.pattern + r")+")            # one or more citations side by side
RANGE = re.compile(r"^p(\d{3,})(?:-p(\d{3,}))?$")       # "p004", or a range: "p003-p004"
PRINT_AT_MOST = 15                            # the terminal shows at most this many findings; check.md has them all
CODE_FIELDS = {"label", "priority", "covers", "cues", "excludes"}   # what every code in codebook.json must have
SKIP_FIELDS = {"label", "covers", "cues", "excludes"}               # what the skip entry must have
BRACKETED_CODE = re.compile(r"\(([A-Z][A-Z_]+)\)")                 # "(GENERAL)" inside an excludes text
STANCE_FIELDS = SKIP_FIELDS                                          # each stance has the same four fields
SUBCODE_FIELDS = {"code", "label", "covers", "cues"}                 # what every subcode must have; "code" is its parent
BRACKETED_STANCE = re.compile(r"\(([a-z]+(?:-[a-z]+)*)\)")          # "(conditional-minor)": lowercase words, joined by hyphens
STANCE_NAME = re.compile(r"^[a-z]+(?:-[a-z]+)*$")                    # a stance's name has that shape, so that an excludes can point to it
FILE_KEYS = ("comment_id", "tags", "skipped")                       # a tag file has exactly these fields,
TAG_KEYS = ("code", "subcode", "paragraph", "stance", "gist")        # a tag exactly these,
SKIP_KEYS = ("paragraph", "reason")                                  # and a skip exactly these
SUBCODE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")             # a subcode's name is also a file name: evidence/Q19.md
SECTION_HEADING = re.compile(r"^### ([A-Za-z0-9-]+): ")              # a subcode's heading, as build writes it
HEADING_COUNTS = re.compile(r"\((\d+) comments?, (\d+) tags?")       # "(43 comments, 91 tags: ...", at the end of a heading


def paragraph_texts(comment_file):
    """Each paragraph's text by its id, for example {"p001": "Thank you for ..."}."""
    texts = {}
    for line in comment_file.read_text(encoding="utf-8").splitlines():
        match = PARAGRAPH.match(line)
        if match:
            texts[match[1]] = match[2]
    return texts


def comment_words(comment_file):
    """The comment's length in words, from its header ("words: 1234"); counted from its paragraphs if there is none."""
    for line in comment_file.read_text(encoding="utf-8").splitlines():
        if PARAGRAPH.match(line):
            break
        if line.startswith("words: ") and line[7:].strip().isdigit():
            return int(line[7:])
    return sum(len(text.split()) for text in paragraph_texts(comment_file).values())


def duplicates(comment_files):
    """Which comments repeat another: {duplicate id: id of the comment kept instead}.

    A comment is a duplicate when at least DUPLICATE_SHARE of its substantive paragraphs (SUBSTANTIVE_WORDS words or
    more, compared without regard to case or spacing) appear in one other comment. Of two comments that contain each
    other, as a resubmission and its original do, the later (higher id) is kept. If only one contains the other, the
    larger is kept, so no content is lost. Short fragments such as "Sincerely," never make two comments duplicates."""
    norm = lambda text: " ".join(text.lower().split())
    paras = {f.stem: {norm(t) for t in paragraph_texts(f).values() if len(t.split()) >= SUBSTANTIVE_WORDS}
             for f in comment_files}
    def inside(a, b):
        return bool(paras[a]) and len(paras[a] & paras[b]) / len(paras[a]) >= DUPLICATE_SHARE
    found, ids = {}, sorted(paras)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:                       # a has the lower id
            if inside(a, b):
                found[a] = b                        # a is in b (whether or not b is also in a): keep the later, b
            elif inside(b, a):
                found[b] = a                        # only b is in a: keep the larger, a
    for dup in list(found):                         # follow chains, so each points to a comment that is kept
        kept, seen = found[dup], {dup}
        while kept in found and kept not in seen:
            seen.add(kept)
            kept = found[kept]
        found[dup] = kept
    return found


def runs_of_words(text, length):
    """Every run of `length` consecutive words in the text. A run never crosses punctuation, so a list
    such as 'data minimization, retention limits, access controls' is not one long run: repeating a list
    of terms isn't copying prose. Arrows, as in 'evaluation → deployment', separate items the same way.
    Hyphenated words, such as 're-benchmarking', count as one word."""
    runs = []
    for clause in re.split(r"[,;:.!?()\u2013\u2014\u2192]", text.lower()):
        words = re.findall(r"[a-z0-9]+(?:['\-][a-z0-9]+)*", clause)
        runs += [" ".join(words[i:i + length]) for i in range(len(words) - length + 1)]
    return runs


def copied_run(gist, paragraph):
    """The first run of COPIED_RUN words that the gist shares with its paragraph, or None."""
    paragraph_runs = set(runs_of_words(paragraph, COPIED_RUN))
    return next((run for run in runs_of_words(gist, COPIED_RUN) if run in paragraph_runs), None)


def now():
    """The current time, labelled UTC: the sandbox's clock runs on UTC, and an unlabelled time is ambiguous."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def plural(n, word):
    """'1 comment', '2 comments'."""
    return f"{n} {word}{'' if n == 1 else 's'}"


def codebook_problems(codebook):
    """Check codebook.json itself. Every other check trusts it, so if it's broken, their results can't be trusted."""
    codes = codebook.get("codes") or {}
    skip = codebook.get("skip") or {}
    problems = [] if codes else ["there are no codes under 'codes'"]
    for code, entry in codes.items():
        if set(entry) != CODE_FIELDS:
            problems.append(f"code {code} has the fields {sorted(entry)}; it needs {sorted(CODE_FIELDS)}")
        elif not isinstance(entry["priority"], int):
            problems.append(f"code {code}: its priority must be a whole number")
    if set(skip) != SKIP_FIELDS:
        problems.append(f"the skip entry has the fields {sorted(skip)}; it needs {sorted(SKIP_FIELDS)}")
    # A code named in brackets in an `excludes` must exist. Otherwise, renaming a code leaves a pointer to nothing.
    for owner, entry in list(codes.items()) + [("skip", skip)]:
        for named in BRACKETED_CODE.findall(str(entry.get("excludes", ""))):
            if named not in codes:
                problems.append(f"{owner}: its excludes points to ({named}), which is not a code")
    # The stances: the same four fields as the skip entry, and the same rule for names in brackets.
    stances = codebook.get("stances") or {}
    if not stances:
        problems.append("there are no stances under 'stances'")
    for stance, entry in stances.items():
        if not STANCE_NAME.match(stance):      # otherwise a pointer to it in brackets could not be recognized, or checked
            problems.append(f"stance {stance}: its name must be lowercase words joined by hyphens, like conditional-minor")
        if set(entry) != STANCE_FIELDS:
            problems.append(f"stance {stance} has the fields {sorted(entry)}; it needs {sorted(STANCE_FIELDS)}")
        for named in BRACKETED_STANCE.findall(str(entry.get("excludes", ""))):
            if named not in stances:
                problems.append(f"stance {stance}: its excludes points to ({named}), which is not a stance")
    # The subcodes: the second level. Each points to its parent code, and every code needs at least one.
    subcodes = codebook.get("subcodes") or {}
    if not subcodes:
        problems.append("there are no subcodes under 'subcodes'")
    for name, entry in subcodes.items():
        if set(entry) != SUBCODE_FIELDS:
            problems.append(f"subcode {name} has the fields {sorted(entry)}; it needs {sorted(SUBCODE_FIELDS)}")
        elif entry["code"] not in codes:
            problems.append(f"subcode {name} belongs to {entry['code']}, which is not a code")
        if name in codes:
            problems.append(f"subcode {name} has the same name as a code; the two levels must not share names")
        if not SUBCODE_NAME.match(name):
            problems.append(f"subcode '{name}': its name is also used as a file name, so it may contain only letters, "
                            f"digits and hyphens")
    for code in codes:
        if not any(entry.get("code") == code for entry in subcodes.values()):
            problems.append(f"code {code} has no subcodes; every code needs at least one")
    return problems


def expand(value):
    """The paragraphs a tag covers: "p004" gives ["p004"]; "p003-p005" gives ["p003", "p004", "p005"].
    Returns None when the value is neither a paragraph id nor a range, or when the range runs backwards."""
    match = RANGE.match(str(value or ""))
    if not match:
        return None
    first = int(match[1])
    last = int(match[2]) if match[2] else first
    if last < first:
        return None
    width = len(match[1])                               # keep the zero padding: 3 gives "p003"
    return [f"p{number:0{width}d}" for number in range(first, last + 1)]


def section_budget(tags):
    """How many words a subcode's summary section may have: the more tags it has to cover, the more words, up to a
    ceiling. build states the budget in the section's part file and cites enforces it: one definition for both."""
    return min(MAX_SECTION_WORDS, SECTION_WORDS + SECTION_WORDS_PER_TAG * tags)


def stance_columns(stances):
    """The stances' column headings in build's table: their first four letters, as long as those tell the stances
    apart. If two stances share them, a name with a hyphen is shortened around it instead (conditional-minor becomes
    c-min); and if headings still collide, the full names are used."""
    first_four = [stance[:4] for stance in stances]
    around_hyphen = [stance[0] + "-" + stance.split("-", 1)[1][:3] if "-" in stance else stance[:4] for stance in stances]
    for headings in (first_four, around_hyphen):
        if len(set(headings)) == len(headings):
            return headings
    return list(stances)


def summary_plan(sections):
    """What is left of the summary: (the sections still to write, the next part, the next part's words of evidence).

    A section is written once its file exists in summary/. The next part is what one session reviews and summarizes:
    the sections still to write, in evidence.md's order, up to PART_WORDS words of evidence. A section whose evidence
    is longer than that is a part of its own."""
    still = [name for name in sections if not (SECTIONS / f"{name}.md").exists()]
    part, part_words = [], 0
    for name in still:
        words = len((PARTS / f"{name}.md").read_text(encoding="utf-8").split())
        if part and part_words + words > PART_WORDS:
            break
        part.append(name)
        part_words += words
    return still, part, part_words


def check_file(tag_file, paragraphs, codes, stances, subcodes):
    """Return (errors, warnings) for one tag file: two lists of sentences, empty if all is well."""
    # Guard 1: a file that isn't valid JSON can't be checked any further.
    try:
        data = json.loads(tag_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"not valid JSON ({error})"], []

    errors, warnings = [], []
    # Guard 2: a missing list is itself a problem; treat it as empty so the other checks can still run.
    for key in ("tags", "skipped"):
        if key not in data:
            errors.append(f"the '{key}' list is missing")
    tags = data.get("tags", [])
    skips = data.get("skipped", [])
    # Question 6: nothing outside the format. A field no tool reads is never checked, counted or shown, so an
    # invented one (a "topic" label, say) would drift silently. Say which field, and list the ones that exist.
    for key in sorted(set(data) - set(FILE_KEYS)):
        errors.append(f"the file has a field '{key}' that the format doesn't have; a tag file has exactly: {', '.join(FILE_KEYS)}")

    # Question 5a: the file names its own comment. Files get copied and renamed; a mismatch means a mix-up.
    if data.get("comment_id") != tag_file.stem:
        errors.append(f"comment_id is '{data.get('comment_id')}' but the file is named {tag_file.name}")

    # Questions 1 and 2: every tag uses a real code and points to a real paragraph.
    seen = set()                                    # (paragraph, code) pairs met so far
    tagged = set()                                  # every paragraph covered by at least one tag
    for number, tag in enumerate(tags, 1):
        for key in sorted(set(tag) - set(TAG_KEYS)):
            errors.append(f"tag {number}: it has a field '{key}' that the format doesn't have; a tag has exactly: {', '.join(TAG_KEYS)}")
        if tag.get("code") not in codes:
            errors.append(f"tag {number}: '{tag.get('code')}' is not a code in codebook.json")
        # The subcode must exist and belong to the tag's code: the two fields must agree.
        options = ", ".join(name for name, entry in subcodes.items() if entry["code"] == tag.get("code"))
        if "subcode" not in tag:
            errors.append(f"tag {number}: the subcode is missing" + (f"; {tag.get('code')}'s subcodes are: {options}" if options else ""))
        elif tag["subcode"] not in subcodes:
            errors.append(f"tag {number}: '{tag['subcode']}' is not a subcode in codebook.json"
                          + (f"; {tag.get('code')}'s subcodes are: {options}" if options else ""))
        elif tag.get("code") in codes and subcodes[tag["subcode"]]["code"] != tag["code"]:
            errors.append(f"tag {number}: subcode {tag['subcode']} belongs to {subcodes[tag['subcode']]['code']}, "
                          f"not to {tag['code']}; {tag['code']}'s subcodes are: {options}")
        if "stance" not in tag:
            errors.append(f"tag {number}: the stance is missing; it must be one of {', '.join(stances)}")
        elif tag["stance"] not in stances:
            errors.append(f"tag {number}: stance '{tag['stance']}' is not one of {', '.join(stances)}")
        covered = expand(tag.get("paragraph"))
        if covered is None:
            errors.append(f"tag {number}: '{tag.get('paragraph')}' is neither a paragraph id like p004 "
                          f"nor a forward range like p003-p004")
            covered = []
        missing = [paragraph for paragraph in covered if paragraph not in paragraphs]
        if missing:
            errors.append(f"tag {number}: {', '.join(missing)} does not exist in this comment")
        tagged.update(covered)

        # Warning: the same code twice on one paragraph is usually one point tagged twice, but could be two points.
        for paragraph in covered:
            if (paragraph, tag.get("code")) in seen:
                warnings.append(f"tag {number}: {paragraph} already has a {tag.get('code')} tag; remove it if it's "
                                f"the same point, or explain why it's a second one")
                break
        seen.update((paragraph, tag.get("code")) for paragraph in covered)

        # Question 4: the gist's length is a hard rule, so breaking it is an error.
        gist = str(tag.get("gist") or "")
        word_count = len(gist.split())
        if word_count == 0:
            errors.append(f"tag {number}: the gist is empty")
        elif word_count > MAX_GIST_WORDS:
            errors.append(f"tag {number}: the gist has {word_count} words; the limit is {MAX_GIST_WORDS}")

        # Warning: repeated wording may be copying, or may be precise technical language. Claude must judge.
        for paragraph in covered:
            run = copied_run(gist, paragraphs[paragraph]) if paragraph in paragraphs else None
            if run:
                warnings.append(f"tag {number}: the gist repeats {COPIED_RUN} words in a row from {paragraph} "
                                f"(\"{run}\"); put the point in your own words, or explain why not")
                break
    for number, skip in enumerate(skips, 1):
        for key in sorted(set(skip) - set(SKIP_KEYS)):
            errors.append(f"skip {number}: it has a field '{key}' that the format doesn't have; a skip has exactly: {', '.join(SKIP_KEYS)}")
        if "-" in str(skip.get("paragraph")):
            errors.append(f"skip {number}: '{skip.get('paragraph')}' is a range, but a skip covers one paragraph; "
                          f"give each skipped paragraph its own skip")
        elif skip.get("paragraph") not in paragraphs:
            errors.append(f"skip {number}: paragraph '{skip.get('paragraph')}' does not exist in this comment")

        # Question 5b: every skip gives a reason, so every skip is a decision someone can review.
        reason = str(skip.get("reason") or "").strip()
        if not reason:
            errors.append(f"skip {number}: the reason is empty")

        # Warning: a heading's reason names where its point was tagged. If that paragraph has no tag, the point
        # may have been lost. Only a warning: a reason is free text and may mention a paragraph for another purpose.
        for pointer in re.findall(r"\bp\d{3}\b", reason):
            if pointer != skip.get("paragraph") and pointer not in tagged:
                warnings.append(f"skip {number}: the reason points to {pointer}, which has no tag")

    # Question 3: every paragraph is accounted for, exactly one way, and skipped at most once.
    skip_counts = Counter(skip.get("paragraph") for skip in skips)
    skipped = set(skip_counts)
    for paragraph in sorted(paragraphs):
        if paragraph not in tagged and paragraph not in skipped:
            errors.append(f"{paragraph} is neither tagged nor skipped")
        if paragraph in tagged and paragraph in skipped:
            errors.append(f"{paragraph} is both tagged and skipped")
        if skip_counts[paragraph] > 1:
            errors.append(f"{paragraph} is skipped {skip_counts[paragraph]} times")
    return errors, warnings


def check(hand_over=True):
    # Step 0: the codebook itself. If it's broken, stop: a check built on a broken codebook would mislead.
    # Nothing is written to check.md or log.md, because a check that didn't run has no result to record.
    try:
        codebook = json.loads((HERE / "codebook.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"check could not run: cannot read codebook.json ({error})")
        return 2
    problems = codebook_problems(codebook)
    if problems:
        print("check could not run: codebook.json has problems:")
        for problem in problems:
            print(f"  {problem}")
        return 2
    codes, stances, subcodes = codebook["codes"], codebook["stances"], codebook["subcodes"]
    findings, still_to_tag = [], []
    error_total = warning_total = 0
    # Every tag file must belong to a comment. The loop below starts from the comments, so a tag file named after no
    # comment would never be checked there, and build, which reads every file in tags/, would crash on it. These
    # findings come first: they are about the folder, and at scale the terminal shows only the first few findings.
    comment_files = sorted((HERE / "comments").glob("*.md"))
    comment_ids = {comment_file.stem for comment_file in comment_files}
    dups = duplicates(comment_files)
    for tag_file in sorted((HERE / "tags").glob("*.json")):
        if tag_file.stem not in comment_ids:
            findings.append(f"{tag_file.name}: ERROR: there is no comment {tag_file.stem} in comments/, and every tag "
                            f"file must be named after one. Rename it if it belongs to a comment; otherwise move it out of tags/")
            error_total += 1
        elif tag_file.stem in dups:
            findings.append(f"{tag_file.name}: ERROR: {tag_file.stem} is a duplicate of {dups[tag_file.stem]}, so it is not "
                            f"tagged: a tag file for it would count its points twice. Move this file out of tags/")
            error_total += 1
    for comment_file in comment_files:
        if comment_file.stem in dups:
            continue                                # a duplicate is never tagged: its points are counted once, in the kept one
        tag_file = HERE / "tags" / f"{comment_file.stem}.json"
        if not tag_file.exists():
            still_to_tag.append(comment_file.stem)
            continue
        errors, warnings = check_file(tag_file, paragraph_texts(comment_file), codes, stances, subcodes)
        findings += [f"{tag_file.name}: ERROR: {error}" for error in errors]
        findings += [f"{tag_file.name}: warning: {warning}" for warning in warnings]
        error_total += len(errors)
        warning_total += len(warnings)

    # The next batch: the comments still to tag, in id order, up to BATCH_WORDS words, so that one session never holds
    # more than it can work with. A comment longer than the budget is a batch of its own.
    batch, batch_words = [], 0
    for comment_id in still_to_tag:
        words = comment_words(HERE / "comments" / f"{comment_id}.md")
        if batch and batch_words + words > BATCH_WORDS:
            break
        batch.append(comment_id)
        batch_words += words

    # Unfinished work is counted in the summary, so "0 errors" can never hide an untagged comment.
    summary = f"{error_total} error(s), {warning_total} warning(s), {len(still_to_tag)} comment(s) still to tag"
    if dups:
        summary += f", {len(dups)} duplicate(s) not to tag"
    stamp = now()

    # 1. The terminal, which Claude reads first. It stays short: at scale, a full list would crowd out everything else.
    for finding in findings[:PRINT_AT_MOST]:
        print(finding)
    if len(findings) > PRINT_AT_MOST:
        print(f"... and {len(findings) - PRINT_AT_MOST} more in check.md")
    if len(still_to_tag) > PRINT_AT_MOST:
        print(f"still to tag: {len(still_to_tag)} comments, listed in check.md")
    elif still_to_tag:
        print("still to tag: " + ", ".join(still_to_tag))
    if dups:
        print("duplicates, not to tag: " + ", ".join(f"{dup} (kept: {kept})" for dup, kept in sorted(dups.items())))
    if batch:
        print(f"next batch ({batch_words} words): " + ", ".join(batch))
    if hand_over and not still_to_tag and not error_total:   # the tagging is done: say what comes next, where Claude will meet it
        print("every comment is tagged: `python mini.py build` writes the evidence and names the next part to summarize")
    print(f"check finished: {summary}")

    # 2. check.md: the full report, for reading in detail. Each run replaces the last.
    report = [f"# Check report, {stamp}", "", summary, "", "## Still to tag", ""]
    report += [f"- {comment_id}" for comment_id in still_to_tag] or ["(none)"]
    report += ["", f"## Next batch ({batch_words} words)", ""] + ([f"- {comment_id}" for comment_id in batch] or ["(none)"])
    report += ["", "## Duplicates, not to tag", ""] + ([f"- {dup} (kept: {kept})" for dup, kept in sorted(dups.items())] or ["(none)"])
    report += ["", "## Errors and warnings", ""] + ([f"- {finding}" for finding in findings] or ["(none)"])
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

    # 3. log.md: one line per run, in the tool's own words, next to Claude's own entries.
    with LOG.open("a", encoding="utf-8") as log:
        log.write(f"\n[mini.py check, {stamp}] {summary}" + (f"; next batch: {', '.join(batch)} ({batch_words} words)" if batch else "") + "\n")

    # 4. The exit code, for programs rather than people. Warnings don't count: they never block.
    return 0 if error_total == 0 and not still_to_tag else 1


def build():
    """Count, for every code and subcode, how many comments use it and how many tags it has, and write the evidence.

    comments: how many comments have at least one tag with this code ("how many commenters raised it?")
    tags:     how many tags have this code, in all ("how much was said about it?")
    The evidence is written in two layers, because at scale no session can read all of it at once:
        evidence.md    the overview: the totals, every code's and subcode's heading with its counts, and the
                       subcodes nobody raised
        evidence/      one part file per subcode that has tags, such as evidence/Q19.md: every tag's gist, its
                       citation and the paragraph it cites, and the word budget of that subcode's summary section
    It also plans the summary, as check plans the tagging: its "next part" line names the sections that one session
    reviews and summarizes.
    """
    # First, the check. Sorting notes that contain mistakes, or counting while some comments are still
    # untagged, would give wrong evidence and wrong numbers. So build only runs on clean, complete work.
    if check(hand_over=False) != 0:
        EVIDENCE.unlink(missing_ok=True)    # remove any old evidence: it would describe earlier tags
        for old in PARTS.glob("*.md"):
            old.unlink()
        print("build could not run: the check above is not clean. Fix what it reports, then build again.")
        return 2
    codebook = json.loads((HERE / "codebook.json").read_text(encoding="utf-8"))
    codes, stances, subcodes = codebook["codes"], codebook["stances"], codebook["subcodes"]
    # One set of counters serves both levels, because code and subcode names never collide (the codebook
    # check makes sure of that). Each tag is counted twice: under its code and under its subcode.
    names = list(codes) + list(subcodes)
    comments_with = {name: set() for name in names}     # name -> the comments that use it; a set counts each once
    stance_count = {name: Counter() for name in names}  # name -> how many of its tags take each stance
    tag_count = {name: 0 for name in names}             # name -> how many tags use it
    evidence = {name: [] for name in subcodes}          # subcode -> (comment, paragraph, gist, stance) per tag
    texts = {}                                          # comment -> {paragraph id: paragraph text}
    skip_total = 0
    tag_files = sorted((HERE / "tags").glob("*.json"))
    for tag_file in tag_files:
        data = json.loads(tag_file.read_text(encoding="utf-8"))
        texts[tag_file.stem] = paragraph_texts(HERE / "comments" / f"{tag_file.stem}.md")
        skip_total += len(data["skipped"])
        for tag in data["tags"]:
            for name in (tag["code"], tag["subcode"]):
                comments_with[name].add(tag_file.stem)
                tag_count[name] += 1
                stance_count[name][tag["stance"]] += 1
            evidence[tag["subcode"]].append((tag_file.stem, tag["paragraph"], tag["gist"], tag["stance"]))

    def counts(name):
        """'(3 comments, 6 tags: 4 support, 2 oppose)': the same form at both levels."""
        taken = ", ".join(f"{stance_count[name][stance]} {stance}" for stance in stances if stance_count[name][stance])
        return f"({plural(len(comments_with[name]), 'comment')}, {plural(tag_count[name], 'tag')}{': ' + taken if taken else ''})"

    columns = stance_columns(stances)             # one short heading per stance
    widths = [max(5, len(column)) for column in columns]

    def row(shown, name, label):
        label = label if len(label) <= 44 else label[:43] + "\u2026"
        return (f"{shown:13} {label:44} {len(comments_with[name]):>8} {tag_count[name]:>5}"
                + "".join(f" {stance_count[name][stance]:>{width}}" for stance, width in zip(stances, widths)))

    # Every code is listed, in codebook order, even with a count of 0: a code nobody raised is information too.
    # Under each code, its subcodes that have tags. Stances are counted per tag, not per comment.
    print(f"{'code':13} {'label':44} {'comments':>8} {'tags':>5}"
          + "".join(f" {column:>{width}}" for column, width in zip(columns, widths)))
    for code, entry in codes.items():
        print(row(code, code, entry["label"]))
        for name, sub in subcodes.items():
            if sub["code"] == code and tag_count[name]:
                print(row("  " + name, name, sub["label"]))
    totals = f"{len(tag_files)} tagged comments, {sum(tag_count[code] for code in codes)} tags, {skip_total} skips"
    dups = duplicates(sorted((HERE / "comments").glob("*.md")))
    if dups:
        totals += f", {len(dups)} duplicates not tagged"
    stamp = now()

    # The evidence, in two layers. evidence.md, the overview, lists every code in codebook order and, under it, the
    # heading of each subcode that has tags; a closing line names the subcodes nobody raised. Each of those subcodes
    # gets a part file in evidence/, with its tags sorted by comment and paragraph and the full paragraph shown,
    # because the citation points to the whole paragraph. A part file carries no build time, so the same tag files
    # always give exactly the same part. Everything is rebuilt every time: fix tags, never these files.
    PARTS.mkdir(exist_ok=True)
    lines = [f"# Evidence by code (built {stamp})", "", totals, ""]
    if dups:                                    # a plain line, not a heading: cites reads the headings of this file
        lines += ["Duplicates not tagged (kept instead): " + ", ".join(f"{dup} ({kept})" for dup, kept in sorted(dups.items())), ""]
    lines += ["The evidence itself is in the folder evidence/, one part file per subcode, named under the subcode's "
              "heading below. The summary has one section for each part file.", ""]
    sections = []                               # the subcodes that have tags, in codebook order: one summary section each
    for code, entry in codes.items():
        code_heading = f"## {code}: {entry['label']} {counts(code)}"
        lines += [code_heading, ""]
        if not tag_count[code]:
            lines += ["(no tags)", ""]
            continue
        mine = [name for name, sub in subcodes.items() if sub["code"] == code]
        for name in mine:
            if not evidence[name]:
                continue
            heading = f"### {name}: {subcodes[name]['label']} {counts(name)}"
            budget = section_budget(tag_count[name])
            part = [f"# Evidence for {name}", "", code_heading, "", heading, "",
                    f"Summary budget: at most {budget} words, not counting citations.", ""]
            for comment_id, value, gist, stance in sorted(evidence[name]):
                covered = expand(value)                 # a tag may cover a range: one citation per paragraph
                part.append(f"- ({stance}) {gist} " + " ".join(f"[{comment_id} \u00b6{paragraph}]" for paragraph in covered))
                for number, paragraph in enumerate(covered):
                    if number:
                        part.append("  >")              # a blank quote line keeps the paragraphs apart
                    part.append(f"  > {texts[comment_id][paragraph]}")
                part.append("")
            part_text = "\n".join(part)
            (PARTS / f"{name}.md").write_text(part_text, encoding="utf-8")
            lines += [heading, "", f"evidence/{name}.md: {len(part_text.split())} words of evidence; "
                                   f"its summary section may have at most {budget} words", ""]
            sections.append(name)
        silent = [name for name in mine if not evidence[name]]
        if silent:
            lines += ["Not raised: " + ", ".join(silent), ""]
    EVIDENCE.write_text("\n".join(lines), encoding="utf-8")
    for old in PARTS.glob("*.md"):              # a part left by an earlier build, for a subcode that has no tags now
        if old.stem not in sections:
            old.unlink()

    # The plan for the summary: what is still to write, and what one session takes on.
    still, part, part_words = summary_plan(sections)
    print(f"still to summarize: {len(still)} of {plural(len(sections), 'section')}")
    if part:
        print(f"next part ({part_words} words): " + ", ".join(part))
    elif sections:
        print("every section is written: `python mini.py cites` checks them and writes summary.md")
    wrote = f"wrote evidence.md and {plural(len(sections), 'part')} in evidence/"

    # One line in the log, in the tool's own words, as the checker does.
    with LOG.open("a", encoding="utf-8") as log:
        log.write(f"\n[mini.py build, {stamp}] {totals}; {wrote}"
                  + (f"; next part: {', '.join(part)} ({part_words} words)" if part else "") + "\n")
    print(f"total: {totals}; {wrote}")
    return 0


def cites():
    """Check the summary sections in summary/, one file per subcode, and put them together as summary.md.

    For every section file, three questions: is its first line its subcode's heading, copied exactly from
    evidence.md; is the text under it within the section's word budget, counted with WORD and not counting citations;
    and is that first line its only heading? For every citation, three more: does the comment exist, does the
    paragraph exist, and is the paragraph tagged with the section's subcode? Bracketed text that looks like a citation
    but isn't in the exact form is reported too: otherwise it would slip through unchecked. So is a file in summary/
    that is named after no section: it can't be checked, and it would never reach summary.md.

    Where the results go:
        the terminal   the problems (at most 15) and, last, a one-line summary
        cites.md       the full report, replaced on every run
        cites/         for each section, a file with every claim (the text a run of citations is attached to) next
                       to the paragraphs it cites, and a count of them, so that whether the paragraphs support the
                       claim and its wording can be judged side by side. Text with no citation is listed too, for
                       a reviewer to decide whether it makes a claim that needs one
        summary.md     the sections put together under evidence.md's headings. It is written only when every section
                       is there and there are no problems, and removed otherwise: it never shows unfinished work
        log.md         one line per run
        exit code      0 when every section is written and there are no problems, otherwise 1;
                       2 when the job could not run at all, because there is no evidence yet
    """
    index = EVIDENCE.read_text(encoding="utf-8").splitlines() if EVIDENCE.exists() else []
    wanted = {}                                         # section -> its heading line, in evidence.md's order
    for line in index:
        heading = SECTION_HEADING.match(line)
        if heading:
            wanted[heading[1]] = line
    if len(index) < 3 or not PARTS.is_dir():
        print("cites could not run: there is no evidence yet. Run `python mini.py build` first.")
        return 2
    problems, checked = [], 0
    words, budgets, bodies = {}, {}, {}                 # section -> its word count; its budget; its lines of text
    texts_of, tags_of = {}, {}                          # comment -> its paragraphs; its tags: each file is read once

    def paragraphs(comment_id):
        if comment_id not in texts_of:
            comment_file = HERE / "comments" / f"{comment_id}.md"
            texts_of[comment_id] = paragraph_texts(comment_file) if comment_file.exists() else None
        return texts_of[comment_id]

    def tags(comment_id):
        if comment_id not in tags_of:
            tag_file = HERE / "tags" / f"{comment_id}.json"
            tags_of[comment_id] = json.loads(tag_file.read_text(encoding="utf-8"))["tags"] if tag_file.exists() else []
        return tags_of[comment_id]

    # Every section file must belong to a section. These findings come first: they are about the folder.
    for section_file in sorted(SECTIONS.glob("*.md")):
        if section_file.stem not in wanted:
            problems.append(f"summary/{section_file.name}: there is no section {section_file.stem} in evidence.md, and every "
                            f"section file must be named after one. Rename it if it belongs to a section; otherwise move "
                            f"it out of summary/")
    CLAIMS.mkdir(exist_ok=True)
    written = [name for name in wanted if (SECTIONS / f"{name}.md").exists()]
    for old in CLAIMS.glob("*.md"):                     # rebuilt every run, like the evidence: none is left for a section that has gone
        if old.stem not in written:
            old.unlink()
    for name in written:
        where = f"summary/{name}.md"
        lines = (SECTIONS / f"{name}.md").read_text(encoding="utf-8-sig").splitlines()   # "-sig": some editors add a mark
        start = next((n for n, line in enumerate(lines) if line.strip()), len(lines))    # the first line that has text
        if start == len(lines) or lines[start].rstrip() != wanted[name]:
            problems.append(f"{where}: its first line isn't the section's heading copied exactly from evidence/{name}.md; "
                            f"it should be: {wanted[name]}")
        if start < len(lines) and lines[start].startswith("#"):
            start += 1                                  # a heading, right or wrong, is not part of the text
        counted = HEADING_COUNTS.findall(wanted[name])  # the label may hold brackets of its own: the counts come last
        section_comments, section_tags = (int(counted[-1][0]), int(counted[-1][1])) if counted else (0, 0)
        budgets[name] = section_budget(section_tags)
        claims, uncited, text = [], [], ""              # [(claim, citations)]; [text with no citation]; all the text
        for number, line in enumerate(lines[start:], start + 1):
            if line.startswith("#"):
                problems.append(f"{where}, line {number}: a section file has one heading, its first line; remove this one, "
                                f"because cites puts the sections together under evidence.md's headings")
                continue
            text += " " + line
            # Split the line at each run of citations: the text before a run is the claim that run supports.
            last_end = 0
            for run in CITATION_RUN.finditer(line):
                claims.append((line[last_end:run.start()].strip(" .,;:"), CITATION.findall(run.group())))
                last_end = run.end()
            rest = line[last_end:].strip(" .,;:")
            if WORD.search(rest):
                uncited.append(rest)
            for bracket in re.findall(r"\[[^\]]*\]", line):
                match = CITATION.fullmatch(bracket)
                if not match:
                    if "\u00b6" in bracket or "FDA-" in bracket:
                        problems.append(f"{where}, line {number}: {bracket} looks like a citation but isn't in the form "
                                        f"[FDA-2026-N-7874-0039 \u00b6p003]")
                    continue
                checked += 1
                comment_id, paragraph = match[1], match[2]
                if paragraphs(comment_id) is None:                                   # question 1
                    problems.append(f"{where}, line {number}: {bracket}: there is no comment {comment_id}")
                    continue
                if paragraph not in paragraphs(comment_id):                          # question 2
                    problems.append(f"{where}, line {number}: {bracket}: comment {comment_id} has no paragraph {paragraph}")
                    continue
                tagged_as = {t["subcode"] for t in tags(comment_id)                  # question 3
                             if paragraph in (expand(t["paragraph"]) or [])}
                if name not in tagged_as:
                    how = f"it's tagged {', '.join(sorted(tagged_as))}" if tagged_as else "it has no tag at all"
                    problems.append(f"{where}, line {number}: {bracket} is in the {name} section, "
                                    f"but that paragraph isn't tagged {name} ({how})")

        # The word budget. Citations don't count.
        words[name] = len(WORD.findall(CITATION.sub("", text)))
        if not words[name]:
            problems.append(f"{where}: the section has no text under its heading")
        elif words[name] > budgets[name]:
            problems.append(f"{where}: the section has {words[name]} words; the limit is {budgets[name]}, not counting citations")
        body = lines[start:]
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        bodies[name] = body

        # cites/<section>.md: each claim, how much it cites, then each paragraph it cites, quoted in full.
        report = [f"# Citations for {name}, claim by claim", "", wanted[name], "",
                  f"Each claim from summary/{name}.md, followed by the paragraphs it cites. For each one, judge: does the "
                  f"paragraph say this, and no more? The line under each claim counts what it cites: wording such as "
                  f"\"several\", \"many\" or \"most\" must fit that count.", ""]
        for n, (claim, cited) in enumerate(claims, 1):
            cited = list(dict.fromkeys(cited))          # each paragraph once, in the order cited
            report.append(f"{n}. {claim}")
            report.append(f"   (cites {plural(len(cited), 'paragraph')}, from {len({comment_id for comment_id, _ in cited})} "
                          f"of this section's {plural(section_comments, 'comment')})")
            for comment_id, paragraph in cited:
                quoted = (paragraphs(comment_id) or {}).get(paragraph)
                report.append(f"   - [{comment_id} \u00b6{paragraph}]")
                report.append(f"     > {quoted}" if quoted else "     > (no such paragraph: see the problems cites reported)")
            report.append("")
        for passage in uncited:
            report += [f"Text with no citation: {passage}", ""]
        (CLAIMS / f"{name}.md").write_text("\n".join(report), encoding="utf-8")

    # summary.md: the sections under evidence.md's own headings, so every heading and count in it comes from build.
    still = [name for name in wanted if name not in written]
    complete = bool(wanted) and not still and not problems
    if complete:
        out = ["# Summary of comments", "", index[2], ""]       # build writes the totals as the third line
        for line in index[3:]:
            heading = SECTION_HEADING.match(line)
            if heading:
                out += [line, ""] + bodies[heading[1]] + [""]
            elif line.startswith("## ") or line.startswith("Not raised: "):
                out += [line, ""]
            elif line == "(no tags)":
                out += ["No commenter raised this.", ""]
        SUMMARY.write_text("\n".join(out), encoding="utf-8")
    else:
        SUMMARY.unlink(missing_ok=True)     # an old summary.md would describe sections that have changed or gone

    summary = (f"{len(written)} of {plural(len(wanted), 'section')} written, {checked} citation(s) checked, "
               f"{len(problems)} problem(s)" + ("; wrote summary.md" if complete else ""))
    stamp = now()

    # 1. The terminal. It stays short, as the checker's does.
    for problem in problems[:PRINT_AT_MOST]:
        print(problem)
    if len(problems) > PRINT_AT_MOST:
        print(f"... and {len(problems) - PRINT_AT_MOST} more in cites.md")
    if still:
        print(f"still to summarize: {len(still)} of {plural(len(wanted), 'section')}, listed in cites.md")
    print(f"cites finished: {summary}")

    # 2. cites.md: the full report. Each run replaces the last.
    report = [f"# Citation check, {stamp}", "", summary, "", "## Still to summarize", ""]
    report += [f"- {name}" for name in still] or ["(none)"]
    report += ["", "## Problems", ""] + ([f"- {problem}" for problem in problems] or ["(none)"])
    report += ["", "## Words per section", ""]
    report += [f"- {name}: {words[name]} of at most {budgets[name]}" for name in written] or ["(none)"]
    CITES.write_text("\n".join(report) + "\n", encoding="utf-8")

    # 3. log.md: one line per run, as the other two jobs do.
    with LOG.open("a", encoding="utf-8") as log:
        log.write(f"\n[mini.py cites, {stamp}] {summary}\n")

    # 4. The exit code: 0 only when the summary is complete and clean.
    return 0 if complete else 1


# The word after "python mini.py" chooses the job. Anything else is a usage mistake: exit code 2, could not run.
COMMANDS = {"check": check, "build": build, "cites": cites}

if __name__ == "__main__":
    # On Windows, Python writes to a pipe in the system's legacy code page, but Claude Code reads its output as
    # UTF-8, so characters such as the ellipsis and the paragraph sign arrived garbled (run 19). UTF-8 everywhere.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print("usage: python mini.py check, python mini.py build or python mini.py cites")
        sys.exit(2)
    sys.exit(COMMANDS[sys.argv[1]]())
