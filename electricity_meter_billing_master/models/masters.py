from odoo import _, api, fields, models


class CustomerType(models.Model):
    _name = 'customer.type'
    _description = 'Customer Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Customer Type', required=True, tracking=True,
        help="Customer type name (e.g., Residential, Commercial, Industrial)")
    description = fields.Text(help="Description of this customer type")
    active = fields.Boolean(default=True, help="Uncheck to archive this customer type")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)
    house_count = fields.Integer(
        compute='_compute_counts', help="Number of houses with this customer type")
    partner_count = fields.Integer(
        string='Customer Count', compute='_compute_counts',
        help="Number of customers with this type")

    _name_company_uniq = models.Constraint(
        'UNIQUE(name, company_id)', 'This customer type already exists for the company.')

    def _compute_counts(self):
        for rec in self:
            rec.house_count = self.env['res.house'].search_count([('customer_type_id', '=', rec.id)])
            rec.partner_count = self.env['res.partner'].search_count(
                [('customer_type_ids', 'in', rec.id)])

    def action_view_houses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Houses'), 'res_model': 'res.house',
            'view_mode': 'list,form', 'domain': [('customer_type_id', '=', self.id)],
            'context': {'default_customer_type_id': self.id},
        }

    def action_view_partners(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Customers'), 'res_model': 'res.partner',
            'view_mode': 'list,form', 'domain': [('customer_type_ids', 'in', self.id)],
        }


class ReasonMaster(models.Model):
    _name = 'reason.master'
    _description = 'Reason Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reason_type, name'

    name = fields.Char(
        string='Reason', required=True, tracking=True,
        help="Reason description for activation, deactivation or a meter reading update")
    reason_type = fields.Selection([
        ('activation', 'Activation'),
        ('deactivation', 'Deactivation'),
        ('meter_update', 'Meter Reading Update'),
    ], string='Reason Type', required=True, default='activation', tracking=True,
        help="Where this reason can be chosen")
    active = fields.Boolean(default=True, help="Set to false to archive this record")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)

    _name_type_company_uniq = models.Constraint(
        'UNIQUE(name, reason_type, company_id)', 'This reason already exists for the same type.')


class MeterType(models.Model):
    _name = 'meter.type'
    _description = 'Meter Type'
    _order = 'name'

    name = fields.Char(
        string='Meter Type', required=True,
        help="Name of the meter type (e.g., Digital, Analog, Smart Meter)")
    description = fields.Text(help="Description of the meter type")
    active = fields.Boolean(default=True, help="If unchecked, this meter type will be archived")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    sub_meter_type_ids = fields.One2many(
        'sub.meter.type', 'meter_type_id', string='Sub Meter Types',
        help="Sub meter types under this meter type")
    sub_meter_type_count = fields.Integer(
        compute='_compute_sub_meter_type_count', help="Number of sub meter types under this meter type")

    @api.depends('sub_meter_type_ids')
    def _compute_sub_meter_type_count(self):
        for rec in self:
            rec.sub_meter_type_count = len(rec.sub_meter_type_ids)


class SubMeterType(models.Model):
    _name = 'sub.meter.type'
    _description = 'Sub Meter Type'
    _order = 'meter_type_id, name'

    name = fields.Char(string='Sub Meter Type', required=True, help="Name of the sub meter type")
    meter_type_id = fields.Many2one(
        'meter.type', string='Meter Type', required=True, ondelete='cascade',
        help="Parent meter type this sub meter type belongs to")
    description = fields.Text(help="Description of the sub meter type")
    active = fields.Boolean(default=True, help="If unchecked, this sub meter type will be archived")
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)
