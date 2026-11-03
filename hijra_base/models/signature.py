from odoo import api, fields, models


class HijraSignature(models.Model):
    _name = 'hijra.signature'
    _description = 'HIJRA User Signature'
    _rec_name = 'user_id'

    user_id = fields.Many2one(
        'res.users', string='User', required=True, ondelete='cascade', index=True,
        default=lambda self: self.env.user)
    image = fields.Image(
        string='Signature', max_width=800, max_height=320,
        help="Picture of your signature. A PNG with a transparent background looks best.")

    _user_uniq = models.Constraint('UNIQUE(user_id)', 'Each user can have only one signature.')

    @api.model
    def action_open_my_signature(self):
        """Open the current user's signature, creating it the first time."""
        signature = self.search([('user_id', '=', self.env.uid)], limit=1)
        if not signature:
            signature = self.create({'user_id': self.env.uid})
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('My Signature'),
            'res_model': self._name,
            'res_id': signature.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    @api.model
    def get_signatures(self, users):
        """Signature images (base64) by user id, readable by any user for printing."""
        records = self.sudo().search([('user_id', 'in', users.ids)])
        return {record.user_id.id: record.image for record in records if record.image}
