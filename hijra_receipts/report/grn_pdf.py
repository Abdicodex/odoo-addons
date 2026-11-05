"""The HIJRA Goods Received Note, drawn as a PDF (A4) at the positions of the paper template."""
from io import BytesIO

from reportlab.pdfgen import canvas

from odoo.addons.hijra_procurement.report.pdf_common import A4_H, A4_W, Page, load_image, wrap

HEL, HELB = 'Helvetica', 'Helvetica-Bold'
LEFT = 56.7
COLS = [57.0, 104.3, 239.7, 295.2, 364.0, 434.7, 583.0]    # no, description, uom, ordered, received, comment
HEAD_FILL = (0.70, 0.90, 0.63)
EDGE = (0.31, 0.65, 0.18)
ROW_EDGE = (0.55, 0.85, 0.45)
ORG_LINES = ['Humanitarian Initiative Just Relief Aid', 'Kilometer Five, Mogadishu', '+252-61-5057981']
ORG_EMAIL = 'info@hijra.or.ke'
BOTTOM = 700.0


def asc(size):
    return 0.905 * size


def _fmt_date(value):
    return value.strftime('%d/%m/%Y') if value else ''


def _qty(value):
    return '%g' % value if value not in (None, False) else ''


def _header(page, data):
    page.text(A4_W / 2.0, 85.1 + asc(14), 'GOODS RECEIVED NOTE', HELB, 14, align='center')
    page.line(57.6, 109.9, 571.1, 109.9, 1.5, 0)
    for index, text in enumerate(ORG_LINES):
        page.text(LEFT, 141.0 + 21.2 * index + asc(10), text, HEL, 10)
    page.text(LEFT, 204.6 + asc(10), ORG_EMAIL, HEL, 10, (0.275, 0.471, 0.525))
    page.line(LEFT, 215.1, 124.7, 215.1, 0.73, 0.4)
    x = 272.7
    for index, (label, value) in enumerate((
            ('Vendor      : ', data['vendor']), ('GRN No    : ', data['name']),
            ('Location    : ', data['location']), ('Date          : ', _fmt_date(data['date']) or '_' * 17))):
        page.text(x, 141.0 + 21.2 * index + asc(10), label + (value or ''), HEL, 10)
    if data.get('logo'):
        page.image(data['logo'], (461.3, 146.8, 570.8, 204.4), align='right')
    page.text(LEFT, 247.1 + asc(10), 'PO No: ', HEL, 10)
    page.text(92.7, 247.1 + asc(10), data['order'], HEL, 10)
    invoice_x = max(164.7, 92.7 + page.c.stringWidth(data['order'], HEL, 10) + 18)
    page.text(invoice_x, 247.1 + asc(10), 'Invoice Number: %s' % (data.get('invoice_number') or ''), HEL, 10)
    # the documents received with the goods, ticked
    y = 285.6 + asc(9)
    page.text(LEFT, y, 'Documents', HELB, 9)
    x = 104.8
    page.text(x, y, ':', HEL, 9)
    x += 6
    for label, key in (('Invoice', 'invoice'), ('Delivery', 'delivery'), ('Complete order', 'complete_order'),
                       ('Part order', 'part_order'), ('Complete shipment', 'complete_shipment'),
                       ('Part shipment', 'part_shipment')):
        page.text(x, y, label + ':', HEL, 9)
        x += page.c.stringWidth(label + ': ', HEL, 9)
        page.line(x, y + 1.5, x + 14, y + 1.5, 0.5, 0)
        if data['docs'].get(key):
            page.text(x + 7, y - 1, 'X', HELB, 9, align='center')
        x += 22


def _table_header(page, top):
    page.rect(COLS[0], top, COLS[-1], top + 31.5, fill=HEAD_FILL, stroke=False)
    page.c.setStrokeColorRGB(*EDGE)
    page.c.setLineWidth(0.5)
    page.c.rect(COLS[0], page._y(top + 31.5), COLS[-1] - COLS[0], 31.5, stroke=1, fill=0)
    page.c.setStrokeGray(0)
    for x in COLS[1:-1]:
        page.line(x, top, x, top + 31.5, 0.5, 0.5)
    page.text(62.4, top + 11.2 + asc(12), 'No', HEL, 12)
    page.text(109.7, top + 11.2 + asc(12), 'Description', HEL, 12)
    page.text(253.4, top + 11.2 + asc(12), 'UOM', HEL, 12)
    page.text(329.6, top + 4.3 + asc(12), 'Quantity', HEL, 12, align='center')
    page.text(329.6, top + 18.1 + asc(12), 'Ordered', HEL, 12, align='center')
    page.text(399.4, top + 4.3 + asc(12), 'Quantity', HEL, 12, align='center')
    page.text(399.4, top + 18.1 + asc(12), 'Received', HEL, 12, align='center')
    page.text(440.1, top + 11.2 + asc(12), 'Comment', HEL, 12)
    return top + 32.0


def _row(page, y, line):
    desc = wrap(line['description'], HEL, COLS[2] - COLS[1] - 10, 11)
    comment = wrap(line.get('comment') or '', HEL, COLS[6] - COLS[5] - 10, 11)
    height = max(30.0, max(len(desc), len(comment)) * 12.6 + 12)
    page.c.setStrokeColorRGB(*ROW_EDGE)
    page.c.setLineWidth(0.5)
    page.c.rect(COLS[0], page._y(y + height), COLS[-1] - COLS[0], height, stroke=1, fill=0)
    for x in COLS[1:-1]:
        page.c.line(x, page._y(y), x, page._y(y + height))
    page.c.setStrokeGray(0)
    mid = y + height / 2.0
    page.text((COLS[0] + COLS[1]) / 2.0, mid + 4, line['no'], HELB, 11, align='center')
    first = mid - (len(desc) - 1) * 6.3 + 4
    for i, text in enumerate(desc):
        page.text(109.7, first + 12.6 * i, text, HEL, 11)
    page.text(255.1, mid + 4.5, line['uom'], HEL, 12)
    page.text((COLS[3] + COLS[4]) / 2.0, mid + 4.5, _qty(line['ordered']), HEL, 12, align='center')
    page.text((COLS[4] + COLS[5]) / 2.0, mid + 4.5, _qty(line['received']), HEL, 12, align='center')
    first = mid - (len(comment) - 1) * 6.3 + 4
    for i, text in enumerate(comment):
        page.text(COLS[5] + 5.4, first + 12.6 * i, text, HEL, 11)
    return y + height


def _person_blocks(page, data, bottom):
    for x, title, person in ((LEFT, 'Received by:', data['received']), (344.7, 'Checked by: ', data['checked'])):
        top = bottom + 24.6
        page.text(x, top + asc(11), title, HEL, 11)
        page.text(x, top + 22.6 + asc(11), 'Name', HEL, 11)
        page.text(x + 36, top + 22.6 + asc(11), person.get('name') or '_' * 22, HEL, 11)
        page.text(x, top + 62.0 + asc(11), 'Signature', HEL, 11)
        sx = x + 58
        page.line(sx, top + 62.0 + asc(11) + 1.5, x + 180, top + 62.0 + asc(11) + 1.5, 0.6, 0)
        if person.get('signature'):
            page.image(person['signature'], (sx + 2, top + 40, x + 178, top + 62.0 + asc(11)), 'left', 'bottom')
        page.text(x, top + 84.6 + asc(11), 'Date', HEL, 11)
        page.text(x + 36, top + 84.6 + asc(11), _fmt_date(person.get('date')) or '_' * 22, HEL, 11)


def draw(canv, data):
    page = Page(canv, A4_W, A4_H, LEFT)
    _header(page, data)
    y = _table_header(page, 309.5)
    for line in data['lines']:
        height = max(30.0, len(wrap(line['description'], HEL, COLS[2] - COLS[1] - 10, 11)) * 12.6 + 12)
        if y + height > BOTTOM:
            canv.showPage()
            y = _table_header(page, 60.0)
        y = _row(page, y, line)
    if y + 150 > A4_H - 40:
        canv.showPage()
        y = 60.0
    _person_blocks(page, data, y)


def build_pdf(notes):
    """PDF bytes for a list of goods received note dicts (one document each)."""
    buffer = BytesIO()
    canv = canvas.Canvas(buffer, pagesize=(A4_W, A4_H))
    canv.setTitle('Goods Received Note')
    for data in notes:
        draw(canv, data)
        canv.showPage()
    canv.save()
    return buffer.getvalue()
