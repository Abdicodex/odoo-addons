from odoo import _, models


class ProcurementFile(models.Model):
    _inherit = 'procurement.file'

    def _payments(self):
        order = self._awarded_order()
        return order.sudo().finance_transaction_ids.filtered(lambda t: t.state != 'cancelled') if order \
            else self.env['finance.transaction']

    def _stage_after_order(self, order):
        if order.paid_amount > 0 and order.amount_to_pay <= 0:
            return 'paid'
        return super()._stage_after_order(order)

    def _after_order(self, order):
        """The payment, once the goods or service have been received."""
        text, users = super()._after_order(order)
        if text:
            return text, users
        order = order.sudo()
        if order.payment_status == 'paid':
            return '', users
        Role = self.env['hijra.role']
        finance = Role._get_users('finance_officer') | Role._get_users('fa_officer')
        payments = self._payments()
        pending = payments.filtered(lambda t: t.state in ('draft', 'to_approve', 'approved'))[:1]
        if not pending:
            return (_("Pay the balance") if payments else _("Pay the vendor")), finance
        if pending.state == 'draft':
            return _("Send the payment for approval"), pending.create_uid | finance
        if pending.state == 'to_approve':
            return _("Approve the payment"), pending.approver_id or finance
        return _("Post the payment"), finance

    def _build_steps(self):
        steps = super()._build_steps()
        order = self._awarded_order()
        if order and order.state in ('purchase', 'done'):
            payments = self._payments()
            for payment in payments:
                steps.append(self._step(
                    _("Payment"), payment.name, 'done' if payment.state == 'posted' else 'pending',
                    "%s %s" % (format(payment.amount, ',.2f'), payment.currency_id.name or ''),
                    payment, 'hijra_finance.action_report_transaction_voucher', payment, phase='payment'))
            if not payments:
                steps.append(self._step(
                    _("Payment"), '', 'todo', _("Not paid yet"), phase='payment',
                    create=(order, 'action_pay_vendor', _("Pay Vendor"))))
        return steps

    def _extra_pdf_parts(self, font_dir):
        parts = super()._extra_pdf_parts(font_dir)
        posted = self._payments().filtered(lambda t: t.state == 'posted')
        if posted:
            from odoo.addons.hijra_finance.report import voucher_pdf
            parts.append(voucher_pdf.build_pdf([payment._prepare_voucher_data() for payment in posted]))
        return parts
