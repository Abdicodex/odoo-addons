from odoo import api, models


class PurchaseRequest(models.Model):
    _inherit = ['purchase.request', 'procurement.touch.mixin']
    _file_path = ''

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        # every requisition has its procurement file from the start
        self.env['procurement.file'].sudo().create([{'request_id': request.id} for request in requests])
        return requests

    def action_open_procurement_file(self):
        """The screen with every step and document of this requisition's procurement."""
        self.ensure_one()
        File = self.env['procurement.file'].sudo()
        file = File.search([('request_id', '=', self.id)], limit=1) or File.create({'request_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'name': file.name,
            'res_model': 'procurement.file',
            'res_id': file.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
