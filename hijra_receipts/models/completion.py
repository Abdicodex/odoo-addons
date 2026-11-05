from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProcurementCompletion(models.Model):
    """Service Completion Note: certifies that a purchased service was delivered, approved by the
    programme manager. Drafted from the order, then edited (like the committee minutes)."""
    _name = 'procurement.completion'
    _description = 'Service Completion Note'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Note No', default='New', copy=False, readonly=True, tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('approved', 'Approved'), ('cancelled', 'Cancelled')],
        default='draft', required=True, copy=False, tracking=True)
    order_id = fields.Many2one(
        'purchase.order', string='Purchase Order', required=True, ondelete='restrict', index=True,
        tracking=True, domain="[('state', 'in', ('purchase', 'done'))]")
    partner_id = fields.Many2one(related='order_id.partner_id', string='Vendor', store=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    request_id = fields.Many2one(related='order_id.purchase_request_id', store=True)
    date = fields.Date(string='Date of Note', default=fields.Date.context_today, tracking=True)
    service = fields.Char(
        string='Service', help="What was provided, e.g. refreshments and lunch for 200 participants.")
    activity = fields.Char(
        string='Activity', help="The activity it was provided for, e.g. the Agricultural Training for Smallholder Farmers.")
    place = fields.Char(string='Place of Activity')
    activity_dates = fields.Char(string='Date of Activity')
    background = fields.Text()
    benefits = fields.Text(string='Key Benefits', help="One benefit per line.")
    conclusion = fields.Text()
    approver_id = fields.Many2one(
        'res.users', string='Approved By', tracking=True,
        help="The programme manager who reviews and approves the note.")
    approver_date = fields.Datetime(string='Approved On', copy=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('procurement.completion') or _('New')
        notes = super().create(vals_list)
        for note in notes:
            if not note.background and not note.conclusion:
                note.action_draft_text()
        return notes

    # ------------------------------------------------------------------
    # Draft text
    # ------------------------------------------------------------------
    def action_draft_text(self):
        """Write the background and the conclusion from the order, to be edited if needed."""
        for rec in self:
            rec.write({'background': rec._build_background(), 'conclusion': rec._build_conclusion()})

    def _build_background(self):
        self.ensure_one()
        vendor = self.partner_id.name or _("the vendor")
        service = self.service or _("the services")
        activity = (_(" during the %s", self.activity)) if self.activity else ""
        paragraphs = [_(
            "This is to certify that the provision of %(service)s%(activity)s was successfully completed by %(vendor)s.",
            service=service, activity=activity, vendor=vendor)]
        if self.place or self.activity_dates:
            where = (_(" at %s", self.place)) if self.place else ""
            when = (_(" on %s", self.activity_dates)) if self.activity_dates else ""
            paragraphs.append(_("The activity was conducted%(where)s%(when)s.", where=where, when=when))
        paragraphs.append(_(
            "All services were provided by %(vendor)s%(where)s in accordance with the agreed standards and requirements.",
            vendor=vendor, where=(_(" at %s", self.place)) if self.place else ""))
        paragraphs.append(_(
            "The services were delivered efficiently and on schedule, contributing to a conducive environment "
            "for active participation and productive discussions throughout the activity."))
        return "\n\n".join(paragraphs)

    def _build_conclusion(self):
        self.ensure_one()
        vendor = self.partner_id.name or _("the vendor")
        activity = self.activity or _("activity")
        return _(
            "The %(activity)s was successfully conducted, with the services provided by %(vendor)s in a "
            "satisfactory and timely manner. The quality of the services contributed significantly to the smooth "
            "implementation of the activity and the achievement of its objectives.\n\n"
            "This note confirms the successful and satisfactory completion of the services provided.",
            activity=activity, vendor=vendor)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_approve(self):
        user = self.env.user
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only a draft note can be approved."))
            if not (rec.background or '').strip() or not (rec.conclusion or '').strip():
                raise UserError(_("Write the background and the conclusion first (Draft Note does it)."))
            if rec.approver_id and rec.approver_id != user and not user.has_group('base.group_system'):
                raise UserError(_("Only %s can approve this note.", rec.approver_id.name))
            rec.write({'state': 'approved', 'approver_id': user.id, 'approver_date': fields.Datetime.now()})
            rec.message_post(body=_("Approved by %s.", user.name))

    def action_cancel(self):
        for rec in self:
            if rec.state == 'approved':
                raise UserError(_("An approved note cannot be cancelled."))
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_("Only a cancelled note can be set to draft."))
            rec.state = 'draft'

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------
    def _prepare_completion_pdf_data(self):
        self.ensure_one()
        company = self.company_id.sudo()
        approver = self.approver_id.sudo()
        signatures = approver._get_signature_images() if approver else {}
        approved = self.state == 'approved'
        return {
            'logo': [value for value in (company.logo, getattr(company, 'logo_web', False)) if value],
            'date': self.date,
            'background': self.background or '',
            'benefits': self.benefits or '',
            'conclusion': self.conclusion or '',
            'place': self.place or '',
            'activity_dates': self.activity_dates or '',
            'approver': {
                'name': (approver.employee_id.name or approver.name or '') if approver else '',
                'date': fields.Datetime.context_timestamp(self, self.approver_date).date()
                if approved and self.approver_date else None,
                'signature': signatures.get(approver.id) if approved and approver else False,
            },
        }
