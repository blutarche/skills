# Authoring rules

The page explains a finished change to someone who has not seen it. It is not a review: no
verdicts, no severities, no scores. If you found a real defect while writing the walkthrough,
say it plainly in the chapter overview as a thing to check, or hand it to a review skill.

## Page order

Header with the revision banner, the digest, Overview, Where to focus, Intuition, Background,
then the walkthrough: Read first (flagged files, then `attention` and `medium` chapters), Skim
(`safe` chapters), Matched by the build, and On the agent's word. Then Verify and Notes. One page,
readable top to bottom, and readable with JavaScript off.

## Title and overview

- The title names the change, not a category: "Send the chat reply in one call", not "Chat API
  update".
- `overview`: first sentence says what changed and why. 100 to 250 words. State the alternative
  you rejected and why, in one sentence, without the words "deliberately" or "left out". Counts
  belong in the digest the build renders, never in prose. An overview claims something the reader
  can check.
- `focus`: three to five items, each naming a chapter with `<a href="#ch-id">` and saying what to
  check there. This is where a reader who has ten minutes should spend them. Use "Check that" at
  most twice per page; otherwise name the property directly.
- `intuition`: the shape of the mechanism in three sentences, before any code.
- `background`: only what the reader needs about the surrounding code to follow the chapters. Cut
  it when the change stands alone.

## Chapters

- Cut by what changed and why, never by folder. 1 to 6 chapters; more than 10 is rejected.
- Order: the contract first, then the heart, then the consequences, then the glue.
- One file may appear in several chapters when it holds several concepts. The heart of a change
  usually does.
- A chapter title states its claim. A chapter that exists only for completeness is not a chapter;
  its files belong in a glue chapter, a group, or `everythingElse`.
- The overview is two to six sentences: what changed here, why, and what to check. Say what you
  would say out loud before the reader looks at the code.
- `risk`: `attention` when the chapter carries behaviour the reader must reason about, `medium`
  for contract surface and tests, `safe` for glue. The build expands hunks for attention and
  medium, and collapses them for safe. Attention and medium chapters go under Read first, safe
  ones under Skim, and chapter numbers follow that order.

## Files and hunks

- A file `why` must not be a noun phrase that restates the filename or its role ("The page
  shell.", "The diff loader."). Say what the reader learns from this file that the chapter
  overview did not.
- The hunk rule: show a hunk only when the prose makes a claim about it. Everything else in the
  chapter is a file card with its path, status, counts, and the names it adds.
- Anchor to the smallest range that holds the claim.
- A hunk `why` says why the lines matter, not what they do. The lines already say what they do.
  If the `why` could be inferred by reading the hunk, delete it and say why the lines matter
  instead.
- Never type a line number from memory. Write the range, run the build, and let it reject the
  range that no longer holds a changed line.

## Groups

A big diff often holds many files with one mechanical change. Put them in a group, not a
chapter, so the reader's time goes to the files that need it.

- Use a substitution group when one `from` and `to` explains every change in those files: a
  rename, an import path, a version string. The build replays the rule and proves it. A file the
  rule does not explain goes to the top of the reading list, so do not widen a glob to sweep up
  files you have not checked.
- Use a chapter when the change needs a claim the reader must check, even when it looks
  mechanical. A rule shows the change is mechanical, not that it is right. If the rename itself
  is the risk, say so in a chapter.
- Use `generated` or `lockfile` for files a tool wrote, and say which tool and command in `why`.
  When a lockfile group rests on your word, put the manifest that drives it (for example
  `package.json`) in a chapter, so the reader sees what you asked for.
- Never put a behaviour change in a `bulk` group. A bulk group is for files the reader may skip,
  such as fixtures or snapshots. The build samples a few of them; that is a spot check, not a
  review.
- Let the build find moves, line-ending changes, deletions, and binary files. Do not list them.

## Verify

- `verify.ran` lists the commands that actually ran this session, with their real exit codes and
  the tree they ran on. A command you did not run is written out as not run, with `exit: null`.
  Do not describe a green suite you did not see.
- `verify.manual` gives the reader steps they can run themselves, each with the result it should
  produce.

## Coverage

Coverage is derived, not claimed. The build refuses a changed file with no home and a placed file
that is not in the diff. `everythingElse` is for a few small leftovers, each with its own `why`.
It has a cap; past it the build fails and asks for groups or chapters.

## Voice

Sentences of at most 25 words. Plain words. At most two code spans per sentence. No verdicts, no
emoji, no em dashes, plain hyphens only. Write for a reader who knows the language but not this
change.

## Anti-patterns

- Counting files or lines in prose. The digest does that, from the diff.
- A substitution group or a `bulk` group that hides a behaviour change.
- A chapter per commit or per folder.
- Showing every hunk for completeness.
- Line numbers typed by hand instead of validated by the build.
- Grading the change ("clean", "solid", "looks good"). The reader grades it.
- A page that only works with JavaScript.
