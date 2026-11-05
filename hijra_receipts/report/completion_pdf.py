"""The Service Completion Note, drawn as a PDF (A4) following the HIJRA sample document."""
from io import BytesIO

from reportlab.pdfgen import canvas

from odoo.addons.hijra_procurement.report.pdf_common import A4_H, A4_W, GREEN, Page, text_width, wrap

M = 60.0
SANS, SANS_BOLD = 'Helvetica', 'Helvetica-Bold'
SIZE, LEADING = 10.5, 13.6


def _fmt_date(value):
    return value.strftime('%d %B %Y').lstrip('0') if value else ''


class _Flow:
    """Writes paragraphs down the page, starting a new page when one is full."""

    def __init__(self, canv, data):
        self.canv, self.data = canv, data
        self.page = Page(canv, A4_W, A4_H, M)
        self.width = A4_W - 2 * M
        self.y = 0.0

    def start(self):
        if self.canv.getPageNumber() == 1 and self.y == 0.0:
            self.page.logo(self.data, top=24, box=(100, 50))
            self.page.text(M, 112, 'Service Completion Note', SANS_BOLD, 18)
            self.page.text(M, 136, 'Date: %s' % _fmt_date(self.data['date']), SANS_BOLD, 10.5)
            self.y = 160.0
        else:
            self.y = 60.0

    def need(self, height):
        if self.y + height > A4_H - 56:
            self.canv.showPage()
            self.page = Page(self.canv, A4_W, A4_H, M)
            self.y = 60.0

    def heading(self, text):
        self.need(30)
        self.page.text(M, self.y + 11, text, SANS_BOLD, 12, GREEN)
        self.y += 22

    def paragraph(self, text, bullet=False, bold=False):
        indent = 14 if bullet else 0
        lines = wrap(text, SANS_BOLD if bold else SANS, self.width - indent, SIZE)
        for index, line in enumerate(lines):
            self.need(LEADING + 2)
            if bullet and index == 0:
                self.page.text(M + 2, self.y + SIZE, '-', SANS, SIZE)
            self.page.text(M + indent, self.y + SIZE, line, SANS_BOLD if bold else SANS, SIZE)
            self.y += LEADING
        self.y += 6

    def lines(self, text, bullets=False):
        for paragraph in [p.strip() for p in str(text or '').split('\n')]:
            if paragraph:
                self.paragraph(paragraph, bullet=bullets)


def draw(canv, data):
    flow = _Flow(canv, data)
    flow.start()
    flow.heading('Background')
    flow.lines(data['background'])
    if data.get('benefits'):
        flow.heading('Key Benefits of the Activity')
        flow.lines(data['benefits'], bullets=True)
    flow.heading('Conclusion')
    flow.lines(data['conclusion'])
    if data.get('place') or data.get('activity_dates'):
        flow.need(60)
        text = ''
        if data.get('place'):
            text += 'Place of Activity: %s ' % data['place']
        if data.get('activity_dates'):
            text += 'Date of Activity: %s' % data['activity_dates']
        flow.paragraph(text.strip(), bold=True)
    flow.need(120)
    page = flow.page
    y = flow.y + 8
    page.text(M, y + SIZE, 'Reviewed and approved by:', SANS_BOLD, SIZE)
    y += 34
    approver = data['approver']
    page.text(M, y, 'Name:', SANS, SIZE)
    page.text(M + 34, y - 2, approver.get('name') or '', SANS, SIZE)
    page.line(M + 32, y + 2, M + 170, y + 2, 0.6, 0)
    page.text(M + 182, y, 'Signature:', SANS, SIZE)
    sx = M + 182 + text_width('Signature: ', SANS, SIZE)
    page.line(sx, y + 2, M + 352, y + 2, 0.6, 0)
    if approver.get('signature'):
        page.image(approver['signature'], (sx + 2, y - 34, M + 350, y), 'left', 'bottom')
    page.text(M + 364, y, 'Date:', SANS, SIZE)
    page.text(M + 392, y - 2, approver['date'].strftime('%d/%m/%Y') if approver.get('date') else '', SANS, SIZE)
    page.line(M + 390, y + 2, A4_W - M, y + 2, 0.6, 0)


def build_pdf(notes):
    """PDF bytes for a list of completion note dicts (one document each)."""
    buffer = BytesIO()
    canv = canvas.Canvas(buffer, pagesize=(A4_W, A4_H))
    canv.setTitle('Service Completion Note')
    for data in notes:
        draw(canv, data)
        canv.showPage()
    canv.save()
    return buffer.getvalue()
