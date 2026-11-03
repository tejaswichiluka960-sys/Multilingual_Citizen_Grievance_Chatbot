from html import escape
from pathlib import Path

from docx import Document
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, LongTable, PageTemplate, Paragraph, Spacer, TableStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics


DOCX_PATH = Path("Multilingual_Citizen_Grievance_Chatbot_Execution_Plan.docx")
PDF_PATH = Path("Multilingual_Citizen_Grievance_Chatbot_Execution_Plan.pdf")


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawCentredString(
        LETTER[0] / 2,
        0.38 * inch,
        f"HI-02  |  Multilingual Citizen Grievance Chatbot  |  Page {doc.page}",
    )
    canvas.restoreState()


def doc_children(document):
    parent = document.element.body
    for child in parent.iterchildren():
        if child.tag.endswith("}p"):
            yield DocxParagraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield DocxTable(child, document)


def para_text(p):
    text = p.text.strip()
    return text


def paragraph_markup(text):
    safe = escape(text)
    return safe.replace(" -> ", " &rarr; ")


def build_pdf():
    source = Document(DOCX_PATH)
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "PlanBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=12.2,
        spaceAfter=5,
        textColor=colors.HexColor("#1F1F1F"),
    )
    title = ParagraphStyle(
        "PlanTitle",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=27,
        spaceAfter=6,
        textColor=colors.black,
    )
    subtitle = ParagraphStyle(
        "PlanSubtitle",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=16,
        spaceAfter=13,
        textColor=colors.HexColor("#1F4E78"),
    )
    h1 = ParagraphStyle(
        "PlanH1",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True,
        textColor=colors.black,
    )
    h2 = ParagraphStyle(
        "PlanH2",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True,
        textColor=colors.black,
    )
    bullet = ParagraphStyle(
        "PlanBullet",
        parent=body,
        leftIndent=14,
        firstLineIndent=-8,
        bulletIndent=0,
        spaceAfter=2.5,
    )
    small = ParagraphStyle(
        "PlanTable",
        parent=body,
        fontSize=7.7,
        leading=9.4,
        spaceAfter=0,
    )
    small_header = ParagraphStyle(
        "PlanTableHeader",
        parent=small,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    story = []
    seen_title = False
    for item in doc_children(source):
        if isinstance(item, DocxParagraph):
            text = para_text(item)
            if not text:
                continue
            style_name = item.style.name if item.style else ""
            if style_name == "Title":
                story.append(Paragraph(paragraph_markup(text), title))
                seen_title = True
            elif seen_title and text == "Complete Execution Plan and Technical Scope":
                story.append(Paragraph(paragraph_markup(text), subtitle))
            elif style_name == "Heading 1":
                story.append(Paragraph(paragraph_markup(text), h1))
            elif style_name in ("Heading 2", "Heading 3"):
                story.append(Paragraph(paragraph_markup(text), h2))
            elif style_name.startswith("List Bullet"):
                story.append(Paragraph("&bull;&nbsp;&nbsp;" + paragraph_markup(text), bullet))
            elif style_name == "List Number":
                story.append(Paragraph(paragraph_markup(text), bullet))
            else:
                story.append(Paragraph(paragraph_markup(text), body))
        elif isinstance(item, DocxTable):
            data = []
            for row_idx, row in enumerate(item.rows):
                cells = []
                for cell in row.cells:
                    txt = cell.text.strip().replace("\n", "<br/>")
                    cells.append(Paragraph(escape(txt).replace("&lt;br/&gt;", "<br/>"), small_header if row_idx == 0 else small))
                data.append(cells)
            if not data:
                continue
            ncols = len(data[0])
            avail = 7.0 * inch
            if ncols == 2:
                widths = [1.55 * inch, 5.45 * inch]
            elif ncols == 3:
                widths = [1.25 * inch, 4.55 * inch, 1.2 * inch]
            else:
                widths = [avail / ncols] * ncols
            table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
            commands = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9D9D9")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
            for r_idx in range(1, len(data)):
                if r_idx % 2 == 0:
                    commands.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F3F8FC")))
            table.setStyle(TableStyle(commands))
            story.append(Spacer(1, 3))
            story.append(table)
            story.append(Spacer(1, 6))

    doc = BaseDocTemplate(
        str(PDF_PATH),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.62 * inch,
        title="Multilingual Citizen Grievance Chatbot Execution Plan",
        author="Codex",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="plan", frames=frame, onPage=add_page_number)])
    doc.build(story)
    print(PDF_PATH)


if __name__ == "__main__":
    build_pdf()
