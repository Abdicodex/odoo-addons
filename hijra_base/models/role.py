from odoo import Command, api, fields, models


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
    group_ids = fields.Many2many(
        'res.groups', 'hijra_role_group_rel', 'role_id', 'group_id', string='Access Granted',
        help="The people who hold this role get these access groups automatically, and lose them "
             "(unless another of their roles grants them) when the role is taken away.")
    description = fields.Text()

    _code_uniq = models.Constraint('UNIQUE(code)', 'The role code must be unique.')

    # ------------------------------------------------------------------
    # Role -> access groups
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        roles = super().create(vals_list)
        for role in roles:
            role._grant()
        return roles

    def write(self, vals):
        before = {role.id: (role.user_ids, role.group_ids) for role in self}
        result = super().write(vals)
        if {'user_ids', 'group_ids', 'active'} & set(vals):
            for role in self:
                old_users, old_groups = before[role.id]
                role._grant()
                self._revoke(old_users - role.user_ids, old_groups)
                self._revoke(role.user_ids, old_groups - role.group_ids)
        return result

    def _grant(self):
        self.ensure_one()
        if self.active and self.user_ids:
            for group in self.group_ids.sudo():
                group.write({'user_ids': [Command.link(user.id) for user in self.user_ids]})

    @api.model
    def _revoke(self, users, groups):
        """Take `groups` from `users`, except those another of their roles still grants."""
        for user in users.sudo():
            still = self.sudo().search([('user_ids', 'in', user.id)]).group_ids
            for group in (groups - still).sudo():
                group.write({'user_ids': [Command.unlink(user.id)]})

    @api.model
    def _get_users(self, code):
        """Users who hold the role `code`."""
        return self.sudo().search([('code', '=', code)], limit=1).user_ids

    @api.model
    def _user_has_role(self, user, *codes):
        return bool(self.sudo().search_count([('code', 'in', codes), ('user_ids', 'in', user.ids)]))
