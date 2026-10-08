window.USE_CASE_MARKDOWN = {
    "ai-coding-teams.md":  "# AI Coding Teams\n\nUse case:\nAI coding handoffs\n\nWho it is for:\nTeams using Claude Code, Codex, Cursor, CI jobs, scripts, and human engineers on the same repo.\n\nWhat breaks today:\nThe work gets scattered. One agent changes files. Another claims tests passed. CI says something else. A human comes back later and has to reconstruct the truth from chats, logs, diffs, and guesses.\n\nWhy Yare fits:\nYare turns those scattered runs into one verified working-memory handoff.\n\nWhat Yare stores:\n- what changed\n- what is true\n- what is unverified\n- contradictions\n- human approval items\n- open loops\n- next clean action\n- receipts\n\nWhat Roach makes durable:\nThe current-state memory lives in CockroachDB, so it can be read later by another agent, another tool, or another teammate.\n\nWhat the user sees:\nA plain handoff:\n\"Here is what happened. Here is what is verified. Here is what still needs review. Here is what to do next.\"\n\nWhen they use it:\n- before a new agent starts work\n- before a PR review\n- after a long AI coding session\n- before release\n- after CI or tests change state\n- when switching from Claude to Codex to Cursor\n\nWhy it matters:\nThe team stops treating AI output like disposable chat history. The repo gets a memory trail that survives tool switching, model switching, and human context loss.\n\nDemo proof:\nClaude Code, Codex, and Cursor used MCP to read Yare\u0027s CockroachDB memory and report the same repo handoff.\n\nOne-line pitch:\nYare gives AI coding teams a durable handoff so every agent knows what changed, what is true, and what needs human review.\n",
    "engineering-audit.md":  "# Engineering Audit\n\nUse case:\nAgent-written work audit\n\nWho it is for:\nEngineering teams reviewing code, tests, docs, and repo changes produced by AI agents.\n\nWhat breaks today:\nAgents say work is done, but reviewers still have to dig through chats, diffs, logs, CI output, and partial receipts to know what actually happened.\n\nWhy Yare fits:\nYare gives reviewers one verified handoff instead of scattered agent claims.\n\nWhat Yare stores:\n- files changed\n- claims made by agents\n- verified facts\n- unverified claims\n- contradictions\n- human approval items\n- receipts\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB keeps the audit record available across runs, tools, agents, and review sessions.\n\nWhat the user sees:\nA plain audit view:\n\"What changed, what was proven, what is still risky, and what needs review.\"\n\nWhen they use it:\n- before PR review\n- before merge\n- after CI changes\n- after a failed agent run\n- during release review\n- when investigating bad AI-written work\n\nWhy it matters:\nReviewers stop trusting agent summaries blindly. They get a durable proof trail.\n\nDemo proof:\nClaude Code, Codex, and Cursor queried Yare\u0027s CockroachDB memory through MCP and reported the same state.\n\nOne-line pitch:\nYare helps engineering teams audit agent-written work before it becomes production risk.\n",
};

Object.assign(window.USE_CASE_MARKDOWN, {
  "search-prior-memory.md": "# Search Prior Memory\n\nUse case:\nFind a relevant section from an earlier compiled handoff.\n\nWho it is for:\nAgents and engineers returning to a task with stored work history.\n\nWhat breaks today:\nThe needed unresolved claim or approval item is buried in an older state record.\n\nWhy Yare fits:\nThe `memory search` command queries sections stored in CockroachDB's vector index.\n\nWhat Yare stores:\n- section name and source text\n- current-state hash\n- embedding vector\n- run ID\n\nWhat Roach makes durable:\nCockroachDB stores and indexes the memory sections for later queries.\n\nWhat the user sees:\nMatching section names, distances, state hashes, and source text.\n\nWhen they use it:\nWhen searching for a prior decision, unresolved issue, or next action.\n\nWhy it matters:\nThe next worker can locate recorded context without rereading every handoff.\n\nDemo proof:\nA real CockroachDB vector index and query returned stored memory sections. See `docs/VECTOR_SMOKE_RESULT.md`.\n\nOne-line pitch:\nSearch prior handoff sections through CockroachDB's vector index.\n",
  "archive-proof-artifacts.md": "# Archive Proof Artifacts\n\nUse case:\nKeep compiled state exports and receipts outside the working directory.\n\nWho it is for:\nTeams that need to retain the files behind a Yare handoff.\n\nWhat breaks today:\nLocal proof files can disappear when a workspace or sandbox is replaced.\n\nWhy Yare fits:\nWhen an S3 bucket is configured, `lead compile` uploads the current-state JSON, Markdown, and receipt.\n\nWhat Yare stores:\n- current-state JSON\n- current-state Markdown\n- receipt JSONL\n- deterministic object keys\n\nWhat Roach makes durable:\nCockroachDB remains the primary store for working memory; S3 is an archive for proof files.\n\nWhat the user sees:\nS3 object URIs printed after a successful compile.\n\nWhen they use it:\nAfter compiling a handoff that needs an external proof archive.\n\nWhy it matters:\nThe files supporting a handoff are not confined to one local workspace.\n\nDemo proof:\nThe Amazon S3 smoke test uploaded and confirmed all three objects. See `docs/S3_SMOKE_RESULT.md`.\n\nOne-line pitch:\nArchive current-state exports and receipts to Amazon S3 after compile.\n",
  "local-handoff-export.md": "# Local Handoff Export\n\nUse case:\nCompile and inspect a handoff without configuring cloud services.\n\nWho it is for:\nSomeone trying Yare locally or keeping an export beside the project.\n\nWhat breaks today:\nAn agent summary may be scattered across source artifacts with no single local current-state file.\n\nWhy Yare fits:\n`lead compile` writes local current-state JSON, Markdown, and a receipt even when the database and S3 environment variables are unset.\n\nWhat Yare stores:\n- compiled current-state JSON\n- readable current-state Markdown\n- receipt JSONL\n- deterministic current-state hash\n\nWhat Roach makes durable:\nNothing in this mode. CockroachDB is used only when `YARE_DATABASE_URL` is configured.\n\nWhat the user sees:\nLocal `.sticky` output paths and hashes after the compile.\n\nWhen they use it:\nDuring local setup, offline review, or export from a database-backed run.\n\nWhy it matters:\nThe core compiler remains usable without cloud credentials.\n\nDemo proof:\nRun `scripts/demo-lead-compile.ps1` with `YARE_DATABASE_URL` and `YARE_S3_BUCKET` unset; the script prints the local output paths and deterministic hash.\n\nOne-line pitch:\nCompile a local handoff and receipt without CockroachDB or S3 credentials.\n",
  "sandbox-access-evidence.md": "# Sandbox Access Evidence\n\nUse case:\nReview an agent's access decision alongside its code and test evidence.\n\nWho it is for:\nEngineers evaluating a permission-scoped coding handoff.\n\nWhat breaks today:\nAn agent may report an access failure without preserving the policy result with its work receipt.\n\nWhy Yare fits:\nYare can record OpenShell's access result in a compiled handoff and receipt.\n\nWhat Yare stores:\n- stated agent action\n- allowed or denied access result\n- code and test evidence\n- receipt hash\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB retains the compiled handoff and access-bearing receipt.\n\nWhat the user sees:\nThe recorded access result beside the partial and completed coding runs.\n\nWhen they use it:\nAfter separate agents work under different OpenShell policies.\n\nWhy it matters:\nThe access decision remains reviewable with the work it affected. OpenShell enforces the boundary; Yare records it.\n\nDemo proof:\nIn the isolated A/B coding run, A read a sandboxed source snapshot, B was denied access to that same snapshot, and B still completed its separate working copy. See `docs/NEMOTRON_BOUNDARY_RESULT.md`.\n\nOne-line pitch:\nReview recorded OpenShell access decisions with the agent handoff and receipts.\n",
  "contradiction-approval-review.md": "# Contradiction and Approval Review\n\nUse case:\nReview conflicting agent claims and work that needs a human decision.\n\nWho it is for:\nEngineers and reviewers deciding whether an agent-produced change can proceed.\n\nWhat breaks today:\nOne run reports a fact that another disputes, while approval requests get buried in separate logs.\n\nWhy Yare fits:\nThe compiled current state lists contradictions and human approval items separately from verified facts.\n\nWhat Yare stores:\n- verified and unverified claims\n- contradictions\n- human approval items\n- receipts\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB keeps that review state available after the original run ends.\n\nWhat the user sees:\nA handoff that says what conflicts, what needs approval, and what to check next.\n\nWhen they use it:\nBefore another agent continues, a PR is reviewed, or a release decision is made.\n\nWhy it matters:\nA contradiction is not silently promoted to a fact, and an approval item is not mistaken for completed work.\n\nDemo proof:\nThe recorded multi-agent handoff contains a contradiction and human approval items; the current-state and receipt records were read through CockroachDB MCP. See `docs/REAL_USE_CASE_RESULT.md` and `docs/MCP_SMOKE_RESULT.md`.\n\nOne-line pitch:\nSee conflicting claims and pending human approvals together before deciding what can proceed.\n",
  "restart-after-partial-run.md": "# Restart After a Partial Run\n\nUse case:\nContinue a coding task after the first agent stops with work unfinished.\n\nWho it is for:\nTeams handing an incomplete agent run to a fresh agent or engineer.\n\nWhat breaks today:\nThe next worker may see only a confident summary, not the partial code and actual failing test output.\n\nWhy Yare fits:\nYare stores the partial artifact, compiled state, and receipt so a fresh worker can assess the real result.\n\nWhat Yare stores:\n- task and code artifact\n- actual test output\n- unverified claims\n- unresolved work\n- next clean action\n- receipt hashes\n\nWhat Roach makes durable:\nCockroachDB preserves the handoff between separate agent sessions.\n\nWhat the user sees:\nThe first run's passing targeted tests and failing full suite, followed by the second run's final result.\n\nWhen they use it:\nWhen an agent stops, a sandbox is replaced, or another agent takes over.\n\nWhy it matters:\nThe next worker can start from stored evidence instead of guessing what the first worker finished.\n\nDemo proof:\nIn one isolated coding task, A passed four targeted tests but left two full-suite failures. Fresh B read A's CockroachDB handoff, fixed the remaining issue, and passed all six tests. See `docs/NEMOTRON_RESUMED_HANDOFF_RESULT.md`.\n\nOne-line pitch:\nResume a coding task after the first agent stops, using stored code and actual test output.\n",
  "cross-tool-memory-read.md": "# Cross-Tool Memory Read\n\nUse case:\nLet different agent clients inspect the same stored work state.\n\nWho it is for:\nTeams switching among Claude Code, Codex, and Cursor.\n\nWhat breaks today:\nEach client has its own conversation context, so the next agent may reconstruct the work differently.\n\nWhy Yare fits:\nYare compiles one current state in CockroachDB that clients can query through CockroachDB Managed MCP.\n\nWhat Yare stores:\n- task and current-state hash\n- verified and unverified claims\n- contradictions\n- approval items\n- receipts\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB is the shared source for the compiled state and receipts.\n\nWhat the user sees:\nThe same recorded handoff can be reported from more than one agent client.\n\nWhen they use it:\nWhen changing tools or asking another agent to review prior work.\n\nWhy it matters:\nThe handoff is not trapped in the first client's chat history.\n\nDemo proof:\nClaude Code, Codex, and Cursor each queried Yare's CockroachDB memory through Managed MCP and reported the recorded handoff. See `docs/MCP_SMOKE_RESULT.md`, `docs/CODEX_MCP_SMOKE_RESULT.md`, and `docs/CURSOR_MCP_SMOKE_RESULT.md`.\n\nOne-line pitch:\nClaude Code, Codex, and Cursor can read the same CockroachDB handoff through Managed MCP.\n",
  "state-change-review.md": "# State Change Review\n\nUse case:\nSee how the compiled work state changed between runs.\n\nWho it is for:\nEngineers reviewing whether new work resolved or introduced open issues.\n\nWhat breaks today:\nA latest-state summary does not explain which facts, claims, contradictions, or next actions changed.\n\nWhy Yare fits:\nThe memory timeline lists stored states, and the latest-state diff compares the two newest snapshots.\n\nWhat Yare stores:\n- current-state hashes and timestamps\n- task and run ID\n- receipt hashes\n- facts and unresolved claims\n- contradictions and approval items\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB retains the snapshots that the timeline and diff read.\n\nWhat the user sees:\nA previous-to-latest comparison with new truths, unresolved claims, cleared contradictions, and any changed next action.\n\nWhen they use it:\nAfter a new compile, before review, or when returning to a task after several runs.\n\nWhy it matters:\nReviewers can see what changed in the memory, not only the latest summary.\n\nDemo proof:\nThe live CockroachDB smoke ran `memory timeline` and `memory diff --latest` against stored current states. See `docs/MEMORY_TIMELINE_RESULT.md`.\n\nOne-line pitch:\nCompare stored states to see new facts, unresolved claims, cleared contradictions, and changed next actions.\n"
});

function copyUseCaseText(text, button) {
  const done = () => {
    const original = button.getAttribute("aria-label");
    button.setAttribute("aria-label", "Copied");
    setTimeout(() => button.setAttribute("aria-label", original), 1200);
  };

  const fallback = () => {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    done();
  };

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done).catch(fallback);
    return;
  }

  fallback();
}

document.querySelectorAll("[data-copy-card]").forEach((button) => {
  button.addEventListener("click", () => {
    const card = button.closest(".use-case-card");
    const downloadLink = card.querySelector("a[download]");
    const fileName = downloadLink.dataset.file || downloadLink.getAttribute("href").split("/").pop();
    copyUseCaseText(window.USE_CASE_MARKDOWN[fileName], button);
  });
});

document.querySelectorAll(".use-case-actions a[download]").forEach((link) => {
  link.addEventListener("click", (event) => {
    const fileName = link.dataset.file || link.getAttribute("href").split("/").pop();
    const markdown = window.USE_CASE_MARKDOWN[fileName];
    if (!markdown) return;

    event.preventDefault();
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const download = document.createElement("a");
    download.href = url;
    download.download = fileName;
    document.body.appendChild(download);
    download.click();
    download.remove();
    URL.revokeObjectURL(url);
  });
});

if (window.gsap && window.ScrollTrigger && window.MotionPathPlugin) {
gsap.registerPlugin(ScrollTrigger, MotionPathPlugin);

let mpCtx;

function createMotionTimeline() {
  mpCtx && mpCtx.revert();

  mpCtx = gsap.context(() => {
    const box = document.querySelector(".box");
    const pathSection = document.querySelector(".path-section");
    const initMarker = document.querySelector(".mstop.initial .marker");
    const stops = gsap.utils.toArray(".mstop:not(.initial)");

    if (!initMarker || stops.length === 0) return;

    const psRect = pathSection.getBoundingClientRect();
    const imRect = initMarker.getBoundingClientRect();

    gsap.set(box, {
      top: imRect.top - psRect.top,
      left: imRect.left - psRect.left,
      xPercent: -50,
      yPercent: -50
    });

    const boxRect = box.getBoundingClientRect();

    const points = stops.map((stop) => {
      const marker = stop.querySelector(".marker");
      const r = marker.getBoundingClientRect();
      return {
        x: r.left - boxRect.left,
        y: r.top - boxRect.top
      };
    });

    drawTrace(boxRect, stops);

    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: ".mstop.initial",
        start: "clamp(top center)",
        endTrigger: ".path-end",
        end: "clamp(top center)",
        scrub: 1
      }
    });

    tl.to(box, {
      duration: 1,
      ease: "none",
      motionPath: {
        path: points,
        curviness: 1.5
      }
    });
  });
}

function drawTrace(boxRect, stops) {
  const svg = document.getElementById("path-trace");
  const psRect = document
    .querySelector(".path-section")
    .getBoundingClientRect();

  const pts = [{ x: boxRect.left - psRect.left, y: boxRect.top - psRect.top }];
  stops.forEach((stop) => {
    const r = stop.querySelector(".marker").getBoundingClientRect();
    pts.push({ x: r.left - psRect.left, y: r.top - psRect.top });
  });

  let d = `M ${pts[0].x},${pts[0].y}`;
  for (let i = 1; i < pts.length; i++) {
    const prev = pts[i - 1];
    const curr = pts[i];
    const cx1 = prev.x + (curr.x - prev.x) * 0.5;
    const cy1 = prev.y;
    const cx2 = prev.x + (curr.x - prev.x) * 0.5;
    const cy2 = curr.y;
    d += ` C ${cx1},${cy1} ${cx2},${cy2} ${curr.x},${curr.y}`;
  }

  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", d);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "rgba(0,0,0,0.15)");
  path.setAttribute("stroke-width", "2");
  path.setAttribute("stroke-dasharray", "8 6");
  svg.innerHTML = "";
  svg.appendChild(path);

  const len = path.getTotalLength();
  gsap.set(path, { strokeDasharray: len, strokeDashoffset: len });
  gsap.to(path, {
    strokeDashoffset: 0,
    ease: "none",
    scrollTrigger: {
      trigger: ".mstop.initial",
      start: "clamp(top center)",
      endTrigger: ".path-end",
      end: "clamp(top center)",
      scrub: 1
    }
  });
}

createMotionTimeline();
window.addEventListener("resize", createMotionTimeline);

gsap.utils.toArray(".text").forEach((el) => {
  gsap.to(el, {
    backgroundSize: "100% 100%",
    ease: "none",
    scrollTrigger: {
      trigger: el,
      start: "top 82%",
      end: "top 18%",
      scrub: true
    }
  });
});

ScrollTrigger.create({
  start: 0,
  end: "max",
  onUpdate: (self) => {
    document.body.style.filter = `hue-rotate(${Math.round(
      self.progress * 22
    )}deg)`;
  }
});

const isTouchDevice = () => window.matchMedia("(hover: none)").matches;

if (isTouchDevice()) {
  document.querySelectorAll(".text").forEach((el) => {
    el.addEventListener("click", () => {
      el.classList.toggle("tapped");
    });
  });
}
}
