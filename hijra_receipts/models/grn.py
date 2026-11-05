from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class ProcurementGrn(models.Model):
    """Goods Received Note: what arrived against a purchase order, signed by the person who
    received it and checked by a different person (the manual keeps receiving and inspection apart)."""
    _name = 'procurement.grn'
    _description = 'Goods Received Note'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='GRN No', default='New', copy=False, readonly=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('received', 'Received'), ('checked', 'Checked'), ('cancelled', 'Cancelled'),
    ], default='draft', required=True, copy=False, tracking=True)
    order_id = fields.Many2one(
        'purchase.order', string='Purchase Order', required=True, ondelete='restrict', index=True,
        tracking=True, domain="[('state', 'in', ('purchase', 'done'))]")
    partner_id = fields.Many2one(related='order_id.partner_id', string='Vendor', store=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    request_id = fields.Many2one(related='order_id.purchase_request_id', store=True)
    date = fields.Date(string='Date Received', default=fields.Date.context_today, tracking=True)
    location = fields.Char()
    invoice_number = fields.Char(string='Invoice Number')
    doc_invoice = fields.Boolean(string='Invoice received')
    doc_delivery = fields.Boolean(string='Delivery note received')
    order_complete = fields.Selection(
        [('complete', 'Complete order'), ('part', 'Part order')], string='Order',
        compute='_compute_order_complete', store=True, readonly=False)
    shipment = fields.Selection(
        [('complete', 'Complete shipment'), ('part', 'Part shipment')], string='Shipment', default='complete')
    line_ids = fields.One2many('procurement.grn.line', 'grn_id', string='Items', copy=True)
    received_by_id = fields.Many2one('res.users', string='Received By', copy=False, readonly=True)
    received_date = fields.Datetime(string='Received On', copy=False, readonly=True)
    checked_by_id = fields.Many2one(
        'res.users', string='Checked By', compute='_compute_checked_by', store=True, readonly=False,
        help="Who inspects the goods: the requester by default. Not the person who received them.")
    checked_date = fields.Datetime(string='Checked On', copy=False, readonly=True)
    notes = fields.Text()

    @api.depends('order_id')
    def _compute_checked_by(self):
        for rec in self:
            rec.checked_by_id = rec.order_id.sudo().purchase_request_id.requester_id

    @api.depends('line_ids.qty_ordered', 'line_ids.qty_previous', 'line_ids.qty_received')
    def _compute_order_complete(self):
        for rec in self:
            lines = rec.line_ids
            complete = bool(lines) and all(
                line.qty_previous + line.qty_received >= line.qty_ordered for line in lines)
            rec.order_complete = 'complete' if complete else 'part'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('procurement.grn') or _('New')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_receive(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only a draft note can be marked as received."))
            if not any(line.qty_received > 0 for line in rec.line_ids):
                raise UserError(_("Enter the quantity received on at least one item."))
            rec.write({'state': 'received', 'received_by_id': self.env.user.id,
                       'received_date': fields.Datetime.now()})
            rec._apply_received(1)
            rec.message_post(body=_("Received by %s.", self.env.user.name))
            if rec.checked_by_id:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=rec.checked_by_id.id,
                    summary=_("Check the goods of %s", rec.name))

    def action_check(self):
        user = self.env.user
        for rec in self:
            if rec.state != 'received':
                raise UserError(_("Only a received note can be checked."))
            if user == rec.received_by_id:
                raise UserError(_("Receiving and checking must be done by two different people."))
            if rec.checked_by_id and rec.checked_by_id != user and not user.has_group('base.group_system'):
                raise UserError(_("Only %s can check this note.", rec.checked_by_id.name))
            rec.write({'state': 'checked', 'checked_by_id': user.id, 'checked_date': fields.Datetime.now()})
            rec.activity_unlink(['mail.mail_activity_data_todo'])
            rec.message_post(body=_("Checked by %s.", user.name))

    def _apply_received(self, sign):
        """Keep the received quantity of the order lines (the standard Received column) in step."""
        for line in self.line_ids:
            if line.order_line_id and line.qty_received:
                order_line = line.order_line_id.sudo()
                order_line.qty_received = max(order_line.qty_received + sign * line.qty_received, 0.0)

    def action_cancel(self):
        for rec in self:
            if rec.state == 'checked':
                raise UserError(_("A checked note cannot be cancelled."))
            if rec.state == 'received':
                rec._apply_received(-1)
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_("Only a cancelled note can be set to draft."))
            rec.state = 'draft'

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------
    def _prepare_grn_pdf_data(self):
        """Plain values for the printed note (see report/grn_pdf.py)."""
        self.ensure_one()
        company = self.company_id.sudo()
        users = self.received_by_id | self.checked_by_id
        signatures = users.sudo()._get_signature_images()

        def local(value):
            return fields.Datetime.context_timestamp(self, value).date() if value else None

        def person(user, date, show):
            user = user.sudo()
            return {
                'name': (user.employee_id.name or user.name or '') if user else '',
                'date': local(date) if user else None,
                'signature': signatures.get(user.id) if user and show else False,
            }

        return {
            'logo': [value for value in (company.logo, getattr(company, 'logo_web', False)) if value],
            'name': self.name or '',
            'vendor': self.partner_id.name or '',
            'location': self.location or '',
            'date': self.date,
            'order': self.order_id.name or '',
            'invoice_number': self.invoice_number or '',
            'docs': {
                'invoice': self.doc_invoice, 'delivery': self.doc_delivery,
                'complete_order': self.order_complete == 'complete', 'part_order': self.order_complete == 'part',
                'complete_shipment': self.shipment == 'complete', 'part_shipment': self.shipment == 'part',
            },
            'lines': [{
                'no': number, 'description': line.description or '', 'uom': line.uom or '',
                'ordered': line.qty_ordered, 'received': line.qty_received, 'comment': line.comment or '',
            } for number, line in enumerate(self.line_ids.sorted('sequence'), 1)],
            'received': person(self.received_by_id, self.received_date, self.state in ('received', 'checked')),
            'checked': person(self.checked_by_id if self.state == 'checked' else self.env['res.users'],
                              self.checked_date, self.state == 'checked'),
        }


class ProcurementGrnLine(models.Model):
    _name = 'procurement.grn.line'
    _description = 'Goods Received Note Item'
    _order = 'grn_id, sequence, id'

    grn_id = fields.Many2one('procurement.grn', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    order_line_id = fields.Many2one('purchase.order.line', string='Order Line')
    description = fields.Text(required=True)
    uom = fields.Char(string='UOM')
    qty_ordered = fields.Float(string='Quantity Ordered', digits='Product Unit')
    qty_previous = fields.Float(string='Received Before', digits='Product Unit')
    qty_received = fields.Float(string='Quantity Received', digits='Product Unit')
    comment = fields.Char()
