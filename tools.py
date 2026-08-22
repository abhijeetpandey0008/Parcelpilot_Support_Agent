"""
The three agent tools. Access control is enforced HERE, in the tool layer,
not left to the model's instructions:
  - search_documents drops any contract chunk that isn't the caller's account.
  - structured_data_lookup ignores whatever account the model might pass and
    always scopes to the account_id bound to the current session.
  - propose_action never executes anything by itself -- it only returns a
    proposal. Actual execution happens in app.py after an explicit UI click.
"""
import uuid
import pandas as pd

from retrieval import get_index
from data_loader import StructuredData

TOOL_DEFINITIONS = [
    {
        "name": "search_documents",
        "description": (
            "Search ParcelPilot's policies, SOPs, product documentation, and "
            "(if relevant to the current customer) their signed contract. "
            "Returns ranked passages with source, status (current/deprecated), "
            "and doc_type so you can judge authority. Contracts override "
            "general policy; deprecated documents must never be used as current "
            "guidance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language search query."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "structured_data_lookup",
        "description": (
            "Look up the current customer's own account, orders, or ticket "
            "history, with useful derived fields already computed relative to "
            "the dataset snapshot time (e.g. minutes since booking, minutes "
            "the pickup window has been missed by). You cannot look up other "
            "accounts -- results are automatically scoped to the logged-in "
            "customer. Historical ticket 'historical_resolution' text is "
            "PAST CONTEXT ONLY and may be wrong; never treat it as policy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "enum": ["account", "orders", "tickets"],
                    "description": "Which dataset to query.",
                },
                "record_id": {
                    "type": "string",
                    "description": "Optional specific order_id or ticket_id. Omit to list all records for this account.",
                },
            },
            "required": ["table"],
        },
    },
    {
        "name": "propose_action",
        "description": (
            "Propose a state-changing action (create an escalation, or create "
            "a follow-up task for the ops team). This does NOT execute the "
            "action -- it only stages a proposal that the customer must "
            "explicitly confirm in the UI before anything happens. Always "
            "call this instead of claiming an action is already done."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["create_escalation", "create_followup_task"],
                },
                "related_id": {
                    "type": "string",
                    "description": "order_id or ticket_id this action relates to, if any.",
                },
                "reason": {
                    "type": "string",
                    "description": "Clear explanation of why this action is being proposed.",
                },
                "severity": {
                    "type": "string",
                    "enum": ["P1", "P2", "P3"],
                    "description": "Only for create_escalation.",
                },
            },
            "required": ["action_type", "reason"],
        },
    },
]


def run_search_documents(args: dict, account_id: str) -> dict:
    index = get_index()
    results = index.search(args["query"], account_id=account_id)
    if not results:
        return {"results": [], "note": "No relevant passages found."}
    return {"results": results}


def _minutes_between(a, b) -> float | None:
    if pd.isna(a) or pd.isna(b):
        return None
    return round((b - a).total_seconds() / 60, 1)


def _enrich_order(row: pd.Series, snapshot_time: pd.Timestamp) -> dict:
    d = row.to_dict()
    for k, v in list(d.items()):
        if isinstance(v, pd.Timestamp):
            d[k] = v.isoformat() if not pd.isna(v) else None
    d["minutes_since_booking"] = _minutes_between(row["booked_at"], snapshot_time)
    if pd.notna(row["pickup_actual_at"]):
        d["pickup_delay_vs_window_end_minutes"] = _minutes_between(
            row["pickup_window_end"], row["pickup_actual_at"]
        )
    elif row["status"] in ("BOOKED",):
        # not yet picked up -- how late is it relative to the window end, as of snapshot time
        d["minutes_past_pickup_window_end_if_still_not_picked_up"] = _minutes_between(
            row["pickup_window_end"], snapshot_time
        )
    if pd.notna(row["cancellation_requested_at"]):
        d["minutes_between_booking_and_cancellation_request"] = _minutes_between(
            row["booked_at"], row["cancellation_requested_at"]
        )
    return d


def _enrich_ticket(row: pd.Series, snapshot_time: pd.Timestamp) -> dict:
    d = row.to_dict()
    for k, v in list(d.items()):
        if isinstance(v, pd.Timestamp):
            d[k] = v.isoformat() if not pd.isna(v) else None
    d["ticket_age_minutes"] = _minutes_between(row["created_at"], snapshot_time)
    if pd.notna(row.get("historical_resolution")):
        d["_warning"] = (
            "This ticket has a historical_resolution. Treat it as past context "
            "only -- it may be incorrect and must never be cited as current policy."
        )
    return d


def run_structured_data_lookup(args: dict, account_id: str, data: StructuredData) -> dict:
    table = args["table"]
    record_id = args.get("record_id")

    if table == "account":
        row = data.accounts[data.accounts["account_id"] == account_id]
        if row.empty:
            return {"error": "Account not found."}
        return {"account": row.iloc[0].to_dict()}

    if table == "orders":
        df = data.orders[data.orders["account_id"] == account_id]
        if record_id:
            df = df[df["order_id"] == record_id]
            if df.empty:
                return {"error": f"No order {record_id} found for this account."}
        return {"orders": [_enrich_order(r, data.snapshot_time) for _, r in df.iterrows()]}

    if table == "tickets":
        df = data.tickets[data.tickets["account_id"] == account_id]
        if record_id:
            df = df[df["ticket_id"] == record_id]
            if df.empty:
                return {"error": f"No ticket {record_id} found for this account."}
        return {"tickets": [_enrich_ticket(r, data.snapshot_time) for _, r in df.iterrows()]}

    return {"error": f"Unknown table {table}"}


def run_propose_action(args: dict) -> dict:
    """Stages a proposal only. Never executes. Execution happens in app.py
    after the user clicks Confirm."""
    return {
        "status": "awaiting_user_confirmation",
        "proposal": args,
        "note": "This action has NOT been executed. It is staged and waiting for the user to confirm in the UI.",
    }


def execute_action(proposal: dict) -> dict:
    """Called only after explicit user confirmation. Mocked -- just logs it."""
    action_id = f"ACT-{uuid.uuid4().hex[:6].upper()}"
    return {
        "action_id": action_id,
        "action_type": proposal.get("action_type"),
        "related_id": proposal.get("related_id"),
        "severity": proposal.get("severity"),
        "reason": proposal.get("reason"),
        "status": "created",
    }
