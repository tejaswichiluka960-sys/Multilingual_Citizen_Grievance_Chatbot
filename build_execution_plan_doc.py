from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUT = "Multilingual_Citizen_Grievance_Chatbot_Execution_Plan.docx"

NAVY = "1F4E78"
BLUE = "D9EAF7"
PALE_BLUE = "F3F8FC"
GRAY = "D9D9D9"
TEXT = RGBColor(31, 31, 31)


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=90, start=110, bottom=90, end=110):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table, color=GRAY, size="6"):
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_col_widths(table, widths):
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = Inches(width)


def add_hyperlink(paragraph, text, url):
    part = paragraph.part
    rid = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    r_pr.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    r_pr.append(underline)
    run.append(r_pr)
    text_node = OxmlElement("w:t")
    text_node.text = text
    run.append(text_node)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    p.paragraph_format.space_after = Pt(3)
    p.add_run(text)
    return p


def add_number(doc, text):
    p = doc.add_paragraph(style="List Number")
    p.paragraph_format.space_after = Pt(3)
    p.add_run(text)
    return p


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)
    header = table.rows[0]
    set_repeat_table_header(header)
    for idx, value in enumerate(headers):
        cell = header.cells[idx]
        cell.text = value
        set_cell_shading(cell, NAVY)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_margins(cell)
        for p in cell.paragraphs:
            p.paragraph_format.space_after = Pt(0)
            for run in p.runs:
                run.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.font.size = Pt(9)
    for r_idx, row_data in enumerate(rows):
        row = table.add_row()
        for c_idx, value in enumerate(row_data):
            cell = row.cells[c_idx]
            cell.text = str(value)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            if r_idx % 2 == 1:
                set_cell_shading(cell, PALE_BLUE)
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.05
                for run in p.runs:
                    run.font.size = Pt(8.5)
                    run.font.color.rgb = TEXT
    if widths:
        set_col_widths(table, widths)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def add_section_heading(doc, text, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    p.add_run(text)
    return p


def add_body(doc, text, bold_lead=None):
    p = doc.add_paragraph(style="Body Text")
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.12
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        r.bold = True
        p.add_run(text[len(bold_lead):])
    else:
        p.add_run(text)
    return p


def add_page_break(doc):
    p = doc.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)


def configure_styles(doc):
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Aptos"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Aptos")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Aptos")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = TEXT

    body = styles["Body Text"]
    body.font.name = "Aptos"
    body._element.rPr.rFonts.set(qn("w:ascii"), "Aptos")
    body._element.rPr.rFonts.set(qn("w:hAnsi"), "Aptos")
    body.font.size = Pt(10.5)
    body.font.color.rgb = TEXT

    title = styles["Title"]
    title.font.name = "Aptos Display"
    title._element.rPr.rFonts.set(qn("w:ascii"), "Aptos Display")
    title._element.rPr.rFonts.set(qn("w:hAnsi"), "Aptos Display")
    title.font.size = Pt(24)
    title.font.bold = True
    title.font.color.rgb = RGBColor(0, 0, 0)
    title.paragraph_format.space_after = Pt(8)

    for name, size in (("Heading 1", 16), ("Heading 2", 12.5), ("Heading 3", 11)):
        style = styles[name]
        style.font.name = "Aptos Display"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Aptos Display")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Aptos Display")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(12 if name == "Heading 1" else 8)
        style.paragraph_format.space_after = Pt(5)
        style.paragraph_format.keep_with_next = True

    for name in ("List Bullet", "List Bullet 2", "List Number"):
        style = styles[name]
        style.font.name = "Aptos"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Aptos")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Aptos")
        style.font.size = Pt(10.5)
        style.font.color.rgb = TEXT


def build_document():
    doc = Document()
    configure_styles(doc)
    section = doc.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run("HI-02  |  Multilingual Citizen Grievance Chatbot  |  Execution Plan")
    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = RGBColor(100, 100, 100)

    title = doc.add_paragraph(style="Title")
    title.add_run("Multilingual Citizen Grievance Chatbot")
    subtitle = doc.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(14)
    r = subtitle.add_run("Complete Execution Plan and Technical Scope")
    r.bold = True
    r.font.size = Pt(13)
    r.font.color.rgb = RGBColor(31, 78, 121)

    add_body(doc, "This document defines the complete development plan for HI-02: a multilingual citizen grievance chatbot that accepts complaints in Indian languages, identifies the correct department, creates and routes tickets, tracks resolution status, and notifies citizens. It incorporates the requirements in the supplied project brief and hackathon guide, including Hugging Face models, LangChain orchestration, Whisper voice input, FastAPI, PostgreSQL, Telegram, web fallback, admin operations, escalation, evaluation and data preparation.")
    add_body(doc, "The implementation will be delivered in working stages. The text-based MVP is the first release target; voice, analytics and additional integrations will be added only after the complete ticketing and status workflow is stable.", bold_lead="Delivery principle: ")

    add_section_heading(doc, "1 Project objective")
    add_body(doc, "Build an inclusive grievance intake and tracking system for citizens who prefer regional Indian languages. The system must accept text and voice complaints, understand code-mixed language, classify each complaint, route it to the appropriate department, create a traceable ticket, and keep the citizen informed until resolution.")

    add_section_heading(doc, "2 Requirements covered")
    add_table(doc, ["Requirement", "Planned implementation", "Priority"], [
        ("Hugging Face", "Use multilingual transformer models and embeddings for language-aware classification and translation.", "Core"),
        ("LangChain", "Use for conversation orchestration, clarification prompts and optional LLM provider integration. Core ticket logic remains deterministic.", "Core integration"),
        ("Whisper voice", "Transcribe Telegram voice notes using Whisper or faster-whisper, then send the transcript through the same NLP pipeline.", "Phase 8"),
        ("FastAPI", "Backend APIs, web chat endpoint, ticket service, admin endpoints and health checks.", "Core"),
        ("PostgreSQL", "Primary production database for users, tickets, departments, events, notifications and audit records.", "Core"),
        ("Telegram", "Primary citizen-facing chatbot with language selection, complaint intake, status lookup and notifications.", "Core"),
        ("Data ideas", "Synthetic multilingual complaints, AI4Bharat resources, public grievance categories and handwritten evaluation data.", "Core"),
    ], widths=[1.25, 4.8, 1.0])

    add_section_heading(doc, "3 Supported languages and complaint types")
    add_bullet(doc, "English, Hindi and Telugu as the initial supported languages.")
    add_bullet(doc, "Hinglish and Tenglish code-mixed messages written in Roman script.")
    add_bullet(doc, "Automatic script and language detection with user confirmation when confidence is low.")
    add_bullet(doc, "Text complaints in the MVP and voice complaints through Whisper in the voice phase.")
    add_bullet(doc, "Optional location or landmark capture to help departments act on the complaint.")

    add_section_heading(doc, "4 End to end system flow")
    add_body(doc, "Citizen message -> language and script detection -> voice transcription when required -> text normalization -> Hugging Face multilingual classification -> LangChain conversation decision -> clarification if confidence is low -> translation or English summary for officers -> ticket creation -> department routing -> officer status update -> citizen notification -> SLA monitoring and escalation.")
    add_body(doc, "Classification will use the original multilingual complaint whenever possible. Translation will be used to provide an officer-facing summary and localized responses, preventing translation errors from becoming the only source of classification information.")

    add_section_heading(doc, "5 Technology architecture")
    add_table(doc, ["Layer", "Technology", "Purpose"], [
        ("Citizen interfaces", "Telegram Bot API and responsive web chat", "Complaint submission, language selection, ticket lookup and notifications."),
        ("API backend", "FastAPI and Pydantic", "REST endpoints, validation, authentication boundaries and service integration."),
        ("Conversation layer", "LangChain with deterministic Python state machine", "Conversation memory, clarification flow and optional LLM-assisted prompts."),
        ("Language and ML", "Hugging Face Transformers, sentence-transformers, MuRIL/IndicBERT or multilingual-e5", "Language-aware embeddings, department prediction, priority prediction and confidence scoring."),
        ("Translation", "IndicTrans2 adapter with configured fallback", "Officer summaries and citizen responses in supported languages."),
        ("Voice", "Whisper or faster-whisper", "Speech-to-text for Telegram voice messages."),
        ("Database", "PostgreSQL with SQLAlchemy", "Persistent tickets, users, departments, events, notifications and audit history."),
        ("Local fallback", "SQLite", "Simple offline setup and reliable demonstration mode."),
        ("Operations", "APScheduler initially; separate worker option for production", "SLA checks, escalation and notification delivery."),
        ("Deployment", "Docker Compose initially", "Repeatable local and demo deployment."),
    ], widths=[1.25, 2.25, 3.55])

    add_section_heading(doc, "6 Functional modules")
    modules = [
        ("6.1 Language detection", ["Detect Devanagari Hindi, Telugu script and Roman-script English/Hinglish/Tenglish.", "Mark code-mixed messages and allow manual language correction.", "Handle empty, emoji-only, gibberish and unsupported-language inputs gracefully."]),
        ("6.2 Voice intake", ["Receive Telegram voice notes.", "Transcribe them with Whisper or faster-whisper.", "Show the transcript for confirmation before filing when confidence is low.", "Preserve the transcript and original message metadata according to privacy settings."]),
        ("6.3 Complaint classification", ["Predict department, intent and priority.", "Return confidence and model version.", "Use keyword rules for urgent cases and model failures.", "Ask a department clarification question below the confidence threshold."]),
        ("6.4 Translation and summaries", ["Use IndicTrans2 through a lazy-loaded adapter.", "Cache translations.", "Keep original complaint text unchanged.", "Display an officer-facing English summary and localized citizen responses."]),
        ("6.5 Ticket management", ["Generate unique IDs such as GRV-2026-000123.", "Create, assign, update, resolve, close and reopen tickets.", "Record every status change as an event.", "Support department and priority filtering."]),
        ("6.6 Citizen experience", ["Language selection through /start.", "Complaint submission and confirmation.", "Ticket ID response.", "Status lookup and recent ticket history.", "Localized notifications and help/cancel commands."]),
        ("6.7 Admin operations", ["Secure officer login.", "Department queue, filters and search.", "Ticket detail page with original text, translation, confidence and event history.", "Status update, officer note and escalation visibility."]),
        ("6.8 SLA and escalation", ["Department-specific SLA hours.", "High-priority SLA reduction.", "Automatic escalation for overdue unresolved tickets.", "Escalation events and citizen notification.", "Demo mode with one- or two-minute SLAs."]),
    ]
    for heading, bullets in modules:
        add_section_heading(doc, heading, level=2)
        for item in bullets:
            add_bullet(doc, item)

    add_section_heading(doc, "7 Department categories")
    add_table(doc, ["Code", "Department", "Example complaints"], [
        ("WATER", "Water Supply and Sewerage", "Leaks, no water, drainage and sewage overflow."),
        ("POWER", "Electricity", "Power outage, damaged poles, exposed wires and billing issues."),
        ("ROADS", "Roads and Infrastructure", "Potholes, broken roads, traffic signals and streetlights."),
        ("SANITATION", "Sanitation and Solid Waste", "Garbage collection, dumping and public cleanliness."),
        ("POLICE", "Police and Public Safety", "Harassment, threats, accidents and urgent safety issues."),
        ("HEALTH", "Health", "Public health facilities, sanitation risks and emergency concerns."),
        ("EDUCATION", "Education", "School services, certificates and public education facilities."),
        ("TRANSPORT", "Transport", "Bus services, permits, road transport and public transit."),
        ("REVENUE", "Revenue, Land and Certificates", "Land records, certificates and civic documentation."),
        ("OTHER", "Other or Human Review", "Low-confidence, cross-department or unsupported complaints."),
    ], widths=[1.0, 2.0, 4.05])

    add_section_heading(doc, "8 Data plan")
    add_body(doc, "The initial model will use a structured multilingual complaint corpus. Synthetic data is appropriate for the hackathon prototype, but results will be reported separately for generated data and realistic handwritten test messages. Public resources will be used only after checking their license and attribution requirements.")
    add_table(doc, ["Data source", "Planned use", "Controls"], [
        ("Synthetic complaint corpus", "60-100 examples per department across English, Hindi, Telugu, Hinglish and Tenglish.", "Deduplicate, balance classes and hold out a test split."),
        ("Handwritten evaluation set", "30-40 realistic, messy complaints for demo and robustness testing.", "Keep separate from training data."),
        ("AI4Bharat datasets", "Translation and multilingual NLU references such as Samanantar, IN22 and IndicXNLI.", "Check dataset license and cite sources."),
        ("Public grievance categories", "Department names, intents and example category structure.", "Use only permitted text; do not copy protected personal information."),
        ("Hugging Face models", "MuRIL, IndicBERT, multilingual-e5 and IndicTrans2 components.", "Record exact model names, versions and licenses."),
    ], widths=[1.55, 3.55, 1.95])
    add_body(doc, "Each record will contain text, language, department, intent and priority. The evaluation script will produce macro-F1, accuracy, per-language results, a confusion matrix and the percentage of messages sent to clarification.")

    add_section_heading(doc, "9 Database design")
    add_table(doc, ["Entity", "Important fields"], [
        ("users", "id, Telegram ID, name, preferred language, created_at"),
        ("departments", "id, name, SLA hours, escalation contact, active"),
        ("tickets", "id, ticket code, user, original text, language, summary, department, intent, priority, confidence, status, location, SLA deadline, escalation level, timestamps"),
        ("ticket_events", "ticket, old status, new status, note, actor, created_at"),
        ("notifications", "ticket, channel, recipient, language, message, delivery status, sent_at"),
        ("admin_users", "id, username, password hash, role, department, active"),
        ("audit_logs", "actor, action, resource, metadata, timestamp"),
    ], widths=[1.45, 5.6])

    add_section_heading(doc, "10 API scope")
    add_table(doc, ["Method", "Endpoint", "Purpose"], [
        ("GET", "/health", "Service health and dependency status."),
        ("POST", "/chat", "Process a web chat message and return the next response."),
        ("POST", "/tickets", "Create a ticket after classification and confirmation."),
        ("GET", "/tickets/{code}", "Return ticket status, department and latest update."),
        ("PATCH", "/tickets/{code}/status", "Update status, add note and create an event."),
        ("GET", "/admin/tickets", "List tickets by department, status, priority or search term."),
        ("POST", "/classify", "Debug endpoint for language, department, intent, priority and confidence."),
        ("POST", "/voice/transcribe", "Transcribe an uploaded voice message when voice support is enabled."),
    ], widths=[0.7, 2.25, 4.1])

    add_section_heading(doc, "11 Delivery phases")
    add_table(doc, ["Phase", "Work", "Output"], [
        ("1", "Inspect workspace, lock scope, create project guide and environment configuration.", "Runnable repository skeleton."),
        ("2", "FastAPI, SQLAlchemy, PostgreSQL/SQLite configuration, models and health endpoint.", "Backend foundation."),
        ("3", "Ticket CRUD, status events, department queues and validation.", "Working ticket API."),
        ("4", "Synthetic data generator, handwritten test set, cleaning, splitting and documentation.", "Training and evaluation data."),
        ("5", "Hugging Face embeddings, department/priority classifiers, confidence logic and rule fallback.", "Working multilingual classifier."),
        ("6", "Language detection, IndicTrans2 adapter, caching and localized strings.", "Language and translation services."),
        ("7", "Telegram bot, LangChain conversation orchestration, clarification flow and status commands.", "End-to-end citizen workflow."),
        ("8", "Whisper voice intake and transcript confirmation.", "Voice complaint support."),
        ("9", "Admin dashboard, officer actions, notifications and escalation worker.", "Operational workflow."),
        ("10", "Web fallback, testing, security hardening and deployment configuration.", "Demo-ready application."),
        ("11", "README, architecture diagram, screenshots, demo script, results and final clean-clone test.", "Submission-ready package."),
    ], widths=[0.55, 4.65, 1.85])

    add_section_heading(doc, "12 Security and reliability requirements")
    for item in [
        "Store Telegram tokens, database credentials and API keys only in environment variables.",
        "Protect admin pages and status update endpoints with authentication and role checks.",
        "Validate and limit message size, uploaded audio size and request frequency.",
        "Use parameterized database access through SQLAlchemy.",
        "Preserve original complaint text while minimizing unnecessary personal information.",
        "Record officer actions and status changes for accountability.",
        "Use deterministic fallback behavior when translation, model loading or external APIs fail.",
        "Keep model artifacts and large files out of Git history; provide reproducible download or training instructions.",
    ]:
        add_bullet(doc, item)

    add_section_heading(doc, "13 Testing and acceptance criteria")
    criteria = [
        "A citizen can submit an English, Hindi, Telugu, Hinglish or Tenglish complaint.",
        "The system detects or confirms the language and handles unsupported input politely.",
        "The system predicts department, intent, priority and confidence.",
        "Low-confidence complaints trigger a clarification question.",
        "A unique ticket ID is created and returned in the selected language.",
        "The ticket appears in the correct admin department queue.",
        "An officer can update the status and add a note.",
        "The citizen can query the status using the ticket ID.",
        "Every status update creates a ticket event and audit record.",
        "Overdue tickets are escalated and notifications are sent.",
        "Voice messages are transcribed when Whisper support is enabled.",
        "The application runs with SQLite for local demonstration and PostgreSQL for the full deployment.",
        "Automated tests pass and the project starts from a clean clone using documented commands.",
    ]
    for item in criteria:
        add_bullet(doc, "[ ] " + item)

    add_section_heading(doc, "14 Risks and fallback decisions")
    add_table(doc, ["Risk", "Fallback"], [
        ("IndicTrans2 is too slow or too large", "Lazy-load it and use a configured translation provider or a deterministic summary fallback."),
        ("Whisper is unavailable on the demo machine", "Keep text intake fully functional and show voice as an optional enabled deployment profile."),
        ("Telegram access is unavailable", "Use the web chat fallback and recorded demo workflow."),
        ("Telugu classification is weak", "Add Telugu/Tenglish examples, improve rules and route uncertain cases to human review."),
        ("PostgreSQL is unavailable locally", "Use SQLite with the same service interfaces."),
        ("Model files are too large for Git", "Ignore artifacts and provide a training/download script."),
        ("Time is limited", "Prioritize ticket creation, department assignment, status lookup and admin updates before analytics."),
    ], widths=[2.2, 4.85])

    add_section_heading(doc, "15 Final deliverables")
    for item in [
        "Working FastAPI backend with PostgreSQL and SQLite configuration.",
        "Telegram chatbot with multilingual text, status tracking and localized notifications.",
        "Whisper-based voice complaint support.",
        "Hugging Face classification and IndicTrans2 translation services.",
        "LangChain conversation and clarification orchestration.",
        "Admin dashboard with department queues and status updates.",
        "SLA monitoring and automatic escalation workflow.",
        "Responsive web fallback interface.",
        "Synthetic and handwritten evaluation datasets.",
        "Automated tests, lint configuration and clean-clone setup.",
        "README, architecture diagram, demo script, screenshots, evaluation report and limitations.",
    ]:
        add_bullet(doc, item)

    add_section_heading(doc, "16 Access required to begin implementation")
    add_body(doc, "Development can start locally without external credentials. The following items may be added later through the environment configuration rather than shared in source files:")
    for item in [
        "Telegram bot token from BotFather.",
        "PostgreSQL connection string, if a hosted database is required.",
        "Optional translation, LLM or notification provider credentials.",
        "GitHub repository or submission instructions.",
        "Any organizer-specific dashboard, presentation or video requirements.",
    ]:
        add_bullet(doc, item)

    add_section_heading(doc, "17 Reference resources")
    p = doc.add_paragraph(style="Body Text")
    p.paragraph_format.space_after = Pt(4)
    p.add_run("AI4Bharat: ")
    add_hyperlink(p, "https://ai4bharat.iitm.ac.in", "https://ai4bharat.iitm.ac.in")
    p = doc.add_paragraph(style="Body Text")
    p.paragraph_format.space_after = Pt(4)
    p.add_run("Bhashini: ")
    add_hyperlink(p, "https://bhashini.gov.in", "https://bhashini.gov.in")
    p = doc.add_paragraph(style="Body Text")
    p.paragraph_format.space_after = Pt(4)
    p.add_run("Model families to evaluate: Hugging Face IndicTrans2, MuRIL, IndicBERT and multilingual-e5. Exact model versions and licenses will be recorded in the final README.")

    doc.core_properties.title = "Multilingual Citizen Grievance Chatbot Execution Plan"
    doc.core_properties.subject = "Complete technical and delivery plan for HI-02"
    doc.core_properties.author = "Codex"
    doc.core_properties.keywords = "multilingual, grievance, chatbot, FastAPI, PostgreSQL, Hugging Face, LangChain, Whisper"
    doc.save(OUT)


if __name__ == "__main__":
    build_document()
    print(OUT)
