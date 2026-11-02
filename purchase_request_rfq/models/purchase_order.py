from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_request_id = fields.Many2one(
        'purchase.request', string='Purchase Request', readonly=True, copy=False,
        index='btree_not_null')
