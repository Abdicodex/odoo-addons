from odoo import _, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_award_order(self):
        """When the committee is required, only the vendor it selected can be awarded, and only
        after every member has signed."""
        self.ensure_one()
        group = self.rfq_group_id
        if group and group.committee_required:
            if group.committee_state != 'decided':
                raise UserError(_(
                    "The procurement committee has to decide first: every member signs the "
                    "declaration, bid analysis, statement and minutes."))
            if group.recommended_order_id and group.recommended_order_id != self:
                raise UserError(_(
                    "The committee selected %s.", group.recommended_order_id.partner_id.name))
        return super().action_award_order()
