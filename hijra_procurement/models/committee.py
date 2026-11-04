from odoo import api, fields, models

COMMITTEE_GROUP = 'hijra_procurement.group_procurement_committee'


class ProcurementCommittee(models.Model):
    """The fixed purchase committee: reviewed once a year, every member signs."""
    _name = 'procurement.committee'
    _description = 'Procurement Committee'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, default='Procurement Committee', tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    review_date = fields.Date(
        string='Next Review', tracking=True,
        help="The committee is reviewed yearly: set the date of the next review.")
    member_ids = fields.One2many('procurement.committee.member', 'committee_id', string='Members')


class ProcurementCommitteeMember(models.Model):
    _name = 'procurement.committee.member'
    _description = 'Procurement Committee Member'
    _order = 'sequence, id'

    committee_id = fields.Many2one('procurement.committee', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    user_id = fields.Many2one('res.users', string='Member', required=True, domain=[('share', '=', False)])
    role = fields.Selection(
        [('chair', 'Chairperson'), ('secretary', 'Secretary'), ('member', 'Member')],
        required=True, default='member')
    position = fields.Char(
        help="Printed under the name on the committee documents, e.g. Finance Officer.")

    _user_uniq = models.Constraint(
        'UNIQUE(committee_id, user_id)', 'This person is already a member of the committee.')

    @api.onchange('user_id')
    def _onchange_user_id(self):
        if self.user_id and not self.position:
            roles = self.env['hijra.role'].sudo().search(
                [('user_ids', 'in', self.user_id.ids), ('code', 'not in', ('officer_in_charge', 'fa_officer'))],
                limit=1)
            self.position = roles.name or self.user_id.job_title or self.user_id.function or False

    # members get the committee group, so they can open and sign the RFQs
    @api.model_create_multi
    def create(self, vals_list):
        members = super().create(vals_list)
        members._add_to_group()
        return members

    def write(self, vals):
        old_users = self.user_id
        result = super().write(vals)
        if 'user_id' in vals:
            self._add_to_group()
            self._remove_from_group(old_users)
        return result

    def unlink(self):
        users = self.user_id
        result = super().unlink()
        self._remove_from_group(users)
        return result

    def _add_to_group(self):
        group = self.env.ref(COMMITTEE_GROUP, raise_if_not_found=False)
        if group:
            group.sudo().write({'user_ids': [(4, user.id) for user in self.user_id]})

    def _remove_from_group(self, users):
        group = self.env.ref(COMMITTEE_GROUP, raise_if_not_found=False)
        if not group:
            return
        still = self.sudo().search([('user_id', 'in', users.ids)]).user_id
        gone = users - still
        if gone:
            group.sudo().write({'user_ids': [(3, user.id) for user in gone]})
