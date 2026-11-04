"""The four documents of a procurement committee session, drawn as PDFs.

Declaration of Impartiality and Confidentiality, Summary of Bid Analysis, Procurement
Committee Statement and the Minutes of the meeting, following the HIJRA templates.
Plain reportlab so it can be tested without Odoo.
"""
from io import BytesIO

from reportlab.pdfgen import canvas

from .pdf_common import (
    A4_H, A4_W, GREEN, GREY_BAND, SANS, SANS_BOLD, Page, fmt_amount, fmt_date, fmt_short_date,
    register_fonts, text_width, wrap)

DECLARATION_PARAGRAPHS = [
    "I, the undersigned, hereby declare that I agree to participate in the evaluation of the "
    "above-mentioned RFQ. By making this declaration, I confirm that I have familiarised myself "
    "with the information available to date concerning HIJRA Purchase and Evaluation procedure.",
    "I confirm that I shall execute my responsibilities impartially and objectively. I hereby "
    "declare that I am independent of all parties which stand to gain from the outcome of the "
    "evaluation process.",
    "To the best of my knowledge and belief, there are no facts or circumstances, past or present, "
    "or that could arise in the foreseeable future, which might call into question my independence "
    "in the eyes of any party; and if I discover or should it become apparent during the course of "
    "the evaluation process that such a relationship exists or has been established, I will "
    "declare it immediately and cease to participate in the evaluation process.",
    "I further declare that to the best of my knowledge; I am not in a situation that could cast "
    "doubt on my ability to evaluate the tender.",
    "I agree to hold in trust and confidence any information or documents (\"confidential "
    "information\") disclosed to me or discovered by me or prepared by me in the course of or as a "
    "result of the evaluation and agree that it shall be used only for the purposes of this "
    "evaluation and shall not be disclosed to any third party. I also agree not to retain copies "
    "of any written information or samples supplied.",
    "Confidential information shall not be disclosed to any employee or expert unless they agree "
    "to execute and be bound by the terms of this Declaration.",
]
DECLARATION_NOTE = (
    "Taking into consideration whether there exists any past or present relationship, direct or "
    "indirect, whether financial, professional or of another kind")

M = 56.0          # page margin of the portrait documents


def _signed(member, document):
    return (member.get('signed') or {}).get(document) or {}


# ---------------------------------------------------------------------------
# 1. Declaration of Impartiality and Confidentiality
# ---------------------------------------------------------------------------
def draw_declaration(canv, data):
    page = Page(canv, A4_W, A4_H, M)
    page.logo(data)
    width = A4_W - 2 * M
    page.text(M, 100, 'Declaration of Impartiality and Confidentiality', SANS_BOLD, 17, GREEN)
    page.text(M, 128, 'Tender ref: %s' % data['tender_ref'], SANS_BOLD, 11.5)
    page.text(M, 146, '(Purchase Committee)', SANS, 11)
    y = 168.0
    for paragraph in DECLARATION_PARAGRAPHS:
        y = page.paragraph(M, y, width, paragraph, SANS, 10.5, 13.4) + 6
    y += 6
    page.text(M, y + 11, 'To be signed during the Purchase Committee Session:', SANS_BOLD, 11)
    y += 22
    c1, c2, c3 = M, M + 110, M + 300
    row_h = 40.0
    for member in data['members']:
        sign = _signed(member, 'declaration')
        page.rect(c1, y, A4_W - M, y + row_h)
        page.line(c2, y, c2, y + row_h)
        page.line(c3, y, c3, y + row_h)
        page.text(c1 + 6, y + row_h / 2.0 + 3.5, 'Name & Signature', SANS_BOLD, 10.5)
        page.text(c2 + 6, y + row_h / 2.0 + 3.5, member['name'], SANS, 10.5)
        if sign.get('signature'):
            page.image(sign['signature'], (c3 + 6, y + 3, A4_W - M - 6, y + row_h - 3), 'left', 'middle')
        y += row_h
    date_value = ''
    dates = [_signed(m, 'declaration').get('date') for m in data['members']]
    dates = [d for d in dates if d]
    if dates:
        date_value = fmt_date(max(dates))
    page.rect(c1, y, A4_W - M, y + 26)
    page.line(c2, y, c2, y + 26)
    page.text(c1 + 6, y + 17, 'Date', SANS_BOLD, 10.5)
    page.text(c2 + 6, y + 17, date_value, SANS, 10.5)
    y += 44
    page.rect(c1, y, A4_W - M, y + 36, fill=GREY_BAND)
    page.paragraph(c1 + 8, y + 5, A4_W - 2 * M - 16, DECLARATION_NOTE, SANS, 10, 12.5)


# ---------------------------------------------------------------------------
# 2. Summary of Bid Analysis (landscape)
# ---------------------------------------------------------------------------
def draw_bid_analysis(canv, data):
    width, height, margin = A4_H, A4_W, 36.0
    page = Page(canv, width, height, margin)
    page.logo(data, box=(100, 50))
    page.text(margin, 70, 'HIJRA', SANS_BOLD, 16, GREEN)
    page.text(width / 2.0, 70, 'SUMMARY OF BID ANALYSIS', SANS_BOLD, 14, (0, 0, 0), 'center')
    page.text(margin, 100, 'Purchase Requisition Number: %s' % data['tender_ref'], SANS_BOLD, 10.5)
    page.text(margin, 124, 'Section I: Vendors', SANS_BOLD, 11, GREEN)

    vendors = data['vendors'][:6]
    avail = width - 2 * margin
    no_w, unit_w, qty_w = 26.0, 66.0, 44.0
    rest = avail - no_w - unit_w - qty_w
    pair_w = min(118.0, (rest - 120.0) / max(len(vendors), 1))
    desc_w = rest - pair_w * len(vendors)
    xs = [margin, margin + no_w]
    xs.append(xs[-1] + desc_w)
    xs.append(xs[-1] + unit_w)
    xs.append(xs[-1] + qty_w)
    for _vendor in vendors:
        xs.append(xs[-1] + pair_w)
    right = xs[-1]
    unit_col = (pair_w * 0.45)

    y = 134.0
    head_h = 24.0
    page.rect(margin, y, right, y + head_h * 2, fill=GREY_BAND)
    for x in xs:
        page.line(x, y, x, y + head_h * 2)
    page.line(margin, y + head_h, right, y + head_h)
    page.text(margin + 4, y + 30, 'No.', SANS_BOLD, 9.5)
    page.text(xs[1] + 4, y + 30, 'Item Description:', SANS_BOLD, 9.5)
    page.text(xs[2] + 4, y + 22, 'Measurement', SANS_BOLD, 9)
    page.text(xs[2] + 4, y + 33, 'Type', SANS_BOLD, 9)
    page.text(xs[3] + 4, y + 30, 'Quantity', SANS_BOLD, 9.5)
    for index, vendor in enumerate(vendors):
        x0, x1 = xs[4 + index], xs[5 + index]
        label = 'Vendor %d: %s' % (index + 1, vendor['name'])
        lines = wrap(label, SANS_BOLD, pair_w - 6, 8.5)[:2]
        for i, line in enumerate(lines):
            page.text(x0 + 3, y + 10 + 9 * i, line, SANS_BOLD, 8.5)
        page.line(x0 + unit_col, y + head_h, x0 + unit_col, y + head_h * 2)
        page.text(x0 + 3, y + head_h + 15, 'UNIT PRICE', SANS_BOLD, 7.5)
        page.text(x0 + unit_col + 3, y + head_h + 15, 'TOTAL', SANS_BOLD, 7.5)
    y += head_h * 2

    for item in data['items']:
        lines = wrap(item['description'], SANS, desc_w - 8, 9.5)
        row_h = max(20.0, len(lines) * 11.5 + 8)
        page.rect(margin, y, right, y + row_h, stroke=False)
        page.line(margin, y + row_h, right, y + row_h)
        for x in xs:
            page.line(x, y, x, y + row_h)
        page.text(margin + 4, y + 13, item['no'], SANS, 9.5)
        for i, line in enumerate(lines):
            page.text(xs[1] + 4, y + 13 + 11.5 * i, line, SANS, 9.5)
        page.text(xs[2] + 4, y + 13, item['unit'], SANS, 9.5)
        page.text(xs[4] - 5, y + 13, '%g' % item['qty'], SANS, 9.5, align='right')
        for index in range(len(vendors)):
            price = item['prices'][index] if index < len(item['prices']) else None
            x0 = xs[4 + index]
            if price:
                page.text(x0 + unit_col - 4, y + 13, fmt_amount(price[0]), SANS, 9, align='right')
                page.text(x0 + pair_w - 4, y + 13, fmt_amount(price[1]), SANS, 9, align='right')
        y += row_h
    # totals
    page.rect(margin, y, right, y + 22, fill=GREY_BAND)
    for x in xs:
        page.line(x, y, x, y + 22)
    page.text(xs[1] + 4, y + 15, 'Total Costs', SANS_BOLD, 10)
    for index, vendor in enumerate(vendors):
        page.text(xs[5 + index] - 4, y + 15, fmt_amount(vendor['total']), SANS_BOLD, 10, align='right')
    y += 34

    if data.get('selected_name'):
        sentence = '%s has been selected as the winning vendor' % data['selected_name']
        if data.get('subject'):
            sentence += ' to provide %s' % data['subject']
        y = page.paragraph(margin, y, avail, sentence + '.', SANS_BOLD, 10.5, 13) + 12

    # committee signatures
    y = max(y, 330.0) if y < 330 else y
    if y > height - 140:
        canv.showPage()
        y = margin
    page.text(margin, y + 10, 'Procurement Committee', SANS_BOLD, 11, GREEN)
    y += 18
    col = [margin, margin + 280, margin + 420, right]
    page.rect(margin, y, right, y + 20, fill=GREY_BAND)
    for x in col[1:-1]:
        page.line(x, y, x, y + 20)
    page.text(col[1] + 6, y + 14, 'Date', SANS_BOLD, 10)
    page.text(col[2] + 6, y + 14, 'Signature', SANS_BOLD, 10)
    y += 20
    for number, member in enumerate(data['members'], 1):
        sign = _signed(member, 'analysis')
        row_h = 34.0
        page.rect(margin, y, right, y + row_h)
        for x in col[1:-1]:
            page.line(x, y, x, y + row_h)
        page.text(margin + 6, y + 15, 'Member # %d' % number, SANS_BOLD, 10)
        page.text(margin + 6, y + 27, member['name'], SANS, 10)
        page.text(col[1] + 6, y + 15, fmt_date(sign.get('date')), SANS, 10)
        page.text(col[1] + 6, y + 27, member.get('position') or '', SANS, 9, (0.35, 0.35, 0.35))
        if sign.get('signature'):
            page.image(sign['signature'], (col[2] + 6, y + 3, right - 6, y + row_h - 3), 'left', 'middle')
        y += row_h


# ---------------------------------------------------------------------------
# 3. Procurement Committee Statement
# ---------------------------------------------------------------------------
def draw_statement(canv, data):
    page = Page(canv, A4_W, A4_H, M)
    page.logo(data)
    width = A4_W - 2 * M
    page.text(M, 100, 'Procurement Committee Statement', SANS_BOLD, 17, GREEN)
    y = 140.0
    for label, value in (('Date:', fmt_date(data.get('date'))), ('Project:', data.get('project')),
                         ('RFQ Date:', fmt_date(data.get('rfq_date')))):
        page.text(M, y, label, SANS_BOLD, 11)
        page.text(M + 70, y, value, SANS, 11)
        y += 24
    y += 6
    y = page.paragraph(
        M, y, width,
        "In accordance with HIJRA Procurement Policy & Procedure, Requests for Quotation were issued; "
        "Shortlisted Vendors quoted as follows:", SANS, 11, 14) + 10
    cols = [M, M + 30, M + 330, M + 430, A4_W - M]
    page.rect(M, y, A4_W - M, y + 22, fill=GREY_BAND)
    for x in cols[1:-1]:
        page.line(x, y, x, y + 22)
    page.text(cols[1] + 6, y + 15, 'Vendor Name', SANS_BOLD, 10.5)
    page.text(cols[2] + 6, y + 15, 'Amount', SANS_BOLD, 10.5)
    page.text(cols[3] + 6, y + 15, 'Currency', SANS_BOLD, 10.5)
    y += 22
    for number, vendor in enumerate(data['vendors'], 1):
        page.rect(M, y, A4_W - M, y + 22)
        for x in cols[1:-1]:
            page.line(x, y, x, y + 22)
        page.text(cols[0] + 8, y + 15, number, SANS, 10.5)
        page.text(cols[1] + 6, y + 15, vendor['name'], SANS, 10.5)
        page.text(cols[3] - 8, y + 15, fmt_amount(vendor['total']), SANS, 10.5, align='right')
        page.text(cols[3] + 6, y + 15, vendor.get('currency_name') or data.get('currency') or '', SANS, 10.5)
        y += 22
    y += 18
    page.text(M, y + 11, 'Bid Analysis:', SANS_BOLD, 11, GREEN)
    y = page.paragraph(
        M, y + 18, width,
        "The information was reviewed and analyzed in accordance with organizational policies and "
        "procedures.", SANS, 11, 14) + 12
    page.text(M, y + 11, 'Recommendation:', SANS_BOLD, 11, GREEN)
    y += 20
    if data.get('selected_name'):
        reason = data.get('reason') or ''
        y = page.paragraph(M, y, width, 'Vendor # %s  %s' % (data.get('selected_no') or '', reason),
                           SANS, 11, 14) + 12
        page.text(M, y + 11, 'The bidding committee therefore recommends the award of the project to:',
                  SANS, 11)
        page.text(M, y + 30, data['selected_name'], SANS_BOLD, 12)
        y += 52
    page.text(M, y + 11, 'In Unanimous Agreement:', SANS_BOLD, 11, GREEN)
    y += 24
    for number, member in enumerate(data['members'], 1):
        sign = _signed(member, 'statement')
        row_h = 40.0
        page.text(M, y + 22, 'Member # %d' % number, SANS_BOLD, 10.5)
        page.text(M + 80, y + 22, member['name'], SANS, 10.5)
        page.line(M + 300, y + row_h - 6, A4_W - M, y + row_h - 6)
        if sign.get('signature'):
            page.image(sign['signature'], (M + 304, y, A4_W - M - 4, y + row_h - 8), 'left', 'bottom')
        if sign.get('date'):
            page.text(A4_W - M, y + row_h + 5, fmt_short_date(sign['date']), SANS, 8, (0.4, 0.4, 0.4), 'right')
        y += row_h + 10
    if data.get('observer'):
        observer = data['observer']
        page.text(M, y + 22, 'Observer', SANS_BOLD, 10.5)
        page.text(M + 80, y + 22, '%s, %s' % (observer.get('name') or '', observer.get('organization') or ''),
                  SANS, 10.5)
        page.line(M + 300, y + 34, A4_W - M, y + 34)


# ---------------------------------------------------------------------------
# 4. Minutes of the meeting
# ---------------------------------------------------------------------------
def draw_minutes(canv, data):
    page = Page(canv, A4_W, A4_H, M)
    page.logo(data)
    width = A4_W - 2 * M
    page.text(M, 100, 'Procurement Committee Minutes', SANS_BOLD, 17, GREEN)
    page.text(M, 122, '%s  -  %s' % (data['tender_ref'], fmt_date(data.get('date'))), SANS, 10.5)
    y = 146.0
    for member in data['members']:
        page.text(M, y, member['name'], SANS_BOLD, 10.5)
        page.text(M + 190, y, member.get('position') or '', SANS, 10.5)
        y += 15
    if data.get('observer'):
        observer = data['observer']
        page.text(M, y, observer.get('name') or '', SANS_BOLD, 10.5)
        page.text(M + 190, y, 'Observer, %s' % (observer.get('organization') or ''), SANS, 10.5)
        y += 15
    y += 10
    page.text(M, y + 11, 'Agenda', SANS_BOLD, 12, GREEN)
    y = page.paragraph(M, y + 18, width, data.get('agenda') or '', SANS, 10.5, 13.4) + 10
    page.text(M, y + 11, 'Preliminaries', SANS_BOLD, 12, GREEN)
    y += 22
    if data.get('start'):
        y = page.paragraph(M, y, width, 'The meeting began at %s' % data['start'], SANS, 10.5, 13.4) + 8
    # the Minute | Status table
    col = M + width * 0.78
    page.rect(M, y, A4_W - M, y + 22, fill=GREY_BAND)
    page.line(col, y, col, y + 22)
    page.text(M + 6, y + 15, 'Minute', SANS_BOLD, 10.5)
    page.text(col + 6, y + 15, 'Status', SANS_BOLD, 10.5)
    y += 22
    lines = wrap(data.get('minutes') or '', SANS, col - M - 12, 10.5)
    top = y
    for line in lines:
        if y + 16 > A4_H - 180:
            page.line(M, top, M, y)
            page.line(A4_W - M, top, A4_W - M, y)
            page.line(col, top, col, y)
            canv.showPage()
            y = top = M
        page.text(M + 6, y + 13, line, SANS, 10.5)
        y += 13.4
    y += 6
    page.rect(M, top, A4_W - M, y, stroke=True)
    page.line(col, top, col, y)
    if data.get('end'):
        y += 12
        y = page.paragraph(
            M, y, width, 'There being no other business, the meeting ended at %s' % data['end'],
            SANS, 10.5, 13.4) + 14
    else:
        y += 14
    if y > A4_H - 150:
        canv.showPage()
        y = M
    for member in data['members']:
        sign = _signed(member, 'minutes')
        row_h = 40.0
        if y + row_h > A4_H - 50:
            canv.showPage()
            y = M
        page.text(M, y + 20, member['name'], SANS_BOLD, 10.5)
        label_x = M + 200
        page.text(label_x, y + 20, 'Signature:', SANS, 10.5)
        sx = label_x + text_width('Signature: ', SANS, 10.5)
        page.line(sx, y + 22, A4_W - M, y + 22)
        if sign.get('signature'):
            page.image(sign['signature'], (sx + 2, y - 8, A4_W - M - 4, y + 21), 'left', 'bottom')
        y += row_h
    page.text(A4_W / 2.0, A4_H - 28, 'Page |%d' % canv.getPageNumber(), SANS, 9, (0.4, 0.4, 0.4), 'center')


DRAWERS = {
    'declaration': draw_declaration,
    'analysis': draw_bid_analysis,
    'statement': draw_statement,
    'minutes': draw_minutes,
}
TITLES = {
    'declaration': 'Declaration of Impartiality and Confidentiality',
    'analysis': 'Summary of Bid Analysis',
    'statement': 'Procurement Committee Statement',
    'minutes': 'Procurement Committee Minutes',
}


def build_pdf(document, items, font_dir):
    """PDF bytes: one page (or more) per data dict in `items` for the given document."""
    register_fonts(font_dir)
    buffer = BytesIO()
    if document == 'analysis':
        canv = canvas.Canvas(buffer, pagesize=(A4_H, A4_W))
    else:
        canv = canvas.Canvas(buffer, pagesize=(A4_W, A4_H))
    canv.setTitle(TITLES[document])
    for data in items:
        DRAWERS[document](canv, data)
        canv.showPage()
    canv.save()
    return buffer.getvalue()
