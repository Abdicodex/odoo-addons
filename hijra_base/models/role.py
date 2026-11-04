from odoo import api, fields, models


class HijraRole(models.Model):
    """A job in the organisation's procurement and finance flows, and who holds it now.

    Approval chains and signature blocks ask for a role (e.g. Officer-in-Charge) instead of a
    named person, so a change of staff is one edit here.
    """
    _name = 'hijra.role'
    _description = 'HIJRA Role'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="Technical name used by the approval flows.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    user_ids = fields.Many2many('res.users', 'hijra_role_user_rel', 'role_id', 'user_id', string='People')
    description = fields.Text()

    _code_uniq = models.Constraint('UNIQUE(code)', 'The role code must be unique.')

    @api.model
    def _get_users(self, code):
        """Users who hold the role `code`."""
        return self.sudo().search([('code', '=', code)], limit=1).user_ids

    @api.model
    def _user_has_role(self, user, *codes):
        return bool(self.sudo().search_count([('code', 'in', codes), ('user_ids', 'in', user.ids)]))
