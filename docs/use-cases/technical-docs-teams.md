# Technical Docs Teams

Use case:
AI-assisted docs review

Who it is for:
Technical writers and docs teams using AI to update README files, API docs, changelogs, examples, tutorials, and release notes.

What breaks today:
AI edits docs quickly, but nobody can easily tell which claims are verified against the code, which examples changed, and which sections still need review.

Why Yare fits:
Yare turns scattered docs edits into one reviewable current-state handoff.

What Yare stores:
- docs files changed
- code files referenced
- verified claims
- unverified claims
- contradictions
- review items
- open loops
- receipts
- next clean action

What Roach makes durable:
CockroachDB keeps the docs review state available after the AI session ends, even when another writer or agent takes over.

What the user sees:
A docs handoff:
"What changed in the docs, what is backed by the repo, what still needs checking, and what to edit next."

When they use it:
- before publishing docs
- after AI rewrites a README
- after API examples change
- before a release note goes out
- when handing docs from writer to engineer
- when checking if docs match code

Why it matters:
Bad AI docs create support debt. Yare helps docs teams separate verified updates from confident guesses.

Demo proof:
Yare already tracks changed files, verified facts, unverified claims, contradictions, receipts, and next action.

One-line pitch:
Yare helps docs teams keep AI-written documentation tied to proof instead of guesses.
