from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

MANAGER_GROUP = 'hijra_finance.group_finance_manager'
TODO = 'mail.mail_activity_data_todo'


class FinanceTransaction(models.Model):
    """One simple record for a payment or a receipt.

    The finance team fills in a flat form; posting it creates the double-entry
    journal entry (expense: debit the account, credit the bank or cash account;
    income: the other way round), so nobody has to think in debits and credits.
    """
    _name = 'finance.transaction'
    _description = 'Finance Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_names_search = ['name', 'description', 'cheque_ref']

    name = fields.Char(string='Number', default='New', readonly=True, copy=False, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'To Approve'),
        ('approved', 'Approved'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, copy=False, tracking=True, index=True)
    transaction_type = fields.Selection(
        [('expense', 'Expense'), ('income', 'Income')], string='Type', required=True,
        default='expense', tracking=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True)
    journal_id = fields.Many2one(
        'account.journal', string='Paid Through', required=True, tracking=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
        default=lambda self: self._default_journal(),
        help="The bank or cash account the money goes out of (or comes into).")
    currency_id = fields.Many2one(
        'res.currency', string='Currency', compute='_compute_currency_id', store=True,
        readonly=False, precompute=True, required=True)
    amount = fields.Monetary(required=True, tracking=True, currency_field='currency_id')
    account_id = fields.Many2one(
        'account.account', string='Account', tracking=True,
        domain="[('account_type', '!=', 'off_balance')]",
        help="The expense account (or income account) this transaction is booked to.")
    partner_id = fields.Many2one('res.partner', string='Vendor / Customer', tracking=True)
    description = fields.Char(string='Description', required=True, tracking=True)
    notes = fields.Text(string='Reference / Notes')
    cheque_ref = fields.Char(string='Cheque / Reference No', copy=False)

    # HIJRA codes (global lists from hijra_base)
    project_id = fields.Many2one('hijra.project', string='Project', tracking=True)
    budget_id = fields.Many2one(
        'hijra.budget', string='Budget Line', domain="[('project_id', '=', project_id)]")
    fund_id = fields.Many2one('hijra.fund', string='Fund')
    location_id = fields.Many2one('hijra.location', string='Location')

    line_ids = fields.One2many(
        'finance.transaction.line', 'transaction_id', string='Split Lines', copy=True,
        help="Only when the amount goes to several accounts or projects. "
             "Leave empty to use the account and codes above.")

    # approval and posting
    approver_id = fields.Many2one(
        'res.users', string='Approver', tracking=True,
        help="Who is asked to approve. Any approver or finance manager can approve if left empty.")
    approved_by_id = fields.Many2one('res.users', string='Approved By', copy=False, readonly=True)
    approved_date = fields.Datetime(string='Approved On', copy=False, readonly=True)
    posted_by_id = fields.Many2one('res.users', string='Posted By', copy=False, readonly=True)
    posted_date = fields.Datetime(string='Posted On', copy=False, readonly=True)
    move_id = fields.Many2one(
        'account.move', string='Journal Entry', copy=False, readonly=True, index=True)

    @api.model
    def _default_journal(self):
        return self.env['account.journal'].search([
            ('type', 'in', ('bank', 'cash')), ('company_id', '=', self.env.company.id),
        ], limit=1)

    @api.depends('journal_id', 'company_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.journal_id.currency_id or rec.company_id.currency_id

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.budget_id and self.budget_id.project_id != self.project_id:
            self.budget_id = False

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        if self.line_ids:
            self.amount = sum(self.line_ids.mapped('amount'))

    @api.constrains('amount', 'line_ids')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("The amount must be greater than zero."))
            if rec.line_ids:
                total = sum(rec.line_ids.mapped('amount'))
                if float_compare(total, rec.amount, precision_rounding=rec.currency_id.rounding):
                    raise ValidationError(_(
                        "The split lines add up to %(total)s, but the amount is %(amount)s.",
                        total=total, amount=rec.amount))

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('finance.transaction') or _('New')
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_processed(self):
        if any(rec.state not in ('draft', 'cancelled') for rec in self):
            raise UserError(_("Only draft or cancelled transactions can be deleted. Cancel it instead."))

    # ------------------------------------------------------------------
    # Journal entry
    # ------------------------------------------------------------------
    def _get_split_lines(self):
        """What is booked: the split lines, or one line from the header fields."""
        self.ensure_one()
        sources = self.line_ids or [self]
        result = []
        for source in sources:
            is_line = source is not self
            account = (source.account_id or self.account_id) if is_line else self.account_id
            if not account:
                raise UserError(_("Choose the account for %s.", self.name))
            result.append({
                'description': (source.description if is_line else '') or self.description,
                'account': account,
                'amount': source.amount if is_line else self.amount,
                'project': (source.project_id or self.project_id) if is_line else self.project_id,
                'budget': (source.budget_id or self.budget_id) if is_line else self.budget_id,
                'fund': (source.fund_id or self.fund_id) if is_line else self.fund_id,
                'location': (source.location_id or self.location_id) if is_line else self.location_id,
            })
        return result

    def _prepare_move_vals(self):
        self.ensure_one()
        journal = self.journal_id
        if not journal.default_account_id:
            raise UserError(_("The journal %s has no default account.", journal.display_name))
        company, currency = self.company_id, self.currency_id
        # expense: debit the account lines, credit the bank; income: the opposite
        sign = 1 if self.transaction_type == 'expense' else -1
        partner = self.partner_id.id
        lines, total_balance, total_currency = [], 0.0, 0.0
        for item in self._get_split_lines():
            balance = company.currency_id.round(
                currency._convert(item['amount'], company.currency_id, company, self.date)) * sign
            amount_currency = item['amount'] * sign
            total_balance += balance
            total_currency += amount_currency
            lines.append(Command.create({
                'name': item['description'],
                'account_id': item['account'].id,
                'partner_id': partner,
                'currency_id': currency.id,
                'amount_currency': amount_currency,
                'debit': balance if balance > 0 else 0.0,
                'credit': -balance if balance < 0 else 0.0,
            }))
        lines.append(Command.create({
            'name': self.description,
            'account_id': journal.default_account_id.id,
            'partner_id': partner,
            'currency_id': currency.id,
            'amount_currency': -total_currency,
            'debit': -total_balance if total_balance < 0 else 0.0,
            'credit': total_balance if total_balance > 0 else 0.0,
        }))
        return {
            'move_type': 'entry',
            'journal_id': journal.id,
            'company_id': company.id,
            'date': self.date,
            'ref': ' - '.join(filter(None, [self.name, self.description])),
            'narration': self.notes or False,
            'line_ids': lines,
        }

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def _is_manager(self):
        return self.env.user.has_group(MANAGER_GROUP)

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft transactions can be sent for approval."))
            rec._get_split_lines()  # makes sure an account is set
            rec.state = 'to_approve'
            rec.message_post(body=_("Sent for approval."))
            if rec.approver_id:
                rec.activity_schedule(
                    TODO, user_id=rec.approver_id.id,
                    summary=_("Approve %s", rec.name),
                    note=_("%(user)s asks you to approve %(name)s: %(description)s (%(amount)s %(currency)s).",
                           user=self.env.user.name, name=rec.name, description=rec.description,
                           amount=rec.amount, currency=rec.currency_id.name))

    def action_approve(self):
        user = self.env.user
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(_("Only transactions waiting for approval can be approved."))
            if rec.approver_id and rec.approver_id != user and not rec._is_manager():
                raise UserError(_("Only %s or a finance manager can approve this transaction.",
                                  rec.approver_id.name))
            rec.write({
                'state': 'approved', 'approved_by_id': user.id, 'approved_date': fields.Datetime.now()})
            rec.activity_unlink([TODO])
            rec.message_post(body=_("Approved by %s.", user.name))

    def action_return_draft(self):
        """Send back for changes (also used to reopen a cancelled transaction)."""
        for rec in self:
            if rec.state not in ('to_approve', 'approved', 'cancelled'):
                raise UserError(_("This transaction cannot be set to draft."))
            rec.write({'state': 'draft', 'approved_by_id': False, 'approved_date': False})
            rec.activity_unlink([TODO])
            rec.message_post(body=_("Set to draft by %s.", self.env.user.name))

    def action_post(self):
        if not self._is_manager():
            raise UserError(_("Only a finance manager can post transactions."))
        user, now = self.env.user, fields.Datetime.now()
        for rec in self:
            if rec.state not in ('draft', 'to_approve', 'approved'):
                raise UserError(_("%s is already posted or cancelled.", rec.name))
            move = rec.env['account.move'].sudo().with_company(rec.company_id).create(
                rec._prepare_move_vals())
            move.action_post()
            values = {'state': 'posted', 'move_id': move.id, 'posted_by_id': user.id, 'posted_date': now}
            if not rec.approved_by_id:
                # finance posted it directly, so this counts as its approval too
                values.update(approved_by_id=user.id, approved_date=now)
            rec.write(values)
            rec.activity_unlink([TODO])
            rec.message_post(body=_("Posted as journal entry %s.", move.name))

    def action_cancel(self):
        if not self._is_manager():
            raise UserError(_("Only a finance manager can cancel transactions."))
        for rec in self:
            if rec.state == 'cancelled':
                continue
            if rec.move_id:
                move = rec.move_id.sudo()
                if move.state == 'posted':
                    move.button_draft()
                move.button_cancel()
                rec.message_post(body=_("Journal entry %s cancelled.", move.name))
            rec.write({'state': 'cancelled', 'move_id': False})
            rec.activity_unlink([TODO])

    def action_view_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------
    def _prepare_voucher_data(self):
        """Plain values for the printed voucher (see report/voucher_pdf.py)."""
        self.ensure_one()
        company = self.company_id.sudo()
        currency = self.currency_id
        # money going out prints as a negative amount, like the paper voucher
        sign = -1 if self.transaction_type == 'expense' else 1
        rows = []
        for item in self._get_split_lines():
            rows.append({
                'project': item['project'].code or '',
                'code': '-'.join(filter(None, [
                    item['fund'].code, item['budget'].code, item['location'].code])),
                'description': item['description'] or '',
                'amount': item['amount'] * sign,
                'currency': currency.name or '',
            })
        users = self.create_uid | self.approved_by_id | self.posted_by_id
        signatures = users._get_signature_images()

        def person(user, signed):
            return {
                'name': (user.name or '') if user else '',
                'position': (user.job_title or user.function or '') if user else '',
                'signature': signatures.get(user.id) if signed and user else False,
            }

        return {
            'title': _('Payment Voucher') if self.transaction_type == 'expense' else _('Receipt Voucher'),
            'name': self.name or '',
            'date': self.date,
            'logo': [value for value in (company.logo, getattr(company, 'logo_web', False)) if value],
            'for': self.description or '',
            'rows': rows,
            'total': sum(row['amount'] for row in rows),
            'currency': currency.name or '',
            'cheque_ref': self.cheque_ref or '',
            'received_label': _('Received by') if self.transaction_type == 'expense' else _('Paid by'),
            'prepared': person(self.create_uid.sudo(), self.state != 'draft'),
            'approved': person(self.approved_by_id.sudo(), bool(self.approved_date)),
            'authorized': person(self.posted_by_id.sudo(), self.state == 'posted'),
        }


class FinanceTransactionLine(models.Model):
    _name = 'finance.transaction.line'
    _description = 'Finance Transaction Split Line'
    _order = 'sequence, id'

    transaction_id = fields.Many2one(
        'finance.transaction', string='Transaction', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='transaction_id.company_id', store=True)
    currency_id = fields.Many2one(related='transaction_id.currency_id')
    sequence = fields.Integer(default=10)
    description = fields.Char()
    account_id = fields.Many2one(
        'account.account', string='Account', domain="[('account_type', '!=', 'off_balance')]")
    amount = fields.Monetary(required=True, currency_field='currency_id')
    project_id = fields.Many2one('hijra.project', string='Project')
    budget_id = fields.Many2one(
        'hijra.budget', string='Budget Line', domain="[('project_id', '=', project_id)]")
    fund_id = fields.Many2one('hijra.fund', string='Fund')
    location_id = fields.Many2one('hijra.location', string='Location')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.budget_id and self.budget_id.project_id != self.project_id:
            self.budget_id = False
