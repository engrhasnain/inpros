"""Single source of truth for report header data, with checks before any report is generated."""

import re

from app.models import Project

REQUIRED = {
    "contract_number": "Contract number",
    "client": "Client",
    "contractor": "Contractor",
    "scope": "Scope of work",
    "supervisor_name": "Prepared by (name)",
    "supervisor_title": "Prepared by (title)",
    "approver_name": "Approved by (name)",
    "approver_title": "Approved by (title)",
}


def report_readiness(p: Project) -> dict:
    missing = [label for field, label in REQUIRED.items() if not (getattr(p, field) or "").strip()]
    problems = []
    cn = (p.contract_number or "").strip()
    if cn and not re.search(r"\d", cn):
        problems.append("Contract number has no digits — check it.")
    if p.supervisor_name and p.approver_name and p.supervisor_name.strip().lower() == p.approver_name.strip().lower():
        problems.append("The same person prepares and approves — reports need two different signatories.")
    return {"ready": not missing and not problems, "missing": missing, "problems": problems}


def header(p: Project) -> dict:
    return {
        "project": p.name,
        "client": p.client or "",
        "location": p.location or "",
        "contract_number": p.contract_number or "",
        "contractor": p.contractor or "",
        "scope": p.scope or "",
        "supervisor_name": p.supervisor_name or "",
        "supervisor_title": p.supervisor_title or "",
        "approver_name": p.approver_name or "",
        "approver_title": p.approver_title or "",
    }
