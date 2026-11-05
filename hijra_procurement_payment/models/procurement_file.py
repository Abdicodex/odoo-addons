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
