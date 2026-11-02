from odoo import _, fields, models
from odoo.exceptions import UserError


class PurchaseRequestMakeRfq(models.TransientModel):
    _name = 'purchase.request.make.rfq'
    _description = 'Create RFQs from a Purchase Request'

    request_id = fields.Many2one('purchase.request', required=True, readonly=True)
    partner_ids = fields.Many2many(
        'res.partner', string='Vendors', required=True,
        help="One RFQ is created for each vendor so quotes can be compared.")

    def action_create_rfqs(self):
        self.ensure_one()
        request = self.request_id
        if request.state not in ('approved', 'rfq_created'):
            raise UserError(_("Only approved requests can be turned into RFQs."))
        orders = self.env['purchase.order']
        for partner in self.partner_ids:
            orders |= self.env['purchase.order'].create(request._prepare_rfq_vals(partner))
        request.state = 'rfq_created'
        request.message_post(body=_(
            "RFQs created: %s", ", ".join(orders.mapped('name'))))
        return request.action_view_rfqs()
