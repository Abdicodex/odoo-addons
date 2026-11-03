from odoo import fields, models
from odoo.addons.hr.models.res_users import related_employee_field


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Lets employees manage their own signature from their Preferences, like
    # the other employee fields Odoo's HR app exposes on the user.
    hijra_signature = fields.Image(**related_employee_field('hijra_signature'), user_writeable=True)

    def _get_signature_images(self):
        """Signature images (base64) by user id, for printing documents.

        Read as sudo: whoever prints a document needs the signatures of the people
        who signed it, whatever their own access rights are.
        """
        signatures = {}
        for user in self.sudo():
            image = user.employee_id.hijra_signature
            if image:
                signatures[user.id] = image
        return signatures
