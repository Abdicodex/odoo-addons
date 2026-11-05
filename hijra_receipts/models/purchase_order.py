from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    grn_ids = fields.One2many('procurement.grn', 'order_id', string='Goods Received Notes')
    grn_count = fields.Integer(compute='_compute_receipt_counts')
    completion_ids = fields.One2many('procurement.completion', 'order_id', string='Service Completion Notes')
    completion_count = fields.Integer(compute='_compute_receipt_counts')

    @api.depends('grn_ids.state', 'completion_ids.state')
    def _compute_receipt_counts(self):
        for order in self:
            order.grn_count = len(order.grn_ids.filtered(lambda g: g.state != 'cancelled'))
            order.completion_count = len(order.completion_ids.filtered(lambda c: c.state != 'cancelled'))

    def _check_can_receive(self):
        self.ensure_one()
        if self.state not in ('purchase', 'done'):
            raise UserError(_("Confirm the order first: it has to be authorized by the Officer-in-Charge."))

    def action_receive_goods(self):
        """A new goods received note for what is still to be received on this order."""
        self.ensure_one()
        self._check_can_receive()
        before = {}
        for done in self.env['procurement.grn.line'].sudo().search(
                [('grn_id.order_id', '=', self.id), ('grn_id.state', 'in', ('received', 'checked'))]):
            if done.order_line_id:
                before[done.order_line_id.id] = before.get(done.order_line_id.id, 0.0) + done.qty_received
        lines = []
        for sequence, line in enumerate(self.order_line.filtered(lambda l: not l.display_type), 1):
            item = line.purchase_request_line_id.sudo()
            uom = getattr(line, 'uom_id', None) or getattr(line, 'product_uom_id', None)
            previous = before.get(line.id, 0.0)
            lines.append(Command.create({
                'sequence': sequence * 10,
                'order_line_id': line.id,
                'description': (item.description if item else '') or line.name or '',
                'uom': (item.unit if item else '') or (uom.name if uom else ''),
                'qty_ordered': line.product_qty,
                'qty_previous': previous,
                'qty_received': max(line.product_qty - previous, 0.0),
            }))
        grn = self.env['procurement.grn'].create({
            'order_id': self.id,
            'location': self.rfq_location_id.sudo().name or '',
            'line_ids': lines,
        })
        return self._open(grn)

    def action_complete_service(self):
        """A new service completion note, drafted from this order."""
        self.ensure_one()
        self._check_can_receive()
        first = self.order_line.filtered(lambda l: not l.display_type)[:1]
        item = (first.purchase_request_line_id.sudo().description or first.name or '').strip()
        request = self.purchase_request_id.sudo()
        note = self.env['procurement.completion'].create({
            'order_id': self.id,
            'service': item.splitlines()[0] if item else '',
            'place': self.rfq_location_id.sudo().name or '',
            'approver_id': request.project_id.user_id.id or False,
        })
        return self._open(note)

    @staticmethod
    def _open(record):
        return {
            'type': 'ir.actions.act_window',
            'name': record.name,
            'res_model': record._name,
            'res_id': record.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_view_grns(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Goods Received Notes'), 'res_model': 'procurement.grn',
            'view_mode': 'list,form', 'domain': [('order_id', '=', self.id)],
            'context': {'default_order_id': self.id},
        }

    def action_view_completions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Service Completion Notes'),
            'res_model': 'procurement.completion', 'view_mode': 'list,form',
            'domain': [('order_id', '=', self.id)], 'context': {'default_order_id': self.id},
        }
