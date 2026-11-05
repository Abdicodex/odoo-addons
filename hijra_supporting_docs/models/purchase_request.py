from odoo import fields, models


class PurchaseRequest(models.Model):
    _inherit = 'purchase.request'

    expenditure_type_id = fields.Many2one(
        'expenditure.type', string='Expenditure Type', tracking=True,
        help="Decides which supporting documents the payment needs. It is carried to the payment.")

    def _prepare_rfq_vals(self, partner):
        """The order starts as goods or as a service, as the expenditure type says."""
        vals = super()._prepare_rfq_vals(partner)
        receipt = self.expenditure_type_id.receipt_type
        if receipt:
            vals['receipt_type'] = receipt
        return vals
