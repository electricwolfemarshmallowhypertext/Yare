# Compliance Teams

Use case:
AI work proof trail

Who it is for:
Teams that need records of AI-assisted work, review steps, approvals, and unresolved issues.

What breaks today:
AI work happens in tools that do not preserve a clean review trail. Later, nobody can easily answer what was generated, checked, approved, or left unresolved.

Why Yare fits:
Yare turns AI work into a structured proof trail with receipts.

What Yare stores:
- task
- changed files
- verified facts
- unverified claims
- contradictions
- human approval items
- receipts
- current-state hash

What Roach makes durable:
CockroachDB keeps the proof trail queryable and persistent instead of trapped in chats or local files.

What the user sees:
A plain compliance record:
"What happened, what was reviewed, what needs approval, and what evidence exists."

When they use it:
- before approval
- before release
- during internal review
- after an incident
- when proving human oversight
- when checking AI-generated changes

Why it matters:
Compliance does not need a giant governance platform to start. It needs a reliable record of AI work and review state.

Demo proof:
Yare persisted current-state memory to CockroachDB and exposed it through MCP clients.

One-line pitch:
Yare gives compliance teams a durable proof trail for AI-assisted work.
