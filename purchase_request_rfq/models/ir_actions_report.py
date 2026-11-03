import os

from odoo import models
from odoo.tools import file_path

REPORT_NAME = 'purchase_request_rfq.report_purchase_request'


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """The requisition form is drawn directly (see report/prf_pdf.py) so it
        matches the HIJRA template exactly instead of going through HTML."""
        report = self._get_report(report_ref)
        if report.report_name != REPORT_NAME:
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        if isinstance(res_ids, int):
            res_ids = [res_ids]
        if not res_ids and data:
            res_ids = (data.get('context') or {}).get('active_ids')
        requests = self.env['purchase.request'].browse(res_ids or [])
        # imported here so a missing reportlab cannot stop the module from loading
        from ..report import prf_pdf
        font_dir = os.path.dirname(
            file_path('purchase_request_rfq/static/fonts/Carlito-Regular.ttf'))
        pdf = prf_pdf.build_pdf([request._prepare_prf_data() for request in requests], font_dir)
        return pdf, 'pdf'
