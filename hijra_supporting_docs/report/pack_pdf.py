"""Cover sheet of the supporting documents pack, and conversion of uploaded files to PDF.

Plain reportlab and PIL so it can be tested without Odoo.
"""
from io import BytesIO

from reportlab.pdfgen import canvas

from odoo.addons.hijra_procurement.report.pdf_common import (
    A4_H, A4_W, GREEN, GREY_BAND, SANS, SANS_BOLD, Page, fmt_amount, register_fonts, text_width, wrap)

M = 48.0
STATUS_COLORS = {
    'missing': (0.75, 0.1, 0.1), 'waived': (0.55, 0.4, 0.0), 'not_provided': (0.45, 0.45, 0.45),
}


def raw_bytes(value):
    value = getattr(value, 'content', value)
    if isinstance(value, str):
        value = value.encode()
    return bytes(value)


def file_to_pdf(content, file_name=''):
    """A PDF (bytes) of an uploaded file: PDFs as they are, images on an A4 page; None if it cannot be printed."""
    if content[:5] == b'%PDF-':
        return content
    try:
        from PIL import Image, ImageOps
        image = ImageOps.exif_transpose(Image.open(BytesIO(content)))
        image.load()
    except Exception:
        return None
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(A4_W, A4_H))
    box_w, box_h = A4_W - 2 * 28, A4_H - 2 * 28
    width, height = image.size
    scale = min(box_w / width, box_h / height, 1.0 if max(width, height) < 700 else 10.0)
    w, h = width * scale, height * scale
    from reportlab.lib.utils import ImageReader
    png = BytesIO()
    image.save(png, format='PNG')
    png.seek(0)
    pdf.drawImage(ImageReader(png), (A4_W - w) / 2.0, A4_H - 28 - h, w, h)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def build_cover(data, font_dir):
    """The checklist page that comes first in the pack."""
    register_fonts(font_dir)
    buffer = BytesIO()
    canv = canvas.Canvas(buffer, pagesize=(A4_W, A4_H))
    canv.setTitle('Supporting Documents')
    page = Page(canv, A4_W, A4_H, M)
    width = A4_W - 2 * M
    if data.get('logo'):
        page.image(data['logo'], (A4_W - M - 100, 24, A4_W - M, 74), align='right')
    page.text(M, 62, 'Supporting Documents', SANS_BOLD, 20, GREEN)
    y = 92.0
    for label, value in (('Payment:', data['number']), ('Expenditure type:', data['expenditure']),
                         ('Payee:', data['payee']), ('Amount:', data['amount'])):
        page.text(M, y, label, SANS_BOLD, 10.5)
        page.text(M + 100, y, value, SANS, 10.5)
        y += 15
    y += 8
    cols = [M, M + 28, M + 290, M + 360, A4_W - M]

    def header(top):
        page.rect(M, top, A4_W - M, top + 22, fill=GREY_BAND)
        for x in cols[1:-1]:
            page.line(x, top, x, top + 22)
        for x0, label in ((cols[0] + 6, '#'), (cols[1] + 6, 'Document'), (cols[2] + 6, 'Required'),
                          (cols[3] + 6, 'Status')):
            page.text(x0, top + 15, label, SANS_BOLD, 10)
        return top + 22

    y = header(y)
    for number, row in enumerate(data['rows'], 1):
        name_lines = wrap(row['name'], SANS, cols[2] - cols[1] - 12, 10)
        status_lines = wrap(row['status'], SANS, cols[4] - cols[3] - 12, 9.5)
        height = max(22.0, max(len(name_lines), len(status_lines)) * 12 + 10)
        if y + height > A4_H - 90:
            canv.showPage()
            page = Page(canv, A4_W, A4_H, M)
            y = header(60.0)
        page.rect(M, y, A4_W - M, y + height)
        for x in cols[1:-1]:
            page.line(x, y, x, y + height)
        page.text(cols[0] + 8, y + 15, number, SANS, 10)
        for i, line in enumerate(name_lines):
            page.text(cols[1] + 6, y + 15 + 12 * i, line, SANS, 10)
        page.text(cols[2] + 6, y + 15, row['requirement'], SANS, 10)
        color = STATUS_COLORS.get(row['state'], (0, 0, 0))
        for i, line in enumerate(status_lines):
            page.text(cols[3] + 6, y + 15 + 12 * i, line, SANS_BOLD if row['state'] == 'missing' else SANS,
                      9.5, color)
        y += height
    if data.get('override'):
        y += 14
        page.text(M, y + 10, 'Posted with missing documents. Reason:', SANS_BOLD, 10, STATUS_COLORS['missing'])
        page.paragraph(M, y + 14, width, data['override'], SANS, 10)
    canv.showPage()
    canv.save()
    return buffer.getvalue()
