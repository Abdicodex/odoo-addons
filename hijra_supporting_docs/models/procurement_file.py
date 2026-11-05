from odoo import _, models

from .finance_transaction import STATUS


class ProcurementFile(models.Model):
    _inherit = 'procurement.file'

    def _checklist_payments(self):
        order = self._awarded_order()
        if not order:
            return self.env['finance.transaction']
        return order.sudo().finance_transaction_ids.filtered(lambda t: t.state != 'cancelled')

    def _build_steps(self):
        """The supporting documents of the payments, as the last part of the chain."""
        steps = super()._build_steps()
        order = self._awarded_order()
        if not order or order.state not in ('purchase', 'done'):
            return steps
        labels = dict(STATUS)
        added = False
        for payment in self._checklist_payments():
            for row in payment.document_ids.sorted(lambda d: (d.sequence, d.id)):
                status = row.status
                if status in ('system', 'attached', 'available', 'waived'):
                    state = 'done'
                elif status == 'missing':
                    state = 'pending'
                else:
                    state = 'todo'
                detail = labels[status]
                if status == 'system' and row.system_ref:
                    detail += ': %s' % row.system_ref
                elif status == 'attached' and row.file_name:
                    detail += ': %s' % row.file_name
                printable = bool(row.file or row.system_available)
                steps.append(self._step(
                    row.document_type_id.name, payment.name, state, detail, payment,
                    'hijra_supporting_docs.action_report_support_doc' if printable else None,
                    row if printable else None, phase='documents'))
                added = True
        if not added:
            steps.append(self._step(
                _("Supporting Documents"), '', 'todo', _("The checklist appears when the payment is prepared"),
                phase='documents', create=(order, 'action_pay_vendor', _("Pay Vendor"))))
        return steps

    def _extra_pdf_parts(self, font_dir):
        """The files uploaded on the payments' checklists are printed after the system documents."""
        parts = super()._extra_pdf_parts(font_dir)
        for payment in self._checklist_payments():
            for row in payment.document_ids.sorted(lambda d: (d.sequence, d.id)):
                parts += row._upload_parts()
        return parts
