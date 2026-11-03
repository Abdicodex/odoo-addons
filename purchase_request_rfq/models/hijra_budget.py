from odoo import fields, models


class HijraBudget(models.Model):
    _inherit = 'hijra.budget'

    purchase_product_id = fields.Many2one(
        'product.product', string='RFQ Product', domain=[('purchase_ok', '=', True)],
        help="Product used on RFQ lines for requisitions in this category. "
             "Leave empty to use the generic service product.")
