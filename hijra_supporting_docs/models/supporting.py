from odoo import fields, models

SOURCES = [
    ('manual', 'Provided by staff'),
    ('requisition', 'Requisition (SR)'),
    ('quotes', 'Quotes'),
    ('evaluation', 'Quote evaluation (committee)'),
    ('order', 'Purchase order (LPO)'),
    ('receipt', 'Goods received / service completion'),
    ('voucher', 'Payment voucher'),
]


class SupportingDocumentType(models.Model):
    """A kind of supporting document, e.g. Invoice or Approved SR.

    Where the system produces the document itself (the requisition, the quotes, the committee's
    evaluation, the order, the goods received or completion note, the voucher) the source says so and
    the document ticks itself on the payment; all others are provided by staff.
    """
    _name = 'supporting.document.type'
    _description = 'Supporting Document Type'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    source = fields.Selection(
        SOURCES, required=True, default='manual',
        help="'Provided by staff' documents are ticked or uploaded on the payment. The others are made by "
             "the system and count as available when their step is done.")
    description = fields.Text(help="Shown on the payment next to the document.")
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint('UNIQUE(name)', 'This document type already exists.')


class ExpenditureType(models.Model):
    """A type of expenditure (Vehicle Rental, Per Diem, Visibility ...) and the supporting documents
    its payments need. Changing the list does not change payments already made; a payment can
    refresh its checklist."""
    _name = 'expenditure.type'
    _description = 'Expenditure Type'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    receipt_type = fields.Selection(
        [('goods', 'Goods (Goods Received Note)'), ('service', 'Service (Service Completion Note)')],
        string='Receipt',
        help="Decides how purchases of this type are received: with a Goods Received Note or with a "
             "Service Completion Note (one or the other). Empty: the buyer chooses on the order.")
    note = fields.Text()
    line_ids = fields.One2many('expenditure.type.line', 'expenditure_type_id', string='Supporting Documents', copy=True)

    _name_uniq = models.Constraint('UNIQUE(name)', 'This expenditure type already exists.')


class ExpenditureTypeLine(models.Model):
    _name = 'expenditure.type.line'
    _description = 'Expenditure Type Document'
    _order = 'expenditure_type_id, sequence, id'

    expenditure_type_id = fields.Many2one('expenditure.type', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    document_type_id = fields.Many2one('supporting.document.type', string='Document', required=True)
    source = fields.Selection(related='document_type_id.source')
    requirement = fields.Selection(
        [('standard', 'Standard'), ('optional', 'Optional')], required=True, default='standard')
    description = fields.Text(string='Details')

    _doc_uniq = models.Constraint(
        'UNIQUE(expenditure_type_id, document_type_id)', 'This document is already in the list.')
