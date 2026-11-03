"""Routes for the browser chat fallback page."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["web"])
CHAT_PAGE = Path(__file__).with_name("chat.html")


@router.get("/chat", response_class=HTMLResponse, include_in_schema=False)
def chat_page() -> HTMLResponse:
    """Serve the single-file browser chat interface."""

    return HTMLResponse(CHAT_PAGE.read_text(encoding="utf-8"))
