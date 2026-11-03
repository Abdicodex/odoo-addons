from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    procurement_email = fields.Char(
        string='Procurement Email',
        help="Where vendors send their quotations. Printed on the Request for Quotation. "
             "Falls back to the company email when empty.")
