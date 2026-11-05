from odoo import _, fields, models


class FinanceTransaction(models.Model):
    _inherit = ['finance.transaction', 'procurement.touch.mixin']
    _file_path = 'purchase_order_id.purchase_request_id'

    purchase_order_id = fields.Many2one(
        'purchase.order', string='Purchase Order', copy=False, index='btree_not_null', tracking=True,
        help="The purchase order this payment is for.")

    def action_open_procurement_file(self):
        """The procurement file (every step and document) of the order this payment is for."""
        self.ensure_one()
        return self.purchase_order_id.action_open_procurement_file()

    def action_post(self):
        result = super().action_post()
        for rec in self.filtered('purchase_order_id'):
            rec._settle_vendor_bills()
        return result

    def _settle_vendor_bills(self):
        """A payment booked to the payable account settles the posted vendor bills of its order."""
        self.ensure_one()
        bills = self.purchase_order_id.sudo().invoice_ids.filtered(
            lambda move: move.state == 'posted' and move.move_type == 'in_invoice')
        payable = self.move_id.sudo().line_ids.filtered(
            lambda line: line.account_id.account_type == 'liability_payable')
        if not bills or not payable:
            return
        open_lines = bills.line_ids.filtered(
            lambda line: line.account_id.account_type == 'liability_payable' and not line.reconciled)
        try:
            (payable | open_lines).reconcile()
        except Exception as error:  # the payment is posted either way; the accountant can match it
            self.message_post(body=_("The payment could not be matched with the vendor bill: %s", error))
        else:
            self.message_post(body=_("Matched with the vendor bill of %s.", self.purchase_order_id.name))
