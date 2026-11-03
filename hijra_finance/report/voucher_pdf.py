"""Draws the HIJRA Payment Voucher as a PDF.

The layout follows the HIJRA voucher template point for point (US Letter, Arial
metrics, green headings), so the printout does not depend on the HTML-to-PDF
engine's scaling. Everything here is plain Python (reportlab only) so it can be
tested without Odoo. Positions are written top-down in points, like the template.
"""
import base64
import logging
from io import BytesIO

from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

_logger = logging.getLogger(__name__)

PAGE_W, PAGE_H = 612.0, 792.0

SANS, SANS_BOLD = 'Helvetica', 'Helvetica-Bold'   # same metrics as the template's Arial
GREEN = (25 / 255.0, 107 / 255.0, 36 / 255.0)
INK = (13 / 255.0, 13 / 255.0, 13 / 255.0)
GREY_BAND = (245 / 255.0, 246 / 255.0, 247 / 255.0)
GREY_LINE = 0.678
GREY_RULE = 0.749

# the organisation block of the template
ORG_NAME = 'HUMANITARIAN INITIATIVE JUST RELIEF AID'
ORG_LINES = ['Rayaan Office Suite, Zoobe, Mogadishu', 'Email: info@hijra.or.ke', 'Phone: + 252-61-5 891401']

TEXT_LEFT, TEXT_RIGHT = 59.8, 570.3
TABLE_COLS = [54.0, 126.0, 301.5, 445.5, 517.5, 576.0]
LOGO_BOX = (462.2, 46.8, 569.5, 118.1)            # left, top, right, bottom
HEADER_TOP = 246.0
HEADER_H = 21.6
ROW_MIN = 28.8
LINE_H = 12.6
SIGN_BLOCK = 325.0                               # height of totals + signatures under the table
CONTINUED_TOP = 60.0
PAGE_LIMIT = 760.0


def ascent(size):
    return 0.905 * size


def clean(value):
    """Text the standard PDF fonts can draw (Latin-1 range)."""
    return str(value or '').encode('cp1252', 'replace').decode('cp1252')


def text_width(text, font, size):
    return pdfmetrics.stringWidth(clean(text), font, size)


def wrap(text, font, width, size):
    lines = []
    for paragraph in str(text or '').split('\n'):
        current = ''
        for word in paragraph.split(' '):
            candidate = f'{current} {word}' if current else word
            if text_width(candidate, font, size) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            while text_width(word, font, size) > width and len(word) > 1:
                cut = len(word) - 1
                while cut > 1 and text_width(word[:cut], font, size) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    return lines or ['']


def load_image(*candidates):
    """First candidate (raw bytes or base64) that PIL can read, as an ImageReader."""
    from PIL import Image
    for value in candidates:
        if not value:
            continue
        raw_value = value.encode() if isinstance(value, str) else bytes(value)
        options = [raw_value]
        try:
            options.append(base64.b64decode(raw_value))
        except Exception:
            pass
        for raw in options:
            try:
                image = Image.open(BytesIO(raw))
                image.load()
                if image.mode not in ('RGB', 'RGBA'):
                    image = image.convert('RGBA')
                buffer = BytesIO()
                image.save(buffer, format='PNG')
                buffer.seek(0)
                return ImageReader(buffer)
            except Exception:
                continue
        _logger.warning("Voucher PDF: could not read an image (%d bytes)", len(value))
    return None


def fmt_date(value):
    return value.strftime('%m/%d/%Y') if value else ''


def fmt_amount(value):
    return f'{value:,.2f}'


class Voucher:
    def __init__(self, canv):
        self.c = canv

    # -- primitives -----------------------------------------------------
    def _y(self, y):
        return PAGE_H - y

    def text(self, x, baseline, value, font=SANS, size=10, color=(0, 0, 0), align='left'):
        value = clean(value)
        if not value:
            return
        self.c.setFont(font, size)
        self.c.setFillColorRGB(*color)
        draw = {'left': self.c.drawString, 'right': self.c.drawRightString,
                'center': self.c.drawCentredString}[align]
        draw(x, self._y(baseline), value)
        self.c.setFillGray(0)

    def hline(self, y, x0, x1, gray=GREY_LINE, width=0.5):
        self.c.setLineWidth(width)
        self.c.setStrokeGray(gray)
        self.c.line(x0, self._y(y), x1, self._y(y))
        self.c.setStrokeGray(0)

    def fit_image(self, value, box, align='right', valign='top'):
        reader = load_image(*(value if isinstance(value, (list, tuple)) else [value]))
        if not reader:
            return False
        left, top, right, bottom = box
        width, height = reader.getSize()
        scale = min((right - left) / width, (bottom - top) / height)
        w, h = width * scale, height * scale
        x = right - w if align == 'right' else left
        y = top if valign == 'top' else bottom - h
        self.c.drawImage(reader, x, self._y(y + h), w, h, mask='auto')
        return True

    # -- sections -------------------------------------------------------
    def header(self, data):
        self.text(TEXT_LEFT, 57.6 + ascent(18), data['title'], SANS_BOLD, 18, GREEN)
        self.text(TEXT_LEFT, 80.1 + ascent(10), ORG_NAME, SANS, 10)
        for index, line in enumerate(ORG_LINES):
            self.text(TEXT_LEFT, 102.7 + 11.4 * index + ascent(9), line, SANS, 9)
        if data.get('logo'):
            self.fit_image(data['logo'], LOGO_BOX)
        number = data['name']
        number_w = text_width(number, SANS_BOLD, 9)
        self.text(TEXT_RIGHT, 118.9 + ascent(10), number, SANS_BOLD, 9, INK, 'right')
        self.text(TEXT_RIGHT - number_w - text_width('NO: ', SANS_BOLD, 10), 118.9 + ascent(10),
                  'NO: ', SANS_BOLD, 10, GREEN)
        date = fmt_date(data['date'])
        date_w = text_width(date, SANS_BOLD, 10)
        self.text(TEXT_RIGHT, 134.6 + ascent(10), date, SANS_BOLD, 10, (0, 0, 0), 'right')
        self.text(TEXT_RIGHT - date_w - text_width('DATE: ', SANS_BOLD, 10), 134.6 + ascent(10),
                  'DATE: ', SANS_BOLD, 10, GREEN)
        self.hline(158.0, 59.5, 570.5, GREY_RULE, 1.5)

    def purpose(self, data):
        """The FOR: block; returns how far the rest of the page moves down."""
        self.text(TEXT_LEFT, 179.1 + ascent(11), 'FOR:', SANS_BOLD, 11, GREEN)
        lines = wrap(data['for'], SANS, TEXT_RIGHT - TEXT_LEFT, 11)[:4]
        for index, line in enumerate(lines):
            self.text(TEXT_LEFT, 196.0 + 13.5 * index + ascent(11), line, SANS, 11)
        return 13.5 * (len(lines) - 1)

    def table_header(self, top):
        xs = TABLE_COLS
        self.c.setFillColorRGB(*GREY_BAND)
        self.c.rect(xs[0], self._y(top + HEADER_H), xs[-1] - xs[0], HEADER_H, stroke=0, fill=1)
        self.c.setFillGray(0)
        self.hline(top - 0.2, xs[0], xs[-1])
        self.hline(top + HEADER_H + 0.3, xs[0], xs[-1])
        base = top + 6.3 + ascent(10)
        self.text(59.4, base, 'Project Fund', SANS_BOLD, 10, INK)
        self.text(131.4, base, 'Code', SANS_BOLD, 10, INK)
        self.text(306.9, base, 'Description', SANS_BOLD, 10, INK)
        self.text((xs[3] + xs[4]) / 2.0, base, 'Amount', SANS_BOLD, 10, INK, 'center')
        self.text((xs[4] + xs[5]) / 2.0, base, 'Currency', SANS_BOLD, 10, INK, 'center')
        return top + HEADER_H + 0.3

    def row(self, top, row):
        xs = TABLE_COLS
        lines = wrap(row['description'], SANS, xs[3] - 306.9 - 6, 11)
        height = max(ROW_MIN, len(lines) * LINE_H + 3.6)
        mid = top + height / 2.0
        code_lines = wrap(row['code'], SANS, xs[2] - 131.4 - 6, 10)
        for index, line in enumerate(code_lines):
            self.text(131.4, mid + 3.65 - (len(code_lines) - 1) * 5.6 + index * 11.2, line, SANS, 10)
        self.text(59.4, mid + 3.65, row['project'], SANS, 10)
        first = mid - len(lines) * LINE_H / 2.0 + 0.3 + ascent(11)
        for index, line in enumerate(lines):
            self.text(306.9, first + index * LINE_H, line, SANS, 11)
        self.text(512.1, mid + 3.65, fmt_amount(row['amount']), SANS_BOLD, 10, (0, 0, 0), 'right')
        self.text((xs[4] + xs[5]) / 2.0, mid + 3.95, row['currency'], SANS, 11, (0, 0, 0), 'center')
        self.hline(top + height, xs[0], xs[-1])
        return top + height

    def totals_and_details(self, data, bottom):
        # TOTAL
        self.hline(bottom + 18.1, 445.5, 576.0)
        self.hline(bottom + 40.2, 445.5, 576.0)
        base = bottom + 22.6 + ascent(11)
        self.text(440.1, base, 'TOTAL', SANS_BOLD, 11, GREEN, 'right')
        self.text(525.2, base, fmt_amount(data['total']), SANS_BOLD, 11, GREEN, 'right')
        self.text(559.0, base, data['currency'], SANS_BOLD, 11, GREEN, 'center')
        # payment details box
        top = bottom + 17.6
        self.c.setFillColorRGB(*GREY_BAND)
        self.c.roundRect(54.0, self._y(top + 58.5), 230.5, 58.5, 10, stroke=0, fill=1)
        self.c.setFillGray(0)
        self.text(64.6, top + 16.05, 'Payment Details', SANS_BOLD, 10)
        label = 'Cheque/Reference No:'
        self.text(64.6, top + 39.1, label, SANS, 11)
        self.text(64.6 + text_width(label, SANS, 11) + 5, top + 39.1, data['cheque_ref'], SANS, 11)

    def signatures(self, data, bottom):
        label_base = bottom + 122.8
        columns = [(59.4, 'Prepared by:', data['prepared']),
                   (229.4, 'Approved by:', data['approved']),
                   (399.5, 'Authorized by', data['authorized'])]
        for x0, title, person in columns:
            self.text(x0, label_base, title, SANS_BOLD, 11)
            for caption, offset, end, key in (('Name:', 28.4, 137.9, 'name'),
                                              ('Position:', 75.4, 135.7, 'position'),
                                              ('Signature:', 120.7, 137.3 if x0 < 390 else 143.1,
                                               'signature')):
                base = label_base + offset
                self.text(x0, base, caption, SANS, 10)
                start = x0 + text_width(caption + ' ', SANS, 10)
                self.hline(base + 1.4, start, x0 + end, 0, 0.6)
                if key == 'signature':
                    if person['signature']:
                        box = (start + 2, base - 40.0, x0 + end, base - 1.0)
                        self.fit_image(person['signature'], box, 'left', 'bottom')
                else:
                    self.text(start + 2, base - 1.8,
                              self._fit_text(person[key], x0 + end - start - 4), SANS, 10)
        # received by
        base = label_base + 168.6
        self.text(315.0, base, data['received_label'], SANS, 11, (0, 0, 0), 'center')
        self.hline(base + 24.7, 241.6, 388.4, 0, 0.6)

    @staticmethod
    def _fit_text(value, width):
        value = clean(value)
        while value and text_width(value, SANS, 10) > width:
            value = value[:-1]
        return value


def draw(form, data):
    form.header(data)
    shift = form.purpose(data)
    top = HEADER_TOP + shift
    bottom = form.table_header(top)
    for row in data['rows']:
        height_probe = max(ROW_MIN, len(wrap(row['description'], SANS, 133.0, 11)) * LINE_H + 3.6)
        if bottom + height_probe > PAGE_LIMIT:
            form.c.showPage()
            bottom = form.table_header(CONTINUED_TOP)
        bottom = form.row(bottom, row)
    if bottom + SIGN_BLOCK > PAGE_LIMIT + 40:
        form.c.showPage()
        bottom = CONTINUED_TOP - 18.1
    form.totals_and_details(data, bottom)
    form.signatures(data, bottom)


def build_pdf(vouchers):
    """Return PDF bytes for a list of voucher dicts (one page, or more for long ones, each)."""
    buffer = BytesIO()
    canv = canvas.Canvas(buffer, pagesize=(PAGE_W, PAGE_H))
    canv.setTitle('Payment Voucher')
    for data in vouchers:
        draw(Voucher(canv), data)
        canv.showPage()
    canv.save()
    return buffer.getvalue()
