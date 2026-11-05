from odoo import models

GRN_REPORT = 'hijra_receipts.report_grn'
COMPLETION_REPORT = 'hijra_receipts.report_completion'


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """The goods received note and the service completion note are drawn directly
        (report/*.py) so they match the HIJRA documents."""
        report = self._get_report(report_ref)
        if report.report_name not in (GRN_REPORT, COMPLETION_REPORT):
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        if isinstance(res_ids, int):
            res_ids = [res_ids]
        if not res_ids and data:
            res_ids = (data.get('context') or {}).get('active_ids')
        # imported here so a missing reportlab cannot stop the module from loading
        from ..report import completion_pdf, grn_pdf
        if report.report_name == GRN_REPORT:
            notes = self.env['procurement.grn'].browse(res_ids or [])
            return grn_pdf.build_pdf([note._prepare_grn_pdf_data() for note in notes]), 'pdf'
        notes = self.env['procurement.completion'].browse(res_ids or [])
        return completion_pdf.build_pdf([note._prepare_completion_pdf_data() for note in notes]), 'pdf'
