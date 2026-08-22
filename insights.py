"""
Problem 1: Proactive Issue Detection.

A lightweight, deterministic aggregation layer for the internal staff view --
no LLM call needed here, this is exactly the kind of thing plain aggregation
does better and more reliably than an agent. Flags:
  - SLA breaches / near-breaches on open tickets
  - Known-issue clustering (KI-208, KI-211)
  - Multiple open tickets on the same account
  - Tickets carrying a historical_resolution (needs human re-verification,
    since the assessment data shows these can be wrong)

SLA response targets below are transcribed once from the current policy
(01_Support_Policy_v3_CURRENT.pdf) and the two signed contracts, and are
used ONLY for this internal flagging view -- customer-facing answers still
go through the agent's document search, not this table, so a future policy
change only requires updating this one place, not the agent's reasoning.
"""
import pandas as pd

# minutes, keyed by (account_id, severity) for accounts with contract overrides,
# else falls back to (plan, severity) from the current policy defaults.
CONTRACT_SLA_MINUTES = {
    ("ACCT-001", "P1"): 15, ("ACCT-001", "P2"): 60, ("ACCT-001", "P3"): 8 * 60,
    ("ACCT-002", "P1"): 120, ("ACCT-002", "P2"): 240, ("ACCT-002", "P3"): 2 * 24 * 60,
}
PLAN_DEFAULT_SLA_MINUTES = {
    ("Enterprise", "P1"): 30, ("Enterprise", "P2"): 120, ("Enterprise", "P3"): 24 * 60,
    ("Growth", "P1"): 120, ("Growth", "P2"): 240, ("Growth", "P3"): 2 * 24 * 60,
    ("Standard", "P1"): 240, ("Standard", "P2"): 24 * 60, ("Standard", "P3"): 2 * 24 * 60,
}

KNOWN_ISSUE_KEYWORDS = {
    "KI-208 (Bulk Upload failures on large CSVs)": ["bulk upload", "csv", "upload"],
    "KI-211 (SwiftShip pickup webhook delay)": ["swiftship", "still shows booked", "webhook", "pickup"],
}

SEVERITY_KEYWORDS = {
    "P1": ["outage", "all shipment creation", "every user", "api key", "security", "credential"],
    "P2": ["fails", "failing", "not working", "unavailable", "degraded"],
}


def _classify_severity(subject: str, description: str) -> str:
    text = f"{subject} {description}".lower()
    for kw in SEVERITY_KEYWORDS["P1"]:
        if kw in text:
            return "P1"
    for kw in SEVERITY_KEYWORDS["P2"]:
        if kw in text:
            return "P2"
    return "P3"


def _sla_minutes(account_id: str, plan: str, severity: str) -> int | None:
    if (account_id, severity) in CONTRACT_SLA_MINUTES:
        return CONTRACT_SLA_MINUTES[(account_id, severity)]
    return PLAN_DEFAULT_SLA_MINUTES.get((plan, severity))


def build_ticket_insights(data) -> pd.DataFrame:
    tickets = data.tickets.merge(
        data.accounts, on="account_id", how="left", suffixes=("", "_account")
    )
    open_tickets = tickets[tickets["status"] == "open"].copy()

    rows = []
    for _, t in open_tickets.iterrows():
        severity = _classify_severity(t["subject"], t["description"])
        sla_minutes = _sla_minutes(t["account_id"], t["plan"], severity)
        age_minutes = (data.snapshot_time - t["created_at"]).total_seconds() / 60
        breached = sla_minutes is not None and age_minutes > sla_minutes
        near_breach = (
            sla_minutes is not None and not breached and age_minutes > 0.8 * sla_minutes
        )

        matched_issue = None
        text = f"{t['subject']} {t['description']}".lower()
        for issue, kws in KNOWN_ISSUE_KEYWORDS.items():
            if any(kw in text for kw in kws):
                matched_issue = issue
                break

        rows.append(
            {
                "ticket_id": t["ticket_id"],
                "account_id": t["account_id"],
                "account_name": t["account_name"],
                "subject": t["subject"],
                "inferred_severity": severity,
                "age_minutes": round(age_minutes, 1),
                "sla_target_minutes": sla_minutes,
                "sla_status": "BREACHED" if breached else ("NEAR BREACH" if near_breach else "OK"),
                "known_issue_match": matched_issue,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # flag accounts with more than one open ticket
    counts = df["account_id"].value_counts()
    df["multiple_open_tickets_same_account"] = df["account_id"].map(lambda a: counts[a] > 1)

    sort_key = {"BREACHED": 0, "NEAR BREACH": 1, "OK": 2}
    df["_sort"] = df["sla_status"].map(sort_key)
    df = df.sort_values("_sort").drop(columns="_sort").reset_index(drop=True)
    return df


def build_known_issue_clusters(insight_df: pd.DataFrame) -> pd.DataFrame:
    if insight_df.empty:
        return pd.DataFrame()
    clustered = insight_df[insight_df["known_issue_match"].notna()]
    if clustered.empty:
        return pd.DataFrame()
    summary = (
        clustered.groupby("known_issue_match")
        .agg(
            affected_tickets=("ticket_id", lambda s: ", ".join(s)),
            affected_accounts=("account_name", lambda s: ", ".join(sorted(set(s)))),
            ticket_count=("ticket_id", "count"),
        )
        .reset_index()
        .sort_values("ticket_count", ascending=False)
    )
    return summary


def historical_resolution_review_queue(data) -> pd.DataFrame:
    """Closed tickets whose historical_resolution text should be re-verified
    against current policy before anyone reuses it as guidance."""
    df = data.tickets[data.tickets["historical_resolution"].notna()].copy()
    if df.empty:
        return df
    return df[["ticket_id", "account_id", "subject", "historical_resolution"]]
