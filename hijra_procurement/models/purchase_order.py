from odoo import _, fields, models
from odoo.exceptions import UserError

OPEN_STATES = ('draft', 'sent', 'to approve')


class PurchaseOrder(models.Model):
    _inherit = ['purchase.order', 'procurement.touch.mixin']
    _file_path = 'purchase_request_id'

    # HIJRA's order approval: the Finance Officer checks, then the Officer-in-Charge authorizes
    po_date = fields.Date(
        string='PO Date', default=fields.Date.context_today, copy=False,
        help="The date printed on the purchase order. Change it when the document is back-dated.")
    po_check_user_id = fields.Many2one('res.users', string='Checked By', copy=False, readonly=True, tracking=True)
    po_check_date = fields.Datetime(string='Checked On', copy=False, readonly=True)
    po_authorize_user_id = fields.Many2one(
        'res.users', string='Authorized By', copy=False, readonly=True, tracking=True)
    po_authorize_date = fields.Datetime(string='Authorized On', copy=False, readonly=True)

    # ------------------------------------------------------------------
    # Award: the winner goes through the approvals before it is confirmed
    # ------------------------------------------------------------------
    def action_award_order(self):
        """The vendor chosen by the committee wins the RFQ; its order is then checked by the
        Finance Officer and authorized by the Officer-in-Charge (which confirms it)."""
        self.ensure_one()
        group = self.rfq_group_id
        if not group:
            raise UserError(_("This order does not belong to an RFQ."))
        if not self.env.user.has_group('purchase.group_purchase_user'):
            raise UserError(_("Only purchase users can award an RFQ."))
        if group.state != 'open':
            raise UserError(_("This RFQ has already been awarded or cancelled."))
        if self.state not in ('draft', 'sent'):
            raise UserError(_("Only a quotation that is still open can be awarded."))
        if group.committee_required:
            if group.committee_state != 'decided':
                raise UserError(_(
                    "The procurement committee has to decide first: every member signs the "
                    "declaration, bid analysis, statement and minutes."))
            if group.recommended_order_id and group.recommended_order_id != self:
                raise UserError(_(
                    "The committee selected %s.", group.recommended_order_id.partner_id.name))
        others = (group.order_ids - self).filtered(lambda order: order.state in OPEN_STATES)
        others.button_cancel()
        group.write({'state': 'awarded', 'awarded_order_id': self.id})
        message = _("Awarded to %(vendor)s (%(order)s). Next: check by the Finance Officer, then "
                    "authorization by the Officer-in-Charge.", vendor=self.partner_id.name, order=self.name)
        group.message_post(body=message)
        group.request_id.message_post(body=_("RFQ %(rfq)s: %(message)s", rfq=group.name, message=message))
        self.message_post(body=message)
        self._schedule_for_role('finance_officer', _("Check %s", self.name))
        return True

    def action_open_procurement_file(self):
        self.ensure_one()
        return self.purchase_request_id.action_open_procurement_file()

    def _schedule_for_role(self, code, summary):
        self.ensure_one()
        for user in self.env['hijra.role']._get_users(code):
            self.activity_schedule('mail.mail_activity_data_todo', user_id=user.id, summary=summary)

    # ------------------------------------------------------------------
    # Check and authorize
    # ------------------------------------------------------------------
    def _is_role(self, *codes):
        user = self.env.user
        return user.has_group('base.group_system') or self.env['hijra.role']._user_has_role(user, *codes)

    def action_po_check(self):
        for order in self:
            if order.state not in OPEN_STATES:
                raise UserError(_("Only an order that is not confirmed yet can be checked."))
            if order.po_check_date:
                raise UserError(_("%s is already checked.", order.name))
            if not order._is_role('finance_officer'):
                raise UserError(_("Only the Finance Officer can check a purchase order."))
            order.write({'po_check_user_id': self.env.user.id, 'po_check_date': fields.Datetime.now()})
            order.activity_unlink(['mail.mail_activity_data_todo'])
            order.message_post(body=_("Checked by %s.", self.env.user.name))
            order._schedule_for_role('officer_in_charge', _("Authorize %s", order.name))

    def action_po_authorize(self):
        for order in self:
            if order.state not in OPEN_STATES:
                raise UserError(_("Only an order that is not confirmed yet can be authorized."))
            if not order.po_check_date:
                raise UserError(_("The Finance Officer has to check %s first.", order.name))
            if order.po_authorize_date:
                raise UserError(_("%s is already authorized.", order.name))
            if not order._is_role('officer_in_charge'):
                raise UserError(_("Only the Officer-in-Charge can authorize a purchase order."))
            order.write({'po_authorize_user_id': self.env.user.id, 'po_authorize_date': fields.Datetime.now()})
            order.activity_unlink(['mail.mail_activity_data_todo'])
            order.message_post(body=_("Authorized by %s: the order is confirmed.", self.env.user.name))
            order.with_context(po_chain_done=True).button_confirm()

    def button_confirm(self):
        if not self.env.context.get('po_chain_done'):
            for order in self.filtered(lambda o: o.state in OPEN_STATES):
                if not order.po_authorize_date:
                    raise UserError(_(
                        "%s cannot be confirmed yet: the Finance Officer checks it, then the "
                        "Officer-in-Charge authorizes it (the Authorize button confirms it).",
                        order.name))
        return super().button_confirm()

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------
    def _prepare_po_pdf_data(self):
        """Plain values for the printed purchase order (see report/po_pdf.py)."""
        self.ensure_one()
        from ..report import po_pdf  # lazy: reportlab is only needed when printing

        company = self.company_id.sudo()
        partner = self.partner_id.sudo()
        request = self.purchase_request_id.sudo()
        fund = request.fund_id.code or ''

        def local(value):
            return fields.Datetime.context_timestamp(self, value) if value else None

        def long_date(value):
            return po_pdf.fmt_long_date(local(value).date()) if value else ''

        lines = []
        for line in self.order_line.filtered(lambda l: not l.display_type):
            item = line.purchase_request_line_id.sudo()
            uom = getattr(line, 'uom_id', None) or getattr(line, 'product_uom_id', None)
            taxes = getattr(line, 'tax_ids', None) or getattr(line, 'taxes_id', None)
            lines.append({
                'code': fund or request.budget_code or '',
                'description': (item.description if item else '') or line.name or '',
                'qty': line.product_qty,
                'unit': (item.unit if item else '') or (uom.name if uom else ''),
                'price': line.price_unit,
                'vat': sum(taxes.mapped('amount')) if taxes else 0.0,
                'amount': line.price_subtotal,
            })
        contact = partner.child_ids.filtered(lambda c: c.type == 'contact')[:1]
        supplier_lines = [value for value in (
            partner.name, contact.name, partner.phone or contact.phone, partner.email or contact.email) if value]
        signed = bool(self.po_check_date or self.state in ('purchase', 'done'))
        users = self.user_id | self.po_check_user_id | self.po_authorize_user_id
        signatures = users.sudo()._get_signature_images()

        def person(user, date, show):
            user = user.sudo()
            return {
                'name': (user.employee_id.name or user.name or '') if user else '',
                'date': long_date(date) if user and date else '',
                'signature': signatures.get(user.id) if user and show else False,
            }

        return {
            'logo': [value for value in (company.logo, getattr(company, 'logo_web', False)) if value],
            'name': self.name or '',
            'date': self.po_date or (
                local(self.date_approve or self.date_order).date() if (self.date_approve or self.date_order) else None),
            'supplier': {'code': partner.ref or '', 'lines': supplier_lines},
            'buyer': {'lines': [po_pdf.ORG_NAME] + po_pdf.ORG_LINES},
            'delivery': self.rfq_location_id.sudo().name or request.location_id.name or '',
            'currency': self.currency_id.name or '',
            'lines': lines,
            'untaxed': self.amount_untaxed,
            'tax': self.amount_tax,
            'total': self.amount_total,
            'prepared': person(self.user_id, self.po_date or self.date_order or self.create_date, signed),
            'checked': person(self.po_check_user_id, self.po_check_date, True),
            'authorized': person(self.po_authorize_user_id, self.po_authorize_date, True),
        }
