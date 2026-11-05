from odoo import models


class ProcurementGrn(models.Model):
    _inherit = 'procurement.grn'

    def action_pay_vendor(self):
        """Pay the vendor of this note's order."""
        self.ensure_one()
        return self.order_id.action_pay_vendor()


class ProcurementCompletion(models.Model):
    _inherit = 'procurement.completion'

    def action_pay_vendor(self):
        """Pay the vendor of this note's order."""
        self.ensure_one()
        return self.order_id.action_pay_vendor()
