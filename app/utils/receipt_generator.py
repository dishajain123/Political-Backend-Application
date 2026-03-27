from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _format_amount(amount: Any) -> str:
    try:
        return f"{float(amount):.2f}"
    except (TypeError, ValueError):
        return str(amount)


def generate_receipt_pdf(
    receipt_id: str,
    contributor_name: str,
    contributor_role: str,
    amount: float,
    campaign_title: str,
    corporator_name: str,
    timestamp: datetime,
    transaction_id: Optional[str] = None,
) -> str:
    app_dir = Path(__file__).resolve().parents[1]
    receipts_dir = app_dir / "static" / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{receipt_id}.pdf"
    file_path = receipts_dir / filename

    receipt_canvas = canvas.Canvas(str(file_path), pagesize=A4)
    width, height = A4

    navy = colors.HexColor("#0F355E")
    accent_blue = colors.HexColor("#1F4E85")
    light_blue = colors.HexColor("#E8F0FA")
    green = colors.HexColor("#2E7D32")
    light_green = colors.HexColor("#E7F5EC")
    gray = colors.HexColor("#6B7280")

    margin_x = 48

    # Header band
    header_h = 90
    receipt_canvas.setFillColor(navy)
    receipt_canvas.rect(0, height - header_h, width, header_h, stroke=0, fill=1)

    receipt_canvas.setFillColor(colors.white)
    receipt_canvas.setFont("Helvetica", 9)
    receipt_canvas.drawString(margin_x, height - 24, "JAN SAMPARK  -  WARD MANAGEMENT PLATFORM")

    receipt_canvas.setFont("Helvetica-Bold", 22)
    receipt_canvas.drawString(margin_x, height - 56, "Donation Receipt")

    receipt_canvas.setFont("Helvetica", 9)
    right_x = width - margin_x - 10
    receipt_canvas.drawRightString(right_x, height - 24, f"Receipt ID: {receipt_id}")

    if hasattr(timestamp, "strftime"):
        date_str = timestamp.strftime("%d %B %Y")
        time_str = timestamp.strftime("%I:%M %p %Z").lstrip("0")
    else:
        date_str = str(timestamp)
        time_str = ""
    header_time = f"{date_str}  -  {time_str}".strip(" -")
    receipt_canvas.drawRightString(right_x, height - 38, header_time)

    # Thank you banner
    banner_y = height - header_h - 48
    banner_h = 42
    receipt_canvas.setFillColor(light_green)
    receipt_canvas.roundRect(margin_x, banner_y, width - margin_x * 2, banner_h, 6, stroke=0, fill=1)
    receipt_canvas.setFillColor(green)
    receipt_canvas.rect(margin_x, banner_y, 6, banner_h, stroke=0, fill=1)
    receipt_canvas.setFillColor(colors.HexColor("#1F2937"))
    receipt_canvas.setFont("Helvetica-Bold", 11)
    receipt_canvas.drawString(margin_x + 16, banner_y + 24, "Thank you for your contribution!")
    receipt_canvas.setFont("Helvetica", 9)
    receipt_canvas.setFillColor(gray)
    receipt_canvas.drawString(
        margin_x + 16,
        banner_y + 10,
        "Your donation has been recorded and will support your ward community.",
    )

    # Amount card
    card_y = banner_y - 76
    card_h = 54
    receipt_canvas.setFillColor(accent_blue)
    receipt_canvas.roundRect(margin_x, card_y, width - margin_x * 2, card_h, 8, stroke=0, fill=1)
    receipt_canvas.setFillColor(colors.white)
    receipt_canvas.setFont("Helvetica-Bold", 10)
    receipt_canvas.drawString(margin_x + 16, card_y + 32, "AMOUNT CONTRIBUTED")
    receipt_canvas.setFont("Helvetica", 9)
    receipt_canvas.drawString(margin_x + 16, card_y + 16, "Indian Rupees")
    receipt_canvas.setFont("Helvetica-Bold", 22)
    receipt_canvas.drawRightString(
        width - margin_x - 16,
        card_y + 20,
        f"Rs {_format_amount(amount)}",
    )

    # Transaction details title
    title_y = card_y - 28
    receipt_canvas.setFillColor(colors.HexColor("#111827"))
    receipt_canvas.setFont("Helvetica-Bold", 11)
    receipt_canvas.drawString(margin_x, title_y, "Transaction Details")

    # Details table
    table_y = title_y - 16
    row_h = 26
    table_w = width - margin_x * 2
    col1_w = 170
    table_rows = [
        ("Contributor Name", contributor_name),
        ("Contributor Role", contributor_role.title() if contributor_role else ""),
        ("Campaign Title", campaign_title),
        ("Corporator Name", corporator_name),
        ("Transaction ID", transaction_id or "N/A"),
        ("Transaction Date", date_str),
        ("Transaction Time", time_str or ""),
    ]

    receipt_canvas.setFillColor(light_blue)
    receipt_canvas.roundRect(margin_x, table_y - row_h, table_w, row_h, 4, stroke=0, fill=1)
    receipt_canvas.setFillColor(colors.HexColor("#1F3B68"))
    receipt_canvas.setFont("Helvetica-Bold", 9)
    receipt_canvas.drawString(margin_x + 12, table_y - row_h + 8, "Field")
    receipt_canvas.drawString(margin_x + col1_w + 12, table_y - row_h + 8, "Value")

    receipt_canvas.setStrokeColor(colors.HexColor("#D6E3F5"))
    receipt_canvas.setLineWidth(1)
    y = table_y - row_h

    for i, (label, value) in enumerate(table_rows):
        y -= row_h
        if i % 2 == 0:
            receipt_canvas.setFillColor(colors.HexColor("#F8FBFF"))
            receipt_canvas.rect(margin_x, y, table_w, row_h, stroke=0, fill=1)

        receipt_canvas.setStrokeColor(colors.HexColor("#E5EEF9"))
        receipt_canvas.line(margin_x, y, margin_x + table_w, y)

        receipt_canvas.setFillColor(colors.HexColor("#5B6B85"))
        receipt_canvas.setFont("Helvetica", 9)
        receipt_canvas.drawString(margin_x + 12, y + 8, label)

        receipt_canvas.setFillColor(colors.HexColor("#1F2937"))
        receipt_canvas.setFont("Helvetica-Bold", 9)
        receipt_canvas.drawString(margin_x + col1_w + 12, y + 8, str(value))

    receipt_canvas.showPage()
    receipt_canvas.save()

    return f"/static/receipts/{filename}"
