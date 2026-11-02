from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseRequestMakeRfq(models.TransientModel):
    _name = 'purchase.request.make.rfq'
    _description = 'Create RFQs from a Purchase Requisition'

    request_id = fields.Many2one('purchase.request', required=True, readonly=True)
    partner_ids = fields.Many2many(
        'res.partner', string='Vendors', required=True,
        help="One RFQ is created for each vendor so quotes can be compared.")
    line_ids = fields.One2many(
        'purchase.request.make.rfq.line', 'wizard_id', string='Items')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        request = self.env['purchase.request'].browse(
            res.get('request_id') or self.env.context.get('default_request_id'))
        if request and 'line_ids' in fields_list:
            res['line_ids'] = [(0, 0, {
                'request_line_id': line.id,
                'product_id': line.product_id.id,
            }) for line in request.line_ids]
        return res

    def action_create_rfqs(self):
        self.ensure_one()
        request = self.request_id
        if request.state not in ('approved', 'rfq_created'):
            raise UserError(_("Only approved requisitions can be turned into RFQs."))
        for line in self.line_ids:
            if not line.product_id:
                raise UserError(_(
                    "Select a product for item %s before creating the RFQ.",
                    line.item_no))
        for line in self.line_ids:
            if line.request_line_id.product_id != line.product_id:
                line.request_line_id.product_id = line.product_id
        orders = self.env['purchase.order']
        for partner in self.partner_ids:
            orders |= self.env['purchase.order'].create(request._prepare_rfq_vals(partner))
        request.state = 'rfq_created'
        request.message_post(body=_(
            "RFQs created: %s", ", ".join(orders.mapped('name'))))
        return request.action_view_rfqs()


class PurchaseRequestMakeRfqLine(models.TransientModel):
    _name = 'purchase.request.make.rfq.line'
    _description = 'Item to include in the RFQs'

    wizard_id = fields.Many2one('purchase.request.make.rfq', required=True, ondelete='cascade')
    request_line_id = fields.Many2one('purchase.request.line', required=True, readonly=True)
    item_no = fields.Integer(related='request_line_id.item_no')
    description = fields.Text(related='request_line_id.description')
    quantity = fields.Float(string='Quantity', compute='_compute_quantity')
    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        domain=[('purchase_ok', '=', True)])

    @api.depends('request_line_id.product_qty', 'request_line_id.frequency')
    def _compute_quantity(self):
        for line in self:
            line.quantity = line.request_line_id.product_qty * line.request_line_id.frequency
