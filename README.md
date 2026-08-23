# 📦 ParcelPilot Support Agent

> An AI-powered customer support agent with multi-tool reasoning, document retrieval, structured data access, human-in-the-loop action confirmation, and proactive issue detection.

Built for the **CalQuity AI Engineer Assessment**.

## 🚀 Live Demo

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)]

**Live App:** [Open the deployed application](https://parcelpilotsupportagent-gnpqwmc22begbotfzidvzz.streamlit.app/)

---

## 🌟 Overview

ParcelPilot Support Agent is a customer-facing AI support system designed to answer questions about:

- Customer accounts
- Orders and shipment status
- Support tickets
- Cancellation policies
- Service credits
- Customer-specific contracts
- Known product or carrier issues

The application combines an LLM with structured data and document retrieval instead of relying solely on the model's knowledge.

The system also includes an internal **Proactive Issue Detection Dashboard** that helps staff identify:

- SLA breaches
- Tickets approaching SLA limits
- Known issue clusters
- Historical resolutions that require verification

---

# ✨ Key Features

## 🤖 AI Customer Support Agent

The customer support assistant can answer questions using multiple sources:

- Structured customer account data
- Order data
- Support ticket history
- Current policies and SOPs
- Customer-specific agreements
- Product documentation
- Known issue documentation

The agent can perform multi-step reasoning and use multiple tools before generating an answer.

---

## 🔎 Document Retrieval

The application includes a retrieval system that searches the supplied document pack using TF-IDF.

The `search_documents` tool retrieves relevant passages from:

- Customer agreements
- Current policies
- SOP documents
- Product documentation
- Known issue documentation

The system follows a source authority hierarchy:

```text
Customer-specific Agreement
            ↓
Current Policy / SOP
            ↓
Current Product Documentation
            ↓
Deprecated Documents
```

Customer-specific contracts take priority over general policies when applicable.

Deprecated documents are never treated as current guidance.

---

## 📊 Structured Data Access

The agent can access the authenticated customer's own:

- Account information
- Orders
- Support tickets

The following tool handles structured data:

```text
structured_data_lookup
```

Access control is enforced at the tool layer.

Even if the model attempts to request another customer's information, the tool always uses the `account_id` associated with the current session.

---

## 🔄 Multi-Tool Agent Reasoning

The agent can combine multiple tools to answer complex questions.

For example:

> "I requested cancellation for my order. Based on my account, order details, and the current cancellation policy, what will happen?"

The agent may perform:

```text
User Question
      │
      ▼
┌───────────────────┐
│ OpenRouter LLM    │
└─────────┬─────────┘
          │
     ┌────┴─────┐
     ▼          ▼
Structured     Document
Data Lookup     Search
     │          │
     └────┬─────┘
          ▼
Compare Information
          │
          ▼
Apply Source Authority
          │
          ▼
Grounded Response
```

---

# 🛠️ Available Tools

The AI agent has access to three tools.

## 1️⃣ `search_documents`

Searches relevant documentation.

Used for:

- Cancellation policies
- Service credit rules
- SOPs
- Customer agreements
- Product documentation
- Known issues

Example:

```text
What is the current cancellation policy?
```

---

## 2️⃣ `structured_data_lookup`

Retrieves customer-specific structured information.

Available datasets:

```text
account
orders
tickets
```

Example:

```text
Show me all my orders.
```

or:

```text
Give me details about order ORD-1001.
```

The tool automatically scopes all queries to the currently authenticated customer.

---

## 3️⃣ `propose_action`

Used when an action should be taken.

Supported actions:

```text
create_escalation
create_followup_task
```

The tool does **not execute the action directly**.

Instead, it creates a proposal that must be approved by the user.

---

# 👤 Human-in-the-Loop Action Confirmation

State-changing actions require explicit user confirmation.

The workflow is:

```text
User requests an action
        │
        ▼
Agent gathers information
        │
        ▼
propose_action
        │
        ▼
Action is staged
        │
        ▼
⚠️ User Confirmation Required
        │
   ┌────┴────┐
   ▼         ▼
Cancel     Confirm
   │         │
   ▼         ▼
No Action   execute_action()
Created       │
              ▼
          Action Created
              │
              ▼
          Agent Resumes
              │
              ▼
          Final Response
```

This prevents the AI from autonomously performing state-changing operations.

---

# 🔐 Access Control

Security is enforced at the tool layer rather than relying only on the system prompt.

```text
Logged-in Customer
        │
        ▼
Session account_id
        │
        ▼
Tool Layer
        │
        ▼
Data filtered by account_id
```

For example:

```python
data.orders[
    data.orders["account_id"] == account_id
]
```

Therefore, the model cannot retrieve another customer's data simply by modifying its request.

---

# 📈 Internal Proactive Issue Detection

The application includes a separate staff-only dashboard.

Features include:

### 🚨 SLA Monitoring

Identifies:

- SLA breaches
- Tickets near SLA breach

### 🔗 Known Issue Clustering

Groups tickets related to known issues.

### 🔍 Historical Resolution Review

Flags closed tickets containing historical resolutions that may be outdated and should not be treated as current policy.

The dashboard is intentionally implemented without LLM calls because these tasks are deterministic and can be handled efficiently using structured data processing.

---

# 🏗️ System Architecture

```text
                     ┌─────────────────────┐
                     │      Customer       │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │    Streamlit UI     │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │   OpenRouter API    │
                     │        LLM          │
                     └──────────┬──────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │   Document   │ │  Structured  │ │    Action    │
        │    Search    │ │     Data     │ │   Proposal   │
        └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
               │                │                │
               ▼                ▼                ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │ TF-IDF Index │ │ Account Data │ │ Human Review │
        │   + Docs     │ │ Orders       │ │ Confirmation │
        └──────────────┘ │ Tickets      │ └──────────────┘
                         └──────────────┘
```

---

# 🔄 Complete Agent Workflow

The following shows how a typical request is processed.

```text
User Message
      │
      ▼
Store Message in Session
      │
      ▼
Send Request to OpenRouter LLM
      │
      ▼
Does the Model Need a Tool?
      │
   ┌──┴──┐
   │     │
  No    Yes
   │     │
   ▼     ▼
Answer  Execute Tool
          │
          ▼
    Send Tool Result
    Back to the Model
          │
          ▼
    Need Another Tool?
          │
       ┌──┴──┐
       │     │
      Yes    No
       │      │
       └──────┘
          │
          ▼
     Generate Response
          │
          ▼
       Display in UI
```

For state-changing actions:

```text
Tool Call
    │
    ▼
propose_action
    │
    ▼
Pause Agent Loop
    │
    ▼
Show Confirm / Cancel
    │
    ├──────────────► Cancel
    │                  │
    │                  ▼
    │             No Action
    │
    ▼
Confirm
    │
    ▼
execute_action()
    │
    ▼
Send Result to Agent
    │
    ▼
Final Response
```

---

# 📂 Project Structure

```text
ParcelPilot/
│
├── app.py
│   └── Streamlit application and UI
│       - Customer support chat
│       - Session management
│       - Account selection
│       - Human confirmation interface
│       - Internal insights dashboard
│
├── agent.py
│   └── OpenRouter agent loop
│       - LLM communication
│       - Tool calling
│       - Multi-step reasoning
│       - Pause/resume logic
│       - Human-in-the-loop workflow
│
├── tools.py
│   └── Agent tools
│       - Document search
│       - Structured data lookup
│       - Action proposal
│       - Access control enforcement
│
├── retrieval.py
│   └── TF-IDF document retrieval system
│
├── data_loader.py
│   └── Loads and prepares:
│       - Excel structured data
│       - PDF documents
│       - Dataset snapshot information
│
├── insights.py
│   └── Internal proactive issue detection
│       - SLA monitoring
│       - Known issue clustering
│       - Historical resolution review
│
├── data/
│   └── Supplied candidate data pack
│
├── requirements.txt
│   └── Project dependencies
│
├── .env.example
│   └── Example environment configuration
│
├── .gitignore
│   └── Prevents secrets and unnecessary files from being uploaded
│
├── ARCHITECTURE.md
│   └── Technical architecture and design decisions
│
├── PRODUCT.md
│   └── Product decisions, scope, and future improvements
│
└── README.md
    └── Project documentation
```

---

# 💻 Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application |
| Streamlit | Web interface |
| OpenRouter | LLM API provider |
| OpenAI Python SDK | OpenRouter-compatible API client |
| Pandas | Structured data processing |
| Scikit-learn | TF-IDF document retrieval |
| PDFPlumber | PDF text extraction |
| OpenPyXL | Excel file handling |

---

# ⚙️ Installation

Clone the repository:

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
```

Move into the project directory:

```bash
cd ParcelPilot
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 🔑 Environment Variables

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=your_openrouter_api_key

OPENROUTER_MODEL=openrouter/free
```

> ⚠️ Never commit your `.env` file or API key to GitHub.

The `.env` file should be included in `.gitignore`.

Example:

```gitignore
.env
__pycache__/
*.pyc
.venv/
venv/
```

---

# ▶️ Running the Application

Run:

```bash
streamlit run app.py
```

The application will open in your browser.

---

# 🧪 Example Queries

## Account Information

```text
What is my account information?
```

---

## Orders

```text
Show me all my orders.
```

Specific order:

```text
Give me complete details about order ORD-1001.
```

---

## Support Tickets

```text
Show me all my support tickets.
```

---

## Policy Retrieval

```text
What is the current cancellation policy?
```

Expected tool:

```text
search_documents
```

---

## Multi-Tool Reasoning

```text
I requested cancellation for ORD-1001.
Based on my account, order details, and the current cancellation policy,
what will happen to my cancellation request?
```

This may trigger both:

```text
structured_data_lookup
```

and:

```text
search_documents
```

---

## Human-in-the-Loop Action

```text
Please create a follow-up task for the ops team.
```

The system will stage the action and display:

```text
⚠️ Action awaiting your confirmation

[ Confirm ] [ Cancel ]
```

The action is only executed after explicit confirmation.

---

# 🧑‍💼 Internal Insights

Select:

```text
Internal Insights (staff only)
```

from the sidebar.

The dashboard provides:

- Open ticket SLA status
- Known issue clusters
- Historical resolution review queue

---

# 🔒 Security Considerations

- API keys are stored in environment variables.
- `.env` is excluded from version control.
- Customer data access is scoped at the tool layer.
- The model cannot directly query arbitrary accounts.
- State-changing actions require explicit user confirmation.
- Historical resolutions are treated as untrusted past context.
- Deprecated documents are not treated as current policy.

---

# 🚀 Deployment

The application can be deployed using **Streamlit Community Cloud**.

After pushing the project to GitHub:

1. Create a Streamlit Community Cloud account.
2. Connect your GitHub repository.
3. Select:

```text
Repository → Branch → app.py
```

4. Add your OpenRouter API key through Streamlit Secrets:

```toml
OPENROUTER_API_KEY = "your_openrouter_api_key"
OPENROUTER_MODEL = "openrouter/free"
```

5. Deploy the application.

---

# 🔮 Future Improvements

Possible future improvements include:

- Persistent user authentication
- Database-backed action storage
- Real ticketing system integration
- Vector database-based retrieval
- Better citation display for retrieved documents
- Conversation persistence
- Role-based access control
- Production-grade monitoring and logging
- Automated evaluation of agent responses
- Streaming responses

---

# 📄 Additional Documentation

For more details, see:

- `ARCHITECTURE.md` — System design and technical decisions
- `PRODUCT.md` — Product scope, trade-offs, and future improvements

---

## 👨‍💻 Author

Abhijeet Pandey

AI / ML & Data Science Enthusiast
