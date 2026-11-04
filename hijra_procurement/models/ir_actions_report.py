import os

from odoo import models
from odoo.tools import file_path

REPORTS = {
    'hijra_procurement.report_declaration': 'declaration',
    'hijra_procurement.report_bid_analysis': 'analysis',
    'hijra_procurement.report_committee_statement': 'statement',
    'hijra_procurement.report_committee_minutes': 'minutes',
}


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """The committee documents are drawn directly (report/committee_pdf.py) so they match
        the HIJRA templates instead of going through HTML."""
        report = self._get_report(report_ref)
        document = REPORTS.get(report.report_name)
        if not document:
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        if isinstance(res_ids, int):
            res_ids = [res_ids]
        if not res_ids and data:
            res_ids = (data.get('context') or {}).get('active_ids')
        rfqs = self.env['purchase.request.rfq'].browse(res_ids or [])
        # imported here so a missing reportlab cannot stop the module from loading
        from ..report import committee_pdf
        font_dir = os.path.dirname(file_path('purchase_request_rfq/static/fonts/Carlito-Regular.ttf'))
        return committee_pdf.build_pdf(document, [rfq._prepare_committee_data() for rfq in rfqs], font_dir), 'pdf'
