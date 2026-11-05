import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ProcurementTouchMixin(models.AbstractModel):
    """Keeps the procurement file of a requisition up to date (stage, next action, who it waits for)
    whenever one of its documents changes. A failure here never blocks the user's save."""
    _name = 'procurement.touch.mixin'
    _description = 'Procurement File Progress Trigger'

    _file_path = ''   # path from a record to its purchase requisition ('' for the requisition itself)

    def _touch_file(self):
        try:
            with self.env.cr.savepoint():
                records = self.sudo()
                requests = records.mapped(self._file_path) if self._file_path else records
                if requests:
                    self.env['procurement.file'].sudo().search(
                        [('request_id', 'in', requests.ids)])._update_progress()
        except Exception:
            _logger.exception("Could not update the procurement file progress")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._touch_file()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._touch_file()
        return result
