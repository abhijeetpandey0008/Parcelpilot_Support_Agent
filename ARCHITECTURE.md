# 🏗️ Architecture Note

## 1. System Overview

ParcelPilot Support Agent is a tool-using AI support system that combines an LLM with document retrieval, structured customer data, deterministic access control, and human confirmation for state-changing actions.

The application has two main components:

1. **Customer Support Agent**
   - AI-powered conversational interface.
   - Uses tools to retrieve customer data and relevant documentation.
   - Supports multi-step and multi-tool reasoning.
   - Requires explicit human confirmation before executing actions.

2. **Internal Proactive Issue Detection**
   - A deterministic staff dashboard.
   - Identifies SLA breaches, known issue clusters, and historical resolutions that require verification.
   - Does not use an LLM because the implemented detection tasks are deterministic.

The high-level architecture is:

```text
                         Customer
                            │
                            ▼
                    ┌───────────────┐
                    │  Streamlit UI │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ OpenRouter LLM│
                    │     Agent     │
                    └───────┬───────┘
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             ▼              ▼              ▼
      search_documents  structured_data  propose_action
             │              │              │
             ▼              ▼              ▼
       Document Index    Customer Data   Human Confirmation
             │              │              │
             └──────────────┴──────────────┘
                            │
                            ▼
                       Final Response
```

---

# 2. Agent Design

A single customer-facing AI agent runs a tool-calling loop implemented in `agent.py`.

The workflow is:

```text
Call the LLM
      │
      ▼
Check for tool calls
      │
   ┌──┴───┐
   │      │
  No     Yes
   │      │
   ▼      ▼
Final    Execute requested
answer   non-action tools
            │
            ▼
       Return tool results
       to the LLM
            │
            ▼
       Continue the loop
```

The agent continues this process until it produces a final text response.

This allows multi-step questions to be handled dynamically rather than pre-scripted.

For example, a question such as:

> "Can this order be cancelled without a fee?"

may require the agent to:

1. Retrieve the customer's order information.
2. Retrieve the customer's account or contract information.
3. Search the current cancellation policy.
4. Compare the relevant sources.
5. Apply source precedence.
6. Generate a grounded answer.

The system prompt describes:

- What each tool is intended for.
- When document retrieval is required.
- When structured data lookup is required.
- The source authority hierarchy.
- When escalation should be recommended.
- The requirement for confirmation before actions.

The model decides which tools to call and in which order.

This enables multi-tool reasoning without manually defining a fixed workflow for every possible customer question.

---

# 3. OpenRouter LLM Integration

The application uses the OpenRouter API as the LLM provider.

The API key is loaded from environment configuration:

```text
OPENROUTER_API_KEY
```

The model is configured through:

```text
OPENROUTER_MODEL
```

The OpenRouter integration allows the agent to use an OpenAI-compatible chat completion and tool-calling interface.

The LLM is responsible for:

- Understanding the customer's request.
- Deciding whether tools are required.
- Selecting the appropriate tools.
- Combining information from multiple tool results.
- Applying the source authority rules defined in the system prompt.
- Producing the final customer-facing response.

The application does not rely on the LLM alone for data access or state-changing actions. Those capabilities are controlled by the application and tool layer.

---

# 4. Tool Design

The system provides three tools.

## 4.1 `search_documents`

This tool performs retrieval over the supplied document pack.

It is used for questions involving:

- Policies.
- SOP rules.
- Contract terms.
- Product documentation.
- Known issues.
- Current operational guidance.

Example:

```text
What is the current cancellation policy?
```

The tool returns relevant document passages along with metadata describing their source and reliability.

---

## 4.2 `structured_data_lookup`

This tool retrieves structured information from:

```text
accounts
orders
tickets
```

The tool automatically scopes all results to the account associated with the current Streamlit session.

The model cannot provide an arbitrary account ID to access another customer's data.

Derived time fields are computed before the data is returned to the model.

Examples include:

- Minutes since booking.
- Minutes past the pickup window.
- Pickup delay relative to the expected window.
- Time between booking and cancellation request.
- Ticket age.

This design allows the model to reason over clean, pre-computed values instead of performing calculations over raw timestamps.

---

## 4.3 `propose_action`

This tool is used when the agent determines that a state-changing action may be appropriate.

Supported actions include:

```text
create_escalation
create_followup_task
```

The tool does not execute the action.

Instead, it returns a staged proposal.

The actual execution only happens after an explicit user confirmation in the Streamlit interface.

---

# 5. Document Handling and Retrieval

The supplied PDFs are processed using `pdfplumber`.

Each document is parsed and split into smaller sections based on document structure, such as numbered headers.

Retrieved chunks include metadata such as:

```text
doc_type
status
account_id
source
```

Document types include:

```text
policy
sop
product_doc
contract
```

Document status includes:

```text
current
deprecated
```

Contracts are additionally associated with the relevant customer account.

Retrieval is implemented using:

```text
TF-IDF
+
Cosine Similarity
```

The implementation is contained in:

```text
retrieval.py
```

## Why TF-IDF instead of a Vector Database?

The supplied data pack contains a relatively small number of documents and chunks.

For this scale, TF-IDF provides:

- Fast retrieval.
- Simple implementation.
- Transparent scoring.
- Easy debugging.
- Minimal operational complexity.

Introducing embeddings and a vector database would add additional infrastructure without providing a clear benefit for the current document set.

For a larger or more complex knowledge base, the architecture could be extended to use:

- Embedding models.
- Vector databases.
- Hybrid search.
- Reranking.

---

# 6. Structured Data Handling

Structured data is loaded using pandas in:

```text
data_loader.py
```

The application loads:

- Customer accounts.
- Orders.
- Support tickets.

Timestamps are parsed when the dataset is loaded.

Time-based calculations are performed relative to the dataset's specified snapshot time rather than the system's wall-clock time.

This ensures that calculations remain consistent with the assessment dataset.

For example:

```text
minutes_since_booking

minutes_past_pickup_window_end

minutes_between_booking_and_cancellation_request

ticket_age_minutes
```

are calculated before the information is returned to the LLM.

---

# 7. Source Reliability and Conflict Handling

The application defines an explicit source authority hierarchy.

```text
1. Customer's signed contract
                │
                ▼
2. Current policy / current SOP
                │
                ▼
3. Current product documentation
                │
                ▼
4. Deprecated documents
   Never treated as current guidance
                │
                ▼
5. Historical ticket resolutions
   Past context only
```

The source hierarchy is included in the agent's system prompt.

The model is instructed to apply this precedence when sources conflict.

For example:

```text
Customer Contract
        overrides
General Cancellation Policy
```

when the contract covers the relevant situation.

## Metadata-Based Reliability

Retrieved document chunks include metadata indicating:

- Document type.
- Document status.
- Contract ownership.

This means the model receives the reliability context together with the retrieved content.

For example:

```text
status: deprecated
```

or:

```text
doc_type: contract
account_id: ACC-001
```

This reduces the risk of the model incorrectly treating outdated documentation as current policy.

## Historical Ticket Resolutions

Historical resolutions are treated as past context rather than current authority.

When a ticket contains a `historical_resolution`, the structured data tool adds an explicit warning:

```text
This ticket has a historical_resolution.
Treat it as past context only.
It may be incorrect and must never be cited as current policy.
```

This prevents the agent from blindly repeating historical answers when they conflict with current policy or contract terms.

---

# 8. Access Control

Access control is enforced in the tool layer rather than relying only on the LLM's instructions.

## Structured Data

The currently selected customer account is stored in the Streamlit session.

The structured data tool receives the session-bound:

```text
account_id
```

All data queries are filtered using this value.

Conceptually:

```text
Current Session
       │
       ▼
account_id
       │
       ▼
structured_data_lookup
       │
       ▼
Filter account / orders / tickets
       │
       ▼
Return only authorized data
```

The model cannot select an arbitrary account ID.

---

## Contract Documents

Document retrieval receives the session's account ID.

Contract chunks belonging to other customers are filtered out before retrieval results are returned to the model.

Therefore:

```text
LumenWorks Session
        │
        ▼
search_documents
        │
        ▼
Northstar Contract Removed
        │
        ▼
Only Authorized Documents
```

This means access control is enforced programmatically rather than depending on the model to follow a security instruction.

---

# 9. Confirmation Before Actions

The Human-in-the-Loop confirmation mechanism is implemented as an application-level control.

When the LLM calls:

```text
propose_action
```

the agent does not immediately execute the proposed action.

Instead:

```text
LLM calls propose_action
          │
          ▼
Agent loop pauses
          │
          ▼
Proposal stored in session state
          │
          ▼
Streamlit displays
Confirm / Cancel
          │
     ┌────┴────┐
     ▼         ▼
  Cancel      Confirm
     │         │
     ▼         ▼
No action   execute_action()
created         │
                ▼
           Action result
                │
                ▼
           Agent resumes
                │
                ▼
          Final response
```

Only the application can call:

```text
execute_action()
```

and it does so only after an explicit user interaction.

This makes confirmation an application-level guarantee rather than relying on the model to remember an instruction such as:

> "Always ask before taking action."

---

# 10. Agent Pause and Resume

The action workflow requires the agent loop to pause when an action proposal is generated.

The current conversation state, including:

- Messages.
- Tool calls.
- Tool results.
- Pending action details.

is preserved.

After the user confirms the action:

```text
execute_action()
```

returns an execution result.

The result is then incorporated into the agent workflow so that the final response can reflect the outcome.

For example:

```text
Action executed: ACT-XXXXXX
```

The agent can then generate a contextual response explaining what was created.

If the user cancels the proposal, no action is executed.

---

# 11. Internal Proactive Issue Detection

The application also includes a staff-only Internal Insights view.

Implemented in:

```text
insights.py
```

The dashboard identifies:

## SLA Status

Tickets are classified as:

```text
BREACHED
NEAR BREACH
```

based on the available ticket information and SLA logic.

---

## Known Issue Clustering

Tickets associated with known problems are grouped together.

This allows staff to identify patterns such as multiple tickets related to the same operational issue.

---

## Historical Resolution Review

Tickets containing historical resolutions are surfaced for verification.

Historical resolutions are not automatically treated as valid current guidance.

---

# 12. Why Internal Insights Does Not Use an LLM

The internal dashboard focuses on deterministic tasks such as:

- Calculating ticket age.
- Checking SLA thresholds.
- Grouping related known issues.
- Identifying tickets containing historical resolutions.

These tasks can be performed directly using structured data.

Using an LLM would introduce:

- Additional latency.
- API cost.
- Non-deterministic behavior.
- Additional potential for incorrect results.

Therefore, deterministic data processing was selected instead.

---

# 13. Major Technical Trade-Offs

## TF-IDF Instead of Embeddings

**Decision:** Use TF-IDF and cosine similarity.

**Reason:** The supplied document collection is small, and the retrieval problem does not justify vector database infrastructure.

**Future improvement:** Move to embeddings, hybrid retrieval, and reranking as the knowledge base grows.

---

## Single Customer-Facing Agent

The application uses one primary customer-facing AI agent.

This keeps the scope focused and allows the project to demonstrate:

- Tool use.
- Access control.
- Retrieval.
- Multi-step reasoning.
- Human-in-the-Loop actions.

The internal staff functionality is implemented separately as a deterministic dashboard.

---

## Deterministic Internal Insights

Internal issue detection is not implemented as a second AI agent.

SLA detection and ticket grouping have deterministic logic and numeric outputs.

Using traditional data processing provides:

- Predictable results.
- Lower complexity.
- Easier debugging.
- Lower latency.

---

## Keyword-Based Severity Classification

Severity classification for open tickets is keyword-based.

This is intentionally a simplified implementation suitable for the supplied dataset.

Advantages:

- Easy to understand.
- Transparent.
- Sufficient for demonstrating the proactive detection mechanism.

Limitations:

- Sensitive to wording.
- Limited semantic understanding.
- May not generalize to real-world ticket distributions.

A production system could improve this using:

- Explicit severity selection during ticket creation.
- A trained text classifier.
- An LLM-assisted classification pipeline with human review.

---

# 14. Key Design Principle

The main architectural principle of the project is:

```text
Use the LLM for judgment and language.
Use deterministic code for security, data access, calculations, and execution control.
```

The LLM decides:

- Which information is required.
- Which tools to call.
- How to combine information.
- How to explain the result.

The application controls:

- Which data the model can access.
- Which documents the model can retrieve.
- Time calculations.
- Source metadata.
- Action execution.
- User confirmation requirements.

This separation reduces the risk of relying on prompt instructions for behaviors that should be guaranteed by the application itself.