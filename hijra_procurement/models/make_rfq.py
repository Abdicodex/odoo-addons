from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseRequestMakeRfq(models.TransientModel):
    _inherit = 'purchase.request.make.rfq'

    vendor_count = fields.Integer(compute='_compute_shortfall')
    min_invitations = fields.Integer(compute='_compute_shortfall')
    shortfall = fields.Boolean(compute='_compute_shortfall')
    shortfall_justification = fields.Text(
        string='Justification',
        help="Why fewer vendors than the procurement policy asks for are invited.")

    @api.depends('request_id.amount_total', 'partner_ids')
    def _compute_shortfall(self):
        Band = self.env['procurement.band']
        for wizard in self:
            band = Band._band_for(wizard.request_id.amount_total)
            wizard.vendor_count = len(wizard.partner_ids)
            wizard.min_invitations = band.min_invitations
            wizard.shortfall = bool(band) and 0 < wizard.vendor_count < band.min_invitations

    def action_create_rfqs(self):
        self.ensure_one()
        if self.shortfall and not (self.shortfall_justification or '').strip():
            raise UserError(_(
                "The procurement policy asks for at least %(needed)s vendors for this value and you chose "
                "%(chosen)s. Write the justification, or add vendors.",
                needed=self.min_invitations, chosen=self.vendor_count))
        action = super().action_create_rfqs()
        if self.shortfall and action.get('res_id'):
            self.env['purchase.request.rfq'].browse(action['res_id']).shortfall_justification = \
                self.shortfall_justification
        return action
