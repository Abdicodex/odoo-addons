from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResHouse(models.Model):
    _name = 'res.house'
    _description = 'House'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Supply Number', required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New'),
        help="Auto-generated supply number in format: ZONE_CODE-SUB_ZONE_PREFIX-SEQ")
    partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, tracking=True, index=True,
        help="Customer associated with this house")
    mobile = fields.Char(related='partner_id.mobile', string='Mobile', readonly=True)
    active = fields.Boolean(default=True, help="Uncheck to archive this house")
    state = fields.Selection([
        ('draft', 'New'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ], string='Status', required=True, default='draft', copy=False, tracking=True,
        help="Current status of the house")
    billing_type = fields.Selection([
        ('metered', 'Metered'),
        ('flat', 'Flat Rate'),
    ], string='Billing Type', required=True, default='metered', tracking=True,
        help="Billing type of the house")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Currency', readonly=True)
    customer_type_id = fields.Many2one(
        'customer.type', string='Customer Type', tracking=True,
        help="Type of customer (e.g., Residential, Commercial, Industrial)")
    connection_date = fields.Date(help="Date when the connection was established")

    # location
    village_id = fields.Many2one(
        'res.village', string='Village / Neighbourhood', tracking=True,
        help="Village or neighbourhood where the customer is located")
    zone_id = fields.Many2one(
        'res.zone', string='Zone', compute='_compute_zone', store=True, readonly=False, index=True,
        help="Auto-filled based on selected Village/Neighbourhood")
    sub_zone_id = fields.Many2one(
        'res.sub.zone', string='Sub-Zone', compute='_compute_sub_zone', store=True, readonly=False,
        help="Auto-filled based on selected Village/Neighbourhood")
    district_id = fields.Many2one(
        'res.district', string='District', compute='_compute_district', store=True, readonly=False,
        help="Auto-filled based on selected Zone")
    region_id = fields.Many2one(
        'res.region', string='Region', compute='_compute_region', store=True, readonly=False,
        help="Auto-filled based on selected District")
    neighbourhood = fields.Char(help="Neighbourhood of the house")
    latitude = fields.Float(digits=(10, 7), help="GPS Latitude coordinate of the house location")
    longitude = fields.Float(digits=(10, 7), help="GPS Longitude coordinate of the house location")
    transformer_id = fields.Many2one(
        'res.transformer', string='Transformer', domain="[('zone_id', '=', zone_id)]",
        help="Transformer linked to the selected Zone")

    # people
    owner_name = fields.Char(help="Name of the property owner")
    owner_phone = fields.Char(help="Phone number of the property owner")
    grantor_name = fields.Char(help="Name of the grantor")
    grantor_mobile = fields.Char(help="Mobile number of the grantor")

    # meter
    meter_number = fields.Char(copy=False, help="Unique meter identification number")
    meter_type_id = fields.Many2one('meter.type', string='Meter Type', help="Type of meter installed")
    sub_meter_type_id = fields.Many2one(
        'sub.meter.type', string='Sub Meter Type', domain="[('meter_type_id', '=', meter_type_id)]",
        help="Sub type of meter, filtered by selected Meter Type")
    billed_reading = fields.Float(
        digits=(12, 2), tracking=True, help="Last billed meter reading for this house")
    can_update_meter_reading = fields.Boolean(compute='_compute_can_update_meter_reading')
    meter_reading_history_ids = fields.One2many(
        'meter.reading.history', 'house_id', string='Meter Reading History',
        help="History of all meter reading updates for this house")
    meter_reading_history_count = fields.Integer(
        string='History Count', compute='_compute_history_count',
        help="Total number of meter reading history records")

    # activation / deactivation
    activation_date = fields.Datetime(
        readonly=True, copy=False, help="Date and time when the house was activated")
    activation_reason_id = fields.Many2one(
        'reason.master', string='Activation Reason', readonly=True, copy=False,
        help="Reason for activating the house")
    activation_remark = fields.Text(readonly=True, copy=False, help="Additional remarks for activation")
    deactivation_date = fields.Datetime(
        readonly=True, copy=False, help="Date and time when the house was deactivated")
    deactivation_reason_id = fields.Many2one(
        'reason.master', string='Deactivation Reason', readonly=True, copy=False,
        help="Reason for deactivating the house")
    deactivation_remark = fields.Text(
        readonly=True, copy=False, help="Additional remarks for deactivation")

    _name_company_uniq = models.Constraint(
        'UNIQUE(name, company_id)', 'The supply number must be unique per company.')
    _meter_company_uniq = models.Constraint(
        'UNIQUE(meter_number, company_id)', 'This meter number is already used by another house.')

    @api.depends('village_id')
    def _compute_zone(self):
        for rec in self:
            if rec.village_id:
                rec.zone_id = rec.village_id.zone_id

    @api.depends('village_id')
    def _compute_sub_zone(self):
        for rec in self:
            if rec.village_id:
                rec.sub_zone_id = rec.village_id.sub_zone_id

    @api.depends('zone_id')
    def _compute_district(self):
        for rec in self:
            if rec.zone_id:
                rec.district_id = rec.zone_id.district_id

    @api.depends('district_id')
    def _compute_region(self):
        for rec in self:
            if rec.district_id:
                rec.region_id = rec.district_id.region_id

    @api.depends('state', 'billing_type')
    def _compute_can_update_meter_reading(self):
        for rec in self:
            rec.can_update_meter_reading = rec.state == 'active' and rec.billing_type == 'metered'

    @api.depends('meter_reading_history_ids')
    def _compute_history_count(self):
        for rec in self:
            rec.meter_reading_history_count = len(rec.meter_reading_history_ids)

    @api.onchange('meter_type_id')
    def _onchange_meter_type_id(self):
        if self.sub_meter_type_id and self.sub_meter_type_id.meter_type_id != self.meter_type_id:
            self.sub_meter_type_id = False

    @api.onchange('zone_id')
    def _onchange_zone_id(self):
        if self.transformer_id and self.transformer_id.zone_id != self.zone_id:
            self.transformer_id = False

    # ------------------------------------------------------------------
    # Supply number: ZONE_CODE-SUB_ZONE_PREFIX-SEQ
    # ------------------------------------------------------------------
    @api.model
    def _generate_supply_number(self, vals):
        village = self.env['res.village'].browse(vals.get('village_id'))
        zone = self.env['res.zone'].browse(vals.get('zone_id') or village.zone_id.id)
        if not zone:
            raise UserError(_("Select a village or zone: the supply number is built from the zone code."))
        sub_zone = self.env['res.sub.zone'].browse(
            vals.get('sub_zone_id') or village.sub_zone_id.id)
        company_id = vals.get('company_id') or self.env.company.id
        number = self.env['res.zone']._next_in_sequence(
            f'res.house.supply.{company_id}.{zone.id}.{sub_zone.id or 0}', 4)
        return f"{zone.code or zone.prefix}-{sub_zone.prefix or 'GEN'}-{number}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self._generate_supply_number(vals)
            if not vals.get('meter_number'):
                vals['meter_number'] = False
        return super().create(vals_list)

    def write(self, vals):
        if 'meter_number' in vals and not vals['meter_number']:
            vals['meter_number'] = False
        return super().write(vals)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_activate(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Activate House'),
            'res_model': 'house.activate.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_house_id': self.id},
        }

    def action_deactivate(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Deactivate House'),
            'res_model': 'house.deactivate.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_house_id': self.id},
        }

    def action_update_meter_reading(self):
        self.ensure_one()
        if not self.can_update_meter_reading:
            raise UserError(_("The meter reading can only be updated on an active, metered house."))
        return {
            'type': 'ir.actions.act_window', 'name': _('Update Meter Reading'),
            'res_model': 'meter.reading.update.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_house_id': self.id},
        }

    def action_view_meter_reading_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Meter Reading History'),
            'res_model': 'meter.reading.history', 'view_mode': 'list,form',
            'domain': [('house_id', '=', self.id)],
            'context': {'default_house_id': self.id},
        }

    def action_open_map(self):
        """Open the house location in OpenStreetMap (no map app needed)."""
        self.ensure_one()
        if not (self.latitude or self.longitude):
            raise UserError(_("Set the latitude and longitude first."))
        return {
            'type': 'ir.actions.act_url', 'target': 'new',
            'url': f"https://www.openstreetmap.org/?mlat={self.latitude}&mlon={self.longitude}"
                   f"#map=18/{self.latitude}/{self.longitude}",
        }
