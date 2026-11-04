import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .signoff import DOCUMENTS, REPORT_NAMES

REQUISITION_REPORT = 'purchase_request_rfq.report_purchase_request'
PREVIEWS = DOCUMENTS + [('requisition', 'Requisition')]


class ProcurementSignWizard(models.TransientModel):
    """The dialog a member signs from: the document is shown first, the signature comes after."""
    _name = 'procurement.sign.wizard'
    _description = 'Review and Sign'

    signoff_id = fields.Many2one('procurement.signoff', required=True, readonly=True, ondelete='cascade')
    rfq_id = fields.Many2one(related='signoff_id.rfq_id')
    document = fields.Selection(related='signoff_id.document')
    can_sign = fields.Boolean(compute='_compute_can_sign')
    preview_document = fields.Selection(PREVIEWS, string='Viewing', required=True, default='declaration')
    preview_pdf = fields.Binary(compute='_compute_preview_pdf')
    confirmed = fields.Boolean(string="I have read this document and agree to sign it")

    @api.depends('signoff_id.signed_date', 'signoff_id.user_id', 'signoff_id.rfq_id.committee_state')
    @api.depends_context('uid')
    def _compute_can_sign(self):
        for wizard in self:
            signoff = wizard.signoff_id
            wizard.can_sign = (
                not signoff.signed_date and signoff.user_id == self.env.user
                and signoff.rfq_id.committee_state == 'session')

    @api.depends('preview_document', 'signoff_id')
    def _compute_preview_pdf(self):
        Report = self.env['ir.actions.report'].sudo()
        for wizard in self:
            rfq = wizard.signoff_id.rfq_id.sudo()
            if not rfq:
                wizard.preview_pdf = False
                continue
            if wizard.preview_document == 'requisition':
                name, ids = REQUISITION_REPORT, [rfq.request_id.id]
            else:
                name, ids = REPORT_NAMES[wizard.preview_document], [rfq.id]
            pdf, _kind = Report._render_qweb_pdf(name, ids)
            wizard.preview_pdf = base64.b64encode(pdf).decode()

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Review and Sign'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'dialog_size': 'extra-large'},
        }

    def action_view_document(self):
        """Switch the document shown (the buttons above the viewer)."""
        self.ensure_one()
        preview = self.env.context.get('preview')
        if preview in dict(PREVIEWS):
            self.preview_document = preview
        return self._reopen()

    def action_sign(self):
        self.ensure_one()
        if not self.confirmed:
            raise UserError(_("Tick the box to confirm you have read the document."))
        self.signoff_id.action_sign()
        return {'type': 'ir.actions.act_window_close'}
