from odoo import models

VOUCHER_REPORT = 'hijra_finance.report_transaction_voucher'


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """The payment voucher is drawn directly (report/voucher_pdf.py) so it matches the
        HIJRA template exactly instead of going through HTML."""
        report = self._get_report(report_ref)
        if report.report_name != VOUCHER_REPORT:
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        if isinstance(res_ids, int):
            res_ids = [res_ids]
        if not res_ids and data:
            res_ids = (data.get('context') or {}).get('active_ids')
        transactions = self.env['finance.transaction'].browse(res_ids or [])
        # imported here so a missing reportlab cannot stop the module from loading
        from ..report import voucher_pdf
        return voucher_pdf.build_pdf([t._prepare_voucher_data() for t in transactions]), 'pdf'
