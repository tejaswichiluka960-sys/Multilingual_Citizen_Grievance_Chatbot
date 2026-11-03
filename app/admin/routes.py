"""Minimal officer dashboard for ticket queues and status updates."""

import html
from collections.abc import Sequence

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Department, Ticket
from app.security import require_admin
from app.services import tickets as ticket_service

router = APIRouter(tags=["admin"])


def _option(value: str, label: str, selected: str | None) -> str:
    """Render one escaped select option."""

    selected_attr = " selected" if value == (selected or "") else ""
    return f'<option value="{html.escape(value)}"{selected_attr}>{html.escape(label)}</option>'


def _ticket_row(ticket: Ticket, statuses: Sequence[str]) -> str:
    """Render one ticket queue row with a status update form."""

    code = html.escape(ticket.ticket_code)
    department = html.escape(ticket.department.name if ticket.department else "Unassigned")
    original = html.escape(ticket.original_text)
    translated = html.escape(ticket.translated_text or "Not available")
    status_options = "".join(_option(item, item, ticket.status) for item in statuses)
    return f"""
      <article class="ticket-card">
        <div class="ticket-header">
          <strong>{code}</strong>
          <span class="status">{html.escape(ticket.status)}</span>
        </div>
        <p><b>Department:</b> {department}</p>
        <p><b>Priority:</b> {html.escape(ticket.priority)} · <b>Language:</b> {html.escape(ticket.language)}</p>
        <details><summary>Complaint and officer translation</summary>
          <p><b>Original:</b> {original}</p>
          <p><b>English summary:</b> {translated}</p>
        </details>
        <form method="post" action="/admin/tickets/{code}/status" class="update-form">
          <label>Status
            <select name="new_status">{status_options}</select>
          </label>
          <label>Officer note
            <input name="note" maxlength="5000" placeholder="Add an update note" />
          </label>
          <button type="submit">Update ticket</button>
        </form>
      </article>
    """


def render_admin_dashboard(
    tickets: Sequence[Ticket],
    departments: Sequence[Department],
    *,
    selected_department: str | None = None,
    selected_status: str | None = None,
    message: str | None = None,
) -> HTMLResponse:
    """Render the self-contained officer dashboard HTML."""

    department_options = _option("", "All departments", selected_department)
    department_options += "".join(
        _option(department.code, f"{department.code} — {department.name}", selected_department)
        for department in departments
    )
    statuses = ("NEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "ESCALATED", "CLOSED", "REOPENED")
    status_options = _option("", "All statuses", selected_status)
    status_options += "".join(_option(item, item, selected_status) for item in statuses)
    cards = "".join(_ticket_row(ticket, statuses) for ticket in tickets)
    if not cards:
        cards = '<p class="empty">No tickets match the selected filters.</p>'
    notice = f'<div class="notice">{html.escape(message)}</div>' if message else ""
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Citizen Grievance — Officer Dashboard</title>
  <style>
    :root {{ color-scheme: light; font-family: Segoe UI, Arial, sans-serif; }}
    body {{ margin: 0; background: #f5f7fb; color: #172033; }}
    header {{ background: #d90445; color: white; padding: 22px 6vw; }}
    main {{ max-width: 1100px; margin: 24px auto; padding: 0 20px 40px; }}
    .filters, .ticket-card {{ background: white; border-radius: 12px; box-shadow: 0 3px 14px #17203318; }}
    .filters {{ display: flex; flex-wrap: wrap; gap: 12px; padding: 16px; margin-bottom: 18px; }}
    label {{ display: flex; flex-direction: column; gap: 5px; font-size: .9rem; font-weight: 600; }}
    select, input, button {{ border: 1px solid #c9d0dc; border-radius: 7px; padding: 9px 10px; font: inherit; }}
    button {{ background: #d90445; color: white; border: 0; cursor: pointer; font-weight: 700; }}
    .ticket-card {{ padding: 18px; margin: 14px 0; }}
    .ticket-header {{ display: flex; justify-content: space-between; gap: 12px; }}
    .status {{ color: #d90445; font-weight: 700; }}
    .update-form {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: end; margin-top: 14px; }}
    .notice {{ border-left: 4px solid #16803c; background: #e8f7ed; padding: 10px 14px; margin-bottom: 16px; }}
    .empty {{ background: white; padding: 22px; border-radius: 12px; }}
    summary {{ cursor: pointer; color: #40506b; }}
  </style>
</head>
<body>
  <header><h1>Officer Dashboard</h1><p>Department queue and grievance status management</p></header>
  <main>
    {notice}
    <form method="get" action="/admin" class="filters">
      <label>Department<select name="department">{department_options}</select></label>
      <label>Status<select name="status">{status_options}</select></label>
      <button type="submit">Apply filters</button>
    </form>
    <p><b>{len(tickets)}</b> ticket(s) shown</p>
    {cards}
  </main>
</body>
</html>"""
    return HTMLResponse(document)


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    department: str | None = Query(default=None, min_length=1),
    status_value: str | None = Query(default=None, alias="status", min_length=1),
    message: str | None = Query(default=None),
    admin_user: str = Depends(require_admin),
    db: Session = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Show the filtered officer ticket queue."""

    departments = list(db.scalars(select(Department).order_by(Department.code)).all())
    department_id = None
    normalized_department = department.strip().upper() if department else None
    if normalized_department:
        record = db.scalar(select(Department).where(Department.code == normalized_department))
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        department_id = record.id
    try:
        tickets = ticket_service.list_tickets(db, department_id=department_id, status=status_value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return render_admin_dashboard(
        tickets,
        departments,
        selected_department=normalized_department,
        selected_status=status_value.upper() if status_value else None,
        message=message,
    )


@router.post("/admin/tickets/{ticket_code}/status")
def update_admin_ticket_status(
    ticket_code: str,
    new_status: str = Form(...),
    note: str = Form(default=""),
    admin_user: str = Depends(require_admin),
    db: Session = Depends(get_db),  # noqa: B008
) -> RedirectResponse:
    """Apply an officer status update and return to the dashboard."""

    try:
        ticket_service.update_ticket_status(
            db,
            ticket_code=ticket_code,
            new_status=new_status,
            actor=admin_user,
            note=note.strip() or None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url="/admin?message=Ticket+updated+successfully", status_code=status.HTTP_303_SEE_OTHER)
