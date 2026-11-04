from odoo import _, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    purchase_product_id = fields.Many2one(
        'product.product', string='RFQ Product', domain=[('purchase_ok', '=', True)],
        help="Product used on RFQ lines for requisitions on this budget line. "
             "Leave empty to use the generic service product.")

    def action_create_requisition(self):
        """A new requisition for this budget line: its project and budget line are filled in."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Requisition'),
            'res_model': 'purchase.request',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {'default_project_id': self.project_id.id, 'default_budget_id': self.id},
        }
