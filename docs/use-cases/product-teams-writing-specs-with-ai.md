# Product Teams Writing Specs With AI

Use case:
AI-assisted spec handoff

Who it is for:
Product teams using AI to draft specs, tickets, acceptance criteria, release notes, and implementation plans.

What breaks today:
Specs change fast. AI generates requirements, engineers change reality, and nobody knows which decisions are current, approved, or contradicted by implementation.

Why Yare fits:
Yare turns AI-assisted product work into a current-state handoff that agents and humans can read before building.

What Yare stores:
- spec files changed
- decisions made
- verified facts
- unverified assumptions
- contradictions
- human approval items
- open loops
- receipts
- next clean action

What Roach makes durable:
CockroachDB keeps the product state durable across planning sessions, agent runs, code changes, and release prep.

What the user sees:
A product handoff:
"What changed, what is decided, what is still an assumption, what conflicts, and what needs approval."

When they use it:
- before engineering starts
- after AI drafts a spec
- after requirements change
- before sprint planning
- before release
- when a new agent continues product work

Why it matters:
AI can write specs fast, but fast specs can become stale lies. Yare keeps the current truth visible.

Demo proof:
Yare compiles scattered run artifacts into one current-state packet and stores it in CockroachDB.

One-line pitch:
Yare helps product teams keep AI-written specs aligned with what is actually true.
