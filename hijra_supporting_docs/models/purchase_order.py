from odoo import models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_pay_vendor(self):
        """Pay Vendor carries the expenditure type of the requisition to the payment."""
        action = super().action_pay_vendor()
        expenditure = self.purchase_request_id.sudo().expenditure_type_id
        if expenditure:
            action['context']['default_expenditure_type_id'] = expenditure.id
        return action
