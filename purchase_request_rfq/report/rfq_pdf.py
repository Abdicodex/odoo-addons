"""Draws the HIJRA Request for Quotation as a PDF (US Letter).

Follows the HIJRA RFQ Word template point for point: title and logo, To/From
blocks, subject beside the RFQ details table, the submission paragraph, the
item table for the vendor to price, the compliance checklist and the vendor
acknowledgement. Plain Python (reportlab only), coordinates top-down in points.
"""
import os
from io import BytesIO

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from .prf_pdf import (
    SANS, SANS_BOLD, SERIF, SERIF_BOLD, load_image, register_fonts, text_width, wrap,
)

PAGE_W, PAGE_H = 612.0, 792.0
LEFT, RIGHT = 72.0, 540.0
TEXT_RIGHT = 543.0              # body paragraphs run from 72 to 543
BOTTOM = 720.0                  # keep content above this (1 inch margin)
TOP = 72.0
GREY = (0.937, 0.941, 0.949)
LIGHT_LINE = (0.90, 0.90, 0.92)
SEPARATOR = (0.93, 0.91, 0.91)
LINK = (0.27, 0.47, 0.53)
APTOS = 1.085                   # Aptos is about 8.5% wider than Carlito

LOGO_BOX = (110.0, 72.0)        # width, height; right edge at 542, top at 24
LOGO_RIGHT, LOGO_TOP = 542.0, 24.0

INFO_COLS = [273.2, 406.5, 539.8]
INFO_ROW = 23.15
ITEM_COLS = [72.2, 110.2, 309.8, 391.5, 440.0, 480.4, 545.2]
COMPLIANCE_COLS = [72.2, 278.5, 353.6, 433.5, 559.9]
ACK_COLS = [72.2, 315.8, 559.3]


def fmt_long_date(value):
    return f"{value.strftime('%B')} {value.day}, {value.year}" if value else ''


def fmt_short_date(value):
    return value.strftime('%m/%d/%y') if value else ''


def fmt_qty(value):
    return f'{value:g}'


class Rfq:
    def __init__(self, canv):
        self.c = canv
        self.y = TOP

    # -- primitives -----------------------------------------------------
    def _y(self, y):
        return PAGE_H - y

    def line(self, x0, y0, x1, y1, gray=0.0, color=None, width=0.5):
        self.c.setLineWidth(width)
        if color:
            self.c.setStrokeColorRGB(*color)
        else:
            self.c.setStrokeGray(gray)
        self.c.line(x0, self._y(y0), x1, self._y(y1))

    def fill(self, x0, y0, x1, y1, color=GREY):
        self.c.setFillColorRGB(*color)
        self.c.rect(x0, self._y(y1), x1 - x0, y1 - y0, stroke=0, fill=1)
        self.c.setFillGray(0)

    def text(self, x, baseline, value, font, size, align='left', color=None):
        if value in (None, False, ''):
            return
        self.c.setFont(font, size)
        self.c.setFillColorRGB(*(color or (0, 0, 0)))
        draw = {'left': self.c.drawString, 'right': self.c.drawRightString,
                'center': self.c.drawCentredString}[align]
        draw(x, self._y(baseline), str(value))
        self.c.setFillGray(0)

    def box_row(self, xs, y0, y1, color=None, shaded=(), outer=True):
        for index in shaded:
            self.fill(xs[index], y0, xs[index + 1], y1)
        kw = {'color': color} if color else {}
        self.line(xs[0], y0, xs[-1], y0, **kw)
        self.line(xs[0], y1, xs[-1], y1, **kw)
        for x in xs:
            self.line(x, y0, x, y1, **kw)

    def new_page(self):
        self.c.showPage()
        self.y = TOP

    def need(self, height):
        if self.y + height > BOTTOM:
            self.new_page()

    # -- text flow (justified, mixed styles) ----------------------------
    def flow(self, x, top, width, segments, size, line_h, justify=True, tolerance=1.5):
        """Draw mixed-style text wrapped to `width`; returns the top of the line after the last.

        `segments` is a list of (text, font, color, underline). Words glued to
        each other without a space (e.g. "(" + email + ")") never split.
        """
        chunks, current, pending_space = [], [], False
        for text, font, color, underline in segments:
            words = text.split()
            if not words:
                pending_space = pending_space or text.startswith(' ') or text.endswith(' ')
                continue
            for index, word in enumerate(words):
                glued = index == 0 and not text[:1].isspace() and not pending_space and current
                if not glued and current:
                    chunks.append(current)
                    current = []
                current.append((word, font, color, underline))
            pending_space = text.endswith(' ')
        if current:
            chunks.append(current)

        def chunk_width(chunk):
            return sum(text_width(w, f, size) for w, f, _c, _u in chunk)

        space = text_width(' ', SERIF, size)
        lines, row, row_w = [], [], 0.0
        for chunk in chunks:
            w = chunk_width(chunk)
            gap = space if row else 0.0
            if row and row_w + gap + w > width + tolerance:
                lines.append(row)
                row, row_w, gap = [], 0.0, 0.0
            row.append(chunk)
            row_w += gap + w
        if row:
            lines.append(row)

        ascent = 0.891 * size
        for index, row in enumerate(lines):
            baseline = top + index * line_h + ascent
            widths = [chunk_width(c) for c in row]
            last = index == len(lines) - 1
            if justify and not last and len(row) > 1:
                gap = (width - sum(widths)) / (len(row) - 1)
            else:
                gap = space
            cursor = x
            for chunk, w in zip(row, widths):
                piece_x = cursor
                for word, font, color, underline in chunk:
                    self.text(piece_x, baseline, word, font, size, color=color)
                    word_w = text_width(word, font, size)
                    if underline:
                        self.line(piece_x, baseline + 1.4, piece_x + word_w, baseline + 1.4,
                                  color=color or (0, 0, 0), width=0.59)
                    piece_x += word_w
                cursor += w + gap
        return top + len(lines) * line_h

    # -- sections -------------------------------------------------------
    def header(self, data):
        self.text(72.0, 49.5 + 19.04, data['title'], SANS_BOLD, 20)
        reader = load_image(*(data.get('logo') or []))
        if reader:
            width, height = reader.getSize()
            scale = min(LOGO_BOX[0] / width, LOGO_BOX[1] / height)
            w, h = width * scale, height * scale
            self.c.drawImage(reader, LOGO_RIGHT - w, self._y(LOGO_TOP + h), w, h, mask='auto')

        to_lines = list(data['to_lines'])
        self.text(71.9, 92.9 + 10.47, 'To:', SANS_BOLD, 11)
        self.text(RIGHT, 92.9 + 10.47, 'FROM:', SANS_BOLD, 11, 'right')
        for index, value in enumerate(to_lines):
            self.text(71.9, 106.4 + index * 15.05 + 10.47, value, SANS, 11)
        for index, value in enumerate(data['from_lines']):
            self.text(RIGHT, 106.4 + index * 15.05 + 10.47, value, SANS, 11, 'right')
        count = max(len(to_lines), len(data['from_lines']), 1)
        last_top = 106.4 + (count - 1) * 15.05
        separator = last_top + 26.5
        self.line(LEFT, separator, RIGHT, separator, color=SEPARATOR, width=1.0)
        table_top = separator + 24.1

        # subject (left) beside the RFQ details table (right)
        size = 12 * APTOS
        self.text(72.0, table_top + 14.4 + 0.952 * size, 'Subject:', SANS_BOLD, size)
        subject_bottom = table_top + 14.4 + 18
        for index, value in enumerate(wrap(data.get('subject') or '', SANS, 190, size)):
            if not value:
                continue
            top = table_top + 39.4 + index * 16.9
            self.text(72.0, top + 0.952 * size, value, SANS, size)
            subject_bottom = top + 16.9

        y = table_top
        label_size = 11 * APTOS
        for label, value in data['info_rows']:
            lines = wrap(value or '', SANS, INFO_COLS[2] - INFO_COLS[1] - 11, label_size)
            height = max(INFO_ROW, len(lines) * 13.2 + 10.0)
            self.box_row(INFO_COLS, y, y + height, color=LIGHT_LINE, shaded=(0,))
            centre = y + height / 2.0
            first = centre + 3.2 - (len(lines) - 1) * 6.6
            self.text(INFO_COLS[0] + 5.4, centre + 3.2, label, SANS_BOLD, label_size)
            for index, value_line in enumerate(lines):
                self.text(INFO_COLS[1] + 5.4, first + index * 13.2, value_line, SANS, label_size)
            y += height
        self.y = max(y, subject_bottom)

    def submission(self, data):
        top = self.y + 39.3
        segments = [
            ('Manner of Submission:', SERIF_BOLD, None, False),
            (' Kindly provide your completed quotation for the following goods and/or '
             'services which should be submitted via email to Procurement office (', SERIF, None, False),
            (data['submission_email'] or '', SERIF, LINK, True),
            (') on or before ', SERIF, None, False),
            (data['deadline_text'], SERIF_BOLD, None, False),
        ]
        bottom = self.flow(LEFT, top, TEXT_RIGHT - LEFT, segments, 12, 15.95)
        self.y = bottom - 15.95 + 47.7

    def items(self, data):
        xs = ITEM_COLS
        self.need(40 + 24)
        y = self.y
        y = self.item_header(y, data['currency'])
        for number, item in enumerate(data['items'], 1):
            lines = wrap(item['description'], SANS, xs[2] - xs[1] - 11, 10)
            height = max(20.0, len(lines) * 12.2)
            if y + height + 22.2 > BOTTOM:
                self.c.showPage()
                y = self.item_header(TOP, data['currency'])
            self.box_row(xs, y, y + height)
            centre = y + height / 2.0
            self.text(xs[1] - 7.3, centre + 3.5, f'{number}.', SANS, 10, 'right')
            first = centre + 3.5 - (len(lines) - 1) * 6.1
            for index, value in enumerate(lines):
                self.text(xs[1] + 5.4, first + index * 12.2, value, SANS, 10)
            self.text((xs[2] + xs[3]) / 2.0, centre + 3.5, fmt_qty(item['qty']), SANS, 10, 'center')
            self.text((xs[3] + xs[4]) / 2.0, centre + 3.5, item['uom'], SANS, 10, 'center')
            y += height
        # total row
        total_h = 22.2
        for x in (xs[0], xs[3], xs[4], xs[5], xs[6]):
            self.line(x, y, x, y + total_h)
        self.line(xs[0], y + total_h, xs[6], y + total_h)
        self.text(xs[4] + 5.4, y + 0.3 + 9.5, 'Total', SANS_BOLD, 10)
        self.y = y + total_h

    def item_header(self, y, currency):
        xs = ITEM_COLS
        self.box_row(xs, y, y + 40.0, shaded=range(6))
        centre = y + 20.0
        self.text((xs[0] + xs[1]) / 2.0, centre + 3.1, 'SN', SANS_BOLD, 9, 'center')
        self.text(xs[1] + 5.4, centre + 3.1, 'Item Description', SANS_BOLD, 9)
        self.text((xs[2] + xs[3]) / 2.0, centre + 3.1, 'QTY', SANS_BOLD, 9, 'center')
        self.text((xs[3] + xs[4]) / 2.0, centre + 3.1, 'UOM', SANS_BOLD, 9, 'center')
        self.text((xs[4] + xs[5]) / 2.0, centre - 2.2, 'Unit', SANS_BOLD, 9, 'center')
        self.text((xs[4] + xs[5]) / 2.0, centre + 8.8, 'Price', SANS_BOLD, 9, 'center')
        self.text((xs[5] + xs[6]) / 2.0, centre + 3.1, f'Amount ({currency})', SANS_BOLD, 9, 'center')
        return y + 40.0

    def additional(self, data):
        y = self.y
        self.text(LEFT, y + 24.7 + 10.7, 'Additional Information:', SERIF_BOLD, 12)
        size = 12 * APTOS
        self.text(LEFT, y + 48.2 + 0.952 * size, 'Quotation Details to Include:', SANS_BOLD, size)
        y += 72.8
        for detail in (data.get('details') or ['']):
            lines = wrap(detail, SANS, RIGHT - 108.0, 11)
            height = len(lines) * 14.0 + 3.0
            self.need(height)
            y = max(y, self.y)
            self.text(90.0, y + 10.5, '•', SANS, 11)
            for index, value in enumerate(lines):
                self.text(108.0, y + 10.5 + index * 14.0, value, SANS, 11)
            y += height
        self.y = y

    def compliance(self, data):
        xs = COMPLIANCE_COLS
        rows = data['requirements']
        heights = [22.4, 23.1, 25.0] + [24.0] * max(0, len(rows) - 3)
        block = 29.4 + 22.0 + sum(heights[:len(rows)])
        self.y += 26.0
        self.need(block)
        top = self.y
        self.text(LEFT, top + 5.4 + 10.7, 'Compliance with Requirements', SERIF_BOLD, 12)
        y = top + 29.4
        self.box_row(xs, y, y + 22.0, shaded=range(4))
        self.text(xs[0] + 5.5, y + 11.0 + 3.1, 'Requirement', SANS_BOLD, 9)
        for index, (first, second) in ((1, ('YES, we will', 'comply')), (2, ('NO, we cannot', 'comply')),
                                       (3, ('If marked as “NO”, please', 'provide counter proposal'))):
            centre_x = (xs[index] + xs[index + 1]) / 2.0
            self.text(centre_x, y + 8.6, first, SANS_BOLD, 9, 'center')
            self.text(centre_x, y + 19.6, second, SANS_BOLD, 9, 'center')
        y += 22.0
        for text, height in zip(rows, heights):
            self.box_row(xs, y, y + height)
            self.text(xs[0] + 5.5, y + 0.3 + 9.5, text, SANS, 10)
            for column_centre in ((xs[1] + xs[2]) / 2.0 - 2.2, (xs[2] + xs[3]) / 2.0 - 2.5):
                box_top = y + (height - 12.6) / 2.0
                self.c.setLineWidth(0.5)
                self.c.setStrokeGray(0)
                self.c.rect(column_centre - 6.9, self._y(box_top + 12.6), 13.8, 12.6, stroke=1, fill=0)
            y += height
        self.y = y

    def acknowledgement(self, data):
        xs = ACK_COLS
        rows = [('Name', 29.7), ('Title/Designation', 28.2), ('Company Name', 29.7),
                ('Date', 28.2), ('Signature (sign & stamp)', 47.7)]
        block = 29.9 + 55.2 + 14.0 + sum(h for _l, h in rows)
        self.y += 26.0
        self.need(block)
        top = self.y
        self.text(LEFT, top + 10.7, 'Vendor Acknowledgement', SERIF_BOLD, 12)
        paragraph = (
            'By signing below, the vendor certifies that they have read, understood and hereby agree '
            'to the terms and conditions outlined in this RFQ. The vendor confirms their intention to '
            'provide the goods or services as described, in accordance with the agreed-upon terms and '
            'at the quoted price as detailed in the RFQ response.')
        bottom = self.flow(LEFT, top + 29.9, TEXT_RIGHT - LEFT, [(paragraph, SERIF, None, False)], 12, 13.8)
        y = bottom + 14.0
        for label, height in rows:
            self.box_row(xs, y, y + height, shaded=(0,))
            self.text(xs[0] + 5.5, y + height / 2.0 + 3.5, label, SANS_BOLD, 10)
            y += height
        self.y = y


def _draw(form, data):
    form.header(data)
    form.submission(data)
    form.items(data)
    form.additional(data)
    form.compliance(data)
    form.acknowledgement(data)


def build_pdf(rfqs, font_dir):
    """PDF bytes for a list of RFQ dicts (one RFQ document each)."""
    register_fonts(font_dir)
    buffer = BytesIO()
    canv = canvas.Canvas(buffer, pagesize=(PAGE_W, PAGE_H))
    canv.setTitle('Request for Quotation')
    for data in rfqs:
        _draw(Rfq(canv), data)
        canv.showPage()
    canv.save()
    return buffer.getvalue()
