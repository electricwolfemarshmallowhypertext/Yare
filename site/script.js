window.USE_CASE_MARKDOWN = {
    "ai-coding-teams.md":  "# AI Coding Teams\n\nUse case:\nAI coding handoffs\n\nWho it is for:\nTeams using Claude Code, Codex, Cursor, CI jobs, scripts, and human engineers on the same repo.\n\nWhat breaks today:\nThe work gets scattered. One agent changes files. Another claims tests passed. CI says something else. A human comes back later and has to reconstruct the truth from chats, logs, diffs, and guesses.\n\nWhy Yare fits:\nYare turns those scattered runs into one verified working-memory handoff.\n\nWhat Yare stores:\n- what changed\n- what is true\n- what is unverified\n- contradictions\n- human approval items\n- open loops\n- next clean action\n- receipts\n\nWhat Roach makes durable:\nThe current-state memory lives in CockroachDB, so it can be read later by another agent, another tool, or another teammate.\n\nWhat the user sees:\nA plain handoff:\n\"Here is what happened. Here is what is verified. Here is what still needs review. Here is what to do next.\"\n\nWhen they use it:\n- before a new agent starts work\n- before a PR review\n- after a long AI coding session\n- before release\n- after CI or tests change state\n- when switching from Claude to Codex to Cursor\n\nWhy it matters:\nThe team stops treating AI output like disposable chat history. The repo gets a memory trail that survives tool switching, model switching, and human context loss.\n\nDemo proof:\nClaude Code, Codex, and Cursor used MCP to read Yare\u0027s CockroachDB memory and report the same repo handoff.\n\nOne-line pitch:\nYare gives AI coding teams a durable handoff so every agent knows what changed, what is true, and what needs human review.\n",
    "engineering-audit.md":  "# Engineering Audit\n\nUse case:\nAgent-written work audit\n\nWho it is for:\nEngineering teams reviewing code, tests, docs, and repo changes produced by AI agents.\n\nWhat breaks today:\nAgents say work is done, but reviewers still have to dig through chats, diffs, logs, CI output, and partial receipts to know what actually happened.\n\nWhy Yare fits:\nYare gives reviewers one verified handoff instead of scattered agent claims.\n\nWhat Yare stores:\n- files changed\n- claims made by agents\n- verified facts\n- unverified claims\n- contradictions\n- human approval items\n- receipts\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB keeps the audit record available across runs, tools, agents, and review sessions.\n\nWhat the user sees:\nA plain audit view:\n\"What changed, what was proven, what is still risky, and what needs review.\"\n\nWhen they use it:\n- before PR review\n- before merge\n- after CI changes\n- after a failed agent run\n- during release review\n- when investigating bad AI-written work\n\nWhy it matters:\nReviewers stop trusting agent summaries blindly. They get a durable proof trail.\n\nDemo proof:\nClaude Code, Codex, and Cursor queried Yare\u0027s CockroachDB memory through MCP and reported the same state.\n\nOne-line pitch:\nYare helps engineering teams audit agent-written work before it becomes production risk.\n",
    "compliance-teams.md":  "# Compliance Teams\n\nUse case:\nAI work proof trail\n\nWho it is for:\nTeams that need records of AI-assisted work, review steps, approvals, and unresolved issues.\n\nWhat breaks today:\nAI work happens in tools that do not preserve a clean review trail. Later, nobody can easily answer what was generated, checked, approved, or left unresolved.\n\nWhy Yare fits:\nYare turns AI work into a structured proof trail with receipts.\n\nWhat Yare stores:\n- task\n- changed files\n- verified facts\n- unverified claims\n- contradictions\n- human approval items\n- receipts\n- current-state hash\n\nWhat Roach makes durable:\nCockroachDB keeps the proof trail queryable and persistent instead of trapped in chats or local files.\n\nWhat the user sees:\nA plain compliance record:\n\"What happened, what was reviewed, what needs approval, and what evidence exists.\"\n\nWhen they use it:\n- before approval\n- before release\n- during internal review\n- after an incident\n- when proving human oversight\n- when checking AI-generated changes\n\nWhy it matters:\nCompliance does not need a giant governance platform to start. It needs a reliable record of AI work and review state.\n\nDemo proof:\nYare persisted current-state memory to CockroachDB and exposed it through MCP clients.\n\nOne-line pitch:\nYare gives compliance teams a durable proof trail for AI-assisted work.\n",
    "vibe-coders.md":  "# Vibe Coders\n\nUse case:\nSafe next step for AI-built projects\n\nWho it is for:\nNontraditional builders using AI tools to ship apps, scripts, websites, and prototypes.\n\nWhat breaks today:\nThey ask AI to build fast, then lose track of what changed, what broke, what is real, and what to do next.\n\nWhy Yare fits:\nYare turns messy AI build sessions into a plain handoff a person can understand.\n\nWhat Yare stores:\n- what changed\n- what is true\n- what is unverified\n- contradictions\n- open loops\n- human approval items\n- next clean action\n- receipts\n\nWhat Roach makes durable:\nCockroachDB keeps the project memory safe across sessions, tools, and restarts.\n\nWhat the user sees:\nA simple answer:\n\"Here is what happened. Here is what is safe. Here is what still needs checking. Do this next.\"\n\nWhen they use it:\n- after a long AI coding session\n- before asking another AI to continue\n- before deploying\n- after something breaks\n- when switching tools\n- when returning to a project days later\n\nWhy it matters:\nVibe coders move fast, but blind speed creates broken projects. Yare gives them a safety rail without making them become senior engineers overnight.\n\nDemo proof:\nYare reads prior AI runs, saves the state in CockroachDB, and prints a current-state handoff.\n\nOne-line pitch:\nYare helps vibe coders know what the AI actually changed and what to do next.\n",
    "content-research-operators.md":  "# Content/Research Operators\n\nUse case:\nAI-assisted content and research handoff\n\nWho it is for:\nNewsletter, podcast, research, editorial, and publishing teams using AI to draft, summarize, fact-check, and revise work.\n\nWhat breaks today:\nAI creates drafts, claims, summaries, edits, and source notes across different tools. The team loses track of what is verified, what is questionable, and what still needs review.\n\nWhy Yare fits:\nYare turns scattered AI content work into one reviewable state.\n\nWhat Yare stores:\n- changed drafts or files\n- verified claims\n- unverified claims\n- contradictions\n- source/checking notes\n- approval items\n- open loops\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB keeps the research and review state available across writers, editors, agents, and publishing steps.\n\nWhat the user sees:\nA plain editorial handoff:\n\"What changed, what is checked, what needs sourcing, what conflicts, and what to review next.\"\n\nWhen they use it:\n- before publishing\n- after AI research runs\n- after edits from multiple tools\n- during fact-checking\n- when handing work from writer to editor\n- when returning to a draft later\n\nWhy it matters:\nAI can produce content quickly, but teams still need truth, sourcing, and review discipline.\n\nDemo proof:\nYare\u0027s handoff format already tracks verified facts, unverified claims, contradictions, approval items, and next action.\n\nOne-line pitch:\nYare helps content and research teams keep AI-assisted work reviewable before it goes public.\n",
    "devtool-founders-ai-agencies.md":  "# Devtool Founders / AI Agencies\n\nUse case:\nMulti-client agent handoff\n\nWho it is for:\nDevtool founders and AI agencies running agent work across many repos, clients, demos, and internal tools.\n\nWhat breaks today:\nAgent work gets spread across client chats, local terminals, Cursor sessions, Codex runs, Claude Code runs, CI output, and hand-written notes. The agency has to explain what happened without a clean record.\n\nWhy Yare fits:\nYare turns each agent run into a durable handoff that can be reviewed later by the founder, client, or next agent.\n\nWhat Yare stores:\n- task\n- changed files\n- verified facts\n- unverified claims\n- contradictions\n- client approval items\n- open loops\n- receipts\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB keeps the project memory queryable across clients, agents, tools, and handoff sessions.\n\nWhat the user sees:\nA client-safe handoff:\n\"What changed, what is proven, what needs approval, and what the next agent or engineer should do.\"\n\nWhen they use it:\n- after a client agent session\n- before sending a client update\n- before handing work to another contractor\n- before demo day\n- before merge or deploy\n- when switching between client projects\n\nWhy it matters:\nAgencies cannot run on vibes. They need proof of work, clean handoffs, and fewer \"what did the AI actually do?\" moments.\n\nDemo proof:\nYare persists working memory to CockroachDB and lets Claude Code, Codex, and Cursor read the same handoff through MCP.\n\nOne-line pitch:\nYare gives devtool founders and AI agencies a durable work record for every agent-run client project.\n",
    "technical-docs-teams.md":  "# Technical Docs Teams\n\nUse case:\nAI-assisted docs review\n\nWho it is for:\nTechnical writers and docs teams using AI to update README files, API docs, changelogs, examples, tutorials, and release notes.\n\nWhat breaks today:\nAI edits docs quickly, but nobody can easily tell which claims are verified against the code, which examples changed, and which sections still need review.\n\nWhy Yare fits:\nYare turns scattered docs edits into one reviewable current-state handoff.\n\nWhat Yare stores:\n- docs files changed\n- code files referenced\n- verified claims\n- unverified claims\n- contradictions\n- review items\n- open loops\n- receipts\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB keeps the docs review state available after the AI session ends, even when another writer or agent takes over.\n\nWhat the user sees:\nA docs handoff:\n\"What changed in the docs, what is backed by the repo, what still needs checking, and what to edit next.\"\n\nWhen they use it:\n- before publishing docs\n- after AI rewrites a README\n- after API examples change\n- before a release note goes out\n- when handing docs from writer to engineer\n- when checking if docs match code\n\nWhy it matters:\nBad AI docs create support debt. Yare helps docs teams separate verified updates from confident guesses.\n\nDemo proof:\nYare already tracks changed files, verified facts, unverified claims, contradictions, receipts, and next action.\n\nOne-line pitch:\nYare helps docs teams keep AI-written documentation tied to proof instead of guesses.\n",
    "product-teams-writing-specs-with-ai.md":  "# Product Teams Writing Specs With AI\n\nUse case:\nAI-assisted spec handoff\n\nWho it is for:\nProduct teams using AI to draft specs, tickets, acceptance criteria, release notes, and implementation plans.\n\nWhat breaks today:\nSpecs change fast. AI generates requirements, engineers change reality, and nobody knows which decisions are current, approved, or contradicted by implementation.\n\nWhy Yare fits:\nYare turns AI-assisted product work into a current-state handoff that agents and humans can read before building.\n\nWhat Yare stores:\n- spec files changed\n- decisions made\n- verified facts\n- unverified assumptions\n- contradictions\n- human approval items\n- open loops\n- receipts\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB keeps the product state durable across planning sessions, agent runs, code changes, and release prep.\n\nWhat the user sees:\nA product handoff:\n\"What changed, what is decided, what is still an assumption, what conflicts, and what needs approval.\"\n\nWhen they use it:\n- before engineering starts\n- after AI drafts a spec\n- after requirements change\n- before sprint planning\n- before release\n- when a new agent continues product work\n\nWhy it matters:\nAI can write specs fast, but fast specs can become stale lies. Yare keeps the current truth visible.\n\nDemo proof:\nYare compiles scattered run artifacts into one current-state packet and stores it in CockroachDB.\n\nOne-line pitch:\nYare helps product teams keep AI-written specs aligned with what is actually true.\n",
    "support-customer-ops-teams-using-agents.md":  "# Support / Customer Ops Teams Using Agents\n\nUse case:\nSupport knowledge handoff\n\nWho it is for:\nSupport and customer ops teams using AI agents to update help docs, bug notes, escalation summaries, customer issue records, and internal runbooks.\n\nWhat breaks today:\nAgents summarize issues, suggest fixes, update docs, and write notes, but the team loses track of what was verified, what was assumed, and what still needs escalation.\n\nWhy Yare fits:\nYare turns support-agent work into a clear handoff with proof, unresolved claims, and next action.\n\nWhat Yare stores:\n- files or notes changed\n- verified customer facts\n- unverified claims\n- contradictions\n- escalation items\n- approval items\n- receipts\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB keeps the support memory available across shifts, agents, teammates, and repeated customer issues.\n\nWhat the user sees:\nA support handoff:\n\"What happened, what is confirmed, what is still unclear, who needs to approve, and what to do next.\"\n\nWhen they use it:\n- during shift handoff\n- after an AI support summary\n- after a bug escalation\n- before updating help docs\n- when a customer issue reopens\n- when multiple agents touched the same issue\n\nWhy it matters:\nSupport teams need continuity. Yare reduces repeated investigation and bad AI summaries.\n\nDemo proof:\nYare\u0027s handoff format already captures verified facts, unverified claims, contradictions, human approval items, and next clean action.\n\nOne-line pitch:\nYare helps support teams keep AI-assisted customer work clear, reviewable, and durable.\n",
    "long-form-writers-using-ai.md":  "# Long-Form Writers Using AI\n\nUse case:\nAI-assisted manuscript handoff\n\nWho it is for:\nWriters using AI across drafts, outlines, chapters, edits, research notes, continuity checks, and revision passes.\n\nWhat breaks today:\nAI changes a draft, suggests edits, rewrites sections, creates notes, and introduces contradictions. The writer loses track of what changed and what still needs review.\n\nWhy Yare fits:\nYare turns each AI writing session into a durable handoff instead of a buried chat transcript.\n\nWhat Yare stores:\n- draft files changed\n- accepted edits\n- unverified notes\n- contradictions\n- continuity issues\n- human review items\n- open loops\n- receipts\n- next clean action\n\nWhat Roach makes durable:\nCockroachDB keeps the writing state available across sessions, tools, drafts, and revision passes.\n\nWhat the user sees:\nA writing handoff:\n\"What changed, what is accepted, what conflicts, what still needs review, and what to revise next.\"\n\nWhen they use it:\n- after an AI revision pass\n- before continuing a draft\n- before sending to an editor\n- after continuity checks\n- when switching writing tools\n- when returning to a project later\n\nWhy it matters:\nAI can help write faster, but it can also muddy continuity and intent. Yare keeps the revision state clean.\n\nDemo proof:\nYare already saves changed files, verified state, contradictions, approval items, open loops, and next action as durable working memory.\n\nOne-line pitch:\nYare helps AI-assisted writers keep drafts, edits, and unresolved issues from turning into chaos.\n"
};

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
    const fileName = downloadLink.getAttribute("href").split("/").pop();
    copyUseCaseText(window.USE_CASE_MARKDOWN[fileName], button);
  });
});

document.querySelectorAll(".use-case-actions a[download]").forEach((link) => {
  link.addEventListener("click", (event) => {
    const fileName = link.getAttribute("href").split("/").pop();
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
