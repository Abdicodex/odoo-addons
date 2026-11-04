"""The HIJRA Purchase Order, drawn as a PDF (A4) following the HIJRA Word template.

Supplier and buyer blocks, delivery address, the item table with a dark header, the totals, the
terms and conditions and the Prepared / Checked / Authorized signature lines. Plain reportlab so it
can be tested without Odoo.
"""
from io import BytesIO

from reportlab.pdfgen import canvas

from .pdf_common import A4_H, A4_W, SANS, SANS_BOLD, Page, fmt_amount, register_fonts, wrap

LEFT, RIGHT = 28.0, 539.0
DARK = (60 / 255.0, 60 / 255.0, 58 / 255.0)
GRID = 0.78
COLS = [LEFT, 77.7, 234.7, 288.7, 338.4, 419.6, 471.0, RIGHT]      # code, description, qty, unit, cost, vat, amount
BODY_BOTTOM = 800.0

ORG_NAME = 'HUMANITARIAN INITIATIVE JUST RELIEF AID (HIJRA)'
ORG_LINES = ['Rayaan Office Suite, KM5 Zoobe', 'info@hijra.or.ke', '252 615891401']
TERMS = [
    "All the goods/services supplied MUST be as per order and MUST meet all the specified conditions",
    "HIJRA reserves the right to return all the goods which may be found defective during consumption "
    "where such conditions could not be verified or established during receipt of the goods.",
    "Goods/services are received subject to verification in due course",
    "All payment will be by crossed cheques issued by HIJRA and in line with stated terms.",
    "The prices on the LPO include delivery costs to the specified delivery/receiving point",
]


def fmt_long_date(value):
    return value.strftime('%B %d, %Y').replace(' 0', ' ') if value else ''


def _header(page, data, first):
    if first:
        page.text(LEFT, 52, 'Purchase Order', SANS_BOLD, 24)
        if data.get('logo'):
            page.image(data['logo'], (RIGHT - 105, 20, RIGHT, 78), align='right')
        page.text(LEFT, 90, 'PO: %s' % data['name'], SANS_BOLD, 14)
        page.text(LEFT + 190, 90, fmt_long_date(data['date']), SANS, 14)
        return 106.0
    page.text(LEFT, 40, 'Purchase Order', SANS_BOLD, 11)
    page.text(LEFT + 90, 40, data['name'], SANS, 11)
    page.text(LEFT + 190, 40, fmt_long_date(data['date']), SANS, 11)
    page.text(RIGHT, 40, 'Page %d' % page.c.getPageNumber(), SANS, 10, align='right')
    return 56.0


def _parties(page, data, y):
    supplier = data['supplier']
    page.text(LEFT, y + 10, 'Supplier: %s' % (supplier.get('code') or ''), SANS_BOLD, 10)
    for index, line in enumerate(supplier['lines']):
        for sub, text in enumerate(wrap(line, SANS, 236, 9.5)):
            page.text(LEFT, y + 24 + 12.5 * index + 12.5 * sub, text, SANS, 9.5)
    page.text(300, y + 10, 'Buyer:', SANS_BOLD, 10)
    for index, line in enumerate(data['buyer']['lines']):
        for sub, text in enumerate(wrap(line, SANS, 236, 9.5)):
            page.text(300, y + 24 + 12.5 * index + 12.5 * sub, text, SANS, 9.5)
    count = max(len(supplier['lines']), len(data['buyer']['lines']))
    return y + 24 + 12.5 * count + 12


def _table_header(page, y):
    page.rect(LEFT, y, RIGHT, y + 22, fill=DARK, stroke=False)
    labels = ['Code', 'Description', 'Quantity', 'Unit', 'Unit Cost', 'VAT %', 'Line Amount']
    for index, label in enumerate(labels):
        if index in (0, 1, 3):
            page.text(COLS[index] + 4, y + 15, label, SANS_BOLD, 9.5, (1, 1, 1))
        else:
            page.text(COLS[index + 1] - 4, y + 15, label, SANS_BOLD, 9.5, (1, 1, 1), 'right')
    return y + 22


def _row(page, y, line):
    desc = wrap(line['description'], SANS, COLS[2] - COLS[1] - 8, 9.5)
    code = wrap(line['code'], SANS, COLS[1] - COLS[0] - 6, 9.5)
    height = max(22.0, max(len(desc), len(code)) * 12 + 9)
    base = y + 15
    for i, text in enumerate(code):
        page.text(COLS[0] + 4, base + 12 * i, text, SANS, 9.5)
    for i, text in enumerate(desc):
        page.text(COLS[1] + 4, base + 12 * i, text, SANS, 9.5)
    page.text(COLS[3] - 4, base, '%g' % line['qty'], SANS, 9.5, align='right')
    page.text(COLS[3] + 4, base, line['unit'], SANS, 9.5)
    page.text(COLS[5] - 4, base, fmt_amount(line['price']), SANS, 9.5, align='right')
    page.text(COLS[6] - 4, base, '%g' % line['vat'], SANS, 9.5, align='right')
    page.text(COLS[7] - 4, base, fmt_amount(line['amount']), SANS, 9.5, align='right')
    page.line(LEFT, y + height, RIGHT, y + height, 0.4, GRID)
    return y + height


def _totals(page, data, y):
    currency = data['currency']
    rows = [('Total %s Excl. VAT' % currency, data['untaxed'], False),
            ('VAT Amount', data['tax'], False),
            ('Total %s Incl. VAT' % currency, data['total'], True)]
    y += 6
    for label, value, bold in rows:
        font = SANS_BOLD if bold else SANS
        page.text(COLS[5] - 6, y + 14, label, font, 9.5, align='right')
        page.text(COLS[7] - 4, y + 14, fmt_amount(value), font, 9.5, align='right')
        y += 18
    return y + 8


def _terms(page, y):
    page.text(LEFT, y + 10, 'TERMS AND CONDITIONS', SANS_BOLD, 10)
    y += 18
    for number, term in enumerate(TERMS, 1):
        lines = wrap(term, SANS, RIGHT - LEFT - 16, 9)
        page.text(LEFT, y + 9, '%d.' % number, SANS, 9)
        for line in lines:
            page.text(LEFT + 16, y + 9, line, SANS, 9)
            y += 11.5
        y += 2
    return y + 6


def _signatures(page, data, y):
    blocks = [('Prepared by:', data['prepared']), ('Checked by:', data['checked']),
              ('Authorized by:', data['authorized'])]
    for label, person in blocks:
        top = y
        page.text(LEFT, top + 28, label, SANS_BOLD, 10)
        name_x = LEFT + 78
        page.text(name_x + 4, top + 26, person.get('name') or '', SANS, 10)
        page.line(name_x, top + 30, name_x + 150, top + 30, 0.6)
        page.text(name_x + 164, top + 28, 'Date:', SANS, 10)
        page.text(name_x + 192, top + 26, person.get('date') or '', SANS, 10)
        page.line(name_x + 190, top + 30, name_x + 296, top + 30, 0.6)
        page.text(name_x + 310, top + 28, 'Signature:', SANS, 10)
        sign_x = name_x + 358
        page.line(sign_x, top + 30, RIGHT, top + 30, 0.6)
        if person.get('signature'):
            page.image(person['signature'], (sign_x + 2, top, RIGHT - 2, top + 29), 'left', 'bottom')
        y += 46
    return y


def draw(canv, data):
    page = Page(canv, A4_W, A4_H, LEFT)
    y = _header(page, data, True)
    y = _parties(page, data, y)
    page.text(LEFT, y + 10, 'Delivery Address:', SANS_BOLD, 10)
    page.text(LEFT + 90, y + 10, data.get('delivery') or '', SANS, 10)
    y += 24
    y = _table_header(page, y)
    for line in data['lines']:
        height = max(22.0, len(wrap(line['description'], SANS, COLS[2] - COLS[1] - 8, 9.5)) * 12 + 9)
        if y + height > BODY_BOTTOM - 20:
            canv.showPage()
            y = _header(page, data, False)
            y = _table_header(page, y)
        y = _row(page, y, line)
    need = 70 + 22 * len(TERMS) + 46 * 3
    if y + need > BODY_BOTTOM:
        canv.showPage()
        y = _header(page, data, False)
    y = _totals(page, data, y)
    y = _terms(page, y)
    _signatures(page, data, y + 4)


def build_pdf(orders, font_dir):
    """PDF bytes for a list of purchase order dicts (one document each)."""
    register_fonts(font_dir)
    buffer = BytesIO()
    canv = canvas.Canvas(buffer, pagesize=(A4_W, A4_H))
    canv.setTitle('Purchase Order')
    for data in orders:
        draw(canv, data)
        canv.showPage()
    canv.save()
    return buffer.getvalue()
