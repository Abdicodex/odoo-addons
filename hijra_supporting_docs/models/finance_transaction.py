import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import file_path

STATUS = [
    ('system', 'Available (system)'),
    ('attached', 'Attached'),
    ('available', 'Available'),
    ('waived', 'Waived'),
    ('missing', 'Missing'),
    ('not_provided', 'Not provided'),
]


class FinanceTransaction(models.Model):
    _inherit = 'finance.transaction'

    expenditure_type_id = fields.Many2one('expenditure.type', string='Expenditure Type', tracking=True)
    document_ids = fields.One2many(
        'finance.transaction.document', 'transaction_id', string='Supporting Documents', copy=False)
    document_override_reason = fields.Char(
        string='Override Reason', copy=False,
        help="Write why the payment is posted although standard documents are missing. It is kept in the history.")
    documents_missing = fields.Integer(compute='_compute_documents_missing')

    @api.depends('document_ids.status', 'document_ids.requirement')
    def _compute_documents_missing(self):
        for rec in self:
            rec.documents_missing = len(rec.document_ids.filtered(lambda d: d.status == 'missing'))

    # ------------------------------------------------------------------
    # The checklist
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered('expenditure_type_id')._load_checklist()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'expenditure_type_id' in vals:
            self._load_checklist()
        return result

    def _load_checklist(self):
        """Build the document rows from the expenditure type. What was already ticked, uploaded or
        waived is kept; rows of another type that were used stay as additional documents."""
        Document = self.env['finance.transaction.document'].sudo()
        for rec in self:
            wanted = {line.document_type_id.id: line for line in rec.expenditure_type_id.line_ids}
            existing = {row.document_type_id.id: row for row in rec.document_ids.sudo()}
            for type_id, line in wanted.items():
                values = {
                    'sequence': line.sequence, 'requirement': line.requirement,
                    'description': line.description or line.document_type_id.description or False,
                }
                if type_id in existing:
                    existing[type_id].write(values)
                else:
                    Document.create(dict(values, transaction_id=rec.id, document_type_id=type_id))
            for type_id, row in existing.items():
                if type_id in wanted or row.requirement == 'extra':
                    continue
                if row.file or row.available or row.waived:
                    row.requirement = 'extra'
                else:
                    row.unlink()

    def action_refresh_checklist(self):
        self._load_checklist()
        return True

    # ------------------------------------------------------------------
    # Posting needs the standard documents
    # ------------------------------------------------------------------
    def action_post(self):
        for rec in self:
            missing = rec.document_ids.filtered(lambda d: d.status == 'missing')
            if not missing:
                continue
            reason = (rec.document_override_reason or '').strip()
            names = ', '.join(missing.mapped('document_type_id.name'))
            if not reason:
                raise UserError(_(
                    "%(number)s cannot be posted: standard supporting documents are missing (%(names)s).\n"
                    "Tick them as available, upload them, or waive them with a note on the Supporting "
                    "Documents tab; or write an override reason there to post anyway.",
                    number=rec.name, names=names))
            rec.message_post(body=_(
                "Posted with missing documents (%(names)s). Reason: %(reason)s", names=names, reason=reason))
        return super().action_post()

    # ------------------------------------------------------------------
    # The pack
    # ------------------------------------------------------------------
    def _font_dir(self):
        return os.path.dirname(file_path('purchase_request_rfq/static/fonts/Carlito-Regular.ttf'))

    def _prepare_cover_data(self):
        self.ensure_one()
        company = self.company_id.sudo()
        labels = dict(STATUS)
        rows = []
        for row in self.document_ids.sorted(lambda d: (d.sequence, d.id)):
            status = row.status
            text = labels[status]
            if status == 'system' and row.system_ref:
                text += ': %s' % row.system_ref
            elif status == 'attached' and row.file_name:
                text += ': %s' % row.file_name
            elif status == 'available':
                text = _("Available (not attached)")
            elif status == 'waived' and row.waiver_note:
                text += ': %s' % row.waiver_note
            rows.append({
                'name': row.document_type_id.name,
                'requirement': dict(row._fields['requirement'].selection)[row.requirement],
                'status': text.upper() if status == 'missing' else text,
                'state': status,
            })
        return {
            'logo': [value for value in (company.logo, getattr(company, 'logo_web', False)) if value],
            'number': self.name if self.name != 'New' else _("Draft"),
            'expenditure': self.expenditure_type_id.name or '',
            'payee': self.partner_id.name or '',
            'amount': '%s %s' % (format(self.amount, ',.2f'), self.currency_id.name or ''),
            'rows': rows,
            'override': (self.document_override_reason or '') if self.documents_missing else '',
        }

    def _render_pack(self):
        """PDF of the cover sheet followed by every document, in the order of the checklist."""
        from odoo.tools.pdf import merge_pdf

        from ..report import pack_pdf
        self.ensure_one()
        parts = [pack_pdf.build_cover(self._prepare_cover_data(), self._font_dir())]
        for row in self.document_ids.sorted(lambda d: (d.sequence, d.id)):
            parts += row._pdf_parts()
        return merge_pdf(parts)


class FinanceTransactionDocument(models.Model):
    """One supporting document of a payment: ticked as available, uploaded, waived, or made by the system."""
    _name = 'finance.transaction.document'
    _description = 'Payment Supporting Document'
    _order = 'transaction_id, sequence, id'

    transaction_id = fields.Many2one(
        'finance.transaction', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=100)
    document_type_id = fields.Many2one('supporting.document.type', string='Document', required=True)
    source = fields.Selection(related='document_type_id.source')
    requirement = fields.Selection(
        [('standard', 'Standard'), ('optional', 'Optional'), ('extra', 'Additional')],
        required=True, default='extra')
    description = fields.Text()
    available = fields.Boolean(string='Available', help="Tick when the document exists (on paper or elsewhere).")
    waived = fields.Boolean(string='Waived')
    waiver_note = fields.Char(string='Waiver Note')
    file = fields.Binary(string='Upload', attachment=True)
    file_name = fields.Char(string='File Name')
    system_available = fields.Boolean(compute='_compute_system')
    system_ref = fields.Char(compute='_compute_system')
    status = fields.Selection(STATUS, compute='_compute_status')

    @api.depends('document_type_id.source', 'transaction_id.purchase_order_id', 'transaction_id.name')
    def _compute_system(self):
        for rec in self:
            source = rec.document_type_id.source
            order = rec.transaction_id.purchase_order_id.sudo()
            request = order.purchase_request_id
            rfq = order.rfq_group_id
            ok, ref = False, ''
            if source == 'voucher':
                ok, ref = True, rec.transaction_id.name
            elif source == 'requisition' and request:
                ok, ref = request.state in ('approved', 'rfq_created'), request.name
            elif source == 'quotes' and rfq:
                ok, ref = rfq.quotes_count > 0, rfq.name
            elif source == 'evaluation' and rfq:
                ok = rfq.committee_state == 'decided' if rfq.committee_required else rfq.state == 'awarded'
                ref = rfq.name
            elif source == 'order' and order:
                ok, ref = order.state in ('purchase', 'done'), order.name
            elif source == 'receipt' and order:
                grns = order.grn_ids.filtered(lambda g: g.state == 'checked')
                notes = order.completion_ids.filtered(lambda c: c.state == 'approved')
                ok, ref = bool(grns or notes), ', '.join(grns.mapped('name') + notes.mapped('name'))
            rec.system_available = ok
            rec.system_ref = ref if ok else ''

    @api.depends('available', 'waived', 'file', 'requirement', 'system_available')
    def _compute_status(self):
        for rec in self:
            if rec.system_available:
                rec.status = 'system'
            elif rec.file:
                rec.status = 'attached'
            elif rec.available:
                rec.status = 'available'
            elif rec.waived:
                rec.status = 'waived'
            elif rec.requirement == 'standard':
                rec.status = 'missing'
            else:
                rec.status = 'not_provided'

    @api.onchange('file')
    def _onchange_file(self):
        if self.file:
            self.available = True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('file'):
                vals['available'] = True
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('file'):
            vals['available'] = True
        return super().write(vals)

    # ------------------------------------------------------------------
    # What this document prints in the pack
    # ------------------------------------------------------------------
    def _pdf_parts(self):
        """PDF documents of this row, in order: the system's own document, then the upload."""
        self.ensure_one()
        from odoo.addons.hijra_procurement.models.procurement_file import COMMITTEE_DOCUMENTS as COMMITTEE
        from odoo.addons.hijra_receipts.report import completion_pdf, grn_pdf
        from odoo.addons.purchase_request_rfq.report import prf_pdf, rfq_pdf

        from odoo.addons.hijra_finance.report import voucher_pdf
        from odoo.addons.hijra_procurement.report import committee_pdf, po_pdf

        from ..report import pack_pdf
        font_dir = self.transaction_id._font_dir()
        source = self.document_type_id.source
        order = self.transaction_id.purchase_order_id.sudo()
        parts = []
        if self.system_available:
            if source == 'voucher':
                try:
                    parts.append(voucher_pdf.build_pdf([self.transaction_id._prepare_voucher_data()]))
                except UserError:
                    pass  # the payment is not complete yet (no account): the cover still lists it
            elif source == 'requisition':
                parts.append(prf_pdf.build_pdf([order.purchase_request_id._prepare_prf_data()], font_dir))
            elif source == 'quotes':
                rfq = order.rfq_group_id
                if rfq.order_ids:
                    parts.append(rfq_pdf.build_pdf([o._prepare_rfq_pdf_data() for o in rfq.order_ids], font_dir))
                for attachment in self.env['ir.attachment'].sudo().search(
                        [('res_model', '=', 'purchase.order'), ('res_id', 'in', rfq.order_ids.ids)]):
                    pdf = pack_pdf.file_to_pdf(attachment.raw or b'', attachment.name)
                    if pdf:
                        parts.append(pdf)
            elif source == 'evaluation':
                rfq = order.rfq_group_id
                data = rfq._prepare_committee_data()
                names = [name for name, _t, _x in COMMITTEE] if rfq.committee_required else ['analysis']
                parts += [committee_pdf.build_pdf(name, [data], font_dir) for name in names]
            elif source == 'order':
                parts.append(po_pdf.build_pdf([order._prepare_po_pdf_data()], font_dir))
            elif source == 'receipt':
                grns = order.grn_ids.filtered(lambda g: g.state == 'checked')
                notes = order.completion_ids.filtered(lambda c: c.state == 'approved')
                if grns:
                    parts.append(grn_pdf.build_pdf([g._prepare_grn_pdf_data() for g in grns]))
                if notes:
                    parts.append(completion_pdf.build_pdf([n._prepare_completion_pdf_data() for n in notes]))
        return parts + self._upload_parts()

    def _upload_parts(self):
        """The uploaded file of this row as PDF, if it can be printed (PDFs and images)."""
        self.ensure_one()
        from ..report import pack_pdf
        if not self.file:
            return []
        pdf = pack_pdf.file_to_pdf(pack_pdf.raw_bytes(self.file), self.file_name or '')
        return [pdf] if pdf else []
