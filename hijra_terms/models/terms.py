from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_id = fields.Many2one(string='Item')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    product_id = fields.Many2one(string='Item')
