from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _inherit = ['analytic.mixin']
    _description = 'Purchase Request Line'
    _order = 'request_id, sequence, id'

    request_id = fields.Many2one('purchase.request', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    currency_id = fields.Many2one(related='request_id.currency_id')
    state = fields.Selection(related='request_id.state')

    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        domain=[('purchase_ok', '=', True)])
    description = fields.Text(
        string='Description', compute='_compute_description', store=True, readonly=False)
    date_planned = fields.Datetime(
        string='Expected Arrival', compute='_compute_date_planned', store=True, readonly=False)
    product_qty = fields.Float(string='Quantity', required=True, default=1.0, digits='Product Unit')
    product_uom_id = fields.Many2one(
        'uom.uom', string='Unit', compute='_compute_product_uom_id',
        store=True, readonly=False, required=True)
    price_unit = fields.Monetary(
        string='Unit Price', compute='_compute_price_unit', store=True, readonly=False)
    tax_ids = fields.Many2many(
        'account.tax', string='Taxes',
        compute='_compute_tax_ids', store=True, readonly=False,
        context={'active_test': False})
    subtotal = fields.Monetary(string='Amount', compute='_compute_amount', store=True)
    price_tax = fields.Monetary(string='Tax', compute='_compute_amount', store=True)
    price_total = fields.Monetary(string='Total', compute='_compute_amount', store=True)

    @api.depends('product_id')
    def _compute_description(self):
        for line in self:
            if line.product_id:
                line.description = line.product_id.display_name

    @api.depends('request_id.date_required')
    def _compute_date_planned(self):
        for line in self:
            if line.request_id.date_required:
                line.date_planned = fields.Datetime.to_datetime(line.request_id.date_required)

    @api.depends('product_id')
    def _compute_product_uom_id(self):
        for line in self:
            if line.product_id:
                line.product_uom_id = line.product_id.uom_id

    @api.depends('product_id')
    def _compute_price_unit(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.standard_price

    @api.depends('product_id', 'company_id')
    def _compute_tax_ids(self):
        for line in self:
            line.tax_ids = line.product_id.supplier_taxes_id.filtered(
                lambda tax: tax.company_id == line.company_id)

    @api.depends('product_qty', 'price_unit', 'tax_ids', 'request_id.partner_id')
    def _compute_amount(self):
        for line in self:
            currency = line.request_id.currency_id or line.company_id.currency_id
            taxes = line.tax_ids.compute_all(
                line.price_unit,
                currency=currency,
                quantity=line.product_qty,
                product=line.product_id,
                partner=line.request_id.partner_id)
            line.subtotal = taxes['total_excluded']
            line.price_total = taxes['total_included']
            line.price_tax = taxes['total_included'] - taxes['total_excluded']

    @api.constrains('product_qty')
    def _check_product_qty(self):
        for line in self:
            if line.product_qty <= 0:
                raise ValidationError(self.env._("Quantity must be greater than zero."))
