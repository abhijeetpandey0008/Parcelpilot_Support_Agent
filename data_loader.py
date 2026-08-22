"""
Loads the raw ParcelPilot data pack (PDFs + xlsx) into structures the rest
of the app can use. Nothing here is hardcoded from the documents' content
-- everything is parsed at runtime from the files in data/.
"""
import re
import pandas as pd
import pdfplumber
from pathlib import Path
from dataclasses import dataclass, field

DATA_DIR = Path(__file__).parent / "data"

# Metadata about each document that the RETRIEVAL LAYER needs in order to
# reason about authority/freshness. This is describing the files (which
# ones are current vs deprecated, which belong to which account), not the
# content of the policies themselves -- that's still read from the PDFs.
DOCUMENT_REGISTRY = [
    {
        "file": "01_Support_Policy_v3_CURRENT.pdf",
        "doc_type": "policy",
        "status": "current",
        "account_id": None,
        "title": "Support Policy v3 (current)",
    },
    {
        "file": "02_Support_Policy_v2_DEPRECATED.pdf",
        "doc_type": "policy",
        "status": "deprecated",
        "account_id": None,
        "title": "Support Policy v2 (deprecated)",
    },
    {
        "file": "03_Cancellation_and_Service_Credit_SOP_v4.pdf",
        "doc_type": "sop",
        "status": "current",
        "account_id": None,
        "title": "Cancellation & Service Credit SOP v4 (current)",
    },
    {
        "file": "04_Product_Operations_Guide_and_Known_Issues.pdf",
        "doc_type": "product_doc",
        "status": "current",
        "account_id": None,
        "title": "Product Operations Guide & Known Issues (current)",
    },
    {
        "file": "05_Northstar_Logistics_Enterprise_Agreement.pdf",
        "doc_type": "contract",
        "status": "current",
        "account_id": "ACCT-001",
        "title": "Northstar Logistics Enterprise Agreement",
    },
    {
        "file": "06_LumenWorks_Service_Agreement.pdf",
        "doc_type": "contract",
        "status": "current",
        "account_id": "ACCT-002",
        "title": "LumenWorks Service Agreement",
    },
]

# Source-reliability ranking used by the retriever & the agent's system
# prompt. Lower number = higher authority when sources conflict.
AUTHORITY_RANK = {
    "contract": 0,
    "sop": 1,
    "policy": 1,
    "product_doc": 2,
}


@dataclass
class Chunk:
    text: str
    title: str
    doc_type: str
    status: str
    account_id: str | None
    section: str


def _extract_pdf_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split a document on numbered section headers (e.g. '2. Severity definitions').
    Falls back to the whole document as one section if no headers are found."""
    pattern = re.compile(r"\n(?=\d+\.\s+[A-Z])")
    parts = pattern.split(text)
    sections = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        first_line = part.split("\n")[0].strip()
        sections.append((first_line, part))
    if not sections:
        sections = [("Full document", text)]
    return sections


def load_document_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    for entry in DOCUMENT_REGISTRY:
        path = DATA_DIR / entry["file"]
        raw_text = _extract_pdf_text(path)
        for section_title, section_text in _split_into_sections(raw_text):
            chunks.append(
                Chunk(
                    text=section_text,
                    title=entry["title"],
                    doc_type=entry["doc_type"],
                    status=entry["status"],
                    account_id=entry["account_id"],
                    section=section_title,
                )
            )
    return chunks


@dataclass
class StructuredData:
    snapshot_time: pd.Timestamp
    accounts: pd.DataFrame
    orders: pd.DataFrame
    tickets: pd.DataFrame


def load_structured_data() -> StructuredData:
    xlsx_path = DATA_DIR / "ParcelPilot_Assessment_Data.xlsx"
    readme = pd.read_excel(xlsx_path, sheet_name="README", header=None)
    snapshot_row = readme[readme[0] == "Dataset snapshot"]
    snapshot_str = str(snapshot_row.iloc[0, 1])
    # format is "YYYY-MM-DD HH:MM Asia/Kolkata" -- strip the tz name, all
    # timestamps in the workbook are naive in the same zone so we just
    # compare them as naive datetimes throughout.
    snapshot_str = re.sub(r"\s+[A-Za-z]+/[A-Za-z_]+$", "", snapshot_str).strip()
    snapshot_time = pd.to_datetime(snapshot_str)

    accounts = pd.read_excel(xlsx_path, sheet_name="accounts")
    orders = pd.read_excel(xlsx_path, sheet_name="orders")
    tickets = pd.read_excel(xlsx_path, sheet_name="tickets")

    for col in ["booked_at", "pickup_window_start", "pickup_window_end",
                "pickup_actual_at", "cancellation_requested_at"]:
        orders[col] = pd.to_datetime(orders[col], errors="coerce")
    for col in ["created_at", "last_customer_message_at"]:
        tickets[col] = pd.to_datetime(tickets[col], errors="coerce")

    return StructuredData(
        snapshot_time=snapshot_time,
        accounts=accounts,
        orders=orders,
        tickets=tickets,
    )
