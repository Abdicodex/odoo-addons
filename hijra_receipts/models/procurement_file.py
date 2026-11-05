from odoo import _, models


class ProcurementFile(models.Model):
    _inherit = 'procurement.file'

    def _receipts(self):
        order = self._awarded_order().sudo()
        grns = order.grn_ids.filtered(lambda g: g.state != 'cancelled')
        notes = order.completion_ids.filtered(lambda c: c.state != 'cancelled')
        return order, grns, notes

    def _build_steps(self):
        steps = super()._build_steps()
        order, grns, notes = self._receipts()
        if not order or order.state not in ('purchase', 'done'):
            return steps
        new = []
        for grn in grns:
            detail = _("Part order") if grn.order_complete == 'part' else _("Complete order")
            new.append(self._step(
                _("Goods Received Note"), grn.name, 'done' if grn.state == 'checked' else 'pending',
                "%s - %s" % (detail, dict(grn._fields['state'].selection).get(grn.state)),
                grn, 'hijra_receipts.action_report_grn', grn))
        for note in notes:
            new.append(self._step(
                _("Service Completion Note"), note.name, 'done' if note.state == 'approved' else 'pending',
                dict(note._fields['state'].selection).get(note.state), note,
                'hijra_receipts.action_report_completion', note))
        if not new:
            new.append(self._step(
                _("Goods Received / Service Completion"), '', 'todo', _("Not recorded yet")))
        anchor = _("Purchase Order")
        index = next((i for i, step in enumerate(steps) if step['name'] == anchor), len(steps) - 1) + 1
        return steps[:index] + new + steps[index:]

    def _extra_pdf_parts(self, font_dir):
        from ..report import completion_pdf, grn_pdf
        _order, grns, notes = self._receipts()
        parts = []
        if grns:
            parts.append(grn_pdf.build_pdf([grn._prepare_grn_pdf_data() for grn in grns]))
        approved = notes.filtered(lambda n: n.state == 'approved') or notes
        if approved:
            parts.append(completion_pdf.build_pdf([note._prepare_completion_pdf_data() for note in approved]))
        return parts + super()._extra_pdf_parts(font_dir)
