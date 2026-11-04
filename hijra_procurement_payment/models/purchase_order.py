from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    finance_transaction_ids = fields.One2many(
        'finance.transaction', 'purchase_order_id', string='Payments')
    paid_amount = fields.Monetary(compute='_compute_paid', currency_field='currency_id')
    amount_to_pay = fields.Monetary(compute='_compute_paid', currency_field='currency_id')
    payment_count = fields.Integer(compute='_compute_paid')

    @api.depends('amount_total', 'finance_transaction_ids.state', 'finance_transaction_ids.amount')
    def _compute_paid(self):
        for order in self:
            transactions = order.finance_transaction_ids
            posted = transactions.filtered(lambda t: t.state == 'posted')
            order.paid_amount = sum(posted.mapped('amount'))
            order.amount_to_pay = max(order.amount_total - order.paid_amount, 0.0)
            order.payment_count = len(transactions.filtered(lambda t: t.state != 'cancelled'))

    def _default_pay_account(self):
        """The account the payment is booked to: the vendor's payable account when a bill was
        posted (the payment then settles it), else the expense account of the item."""
        self.ensure_one()
        order = self.with_company(self.company_id)
        bills = order.invoice_ids.filtered(lambda m: m.state == 'posted' and m.move_type == 'in_invoice')
        if bills:
            return order.partner_id.property_account_payable_id
        product = order.order_line.filtered('product_id')[:1].product_id
        return product.property_account_expense_id or product.categ_id.property_account_expense_categ_id

    def action_pay_vendor(self):
        """Open the finance transaction for this order, filled in."""
        self.ensure_one()
        if self.state not in ('purchase', 'done'):
            raise UserError(_("Confirm the order before paying the vendor."))
        if self.amount_to_pay <= 0:
            raise UserError(_("%s is fully paid.", self.name))
        request = self.purchase_request_id.sudo()
        first = self.order_line.filtered(lambda l: not l.display_type)[:1]
        item = (first.purchase_request_line_id.sudo().description or first.name or '').strip()
        description = _("Payment for %s", self.name) + ((" - " + item.splitlines()[0]) if item else "")
        notes = _("Purchase order %s", self.name)
        if self.partner_ref:
            notes += " / " + _("Vendor reference %s", self.partner_ref)
        account = self._default_pay_account()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pay Vendor'),
            'res_model': 'finance.transaction',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {
                'default_transaction_type': 'expense',
                'default_purchase_order_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_amount': self.amount_to_pay,
                'default_description': description,
                'default_notes': notes,
                'default_project_id': (self.rfq_project_id or request.project_id).id,
                'default_budget_id': request.budget_id.id,
                'default_account_id': account.id or False,
            },
        }

    def action_view_payments(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hijra_finance.finance_transaction_action')
        action.update({
            'name': _('Payments of %s', self.name),
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id},
        })
        return action
