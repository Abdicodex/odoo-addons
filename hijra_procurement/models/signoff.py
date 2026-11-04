from odoo import _, api, fields, models
from odoo.exceptions import UserError

DOCUMENTS = [
    ('declaration', 'Declaration of Impartiality'),
    ('analysis', 'Bid Analysis'),
    ('statement', 'Committee Statement'),
    ('minutes', 'Minutes'),
]


class ProcurementSignoff(models.Model):
    """One member's signature on one committee document of an RFQ."""
    _name = 'procurement.signoff'
    _description = 'Committee Signature'
    _order = 'rfq_id, document, sequence, id'

    rfq_id = fields.Many2one(
        'purchase.request.rfq', string='RFQ', required=True, ondelete='cascade', index=True)
    document = fields.Selection(DOCUMENTS, required=True)
    member_id = fields.Many2one('procurement.committee.member', ondelete='set null')
    user_id = fields.Many2one('res.users', string='Member', required=True)
    sequence = fields.Integer(related='member_id.sequence', store=True)
    signed_date = fields.Datetime(string='Signed On', readonly=True, copy=False)
    can_sign = fields.Boolean(compute='_compute_can_sign')
    member_name = fields.Char(string='Member', compute='_compute_member_name')

    _once = models.Constraint(
        'UNIQUE(rfq_id, document, user_id)', 'A member signs each document once.')

    @api.depends('member_id.full_name', 'user_id')
    def _compute_member_name(self):
        for rec in self:
            rec.member_name = rec.member_id.full_name or rec.user_id.name

    @api.depends('signed_date', 'user_id', 'rfq_id.committee_state')
    @api.depends_context('uid')
    def _compute_can_sign(self):
        for rec in self:
            rec.can_sign = (
                not rec.signed_date and rec.user_id == self.env.user
                and rec.rfq_id.committee_state == 'session')

    def action_open_sign(self):
        """Open the dialog that shows the document; the member whose line it is can sign from it."""
        self.ensure_one()
        wizard = self.env['procurement.sign.wizard'].create(
            {'signoff_id': self.id, 'preview_document': self.document})
        return wizard._reopen()

    def action_sign(self):
        """The member signs: the signature on their employee profile is printed on the document."""
        self.ensure_one()
        rfq = self.rfq_id
        if rfq.committee_state != 'session':
            raise UserError(_("The committee session is not open."))
        if self.signed_date:
            raise UserError(_("Already signed."))
        if self.user_id != self.env.user:
            raise UserError(_("Only %s can sign this.", self.user_id.name))
        if not self.user_id._get_signature_images():
            raise UserError(_(
                "Add your signature to your employee profile first (Employees > your profile > "
                "HR Settings), then sign."))
        if self.document != 'declaration':
            if not rfq.recommended_order_id:
                raise UserError(_("The vendor recommended by the committee must be selected first."))
            if rfq.signoff_ids.filtered(lambda s: s.document == 'declaration' and not s.signed_date):
                raise UserError(_("Every member must sign the declaration first."))
        self.sudo().signed_date = fields.Datetime.now()
        rfq.sudo()._message_signed(self)
        return True
