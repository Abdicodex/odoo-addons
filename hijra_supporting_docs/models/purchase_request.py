from odoo import fields, models


class PurchaseRequest(models.Model):
    _inherit = 'purchase.request'

    expenditure_type_id = fields.Many2one(
        'expenditure.type', string='Expenditure Type', tracking=True,
        help="Decides which supporting documents the payment needs. It is carried to the payment.")
