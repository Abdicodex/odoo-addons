from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_amount

from .signoff import DOCUMENTS

DEFAULT_AGENDA = (
    "Analysis of vendors: Selected for their competitive pricing, high reliability, adequate "
    "capacity, strong past performance, and commitment to quality.")
DEFAULT_CRITERIA = (
    "Competitive Pricing: Offered the lowest price among the quotations received.\n"
    "Capacity: Demonstrated the ability to provide the required goods or services.\n"
    "Past Performance: Proven record of reliable delivery.")
DEFAULT_REASON = "Attained the highest rating in terms of Quality, Quantity, Lead Time and Price"


def _clock(value):
    """8.5 -> '08:30 AM'"""
    if not value and value != 0:
        return ''
    hours, minutes = divmod(int(round(value * 60)), 60)
    suffix = 'AM' if hours < 12 else 'PM'
    return '%02d:%02d %s' % ((hours % 12) or 12, minutes, suffix)


class PurchaseRequestRfq(models.Model):
    _inherit = ['purchase.request.rfq', 'mail.activity.mixin', 'procurement.touch.mixin']
    _file_path = 'request_id'

    currency_id = fields.Many2one(related='request_id.currency_id')
    project_id = fields.Many2one(related='request_id.project_id', string='Project')
    budget_id = fields.Many2one(related='request_id.budget_id', string='Budget Line')
    location_id = fields.Many2one(related='request_id.location_id', string='Location')
    procurement_amount = fields.Monetary(
        string='Estimated Value', related='request_id.amount_total', currency_field='currency_id')
    band_id = fields.Many2one(
        'procurement.band', string='Procurement Band', compute='_compute_band_id', store=True)
    committee_required = fields.Boolean(related='band_id.committee_required')
    observer_required = fields.Boolean(related='band_id.observer_required')
    min_invitations = fields.Integer(related='band_id.min_invitations')
    min_quotes = fields.Integer(related='band_id.min_quotes')
    invited_count = fields.Integer(string='Vendors Invited', compute='_compute_quotes')
    quotes_count = fields.Integer(string='Quotes Received', compute='_compute_quotes')
    shortfall = fields.Boolean(compute='_compute_quotes')
    shortfall_justification = fields.Text(
        string='Justification', help="Why fewer vendors than the policy asks for were invited or quoted.")

    committee_id = fields.Many2one(
        'procurement.committee', string='Committee', default=lambda self: self._default_committee())
    committee_state = fields.Selection([
        ('pending', 'Not Started'),
        ('session', 'In Session'),
        ('decided', 'Decided'),
    ], default='pending', required=True, copy=False, tracking=True)
    meeting_date = fields.Date(string='Meeting Date', default=fields.Date.context_today)
    meeting_start = fields.Float(string='Started')
    meeting_end = fields.Float(string='Ended')
    observer_name = fields.Char(string='Observer')
    observer_organization = fields.Char(string='Observer Organisation', default='Concern Worldwide')
    agenda = fields.Text(default=DEFAULT_AGENDA)
    selection_criteria = fields.Text(default=DEFAULT_CRITERIA)
    recommended_order_id = fields.Many2one(
        'purchase.order', string='Recommended Vendor', copy=False, tracking=True,
        domain="[('rfq_group_id', '=', id)]")
    recommendation_reason = fields.Text(default=DEFAULT_REASON)
    minutes_text = fields.Text(string='Minutes')
    signoff_ids = fields.One2many('procurement.signoff', 'rfq_id', string='Signatures', copy=False)
    signoff_pending = fields.Integer(compute='_compute_signoff_pending')

    @api.model
    def _default_committee(self):
        return self.env['procurement.committee'].search(
            [('company_id', 'in', self.env.companies.ids)], limit=1)

    @api.depends('request_id.amount_total')
    def _compute_band_id(self):
        Band = self.env['procurement.band']
        for rec in self:
            rec.band_id = Band._band_for(rec.request_id.amount_total)

    @api.depends('order_ids.amount_untaxed', 'band_id')
    def _compute_quotes(self):
        for rec in self:
            rec.invited_count = len(rec.order_ids)
            rec.quotes_count = len(rec.order_ids.filtered(lambda o: o.amount_untaxed > 0))
            band = rec.band_id
            rec.shortfall = bool(band) and (
                rec.invited_count < band.min_invitations or rec.quotes_count < band.min_quotes)

    @api.depends('signoff_ids.signed_date')
    def _compute_signoff_pending(self):
        for rec in self:
            rec.signoff_pending = len(rec.signoff_ids.filtered(lambda s: not s.signed_date))

    def write(self, vals):
        if 'recommended_order_id' in vals:
            for rec in self:
                if rec.signoff_ids.filtered(lambda s: s.document != 'declaration' and s.signed_date):
                    raise UserError(_(
                        "The recommended vendor cannot change once members have signed the bid "
                        "analysis, statement or minutes."))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------
    def _check_session_ready(self):
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_("Only an open RFQ can go to the committee."))
        if self.committee_state != 'pending':
            raise UserError(_("The committee session has already started."))
        if not self.committee_required:
            raise UserError(_(
                "This purchase (%(band)s) does not need the committee.", band=self.band_id.name or '-'))
        if not self.committee_id.member_ids:
            raise UserError(_("The committee has no members."))
        if not self.meeting_date:
            raise UserError(_("Set the meeting date."))
        if not self.quotes_count:
            raise UserError(_("Enter the vendors' prices on the quotations before the committee meets."))
        if self.shortfall and not (self.shortfall_justification or '').strip():
            raise UserError(_(
                "Fewer vendors were invited or quoted than the policy asks for (%(invited)s invited, "
                "%(quotes)s quotes; needed %(inv)s and %(q)s). Write the justification.",
                invited=self.invited_count, quotes=self.quotes_count,
                inv=self.min_invitations, q=self.min_quotes))
        if self.observer_required and not (self.observer_name or '').strip():
            raise UserError(_("Enter the name of the observer invited from %s.",
                              self.observer_organization or _("the partner organisation")))

    def action_start_session(self):
        for rec in self:
            rec._check_session_ready()
            lines = [
                Command.create({'document': document, 'member_id': member.id, 'user_id': member.user_id.id})
                for document, _label in DOCUMENTS for member in rec.committee_id.member_ids]
            rec.signoff_ids.unlink()
            rec.write({'signoff_ids': lines, 'committee_state': 'session'})
            rec.message_post(body=_(
                "Committee session started with %s members.", len(rec.committee_id.member_ids)))
            for member in rec.committee_id.member_ids:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=member.user_id.id,
                    summary=_("Sign the declaration for %s", rec.name))

    def action_reset_session(self):
        for rec in self:
            if rec.state != 'open':
                raise UserError(_("The RFQ is already awarded or cancelled."))
            rec.signoff_ids.unlink()
            rec.committee_state = 'pending'
            rec.activity_unlink(['mail.mail_activity_data_todo'])
            rec.message_post(body=_("Committee session reset by %s.", self.env.user.name))

    def _message_signed(self, signoff):
        self.ensure_one()
        self.message_post(body=_(
            "%(user)s signed the %(document)s.", user=signoff.user_id.name,
            document=dict(DOCUMENTS)[signoff.document]))
        self.activity_feedback(['mail.mail_activity_data_todo'], user_id=signoff.user_id.id)
        if not self.signoff_ids.filtered(lambda s: not s.signed_date):
            self.committee_state = 'decided'
            self.message_post(body=_("All members have signed: the committee has decided."))

    def action_generate_minutes(self):
        """Draft the minutes from the quotations and the selection, to be edited if needed."""
        for rec in self:
            rec.minutes_text = rec._build_minutes_text()

    def _build_minutes_text(self):
        self.ensure_one()
        env = self.env
        orders = self._vendor_orders()
        lines = ["A Request for Quotation (RFQ) was issued; quotations were received from the "
                 "following vendors:"]
        for number, order in enumerate(orders, 1):
            lines.append("Vendor %d: %s %s" % (
                number, order.partner_id.name, format_amount(env, order.amount_untaxed, order.currency_id)))
        winner = self.recommended_order_id
        if winner:
            lines += ["", "The winning vendor, %s, has been selected%s." % (
                winner.partner_id.name, (" to provide %s" % self.subject) if self.subject else "")]
        lines += ["", "Selection Criteria", "The selection was based on the following criteria:",
                  self.selection_criteria or ""]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------
    def _vendor_orders(self):
        return self.order_ids.filtered(lambda o: o.amount_untaxed > 0).sorted('id')

    def _people(self):
        """The members as printed: those of the session, else the committee as it is now."""
        self.ensure_one()
        members = self.committee_id.member_ids.sorted(lambda m: (m.sequence, m.id))
        if self.signoff_ids:
            ordered = self.signoff_ids.mapped('user_id')
            by_user = {m.user_id.id: m for m in members}
            return [(user, by_user.get(user.id)) for user in ordered.sorted(
                key=lambda u: by_user[u.id].sequence if u.id in by_user else 999)]
        return [(member.user_id, member) for member in members]

    def _prepare_committee_data(self):
        """Plain values for the committee documents (see report/committee_pdf.py)."""
        self.ensure_one()
        company = self.company_id.sudo()
        request = self.request_id.sudo()
        orders = self._vendor_orders().sudo()
        users = self.signoff_ids.mapped('user_id') | self.committee_id.member_ids.mapped('user_id')
        signatures = users._get_signature_images()

        def local(value):
            return fields.Datetime.context_timestamp(self, value) if value else None

        members = []
        for user, member in self._people():
            signed = {}
            for signoff in self.signoff_ids.filtered(lambda s: s.user_id == user and s.signed_date):
                signed[signoff.document] = {
                    'date': local(signoff.signed_date), 'signature': signatures.get(user.id)}
            members.append({
                'name': (member.full_name if member else '') or user.name or '',
                'position': (member.position if member else '') or user.job_title or '',
                'role': member.role if member else 'member',
                'signed': signed,
            })
        winner = self.recommended_order_id or self.awarded_order_id
        vendors = [{
            'name': order.partner_id.name or '', 'total': order.amount_untaxed,
            'currency_name': order.currency_id.name or '',
        } for order in orders]
        selected_no = (list(orders).index(winner) + 1) if winner and winner in orders else None
        items = []
        for number, item in enumerate(request.line_ids.sorted('sequence'), 1):
            prices, qty = [], item.product_qty
            for order in orders:
                line = order.order_line.filtered(lambda l: l.purchase_request_line_id == item)[:1]
                if line:
                    prices.append((line.price_unit, line.price_subtotal))
                    qty = line.product_qty
                else:
                    prices.append(None)
            items.append({
                'no': number, 'description': item.description or '', 'unit': item.unit or '',
                'qty': qty, 'prices': prices})
        observer = None
        if self.observer_required and self.observer_name:
            observer = {'name': self.observer_name, 'organization': self.observer_organization}
        return {
            'logo': [value for value in (company.logo, getattr(company, 'logo_web', False)) if value],
            'tender_ref': request.name or '',
            'rfq_name': self.name or '',
            'project': request.project_id.name or '',
            'subject': self.subject or '',
            'rfq_date': self.order_ids.sorted('id')[:1].rfq_date or (
                local(self.create_date).date() if self.create_date else None),
            'date': self.meeting_date,
            'vendors': vendors,
            'items': items,
            'currency': self.currency_id.name or '',
            'selected_name': winner.partner_id.name if winner else '',
            'selected_no': selected_no,
            'reason': self.recommendation_reason or '',
            'agenda': self.agenda or '',
            'start': _clock(self.meeting_start) if self.meeting_start else '',
            'end': _clock(self.meeting_end) if self.meeting_end else '',
            'minutes': self.minutes_text or self._build_minutes_text(),
            'members': members,
            'observer': observer,
        }
