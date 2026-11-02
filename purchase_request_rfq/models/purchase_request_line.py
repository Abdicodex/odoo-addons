from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'

    request_id = fields.Many2one('purchase.request', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    currency_id = fields.Many2one(related='request_id.currency_id')
    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        domain=[('purchase_ok', '=', True)])
    description = fields.Text(compute='_compute_description', store=True, readonly=False)
    product_qty = fields.Float(string='Quantity', required=True, default=1.0)
    product_uom_id = fields.Many2one(
        'uom.uom', string='Unit', compute='_compute_product_uom_id',
        store=True, readonly=False, required=True)
    price_unit = fields.Monetary(string='Estimated Unit Price')
    subtotal = fields.Monetary(compute='_compute_subtotal', store=True)

    @api.depends('product_id')
    def _compute_description(self):
        for line in self:
            if line.product_id:
                line.description = line.product_id.display_name

    @api.depends('product_id')
    def _compute_product_uom_id(self):
        for line in self:
            if line.product_id:
                line.product_uom_id = line.product_id.uom_id

    @api.depends('product_qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.product_qty * line.price_unit

    @api.constrains('product_qty')
    def _check_product_qty(self):
        for line in self:
            if line.product_qty <= 0:
                raise ValidationError(self.env._("Quantity must be greater than zero."))
