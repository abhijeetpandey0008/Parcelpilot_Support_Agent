# Product Note

## Which additional client problem I chose

**Problem 1: Proactive Issue Detection.** I built it as a separate internal
dashboard (staff passcode gate) rather than a second chatbot, because the
brief itself describes it as "an internal view," and the underlying
questions (is this ticket breaching SLA, do several tickets share a root
cause, does one account have unusually many open tickets) have
deterministic, checkable answers — a dashboard gets those right every
time; a second chatbot would just add latency and a new way to be wrong.

What it surfaces, using only the supplied data:
- **SLA status per open ticket** — compares ticket age against the
  correct target (contract override if one exists, else the plan default
  from the current policy), flags BREACHED / NEAR BREACH.
- **Known-issue clustering** — groups open tickets that match `KI-208`
  (bulk upload) or `KI-211` (SwiftShip webhook delay) from the Product
  Operations Guide, so support sees "these two tickets are the same root
  cause" instead of two unrelated complaints.
- **Multiple-open-tickets-per-account** flag — Northstar currently has two
  open tickets simultaneously, which is worth a human noticing.
- **Historical-resolution review queue** — surfaces closed tickets whose
  `historical_resolution` exists, since the data pack explicitly warns
  these may be wrong (and, in this dataset, both actually are wrong versus
  current policy/contract). This turns "an old ticket might mislead
  someone" from a silent risk into a visible, actionable list.

I did not touch Problem 2 (Trust & Reliability) as a separate feature,
because I treated it as a first-class constraint on the core chatbot
itself rather than an add-on — the source-precedence rules, the
deprecated-document flagging, and the "historical resolution is context
only" warning are all built into the main agent (see ARCHITECTURE.md),
since a bolt-on trust layer would be weaker than baking the behavior into
every answer from the start.

## What else I'd build next, prioritized

1. **Real authentication + role-based access**, replacing the mock account
   selector/staff passcode — this is the single biggest gap between this
   submission and something deployable, since access control is the part
   customers and CalQuity would actually care about being airtight.
2. **A feedback loop on agent answers** (thumbs up/down + optional
   correction) feeding back into a review queue, especially for anything
   involving money (service credits, fee waivers) — closes the loop on
   catching a wrong answer before it repeats.
3. **Real ticket/CRM integration for `propose_action`** instead of a mock
   — right now escalations are logged in memory only.
4. **Better severity classification** for the internal dashboard (real
   field or small classifier instead of keyword matching), and extending
   SLA tracking to response-time-so-far rather than just ticket age.
5. **Multi-turn memory across sessions** — right now conversation state
   resets when the account or session changes; a real product would want
   ticket-linked conversation history.

## What I intentionally left out

- **Vector database / embeddings-based retrieval** — the data pack is six
  short documents; TF-IDF is honest about being enough for this scale and
  is easier to debug. I'd revisit this if the document set grew.
- **The internal *chatbot* context** (as opposed to the internal
  *dashboard*) — the brief allows building either or both; I judged one
  well-scoped chatbot plus a genuinely useful dashboard was a better use
  of the time than two half-built chat experiences.
- **Persistent storage** — everything runs in-memory / from the workbook
  on each session; there's no database, since this is an assessment
  prototype, not a production service.
- **Automated tests / CI** — I validated the core logic (access control,
  retrieval, the confirmation state machine) with manual and mocked
  dry-run scripts during development, but didn't build out a formal test
  suite given the scope of the assessment.

## One metric to judge whether the product is useful

**% of customer questions resolved by the agent without an escalation AND
without a subsequent human correction.** This single number forces the
two failure modes that actually matter to trade off against each other
honestly: an agent that escalates everything scores badly on "resolved,"
and an agent that confidently answers everything (including wrongly)
scores badly on "without correction." Optimizing for both together is the
actual product goal — fast *and* trustworthy — rather than either one
alone.
