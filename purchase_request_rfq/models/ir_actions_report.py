import os

from odoo import models
from odoo.tools import file_path

PRF_REPORT = 'purchase_request_rfq.report_purchase_request'
RFQ_REPORT = 'purchase.report_purchasequotation'


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _font_dir(self):
        return os.path.dirname(file_path('purchase_request_rfq/static/fonts/Carlito-Regular.ttf'))

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Two documents are drawn directly (report/prf_pdf.py, report/rfq_pdf.py) so they
        match the HIJRA Word templates exactly instead of going through HTML."""
        report = self._get_report(report_ref)
        if report.report_name not in (PRF_REPORT, RFQ_REPORT):
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        if isinstance(res_ids, int):
            res_ids = [res_ids]
        if not res_ids and data:
            res_ids = (data.get('context') or {}).get('active_ids')

        if report.report_name == PRF_REPORT:
            requests = self.env['purchase.request'].browse(res_ids or [])
            # imported here so a missing reportlab cannot stop the module from loading
            from ..report import prf_pdf
            pdf = prf_pdf.build_pdf([request._prepare_prf_data() for request in requests],
                                    self._font_dir())
            return pdf, 'pdf'

        # RFQs created from a requisition use the HIJRA template; any other RFQ keeps Odoo's own
        orders = self.env['purchase.order'].browse(res_ids or [])
        if not orders or not all(order.rfq_group_id for order in orders):
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        from ..report import rfq_pdf
        pdf = rfq_pdf.build_pdf(
            [order.rfq_group_id._prepare_pdf_data(order) for order in orders], self._font_dir())
        return pdf, 'pdf'
