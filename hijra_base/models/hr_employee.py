from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    hijra_signature = fields.Image(
        string='Signature', max_width=800, max_height=320,
        help="Picture of the employee's signature, printed on documents they sign "
             "(requisitions, and later timesheets, payslips and more). "
             "A PNG with a transparent background looks best.")
