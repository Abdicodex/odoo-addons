from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    mobile = fields.Char(help="Mobile phone number")
    is_meter_billing = fields.Boolean(
        string='Is Meter Billing Customer',
        help="Check if this customer is a meter billing customer")
    customer_unique_id = fields.Char(
        string='Unique Customer ID', copy=False, readonly=True, index=True,
        help="Auto-generated unique customer identifier")
    customer_type_ids = fields.Many2many(
        'customer.type', 'res_partner_customer_type_rel', 'partner_id', 'customer_type_id',
        string='Customer Types', compute='_compute_customer_type_ids', store=True,
        help="Types of customer automatically populated from linked houses "
             "(e.g., Residential, Commercial, Industrial)")
    house_ids = fields.One2many(
        'res.house', 'partner_id', string='Houses', help="Houses associated with this customer")
    house_count = fields.Integer(compute='_compute_house_count')
    document_ids = fields.One2many(
        'partner.document', 'partner_id', string='Supporting Documents',
        help="Supporting documents for this customer")

    _customer_unique_id_uniq = models.Constraint(
        'UNIQUE(customer_unique_id)', 'The unique customer ID must be unique.')

    @api.depends('house_ids.customer_type_id')
    def _compute_customer_type_ids(self):
        for partner in self:
            partner.customer_type_ids = partner.house_ids.customer_type_id

    @api.depends('house_ids')
    def _compute_house_count(self):
        for partner in self:
            partner.house_count = len(partner.house_ids)

    def _assign_customer_unique_id(self):
        for partner in self.filtered(lambda p: p.is_meter_billing and not p.customer_unique_id):
            partner.customer_unique_id = self.env['ir.sequence'].next_by_code(
                'meter.billing.customer') or False

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._assign_customer_unique_id()
        return partners

    def write(self, vals):
        result = super().write(vals)
        if vals.get('is_meter_billing'):
            self._assign_customer_unique_id()
        return result

    def action_view_houses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Houses'), 'res_model': 'res.house',
            'view_mode': 'list,form', 'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }


class PartnerDocument(models.Model):
    _name = 'partner.document'
    _description = 'Customer Supporting Document'
    _order = 'id desc'

    partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, ondelete='cascade',
        help="Customer associated with this document")
    document_name = fields.Char(
        required=True, help="Name or description of the document")
    attachment = fields.Binary(
        required=True, attachment=True, help="Upload document file (PDF, Excel, Images, etc.)")
    attachment_name = fields.Char(string='Attachment Filename', help="Name of the uploaded file")


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_collector = fields.Boolean(help="Check if this employee is a collector for bill collection")
    is_technician = fields.Boolean(
        help="Check if this employee is a technician for meter operations")
