"""Draws the HIJRA Purchase Requisition Form as a PDF.

The layout follows the HIJRA Word/Excel template point for point (A4, Calibri
and Times New Roman at 10pt, 0.5pt black borders, light grey label cells), so
the printout does not depend on the HTML-to-PDF engine's scaling.

Everything here is plain Python (reportlab only) so it can be tested without Odoo.
Coordinates are written top-down in points, like the template.
"""
import base64
import logging
import os
from io import BytesIO

from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_logger = logging.getLogger(__name__)

PAGE_W = 595.2756
PAGE_H = 841.8898

SANS, SANS_BOLD, SERIF, SERIF_BOLD = 'PRF-Sans', 'PRF-Sans-Bold', 'PRF-Serif', 'PRF-Serif-Bold'
FONT_FILES = {
    SANS: 'Carlito-Regular.ttf',
    SANS_BOLD: 'Carlito-Bold.ttf',
    SERIF: 'Tinos-Regular.ttf',
    SERIF_BOLD: 'Tinos-Bold.ttf',
}

FONT_SIZE = 10
GREY = 0.949
LINE_WIDTH = 0.5
PAD = 6.0                       # text inset from a cell's left border
ROW = 23.85                     # standard row height
SIGN_ROW = 46.5                 # signature rows
LEFT, RIGHT = 49.65, 557.9      # table edges
TOP = 40.0                      # top of the title text (the sample uses 72)
BOTTOM_LIMIT = 806.0            # keep content above this
LOGO_BOX = (145.7, 79.65)       # width, height of the logo area
LOGO_RIGHT = 551.55

DETAIL_COLS = [LEFT, 148.05, 272.25, 359.1, RIGHT]
ITEM_COLS = [LEFT, 94.5, 254.5, 309.5, 369.5, 429.5, 486.0, RIGHT]
APPROVER_COLS = [LEFT, 173.8, 297.1, 388.4, RIGHT]
PRF_COLS = [LEFT, 124.35, 319.5]


def register_fonts(font_dir):
    registered = set(pdfmetrics.getRegisteredFontNames())
    for name, filename in FONT_FILES.items():
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, os.path.join(font_dir, filename)))


def text_width(text, font, size=FONT_SIZE):
    return pdfmetrics.stringWidth(text, font, size)


def wrap(text, font, width, size=FONT_SIZE):
    """Word-wrap `text` to `width` points, breaking words that are too long."""
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


def _image_bytes(value):
    """Possible raw encodings of a binary field value.

    Odoo 20 returns binary fields as raw bytes; older versions returned base64.
    Try the value as it is first, then decoded from base64.
    """
    if isinstance(value, str):
        value = value.encode()
    options = [bytes(value)]
    try:
        options.append(base64.b64decode(value))
    except Exception:
        pass
    return options


def load_image(*candidates):
    """First candidate (raw bytes or base64) that PIL can read, as an ImageReader."""
    from PIL import Image
    for value in candidates:
        if not value:
            continue
        for raw in _image_bytes(value):
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
        _logger.warning(
            "Requisition PDF: could not read an image (%d bytes, starts with %r)",
            len(value), bytes(value[:8]) if not isinstance(value, str) else value[:8])
    return None


def fmt_date(value):
    return f'{value.month}/{value.day}/{value.year}' if value else ''


def fmt_amount(value):
    return f'{value:,.2f}'


def fmt_number(value):
    return f'{value:g}'


class Form:
    def __init__(self, canv):
        self.c = canv
        self.top = TOP
        self.y = TOP

    # -- primitives -----------------------------------------------------
    def _y(self, y):
        return PAGE_H - y

    def hline(self, y, x0, x1):
        self.c.setLineWidth(LINE_WIDTH)
        self.c.setStrokeGray(0)
        self.c.line(x0, self._y(y), x1, self._y(y))

    def vline(self, x, y0, y1):
        self.c.setLineWidth(LINE_WIDTH)
        self.c.setStrokeGray(0)
        self.c.line(x, self._y(y0), x, self._y(y1))

    def fill(self, x0, y0, x1, y1):
        self.c.setFillGray(GREY)
        self.c.rect(x0, self._y(y1), x1 - x0, y1 - y0, stroke=0, fill=1)
        self.c.setFillGray(0)

    def text(self, x, baseline, value, font, size=FONT_SIZE, align='left'):
        if value in (None, False, ''):
            return
        self.c.setFont(font, size)
        self.c.setFillGray(0)
        draw = {'left': self.c.drawString, 'right': self.c.drawRightString,
                'center': self.c.drawCentredString}[align]
        draw(x, self._y(baseline), str(value))

    def cell_text(self, x0, x1, row_top, row_h, lines, font, line_h, align='left',
                  offset=3.0, size=FONT_SIZE):
        """Draw `lines` vertically centred in a cell, aligned like the template."""
        centre = row_top + row_h / 2.0
        first = centre + offset - (len(lines) - 1) * line_h / 2.0
        for index, line in enumerate(lines):
            baseline = first + index * line_h
            if align == 'left':
                self.text(x0 + PAD, baseline, line, font, size)
            elif align == 'right':
                self.text(x1 - PAD, baseline, line, font, size, 'right')
            else:
                self.text((x0 + x1) / 2.0, baseline, line, font, size, 'center')

    def row_box(self, xs, y0, y1, shaded=()):
        """Border a row: shaded cell indexes are filled grey first."""
        for index in shaded:
            self.fill(xs[index], y0, xs[index + 1], y1)
        self.hline(y0, xs[0], xs[-1])
        self.hline(y1, xs[0], xs[-1])
        for x in xs:
            self.vline(x, y0, y1)

    # -- paging ---------------------------------------------------------
    def need(self, height):
        if self.y + height > BOTTOM_LIMIT:
            self.c.showPage()
            self.y = self.top

    # -- sections -------------------------------------------------------
    def header(self, data, shift):
        # title and logo
        self.text(50.0, self.y + 19.04, 'Purchase Requisition Form', SANS_BOLD, 20)
        logo = data.get('logo')
        if logo:
            self.draw_logo(logo, self.y + 5.55)
        # PRF / date table
        y = self.y + 45.3
        for label, value in (('PRF:', data['name']), ('Date:', fmt_date(data['date']))):
            self.row_box(PRF_COLS, y, y + ROW, shaded=(0,))
            self.cell_text(PRF_COLS[0], PRF_COLS[1], y, ROW, [label], SANS_BOLD, 13.4, offset=2.9)
            self.cell_text(PRF_COLS[1], PRF_COLS[2], y, ROW, [value], SANS_BOLD, 13.4, offset=2.9)
            y += ROW
        self.y = y + shift['gap']

    def draw_logo(self, logo, top):
        candidates = logo if isinstance(logo, (list, tuple)) else [logo]
        reader = load_image(*candidates)
        if not reader:
            return
        width, height = reader.getSize()
        box_w, box_h = LOGO_BOX
        scale = min(box_w / width, box_h / height)
        w, h = width * scale, height * scale
        self.c.drawImage(reader, LOGO_RIGHT - w, self._y(top + h), w, h, mask='auto')

    def draw_signature(self, value, x0, y0, x1, y1):
        """Fit a signature image inside a cell, left-aligned with a small margin."""
        reader = load_image(value)
        if not reader:
            return False
        width, height = reader.getSize()
        box_w, box_h = (x1 - x0) - 8.0, (y1 - y0) - 8.0
        scale = min(box_w / width, box_h / height)
        w, h = width * scale, height * scale
        x = x0 + 4.0
        y = y0 + ((y1 - y0) - h) / 2.0
        self.c.drawImage(reader, x, self._y(y + h), w, h, mask='auto')
        return True

    def details(self, data, shift):
        xs = DETAIL_COLS
        y = self.y
        # band
        self.fill(xs[0], y, xs[-1], y + ROW)
        self.hline(y, xs[0], xs[-1])
        self.hline(y + ROW, xs[0], xs[-1])
        self.vline(xs[0], y, y + ROW)
        self.vline(xs[-1], y, y + ROW)
        self.cell_text(xs[0], xs[-1], y, ROW, ['Requisition Details'], SANS_BOLD, 13.4, offset=2.9)
        y += ROW
        rows = [
            ('Requestor', data['requestor'], SERIF, 'Project', data['project'], SERIF),
            ('Position', data['position'], SERIF, 'Budget', data['budget'], SERIF),
            ('Department', data['department'], SERIF, 'Fund', data['fund'], SERIF),
            ('Location', data['location'], SERIF, 'Category', data['category'], SERIF),
            ('Email', data['email'], SERIF, 'Verifier', data['verifier'], SANS),
        ]
        for label1, value1, font1, label2, value2, font2 in rows:
            lines1 = wrap(value1, font1, xs[2] - xs[1] - 2 * PAD)
            lines2 = wrap(value2, font2, xs[4] - xs[3] - 2 * PAD)
            height = max(ROW, max(len(lines1), len(lines2)) * 12.6 + 10.6)
            self.row_box(xs, y, y + height, shaded=(0, 2))
            self.cell_text(xs[0], xs[1], y, height, [label1], SANS_BOLD, 13.4)
            self.cell_text(xs[1], xs[2], y, height, lines1, font1, 12.6)
            self.cell_text(xs[2], xs[3], y, height, [label2], SANS_BOLD, 13.4)
            self.cell_text(xs[3], xs[4], y, height, lines2, font2, 12.6)
            y += height
        # signature row
        self.row_box(xs, y, y + SIGN_ROW, shaded=(0, 2))
        self.cell_text(xs[0], xs[1], y, SIGN_ROW,
                       wrap("Requestor's Signature", SANS_BOLD, xs[1] - xs[0] - 2 * PAD), SANS_BOLD, 13.4)
        self.cell_text(xs[2], xs[3], y, SIGN_ROW,
                       wrap("Verifier's Signature", SANS_BOLD, xs[3] - xs[2] - 2 * PAD), SANS_BOLD, 13.4)
        self.draw_signature(data.get('requestor_signature'), xs[1], y, xs[2], y + SIGN_ROW)
        self.draw_signature(data.get('verifier_signature'), xs[3], y, xs[4], y + SIGN_ROW)
        self.y = y + SIGN_ROW + shift['gap']

    def items(self, data, shift):
        xs = ITEM_COLS
        # band + header always together with the first row
        first_height = self.item_height(data['lines'][0], shift) if data['lines'] else ROW
        self.need(ROW * 2 + first_height)
        y = self.y
        self.fill(xs[0], y, xs[-1], y + ROW)
        self.hline(y, xs[0], xs[-1])
        self.hline(y + ROW, xs[0], xs[-1])
        self.vline(xs[0], y, y + ROW)
        self.vline(xs[-1], y, y + ROW)
        self.cell_text(xs[0], xs[-1], y, ROW, ['Item Details'], SANS_BOLD, 13.4, offset=2.9)
        y += ROW
        y = self.item_header(y)
        for number, line in enumerate(data['lines'], 1):
            height = self.item_height(line, shift)
            if y + height + ROW > BOTTOM_LIMIT:
                self.c.showPage()
                y = self.item_header(self.top)
            y = self.item_row(y, number, line, height, shift)
        # total
        self.hline(y, xs[0], xs[-1])
        self.hline(y + ROW, xs[0], xs[-1])
        for x in (xs[0], xs[6], xs[-1]):
            self.vline(x, y, y + ROW)
        self.cell_text(xs[0], xs[6], y, ROW, ['Total Amount'], SANS_BOLD, 13.4, 'right', offset=2.9)
        self.cell_text(xs[6], xs[7], y, ROW, [fmt_amount(data['total'])], SERIF_BOLD, 13.4,
                       'center', offset=2.9)
        self.y = y + ROW + shift['gap']

    def item_header(self, y):
        xs = ITEM_COLS
        self.row_box(xs, y, y + ROW, shaded=range(7))
        for index, title in enumerate(
                ('Item #', 'Description', 'Unit', 'Quantity', 'Frequency', 'Unit Price', 'Amount')):
            self.cell_text(xs[index], xs[index + 1], y, ROW, [title], SANS_BOLD, 13.4, 'center',
                           offset=2.9)
        return y + ROW

    def item_lines(self, line, size=FONT_SIZE):
        return wrap(line['description'], SERIF, ITEM_COLS[2] - ITEM_COLS[1] - 2 * PAD, size)

    def item_height(self, line, shift):
        return (len(self.item_lines(line, shift.get('size', FONT_SIZE))) * shift.get('lh', 13.2)
                + shift['pad'])

    def item_row(self, y, number, line, height, shift):
        xs = ITEM_COLS
        pad, lh, size = shift['pad'], shift.get('lh', 13.2), shift.get('size', FONT_SIZE)
        self.row_box(xs, y, y + height)
        # the template's roomy rows keep text a little above centre (-2.25);
        # tighter rows are centred properly so text never touches a border
        roomy = (pad - 6.0) / (20.6 - 6.0)
        centre = 3.3 - max(0.0, min(1.0, roomy)) * 5.55
        cells = (
            (0, [str(number)], 'center'),
            (1, self.item_lines(line, size), 'left'),
            (2, [line['unit']], 'center'),
            (3, [f"{line['quantity']:.2f}"], 'center'),
            (4, [fmt_number(line['frequency'])], 'center'),
            (5, [fmt_amount(line['price'])], 'center'),
            (6, [fmt_amount(line['amount'])], 'center'),
        )
        for index, lines, align in cells:
            self.cell_text(xs[index], xs[index + 1], y, height, lines, SERIF, lh, align,
                           offset=centre, size=size)
        return y + height

    def signatory(self, label, name, position, signed_on, signature, shift):
        xs = APPROVER_COLS
        label_lines = wrap(label, SANS_BOLD, xs[1] - xs[0] - 2 * PAD)
        self.need(SIGN_ROW + ROW)
        y = self.y
        self.row_box(xs, y, y + SIGN_ROW)
        self.cell_text(xs[0], xs[1], y, SIGN_ROW, label_lines, SANS_BOLD, 13.4)
        self.cell_text(xs[1], xs[2], y, SIGN_ROW, wrap(name, SANS, xs[2] - xs[1] - 2 * PAD), SANS, 13.4)
        self.cell_text(xs[2], xs[3], y, SIGN_ROW, ['Signature:'], SANS_BOLD, 13.4)
        if not self.draw_signature(signature, xs[3], y, xs[4], y + SIGN_ROW) and signed_on:
            self.cell_text(xs[3], xs[4], y, SIGN_ROW, ['Approved electronically'], SANS, 13.4,
                           size=7.5)
        y += SIGN_ROW
        self.row_box(xs, y, y + ROW)
        self.cell_text(xs[0], xs[1], y, ROW, ['Position:'], SANS_BOLD, 13.4, offset=2.9)
        self.cell_text(xs[1], xs[2], y, ROW, wrap(position, SANS, xs[2] - xs[1] - 2 * PAD)[:1], SANS,
                       13.4, offset=2.9)
        self.cell_text(xs[2], xs[3], y, ROW, ['Date:'], SANS_BOLD, 13.4, offset=2.9)
        self.cell_text(xs[3], xs[4], y, ROW, [fmt_date(signed_on)], SANS, 13.4, offset=2.9)
        self.y = y + ROW + shift['gap']


def _page_count(data, level):
    """How many pages the form takes at the given spacing."""
    probe = Form(canvas.Canvas(BytesIO(), pagesize=(PAGE_W, PAGE_H)))
    pages = [1]
    original = probe.c.showPage

    def counting_show_page():
        pages[0] += 1
        original()

    probe.c.showPage = counting_show_page
    _draw(probe, data, level)
    return pages[0]


def _fit(data):
    """Pick the roomiest spacing at which everything fits on one page."""
    levels = (
        {'gap': 22.1, 'pad': 20.6},
        {'gap': 14.0, 'pad': 12.0},
        {'gap': 10.0, 'pad': 6.0},
        {'gap': 8.0, 'pad': 4.0, 'lh': 11.8, 'top': 30.0},
        {'gap': 6.0, 'pad': 3.0, 'lh': 10.8, 'size': 9, 'top': 26.0},
    )
    for level in levels:
        if _page_count(data, level) == 1:
            return level
    return levels[-1]


def _draw(form, data, level):
    form.top = form.y = level.get('top', TOP)
    form.header(data, level)
    form.details(data, level)
    form.items(data, level)
    form.signatory('Name of Approver:', data['approver'], data['approver_position'],
                   data['approval_date'], data.get('approver_signature'), level)
    form.signatory('2nd Signatory (if required):', data['second'], data['second_position'],
                   data['second_date'], data.get('second_signature'), level)


def build_pdf(requisitions, font_dir):
    """Return PDF bytes for a list of requisition dicts (one form each)."""
    register_fonts(font_dir)
    buffer = BytesIO()
    canv = canvas.Canvas(buffer, pagesize=(PAGE_W, PAGE_H))
    canv.setTitle('Purchase Requisition Form')
    for data in requisitions:
        level = _fit(data)
        form = Form(canv)
        _draw(form, data, level)
        canv.showPage()
    canv.save()
    return buffer.getvalue()
