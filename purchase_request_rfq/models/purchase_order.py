from odoo import _, fields, models
from odoo.exceptions import UserError

OPEN_ORDER_STATES = ('draft', 'sent', 'to approve')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_request_id = fields.Many2one(
        'purchase.request', string='Purchase Request', readonly=True, copy=False,
        index='btree_not_null')
    rfq_group_id = fields.Many2one(
        'purchase.request.rfq', string='RFQ Reference', readonly=True, copy=False,
        index='btree_not_null', ondelete='set null')

    def action_award_order(self):
        """Buy from this vendor: confirm its order and cancel the other quotations."""
        self.ensure_one()
        group = self.rfq_group_id
        if not group:
            raise UserError(_("This order does not belong to an RFQ."))
        if not self.env.user.has_group('purchase.group_purchase_user'):
            raise UserError(_("Only purchase users can award an RFQ."))
        if group.state != 'open':
            raise UserError(_("This RFQ has already been awarded or cancelled."))
        if self.state not in ('draft', 'sent'):
            raise UserError(_("Only a quotation that is still open can be awarded."))
        others = (group.order_ids - self).filtered(lambda order: order.state in OPEN_ORDER_STATES)
        self.button_confirm()
        others.button_cancel()
        group.write({'state': 'awarded', 'awarded_order_id': self.id})
        message = _("Awarded to %(vendor)s (%(order)s).", vendor=self.partner_id.name, order=self.name)
        group.message_post(body=message)
        group.request_id.message_post(body=_("RFQ %(rfq)s: %(message)s", rfq=group.name, message=message))
        return True

    def action_open_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    purchase_request_line_id = fields.Many2one(
        'purchase.request.line', string='Requisition Item', copy=False,
        index='btree_not_null', ondelete='set null')
