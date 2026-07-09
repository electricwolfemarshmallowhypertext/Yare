# Long-Form Writers Using AI

Use case:
AI-assisted manuscript handoff

Who it is for:
Writers using AI across drafts, outlines, chapters, edits, research notes, continuity checks, and revision passes.

What breaks today:
AI changes a draft, suggests edits, rewrites sections, creates notes, and introduces contradictions. The writer loses track of what changed and what still needs review.

Why Yare fits:
Yare turns each AI writing session into a durable handoff instead of a buried chat transcript.

What Yare stores:
- draft files changed
- accepted edits
- unverified notes
- contradictions
- continuity issues
- human review items
- open loops
- receipts
- next clean action

What Roach makes durable:
CockroachDB keeps the writing state available across sessions, tools, drafts, and revision passes.

What the user sees:
A writing handoff:
"What changed, what is accepted, what conflicts, what still needs review, and what to revise next."

When they use it:
- after an AI revision pass
- before continuing a draft
- before sending to an editor
- after continuity checks
- when switching writing tools
- when returning to a project later

Why it matters:
AI can help write faster, but it can also muddy continuity and intent. Yare keeps the revision state clean.

Demo proof:
Yare already saves changed files, verified state, contradictions, approval items, open loops, and next action as durable working memory.

One-line pitch:
Yare helps AI-assisted writers keep drafts, edits, and unresolved issues from turning into chaos.
