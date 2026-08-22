# 📦 Product Note

## 1. Product Overview

ParcelPilot Support Agent is designed to help customers receive accurate, context-aware support while maintaining strong controls around:

- Customer data access.
- Policy and contract interpretation.
- Outdated information.
- Historical ticket context.
- State-changing actions.

The product combines:

1. An AI-powered customer support agent.
2. Document retrieval and structured data lookup.
3. Deterministic access control.
4. Human confirmation before actions.
5. An internal proactive issue detection dashboard.

The primary design goal is not simply to answer questions quickly.

It is to answer customer questions using the correct information **while avoiding unsafe assumptions and unauthorized actions**.

---

# 2. Additional Client Problem Selected

## Problem 1: Proactive Issue Detection

I chose to implement **Problem 1: Proactive Issue Detection** as a separate internal dashboard.

The assessment describes this as an internal support capability, so a dashboard was a better fit than building a second chatbot.

The questions being answered are primarily deterministic:

- Is a ticket close to or beyond its SLA target?
- Do multiple open tickets relate to the same known issue?
- Does an account currently have multiple open tickets?
- Are historical resolutions potentially misleading and worth reviewing?

These questions can be answered directly using structured data and defined business rules.

Using a second LLM agent for these tasks would introduce:

- Additional latency.
- API cost.
- Non-deterministic behavior.
- Another potential source of incorrect results.

Therefore, the internal capability is implemented as a deterministic dashboard rather than another conversational AI system.

---

# 3. Internal Proactive Issue Detection

The Internal Insights dashboard provides several forms of proactive support monitoring.

## 3.1 SLA Status Monitoring

Each open ticket is evaluated against its relevant SLA target.

The logic considers:

```text
Customer Contract Override
            │
            ▼
Current Policy / Plan Default
            │
            ▼
Ticket Age Calculation
            │
            ▼
SLA Status
```

Tickets can be identified as:

```text
BREACHED

NEAR BREACH
```

This allows support staff to identify issues that require attention before they become larger customer problems.

---

## 3.2 Known-Issue Clustering

The dashboard groups open tickets that correspond to known product or operational issues.

For the supplied dataset, this includes known issues such as:

```text
KI-208 — Bulk Upload Issue

KI-211 — SwiftShip Webhook Delay
```

Instead of showing several similar tickets as unrelated complaints, the dashboard helps support staff identify a possible shared root cause.

Conceptually:

```text
Ticket A ──┐
           │
Ticket B ──┼──► Known Issue Cluster
           │
Ticket C ──┘
```

This can help teams:

- Recognize recurring incidents.
- Avoid investigating identical problems repeatedly.
- Prioritize root-cause investigation.
- Provide more consistent customer communication.

---

## 3.3 Multiple Open Tickets Per Account

The dashboard can identify accounts with multiple open support tickets.

For example, the supplied dataset contains an account with multiple simultaneous open tickets.

This does not automatically mean the account has a critical problem.

However, it is useful operational context because multiple open tickets may indicate:

- Repeated customer friction.
- A larger underlying issue.
- Duplicate or related incidents.
- A customer requiring additional attention.

The dashboard surfaces this information so that a human support team can investigate.

---

## 3.4 Historical Resolution Review Queue

Historical ticket resolutions are treated as past context rather than automatically trusted sources.

The supplied data explicitly warns that historical resolutions may be outdated or incorrect.

Therefore, tickets containing:

```text
historical_resolution
```

are surfaced in a dedicated review queue.

This transforms a hidden risk:

```text
Old Ticket
    │
    ▼
Potentially Incorrect Resolution
    │
    ▼
Accidentally Reused as Current Policy
```

into a visible operational workflow:

```text
Historical Resolution
        │
        ▼
Review Queue
        │
        ▼
Verify Against Current Sources
        │
        ▼
Use or Correct Guidance
```

This aligns the internal dashboard with the same trust and source-authority principles used by the customer-facing AI agent.

---

# 4. Trust and Reliability as a Core Product Feature

I did not implement **Problem 2: Trust & Reliability** as a completely separate feature.

Instead, I treated trust and reliability as a fundamental requirement of the customer support agent itself.

The following mechanisms are built into the core application:

## Source Authority

The agent follows this source hierarchy:

```text
Customer Signed Contract
          │
          ▼
Current Policy / Current SOP
          │
          ▼
Current Product Documentation
          │
          ▼
Deprecated Documents
Never treated as current guidance
          │
          ▼
Historical Ticket Resolutions
Past context only
```

---

## Deprecated Document Awareness

Retrieved documents include metadata describing their status.

For example:

```text
status: current
```

or:

```text
status: deprecated
```

This gives the LLM explicit context about whether a document should be treated as current guidance.

---

## Historical Resolution Warning

Historical ticket resolutions are returned with an explicit warning indicating that they are:

```text
Past context only.
They may be incorrect.
They must not be treated as current policy without verification.
```

This reduces the risk of blindly repeating an old support decision when current policy or contract terms have changed.

---

## Deterministic Access Control

The application does not rely only on the LLM to respect customer boundaries.

Instead:

```text
User Session
      │
      ▼
Bound Account ID
      │
      ├──────────────► Structured Data Filtering
      │
      └──────────────► Contract Document Filtering
```

The model can only receive data and contract documents that belong to the currently authenticated mock customer session.

---

## Human Confirmation Before Actions

Any state-changing action follows this workflow:

```text
Customer Request
       │
       ▼
LLM Determines Action May Be Needed
       │
       ▼
propose_action
       │
       ▼
Action Staged
       │
       ▼
User Confirmation Required
       │
   ┌───┴────┐
   ▼        ▼
Cancel    Confirm
   │        │
   ▼        ▼
No Action  execute_action()
```

The LLM cannot directly execute the action.

This makes confirmation an application-level guarantee rather than depending only on prompt instructions.

---

# 5. Current Product Workflow

The customer-facing workflow is:

```text
Customer Login
      │
      ▼
Customer Asks Question
      │
      ▼
OpenRouter LLM Agent
      │
      ▼
Does the Question Require Data?
      │
  ┌───┴───────────────┐
  │                   │
  ▼                   ▼
Documents        Customer Data
  │                   │
  ▼                   ▼
search_documents structured_data_lookup
  │                   │
  └─────────┬─────────┘
            │
            ▼
     LLM Evaluates Sources
            │
            ▼
     Is an Action Required?
            │
       ┌────┴────┐
       │         │
      No        Yes
       │         │
       ▼         ▼
 Final       propose_action
 Response        │
                 ▼
          User Confirmation
                 │
                 ▼
          Action Executed
                 │
                 ▼
           Final Response
```

The LLM is responsible for reasoning and communication.

The application is responsible for:

- Access control.
- Data filtering.
- Retrieval.
- Time calculations.
- Action execution.
- Confirmation requirements.

---

# 6. What I Would Build Next

The following improvements are prioritized based on their expected product value.

## Priority 1 — Real Authentication and Role-Based Access Control

The current application uses:

- A mock customer selector.
- A mock staff access code.

This is appropriate for an assessment prototype but would not be sufficient for production.

A production implementation should include:

- Real user authentication.
- Secure sessions.
- Role-based access control.
- Customer identity verification.
- Staff permissions.
- Audit logging.

This is the highest-priority improvement because access control is critical in a customer support system.

---

## Priority 2 — Feedback Loop for Agent Answers

Add a feedback mechanism such as:

```text
👍 Helpful

👎 Incorrect / Not Helpful
```

Users or support staff could optionally provide a correction.

Feedback could enter a review queue and help identify:

- Incorrect answers.
- Missing documentation.
- Retrieval failures.
- Policy interpretation problems.
- Repeated customer issues.

This would be particularly valuable for high-impact answers involving:

- Service credits.
- Cancellation fees.
- Contract terms.
- Escalations.

---

## Priority 3 — Real Ticket or CRM Integration

Currently:

```text
propose_action
```

stages an action, and:

```text
execute_action
```

simulates execution.

A production system could integrate with:

- A ticketing system.
- CRM.
- Customer support platform.
- Operations workflow system.

For example:

```text
Customer Confirms Escalation
          │
          ▼
Application Validation
          │
          ▼
CRM / Ticketing API
          │
          ▼
Create Real Escalation
          │
          ▼
Return Ticket Reference
```

---

## Priority 4 — Improved Severity Classification

The current internal severity classification uses keyword-based logic.

This is transparent and sufficient for demonstrating the feature on the assessment dataset, but a production implementation could improve it using:

- Explicit severity fields during ticket creation.
- A trained text classification model.
- Embedding-based similarity.
- LLM-assisted classification with human review.

The system could also track additional SLA metrics such as:

- Time to first response.
- Time to resolution.
- Escalation duration.
- SLA risk prediction.

---

## Priority 5 — Persistent Conversation Memory

Currently, conversation state is session-based.

A production system could support:

- Persistent conversation history.
- Ticket-linked conversations.
- Customer interaction history.
- Agent handoff summaries.
- Context restoration across sessions.

For example:

```text
Customer
    │
    ▼
Previous Support Conversations
    │
    ▼
Relevant Context Retrieval
    │
    ▼
Current Agent Interaction
```

This would provide better continuity across support interactions.

---

# 7. What I Intentionally Left Out

## Vector Database / Embedding-Based Retrieval

The supplied document set is small.

TF-IDF provides sufficient retrieval quality while remaining:

- Fast.
- Transparent.
- Easy to debug.
- Simple to deploy.

A vector database would become more useful if the document collection grew significantly.

Future improvements could include:

```text
Embeddings
+
Vector Search
+
Keyword Search
+
Reranking
```

for hybrid retrieval.

---

## A Second Internal Chatbot

The assessment allows different internal support approaches.

Instead of building two separate chatbots, I chose:

```text
Customer AI Agent
        +
Internal Deterministic Dashboard
```

This provides two different but complementary capabilities:

- Conversational support for customers.
- Proactive operational visibility for staff.

The decision keeps the project focused and avoids building a second shallow chatbot with overlapping functionality.

---

## Persistent Database

The current application loads data from the supplied workbook and documents.

Actions are mocked rather than stored in a production database.

This was an intentional trade-off because the project is designed as an assessment prototype rather than a production deployment.

A production implementation could introduce:

- PostgreSQL or another relational database.
- Conversation persistence.
- Action history.
- Audit logs.
- Customer profiles.
- Ticket history.

---

## Formal Automated Testing and CI

The current prototype was validated using manual and mocked dry-run testing of important functionality, including:

- Access-control behavior.
- Document retrieval.
- Structured data lookup.
- Action confirmation.
- Agent pause and resume behavior.

A production-ready version should add:

```text
Unit Tests
        +
Integration Tests
        +
Security Tests
        +
Regression Tests
        +
CI Pipeline
```

Important tests would include:

- Cross-account access attempts.
- Contract isolation.
- Deprecated document handling.
- Historical resolution conflicts.
- Action cancellation.
- Action confirmation.
- Tool failure handling.

---

# 8. Product Trade-Offs

The project intentionally prioritizes:

```text
Trust
+
Correctness
+
Transparency
```

over unnecessary architectural complexity.

Examples include:

| Decision | Trade-Off |
|---|---|
| TF-IDF instead of vector DB | Simpler and transparent for a small document set |
| One customer-facing AI agent | More focused than building multiple shallow agents |
| Deterministic internal dashboard | More reliable for SLA and aggregation tasks |
| Mock authentication | Faster prototype development but not production-ready |
| Mock action execution | Demonstrates workflow without requiring external infrastructure |
| Keyword severity detection | Simple and transparent but limited in generalization |
| Session-based memory | Simple implementation but no cross-session continuity |

---

# 9. One Metric to Measure Product Usefulness

The primary product metric would be:

## Resolution Rate Without Human Correction

```text
% of customer questions resolved
without escalation
AND
without a subsequent human correction
```

This metric balances two important failure modes.

### Failure Mode 1 — Over-Escalation

An agent that escalates every question may avoid giving incorrect answers, but it does not actually resolve customer problems efficiently.

```text
Safe but not useful.
```

### Failure Mode 2 — Overconfidence

An agent that confidently answers every question may appear efficient but can produce incorrect or unsafe guidance.

```text
Fast but not trustworthy.
```

The desired outcome is:

```text
                 High Resolution Rate
                         +
              Low Human Correction Rate
                         =
              Fast and Trustworthy Support
```

This metric encourages the product to optimize for both usefulness and reliability rather than maximizing only automation.

---

# 10. Future Success Criteria

A more mature version of ParcelPilot could track:

- Resolution rate without escalation.
- Resolution rate without human correction.
- Escalation rate.
- Customer satisfaction.
- Average response time.
- SLA breach prevention rate.
- Agent answer correction rate.
- Retrieval success rate.
- Unsafe or unauthorized action attempts blocked.
- Percentage of actions successfully completed after confirmation.

Together, these metrics would provide a more complete view of whether the AI system is:

```text
Useful
Accurate
Safe
Efficient
Trustworthy
```

---

# 11. Product Philosophy

The central product philosophy behind ParcelPilot is:

> **Automate customer support decisions where the system has sufficient evidence, and escalate when the information is incomplete, conflicting, or requires human judgment.**

The goal is not to create an agent that answers every question.

The goal is to create one that knows:

```text
What it can answer,
What information it needs,
What it should not assume,
and when a human must remain in control.
```

This results in a support system that aims to be both:

**Fast enough to be useful, and controlled enough to be trusted.**
