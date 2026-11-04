from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    purchase_product_id = fields.Many2one(
        'product.product', string='RFQ Product', domain=[('purchase_ok', '=', True)],
        help="Product used on RFQ lines for requisitions on this budget line. "
             "Leave empty to use the generic service product.")
