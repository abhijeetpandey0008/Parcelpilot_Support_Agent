# ParcelPilot Support Agent

A customer-facing support chatbot for ParcelPilot, built for the CalQuity AI
Engineer assessment. Includes an internal "Proactive Issue Detection" view
for staff.

## What this is

- **Customer Support Chat** — a Claude-powered agent with 3 tools
  (document search, structured account/order/ticket lookup, and a
  confirm-before-executing action tool), scoped to a mocked logged-in
  customer.
- **Internal Insights (staff only)** — a non-LLM dashboard that flags SLA
  breaches, known-issue clusters, and tickets whose historical resolution
  should be re-verified. Gated behind a mock staff passcode.

## Setup

```bash
pip install -r requirements.txt
```

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# optional, defaults to claude-sonnet-5
export ANTHROPIC_MODEL=claude-sonnet-5
```

(or create a `.env` file — see `.env.example` — and load it however you
prefer, e.g. `export $(cat .env | xargs)` before running.)

## Run

```bash
streamlit run app.py
```

## Using it

- Pick a mock customer in the sidebar (Northstar Logistics, LumenWorks,
  Beacon Retail, or Axis Labs) — this is the "logged in" account. All tool
  calls are scoped to it server-side; the model cannot query another
  account's data no matter what it's asked.
- Try the example questions from the brief:
  - *"Can Northstar cancel ORD-1001 without a cancellation fee? Explain why."*
    (log in as Northstar Logistics)
  - *"A pickup is three hours late because of carrier fault. Should I get a
    service credit?"* (try as LumenWorks, referencing ORD-2002)
- Ask it to escalate something — it will stage the action and show a
  Confirm/Cancel control before anything is actually "created."
- Switch to **Internal Insights** in the sidebar (passcode: `internal123`)
  to see the proactive-detection dashboard.

## Project layout

```
app.py          Streamlit UI (chat + internal dashboard)
agent.py        Claude tool-use loop, system prompt, confirmation pause/resume
tools.py        Tool implementations + access-control enforcement
retrieval.py    TF-IDF search over the document pack
data_loader.py  Loads PDFs and the xlsx into usable structures
insights.py     Problem 1: proactive issue detection aggregation
data/           The supplied candidate data pack
```

See `ARCHITECTURE.md` and `PRODUCT.md` for the required design/product notes.
