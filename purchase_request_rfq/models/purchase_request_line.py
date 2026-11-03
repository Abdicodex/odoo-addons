from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Requisition Item'
    _order = 'request_id, sequence, id'

    request_id = fields.Many2one('purchase.request', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    item_no = fields.Integer(string='Item #', compute='_compute_item_no')
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    currency_id = fields.Many2one(related='request_id.currency_id')
    state = fields.Selection(related='request_id.state')

    description = fields.Text(string='Description')
    unit = fields.Char(string='Unit', default='Unit')
    product_qty = fields.Float(string='Quantity', required=True, default=1.0, digits='Product Unit')
    frequency = fields.Float(string='Frequency', required=True, default=1.0)
    price_unit = fields.Monetary(string='Unit Price')
    subtotal = fields.Monetary(string='Amount', compute='_compute_subtotal', store=True)

    # Set by the buyer when the RFQ is created; not part of the paper form.
    product_id = fields.Many2one(
        'product.product', string='Product', domain=[('purchase_ok', '=', True)])
    product_uom_id = fields.Many2one(
        'uom.uom', string='Unit of Measure', compute='_compute_product_uom_id',
        store=True, readonly=False)

    def _get_rfq_product(self):
        """Product for this item's RFQ line: its own, else its budget category's,
        else the generic service product."""
        self.ensure_one()
        return (
            self.product_id
            or self.request_id.budget_id.purchase_product_id
            or self.env.ref('purchase_request_rfq.product_generic_service',
                            raise_if_not_found=False)
            or self.env['product.product']
        )

    def _get_rfq_description(self):
        """Requisition text, with the unit and frequency so the vendor sees the breakdown."""
        self.ensure_one()
        text = self.description or self.product_id.display_name or ''
        unit = (self.unit or '').strip()
        if self.frequency != 1:
            detail = f"{self.product_qty:g} {unit} x {self.frequency:g}"
        elif unit and unit.lower() != 'unit':
            detail = f"{self.product_qty:g} {unit}"
        else:
            detail = ''
        return f"{text} ({' '.join(detail.split())})" if detail else text

    @api.depends('request_id.line_ids', 'sequence')
    def _compute_item_no(self):
        numbering = {}
        for request in self.request_id:
            for number, line in enumerate(request.line_ids.sorted('sequence'), 1):
                numbering[line.id] = number
        for line in self:
            line.item_no = numbering.get(line.id, 0)

    @api.depends('product_id')
    def _compute_product_uom_id(self):
        for line in self:
            if line.product_id:
                line.product_uom_id = line.product_id.uom_id
            else:
                line.product_uom_id = False

    @api.depends('product_qty', 'frequency', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.product_qty * line.frequency * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                if not line.description:
                    line.description = line.product_id.display_name
                line.unit = line.product_id.uom_id.name

    @api.constrains('product_qty', 'frequency')
    def _check_positive(self):
        for line in self:
            if line.product_qty <= 0 or line.frequency <= 0:
                raise ValidationError(
                    self.env._("Quantity and frequency must be greater than zero."))
