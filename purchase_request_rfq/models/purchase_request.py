from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'To Approve'),
        ('approved', 'Approved'),
        ('rfq_created', 'RFQ Created'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, copy=False, tracking=True)
    requester_id = fields.Many2one(
        'res.users', string='Requested By', required=True, tracking=True,
        default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date_required = fields.Date(string='Required By', required=True, tracking=True)
    reason = fields.Text(string='Reason / Notes')
    line_ids = fields.One2many('purchase.request.line', 'request_id', string='Lines', copy=True)
    estimated_total = fields.Monetary(compute='_compute_estimated_total')
    approver_id = fields.Many2one('res.users', string='Approved/Rejected By', copy=False, readonly=True)
    decision_date = fields.Datetime(copy=False, readonly=True)
    rfq_ids = fields.One2many('purchase.order', 'purchase_request_id', string='RFQs')
    rfq_count = fields.Integer(compute='_compute_rfq_count')

    @api.depends('line_ids.subtotal')
    def _compute_estimated_total(self):
        for rec in self:
            rec.estimated_total = sum(rec.line_ids.mapped('subtotal'))

    def _compute_rfq_count(self):
        # sudo: requesters may not have access to purchase orders
        for rec in self:
            rec.rfq_count = len(rec.sudo().rfq_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.request') or _('New')
        return super().create(vals_list)

    def _check_group(self, xmlid, message):
        if not self.env.user.has_group(xmlid):
            raise UserError(message)

    def action_submit(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Add at least one line before submitting."))
        self.write({'state': 'to_approve'})

    def action_approve(self):
        self._check_group(
            'purchase_request_rfq.group_purchase_request_manager',
            _("Only purchase request approvers can approve requests."))
        self.write({
            'state': 'approved',
            'approver_id': self.env.user.id,
            'decision_date': fields.Datetime.now(),
        })

    def action_reject(self):
        self._check_group(
            'purchase_request_rfq.group_purchase_request_manager',
            _("Only purchase request approvers can reject requests."))
        self.write({
            'state': 'rejected',
            'approver_id': self.env.user.id,
            'decision_date': fields.Datetime.now(),
        })

    def action_reset_draft(self):
        self.write({'state': 'draft', 'approver_id': False, 'decision_date': False})

    def action_cancel(self):
        if any(rec.rfq_ids for rec in self.sudo()):
            raise UserError(_("Cancel the linked RFQs first."))
        self.write({'state': 'cancelled'})

    def action_open_make_rfq(self):
        self.ensure_one()
        self._check_group(
            'purchase.group_purchase_user',
            _("Only purchase users can create RFQs."))
        if self.state not in ('approved', 'rfq_created'):
            raise UserError(_("Only approved requests can be turned into RFQs."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create RFQs'),
            'res_model': 'purchase.request.make.rfq',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_view_rfqs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('purchase.purchase_rfq')
        action['domain'] = [('purchase_request_id', '=', self.id)]
        action['context'] = {'create': False}
        if self.rfq_count == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = self.rfq_ids.id
        return action

    def _prepare_rfq_vals(self, partner):
        """Values for one RFQ addressed to `partner` with every request line."""
        self.ensure_one()
        po_line_fields = self.env['purchase.order.line']._fields
        uom_field = next(
            name for name in ('uom_id', 'product_uom_id', 'product_uom')
            if name in po_line_fields)
        planned = fields.Datetime.to_datetime(self.date_required)
        lines = []
        for line in self.line_ids:
            line_vals = {
                'product_id': line.product_id.id,
                'name': line.description or line.product_id.display_name,
                'product_qty': line.product_qty,
                uom_field: line.product_uom_id.id,
                'date_planned': planned,
            }
            # let Odoo pick the vendor price when no estimate was entered
            if line.price_unit:
                line_vals['price_unit'] = line.price_unit
            lines.append((0, 0, line_vals))
        return {
            'partner_id': partner.id,
            'company_id': self.company_id.id,
            'origin': self.name,
            'purchase_request_id': self.id,
            'order_line': lines,
        }
