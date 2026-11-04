import os

from odoo import models
from odoo.tools import file_path

REPORTS = {
    'hijra_procurement.report_declaration': 'declaration',
    'hijra_procurement.report_bid_analysis': 'analysis',
    'hijra_procurement.report_committee_statement': 'statement',
    'hijra_procurement.report_committee_minutes': 'minutes',
    'hijra_procurement.report_committee_pack': 'pack',
    'hijra_procurement.report_procurement_file': 'file',
}
PACK_DOCUMENTS = ('declaration', 'analysis', 'statement', 'minutes')
PO_REPORT = 'purchase.report_purchaseorder'


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """The committee documents and the purchase order are drawn directly (report/*.py) so
        they match the HIJRA templates instead of going through HTML."""
        report = self._get_report(report_ref)
        document = REPORTS.get(report.report_name)
        if not document and report.report_name != PO_REPORT:
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        if isinstance(res_ids, int):
            res_ids = [res_ids]
        if not res_ids and data:
            res_ids = (data.get('context') or {}).get('active_ids')
        font_dir = os.path.dirname(file_path('purchase_request_rfq/static/fonts/Carlito-Regular.ttf'))
        if report.report_name == PO_REPORT:
            orders = self.env['purchase.order'].browse(res_ids or [])
            if not orders:
                return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
            from ..report import po_pdf
            return po_pdf.build_pdf([order._prepare_po_pdf_data() for order in orders], font_dir), 'pdf'
        if document == 'file':
            from odoo.tools.pdf import merge_pdf
            parts = []
            for file in self.env['procurement.file'].browse(res_ids or []):
                parts += file.sudo()._pdf_parts()
            return merge_pdf(parts), 'pdf'
        rfqs = self.env['purchase.request.rfq'].browse(res_ids or [])
        # imported here so a missing reportlab cannot stop the module from loading
        from ..report import committee_pdf
        if document != 'pack':
            return committee_pdf.build_pdf(
                document, [rfq._prepare_committee_data() for rfq in rfqs], font_dir), 'pdf'
        # every document of the session in one file: the requisition, then the four committee documents
        from odoo.addons.purchase_request_rfq.report import prf_pdf
        from odoo.tools.pdf import merge_pdf
        parts = []
        for rfq in rfqs:
            parts.append(prf_pdf.build_pdf([rfq.request_id.sudo()._prepare_prf_data()], font_dir))
            data = rfq._prepare_committee_data()
            for name in PACK_DOCUMENTS:
                parts.append(committee_pdf.build_pdf(name, [data], font_dir))
        return merge_pdf(parts), 'pdf'
