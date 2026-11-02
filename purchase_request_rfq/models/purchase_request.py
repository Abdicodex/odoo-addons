from odoo import _, api, fields, models
from odoo.exceptions import UserError

APPROVER_GROUP = 'purchase_request_rfq.group_purchase_request_manager'
BUYER_GROUP = 'purchase.group_purchase_user'


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New'))
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], string='Priority', default='0', index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'To Approve'),
        ('approved', 'Approved'),
        ('rfq_created', 'RFQ Created'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, copy=False, tracking=True, index=True)

    requester_id = fields.Many2one(
        'res.users', string='Requested By', required=True, tracking=True,
        default=lambda self: self.env.user)
    user_id = fields.Many2one(
        'res.users', string='Buyer', tracking=True,
        help="Purchase representative who will turn this request into RFQs.")
    partner_id = fields.Many2one(
        'res.partner', string='Preferred Vendor', tracking=True,
        help="Optional. Pre-filled when creating the RFQ.")
    partner_ref = fields.Char(string='Vendor Reference', copy=False)
    origin = fields.Char(string='Source', copy=False,
                         help="Reference of the document that generated this request.")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms')

    date_request = fields.Datetime(
        string='Request Date', required=True, copy=False, default=fields.Datetime.now)
    date_required = fields.Date(string='Expected Arrival', required=True, tracking=True)

    reason = fields.Text(string='Justification')
    note = fields.Html(string='Terms and Conditions')
    line_ids = fields.One2many(
        'purchase.request.line', 'request_id', string='Products', copy=True)

    amount_untaxed = fields.Monetary(
        string='Untaxed Amount', compute='_compute_amounts', store=True)
    amount_tax = fields.Monetary(string='Taxes', compute='_compute_amounts', store=True)
    amount_total = fields.Monetary(
        string='Total', compute='_compute_amounts', store=True, tracking=True)

    approver_id = fields.Many2one('res.users', string='Approved/Rejected By', copy=False, readonly=True)
    decision_date = fields.Datetime(string='Decision Date', copy=False, readonly=True)
    rejection_reason = fields.Text(copy=False, readonly=True)

    rfq_ids = fields.One2many('purchase.order', 'purchase_request_id', string='RFQs')
    rfq_count = fields.Integer(compute='_compute_rfq_count')

    @api.depends('line_ids.subtotal', 'line_ids.price_tax')
    def _compute_amounts(self):
        for rec in self:
            untaxed = sum(rec.line_ids.mapped('subtotal'))
            tax = sum(rec.line_ids.mapped('price_tax'))
            rec.amount_untaxed = untaxed
            rec.amount_tax = tax
            rec.amount_total = untaxed + tax

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

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def _check_group(self, xmlid, message):
        if not self.env.user.has_group(xmlid):
            raise UserError(message)

    def _get_approvers(self):
        group = self.env.ref(APPROVER_GROUP)
        return group.user_ids.filtered(lambda u: u.active and u.share is False)

    def _close_approval_activities(self):
        self.activity_feedback(['mail.mail_activity_data_todo'])

    def action_request_approval(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Add at least one product before requesting approval."))
        self.write({'state': 'to_approve'})
        for rec in self:
            for approver in rec._get_approvers():
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_("Approve purchase request %s", rec.name),
                    user_id=approver.id)
            rec.message_post(body=_("Approval requested."))

    def action_approve(self):
        self._check_group(
            APPROVER_GROUP, _("Only purchase request approvers can approve requests."))
        self._close_approval_activities()
        self.write({
            'state': 'approved',
            'approver_id': self.env.user.id,
            'decision_date': fields.Datetime.now(),
            'rejection_reason': False,
        })

    def action_open_reject(self):
        self.ensure_one()
        self._check_group(
            APPROVER_GROUP, _("Only purchase request approvers can reject requests."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Purchase Request'),
            'res_model': 'purchase.request.reject',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_reset_draft(self):
        self.write({
            'state': 'draft',
            'approver_id': False,
            'decision_date': False,
            'rejection_reason': False,
        })

    def action_cancel(self):
        if any(rec.rfq_ids for rec in self.sudo()):
            raise UserError(_("Cancel the linked RFQs first."))
        self._close_approval_activities()
        self.write({'state': 'cancelled'})

    def action_open_make_rfq(self):
        self.ensure_one()
        self._check_group(BUYER_GROUP, _("Only purchase users can create RFQs."))
        if self.state not in ('approved', 'rfq_created'):
            raise UserError(_("Only approved requests can be turned into RFQs."))
        context = {'default_request_id': self.id}
        if self.partner_id:
            context['default_partner_ids'] = [(6, 0, self.partner_id.ids)]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create RFQs'),
            'res_model': 'purchase.request.make.rfq',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
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
                'date_planned': line.date_planned or planned,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
            }
            if line.analytic_distribution:
                line_vals['analytic_distribution'] = line.analytic_distribution
            # let Odoo pick the vendor price when no estimate was entered
            if line.price_unit:
                line_vals['price_unit'] = line.price_unit
            lines.append((0, 0, line_vals))
        vals = {
            'partner_id': partner.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'origin': self.name,
            'priority': self.priority,
            'purchase_request_id': self.id,
            'user_id': (self.user_id or self.env.user).id,
            'order_line': lines,
        }
        if self.payment_term_id:
            vals['payment_term_id'] = self.payment_term_id.id
        if self.note:
            vals['note'] = self.note
        return vals
