from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    receipt_type = fields.Selection(
        [('goods', 'Goods'), ('service', 'Service')], string='Receipt Type', default='goods',
        required=True, copy=True, tracking=True,
        help="Goods are received with a Goods Received Note; a service is closed with a Service Completion Note. "
             "One or the other, never both.")
    grn_ids = fields.One2many('procurement.grn', 'order_id', string='Goods Received Notes')
    grn_count = fields.Integer(compute='_compute_receipt_counts')
    completion_ids = fields.One2many('procurement.completion', 'order_id', string='Service Completion Notes')
    completion_count = fields.Integer(compute='_compute_receipt_counts')
    receipt_locked = fields.Boolean(compute='_compute_receipt_counts')

    @api.depends('grn_ids.state', 'completion_ids.state')
    def _compute_receipt_counts(self):
        for order in self:
            order.grn_count = len(order.grn_ids.filtered(lambda g: g.state != 'cancelled'))
            order.completion_count = len(order.completion_ids.filtered(lambda c: c.state != 'cancelled'))
            order.receipt_locked = bool(order.grn_count or order.completion_count)

    def _check_can_receive(self):
        self.ensure_one()
        if self.state not in ('purchase', 'done'):
            raise UserError(_("Confirm the order first: it has to be authorized by the Officer-in-Charge."))

    def _remaining_quantities(self):
        """{order line id: quantity still to receive}, counting the notes already marked as received."""
        self.ensure_one()
        received = {}
        for grn in self.grn_ids.filtered(lambda g: g.state in ('received', 'checked')):
            for line in grn.line_ids:
                if line.order_line_id:
                    received[line.order_line_id.id] = received.get(line.order_line_id.id, 0.0) + line.qty_received
        remaining = {}
        for line in self.order_line.filtered(lambda l: not l.display_type):
            left = line.product_qty - received.get(line.id, 0.0)
            if left > 1e-9:
                remaining[line.id] = left
        return remaining

    def is_fully_received(self):
        """True when the goods are all received, or the service is completed and approved."""
        self.ensure_one()
        if self.receipt_type == 'service':
            return bool(self.completion_ids.filtered(lambda c: c.state == 'approved'))
        return not self._remaining_quantities()

    # ------------------------------------------------------------------
    # One Receive button: it opens the goods received note or the service completion note
    # ------------------------------------------------------------------
    def action_receive(self):
        """The standard Receive button opens the receipt document of this order."""
        if len(self) != 1:
            return super().action_receive()
        self._check_can_receive()
        if self.receipt_type == 'service':
            return self.action_complete_service()
        return self.action_receive_goods()

    def action_receive_goods(self):
        """The goods received note for what is still to be received on this order."""
        self.ensure_one()
        self._check_can_receive()
        if self.receipt_type != 'goods':
            raise UserError(_("%s is an order for a service: use its Service Completion Note.", self.name))
        draft = self.grn_ids.filtered(lambda g: g.state == 'draft')[:1]
        if draft:
            return self._open(draft)
        if not self._remaining_quantities():
            raise UserError(_("Everything on %s has already been received.", self.name))
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
        """The service completion note of this order, drafted from it."""
        self.ensure_one()
        self._check_can_receive()
        if self.receipt_type != 'service':
            raise UserError(_("%s is an order for goods: use its Goods Received Note.", self.name))
        existing = self.completion_ids.filtered(lambda c: c.state != 'cancelled')[:1]
        if existing:
            return self._open(existing)
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
