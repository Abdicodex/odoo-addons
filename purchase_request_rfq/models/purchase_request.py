from odoo import _, api, fields, models
from odoo.exceptions import UserError

BUYER_GROUP = 'purchase.group_purchase_user'
TODO_ACTIVITY = 'mail.mail_activity_data_todo'


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Purchase Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='PRF', required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'To Approve'),
        ('approved', 'Approved'),
        ('rfq_created', 'RFQ Created'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, copy=False, tracking=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id)
    date_request = fields.Datetime(
        string='Date', required=True, copy=False, default=fields.Datetime.now)
    date_required = fields.Date(string='Required By')

    # Requisition details
    # Name, position, department and email come from the requestor's user record.
    requester_id = fields.Many2one(
        'res.users', string='Requestor', required=True, readonly=True, tracking=True,
        default=lambda self: self.env.user)
    requester_position = fields.Char(
        string='Position', compute='_compute_requester_details', store=True)
    requester_email = fields.Char(string='Email', related='requester_id.email')
    department_id = fields.Many2one(
        'hr.department', string='Department', compute='_compute_requester_details', store=True)
    location_id = fields.Many2one('hijra.location', string='Location', tracking=True)
    project_id = fields.Many2one('hijra.project', string='Project', tracking=True)
    # The user picks the category; the budget code follows from it.
    budget_id = fields.Many2one(
        'hijra.budget', string='Category', tracking=True,
        domain="[('project_id', '=', project_id)]")
    budget_code = fields.Char(string='Budget', related='budget_id.code')
    fund_id = fields.Many2one('hijra.fund', string='Fund', tracking=True)
    verifier_id = fields.Many2one('res.users', string='Verifier', tracking=True)

    # Items
    line_ids = fields.One2many(
        'purchase.request.line', 'request_id', string='Item Details', copy=True)
    amount_total = fields.Monetary(
        string='Total Amount', compute='_compute_amount_total', store=True, tracking=True)
    reason = fields.Text(string='Remarks')

    # Approval
    approver_id = fields.Many2one('res.users', string='Name of Approver', tracking=True)
    approver_position = fields.Char(string='Position', compute='_compute_signatory_positions')
    approval_date = fields.Datetime(string='Date', copy=False, readonly=True)
    second_signatory_id = fields.Many2one(
        'res.users', string='2nd Signatory (if required)', tracking=True)
    second_position = fields.Char(string='Position', compute='_compute_signatory_positions')
    second_approval_date = fields.Datetime(string='Date', copy=False, readonly=True)
    decision_by_id = fields.Many2one('res.users', string='Decided By', copy=False, readonly=True)
    decision_date = fields.Datetime(string='Decision Date', copy=False, readonly=True)
    rejection_reason = fields.Text(copy=False, readonly=True)

    rfq_ids = fields.One2many('purchase.order', 'purchase_request_id', string='RFQs')
    rfq_count = fields.Integer(compute='_compute_rfq_count')

    @api.model
    def _get_position(self, user):
        # sudo: employee data is not readable by every user
        user = user.sudo()
        return user.job_title or user.function or False

    @api.depends('requester_id')
    def _compute_requester_details(self):
        for rec in self:
            user = rec.requester_id.sudo()
            rec.requester_position = rec._get_position(user)
            rec.department_id = user.department_id

    @api.depends('approver_id', 'second_signatory_id')
    def _compute_signatory_positions(self):
        for rec in self:
            rec.approver_position = rec._get_position(rec.approver_id)
            rec.second_position = rec._get_position(rec.second_signatory_id)

    @api.depends('line_ids.subtotal')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('subtotal'))

    def _compute_rfq_count(self):
        # sudo: requesters may not have access to purchase orders
        for rec in self:
            rec.rfq_count = len(rec.sudo().rfq_ids)

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.budget_id and self.budget_id.project_id != self.project_id:
            self.budget_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('purchase.requisition.prf') or _('New'))
        return super().create(vals_list)

    def _prepare_prf_data(self):
        """Plain values for the printed requisition form (see report/prf_pdf.py)."""
        self.ensure_one()

        def local_date(value):
            return fields.Datetime.context_timestamp(self, value).date() if value else None

        return {
            'name': self.name or '',
            'date': local_date(self.date_request),
            'logo': self.company_id.sudo().logo or False,
            'requestor': self.requester_id.name or '',
            'position': self.requester_position or '',
            'department': self.department_id.name or '',
            'location': self.location_id.name or '',
            'email': self.requester_email or '',
            'project': self.project_id.code or '',
            'budget': self.budget_code or '',
            'fund': self.fund_id.code or '',
            'category': self.budget_id.name or '',
            'verifier': self.verifier_id.name or '',
            'lines': [{
                'description': line.description or '',
                'unit': line.unit or '',
                'quantity': line.product_qty,
                'frequency': line.frequency,
                'price': line.price_unit,
                'amount': line.subtotal,
            } for line in self.line_ids.sorted('sequence')],
            'total': self.amount_total,
            'approver': self.approver_id.name or '',
            'approver_position': self.approver_position or '',
            'approval_date': local_date(self.approval_date),
            'second': self.second_signatory_id.name or '',
            'second_position': self.second_position or '',
            'second_date': local_date(self.second_approval_date),
        }

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def _schedule_approval_activity(self, user):
        self.ensure_one()
        self.activity_schedule(
            TODO_ACTIVITY,
            summary=_("Approve purchase requisition %s", self.name),
            user_id=user.id)

    def action_request_approval(self):
        required = (
            'department_id', 'location_id', 'project_id', 'budget_id', 'fund_id',
            'verifier_id', 'approver_id')
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Add at least one item before requesting approval."))
            missing = [rec._fields[name].string for name in required if not rec[name]]
            if missing:
                raise UserError(_(
                    "Please fill in: %s", ", ".join(missing)))
        self.write({'state': 'to_approve'})
        for rec in self:
            rec._schedule_approval_activity(rec.approver_id)
            rec.message_post(body=_("Approval requested from %s.", rec.approver_id.name))

    def action_approve(self):
        user = self.env.user
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(_("Only requisitions waiting for approval can be approved."))
            signed = False
            if user == rec.approver_id and not rec.approval_date:
                rec.approval_date = now
                signed = True
            if user == rec.second_signatory_id and not rec.second_approval_date:
                rec.second_approval_date = now
                signed = True
            if not signed:
                raise UserError(_(
                    "Only the named approver or 2nd signatory can approve this requisition."))
            rec.activity_feedback([TODO_ACTIVITY], user_id=user.id)
            rec.message_post(body=_("Approved by %s.", user.name))
            if rec.second_signatory_id and not rec.second_approval_date:
                rec._schedule_approval_activity(rec.second_signatory_id)
            if rec.approval_date and (
                    not rec.second_signatory_id or rec.second_approval_date):
                rec.write({'state': 'approved', 'decision_date': now, 'decision_by_id': user.id})

    def action_open_reject(self):
        self.ensure_one()
        if self.env.user not in (self.approver_id | self.second_signatory_id):
            raise UserError(_(
                "Only the named approver or 2nd signatory can reject this requisition."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Requisition'),
            'res_model': 'purchase.request.reject',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_reset_draft(self):
        self.write({
            'state': 'draft',
            'approval_date': False,
            'second_approval_date': False,
            'decision_by_id': False,
            'decision_date': False,
            'rejection_reason': False,
        })

    def action_cancel(self):
        if any(rec.rfq_ids for rec in self.sudo()):
            raise UserError(_("Cancel the linked RFQs first."))
        self.activity_unlink([TODO_ACTIVITY])
        self.write({'state': 'cancelled'})

    def action_open_make_rfq(self):
        self.ensure_one()
        if not self.env.user.has_group(BUYER_GROUP):
            raise UserError(_("Only purchase users can create RFQs."))
        if self.state not in ('approved', 'rfq_created'):
            raise UserError(_("Only approved requisitions can be turned into RFQs."))
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
        """Values for one RFQ addressed to `partner` with every requisition item."""
        self.ensure_one()
        po_line_fields = self.env['purchase.order.line']._fields
        uom_field = next(
            name for name in ('uom_id', 'product_uom_id', 'product_uom')
            if name in po_line_fields)
        planned = fields.Datetime.to_datetime(self.date_required) or fields.Datetime.now()
        lines = []
        for line in self.line_ids:
            uom = line.product_uom_id or line.product_id.uom_id
            line_vals = {
                'product_id': line.product_id.id,
                'name': line.description or line.product_id.display_name,
                # quantity x frequency, so quantity x unit price matches the requisition amount
                'product_qty': line.product_qty * line.frequency,
                uom_field: uom.id,
                'date_planned': planned,
            }
            # let Odoo pick the vendor price when no estimate was entered
            if line.price_unit:
                line_vals['price_unit'] = line.price_unit
            lines.append((0, 0, line_vals))
        return {
            'partner_id': partner.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'origin': self.name,
            'purchase_request_id': self.id,
            'user_id': self.env.user.id,
            'order_line': lines,
        }
