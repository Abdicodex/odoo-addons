import os

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import file_path

STAGES = [
    ('requisition', 'Requisition'),
    ('rfq', 'Quotations'),
    ('committee', 'Committee'),
    ('order', 'Purchase Order'),
    ('payment', 'Payment'),
    ('paid', 'Paid'),
]
COMMITTEE_DOCUMENTS = [
    ('declaration', 'Declaration of Impartiality', 'hijra_procurement.action_report_declaration'),
    ('analysis', 'Bid Analysis', 'hijra_procurement.action_report_bid_analysis'),
    ('statement', 'Committee Statement', 'hijra_procurement.action_report_committee_statement'),
    ('minutes', 'Minutes', 'hijra_procurement.action_report_committee_minutes'),
]


class ProcurementFile(models.Model):
    """One screen per requisition with every step of its procurement and the documents of each.

    The steps are read from the requisition, its RFQ, the committee session, the purchase order
    and (with the Pay Vendor module) the payments, so nothing is typed in twice.
    """
    _name = 'procurement.file'
    _description = 'Procurement File'
    _order = 'id desc'

    request_id = fields.Many2one('purchase.request', string='Requisition', required=True,
                                 ondelete='cascade', index=True)
    name = fields.Char(related='request_id.name', store=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    currency_id = fields.Many2one(related='request_id.currency_id')
    project_id = fields.Many2one(related='request_id.project_id', store=True)
    requester_id = fields.Many2one(related='request_id.requester_id', store=True)
    amount_total = fields.Monetary(
        related='request_id.amount_total', store=True, currency_field='currency_id')
    vendor_id = fields.Many2one('res.partner', string='Vendor', compute='_compute_vendor')
    stage = fields.Selection(STAGES + [('cancelled', 'Cancelled')], compute='_compute_stage')
    step_ids = fields.One2many('procurement.file.step', 'file_id', string='Steps')

    _request_uniq = models.Constraint('UNIQUE(request_id)', 'A requisition has one procurement file.')

    # ------------------------------------------------------------------
    # What the file reads
    # ------------------------------------------------------------------
    def _rfqs(self):
        self.ensure_one()
        return self.env['purchase.request.rfq'].sudo().search(
            [('request_id', '=', self.request_id.id)], order='id')

    def _awarded_order(self):
        self.ensure_one()
        rfqs = self._rfqs()
        order = rfqs.filtered('awarded_order_id')[-1:].awarded_order_id
        if not order:
            order = self.env['purchase.order'].sudo().search([
                ('purchase_request_id', '=', self.request_id.id), ('state', 'in', ('purchase', 'done'))], limit=1)
        return order

    @api.depends('request_id')
    def _compute_vendor(self):
        for rec in self:
            rec.vendor_id = rec._awarded_order().partner_id

    @api.depends('request_id.state')
    def _compute_stage(self):
        for rec in self:
            rec.stage = rec._current_stage()

    def _current_stage(self):
        self.ensure_one()
        request = self.request_id.sudo()
        if request.state in ('cancelled', 'rejected'):
            return 'cancelled'
        rfqs = self._rfqs()
        if not rfqs:
            return 'requisition'
        order = self._awarded_order()
        if not order:
            session = rfqs.filtered(lambda r: r.state == 'open' and r.committee_required
                                    and r.committee_state != 'pending')
            return 'committee' if session else 'rfq'
        if order.state in ('draft', 'sent', 'to approve'):
            return 'order'
        return self._stage_after_order(order)

    def _stage_after_order(self, order):
        """Hook: the Pay Vendor module tells when the order is paid."""
        return 'payment'

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    @staticmethod
    def _step(name, reference, state, detail, open_rec=None, print_xmlid=None, print_recs=None):
        return {
            'name': name,
            'reference': reference or '',
            'state': state,
            'detail': detail or '',
            'open_model': open_rec._name if open_rec else False,
            'open_id': open_rec.id if open_rec else 0,
            'print_xmlid': print_xmlid if print_recs else False,
            'print_model': print_recs._name if print_recs else False,
            'print_ids': ','.join(str(i) for i in print_recs.ids) if print_recs else False,
        }

    def _build_steps(self):
        """The steps, in the order of the procurement cycle."""
        self.ensure_one()
        request = self.request_id.sudo()
        steps = []
        label = dict(request._fields['state'].selection).get(request.state, request.state)
        steps.append(self._step(
            _("Purchase Requisition"), request.name,
            'done' if request.state in ('approved', 'rfq_created') else 'pending', label,
            request, 'purchase_request_rfq.action_report_purchase_request', request))
        rfqs = self._rfqs()
        if not rfqs:
            steps.append(self._step(_("Request for Quotation"), '', 'todo', _("Not created yet")))
        for rfq in rfqs:
            steps.append(self._step(
                _("Request for Quotation"), rfq.name, 'done' if rfq.quotes_count else 'pending',
                _("%(quotes)s quotes from %(vendors)s vendors", quotes=rfq.quotes_count,
                  vendors=rfq.invited_count),
                rfq, 'purchase.report_purchase_quotation', rfq.order_ids))
            if not rfq.committee_required:
                steps.append(self._step(
                    _("Committee"), rfq.name, 'done', _("Not required for this value"), rfq))
                continue
            for document, title, xmlid in COMMITTEE_DOCUMENTS:
                rows = rfq.signoff_ids.filtered(lambda s: s.document == document)
                signed = len(rows.filtered('signed_date'))
                if rows and signed == len(rows):
                    state = 'done'
                elif rows:
                    state = 'pending'
                else:
                    state = 'todo'
                detail = _("%(signed)s of %(total)s signed", signed=signed, total=len(rows)) if rows \
                    else _("Session not started")
                steps.append(self._step(title, rfq.name, state, detail, rfq, xmlid, rfq))
        order = self._awarded_order()
        if order:
            if order.state in ('purchase', 'done'):
                state, detail = 'done', _("Confirmed")
            elif not order.po_check_date:
                state, detail = 'pending', _("Waiting for the Finance Officer's check")
            else:
                state, detail = 'pending', _("Waiting for the Officer-in-Charge's authorization")
            steps.append(self._step(
                _("Purchase Order"), order.name, state, detail, order,
                'purchase.action_report_purchase_order', order))
            for bill in order.invoice_ids:
                steps.append(self._step(
                    _("Vendor Bill"), bill.name or _("Draft"),
                    'done' if bill.state == 'posted' else 'pending',
                    dict(bill._fields['payment_state'].selection).get(bill.payment_state, ''),
                    bill, 'account.account_invoices', bill))
        elif rfqs:
            steps.append(self._step(_("Purchase Order"), '', 'todo', _("Not awarded yet")))
        return steps

    def _refresh_steps(self):
        for rec in self:
            rec.step_ids.unlink()
            rec.step_ids = [
                Command.create(dict(step, sequence=index * 10))
                for index, step in enumerate(rec._build_steps(), 1)]

    def web_read(self, specification):
        """Opening the file rebuilds its steps, so they always show the current state."""
        if 'step_ids' in specification and len(self) == 1:
            self.sudo()._refresh_steps()
        return super().web_read(specification)

    def action_refresh(self):
        self.sudo()._refresh_steps()
        return True

    # ------------------------------------------------------------------
    # Printing everything
    # ------------------------------------------------------------------
    def _extra_pdf_parts(self, font_dir):
        """Hook: the Pay Vendor module adds the payment vouchers."""
        return []

    def _pdf_parts(self):
        """The PDF of every document of the file, in the order of the cycle."""
        self.ensure_one()
        from odoo.addons.purchase_request_rfq.report import prf_pdf, rfq_pdf

        from ..report import committee_pdf, po_pdf
        font_dir = os.path.dirname(file_path('purchase_request_rfq/static/fonts/Carlito-Regular.ttf'))
        request = self.request_id.sudo()
        parts = [prf_pdf.build_pdf([request._prepare_prf_data()], font_dir)]
        for rfq in self._rfqs():
            if rfq.order_ids:
                parts.append(rfq_pdf.build_pdf([o._prepare_rfq_pdf_data() for o in rfq.order_ids], font_dir))
            if rfq.committee_required:
                data = rfq._prepare_committee_data()
                for document, _title, _xmlid in COMMITTEE_DOCUMENTS:
                    parts.append(committee_pdf.build_pdf(document, [data], font_dir))
        order = self._awarded_order()
        if order:
            parts.append(po_pdf.build_pdf([order._prepare_po_pdf_data()], font_dir))
        parts += self._extra_pdf_parts(font_dir)
        return parts


class ProcurementFileStep(models.Model):
    _name = 'procurement.file.step'
    _description = 'Procurement File Step'
    _order = 'file_id, sequence, id'

    file_id = fields.Many2one('procurement.file', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer()
    name = fields.Char(string='Step', required=True)
    reference = fields.Char()
    state = fields.Selection(
        [('done', 'Done'), ('pending', 'In Progress'), ('todo', 'Not Started')], required=True)
    detail = fields.Char()
    open_model = fields.Char()
    open_id = fields.Integer()
    print_xmlid = fields.Char()
    print_model = fields.Char()
    print_ids = fields.Char()

    def action_open(self):
        """Go to the record of this step."""
        self.ensure_one()
        if not self.open_model or not self.open_id:
            raise UserError(_("Nothing to open for this step yet."))
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': self.open_model,
            'res_id': self.open_id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_print(self):
        """Print the document of this step."""
        self.ensure_one()
        if not self.print_xmlid or not self.print_ids:
            raise UserError(_("There is no document to print for this step yet."))
        ids = [int(value) for value in self.print_ids.split(',') if value]
        report = self.env.ref(self.print_xmlid)
        return report.with_context(discard_logo_check=True).report_action(
            self.env[self.print_model].browse(ids))
