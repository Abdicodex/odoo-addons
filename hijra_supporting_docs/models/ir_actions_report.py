from odoo import models

PACK_REPORT = 'hijra_supporting_docs.report_support_pack'


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """The supporting documents pack: a cover checklist and every document, merged."""
        report = self._get_report(report_ref)
        if report.report_name != PACK_REPORT:
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        if isinstance(res_ids, int):
            res_ids = [res_ids]
        if not res_ids and data:
            res_ids = (data.get('context') or {}).get('active_ids')
        from odoo.tools.pdf import merge_pdf
        packs = [transaction._render_pack() for transaction in self.env['finance.transaction'].browse(res_ids or [])]
        return (merge_pdf(packs) if len(packs) > 1 else packs[0]), 'pdf'
