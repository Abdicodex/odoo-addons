from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ResRegion(models.Model):
    _name = 'res.region'
    _description = 'Region'
    _order = 'name'

    name = fields.Char(string='Region Name', required=True, help="Region name identifier")
    active = fields.Boolean(default=True, help="Uncheck to archive this region")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    district_ids = fields.One2many(
        'res.district', 'region_id', string='Districts', help="Districts under this region")
    district_count = fields.Integer(compute='_compute_counts')
    zone_count = fields.Integer(compute='_compute_counts')

    _name_company_uniq = models.Constraint(
        'UNIQUE(name, company_id)', 'This region already exists for the company.')

    @api.depends('district_ids.zone_ids')
    def _compute_counts(self):
        for rec in self:
            rec.district_count = len(rec.district_ids)
            rec.zone_count = sum(len(district.zone_ids) for district in rec.district_ids)


class ResDistrict(models.Model):
    _name = 'res.district'
    _description = 'District'
    _order = 'region_id, name'

    name = fields.Char(string='District Name', required=True, help="District name identifier")
    region_id = fields.Many2one(
        'res.region', string='Region', required=True, ondelete='restrict', help="Parent region")
    active = fields.Boolean(default=True, help="Uncheck to archive this district")
    company_id = fields.Many2one(
        'res.company', string='Company', related='region_id.company_id', store=True, readonly=True)
    zone_ids = fields.One2many('res.zone', 'district_id', string='Zones', help="Zones under this district")
    zone_count = fields.Integer(compute='_compute_counts')
    sub_zone_count = fields.Integer(compute='_compute_counts')

    _name_region_uniq = models.Constraint(
        'UNIQUE(name, region_id)', 'This district already exists in the region.')

    @api.depends('zone_ids.sub_zone_ids')
    def _compute_counts(self):
        for rec in self:
            rec.zone_count = len(rec.zone_ids)
            rec.sub_zone_count = sum(len(zone.sub_zone_ids) for zone in rec.zone_ids)


class ResZone(models.Model):
    _name = 'res.zone'
    _description = 'Zone'
    _order = 'code, name'

    name = fields.Char(string='Zone Name', required=True, help="Zone name identifier")
    prefix = fields.Char(
        string='Zone Prefix', required=True,
        help="Prefix for zone code (e.g., 'ZONE', 'ZN'). A 3-digit sequence will be appended to this "
             "prefix. Changing it later does not change codes already issued.")
    code = fields.Char(string='Zone Code', readonly=True, copy=False, index=True)
    district_id = fields.Many2one(
        'res.district', string='District', required=True, ondelete='restrict', help="Parent district")
    region_id = fields.Many2one(
        'res.region', string='Region', related='district_id.region_id', store=True, readonly=True,
        help="Parent region (computed from district)")
    company_id = fields.Many2one(
        'res.company', string='Company', related='district_id.company_id', store=True, readonly=True)
    active = fields.Boolean(default=True, help="Uncheck to archive this zone")
    sub_zone_ids = fields.One2many(
        'res.sub.zone', 'zone_id', string='Sub-Zones', help="Sub-zones under this zone")
    village_ids = fields.One2many(
        'res.village', 'zone_id', string='Villages/Neighbourhoods',
        help="Villages/Neighbourhoods under this zone")
    house_ids = fields.One2many('res.house', 'zone_id', string='Houses')
    sub_zone_count = fields.Integer(compute='_compute_counts')
    village_count = fields.Integer(compute='_compute_counts')
    house_count = fields.Integer(compute='_compute_counts')

    _code_company_uniq = models.Constraint(
        'UNIQUE(code, company_id)', 'The zone code must be unique per company.')

    @api.depends('sub_zone_ids', 'village_ids', 'house_ids')
    def _compute_counts(self):
        for rec in self:
            rec.sub_zone_count = len(rec.sub_zone_ids)
            rec.village_count = len(rec.village_ids)
            rec.house_count = len(rec.house_ids)

    @api.model
    def _next_in_sequence(self, code, padding, prefix=''):
        """Next number of a counter kept in an ir.sequence, created the first time it is used."""
        sequence = self.env['ir.sequence'].sudo().search([('code', '=', code)], limit=1)
        if not sequence:
            sequence = self.env['ir.sequence'].sudo().create({
                'name': code, 'code': code, 'padding': padding, 'prefix': prefix,
                'number_increment': 1, 'company_id': False,
            })
        return sequence.next_by_id()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            prefix = (vals.get('prefix') or '').strip().upper()
            vals['prefix'] = prefix
            district = self.env['res.district'].browse(vals.get('district_id'))
            company = district.company_id or self.env.company
            if prefix and not vals.get('code'):
                vals['code'] = self._next_in_sequence(
                    f'res.zone.code.{company.id}.{prefix}', 3, prefix)
        zones = super().create(vals_list)
        zones.env['res.zone.report']._ensure_for_zones(zones)
        return zones


class ResSubZone(models.Model):
    _name = 'res.sub.zone'
    _description = 'Sub-Zone'
    _order = 'zone_id, name'

    name = fields.Char(string='Sub-Zone Name', required=True, help="Sub-zone name identifier")
    prefix = fields.Char(
        string='Sub-Zone Prefix', required=True,
        help="Prefix for sub-zone code (e.g., 'SUB-ZONE', 'SZ'). Used in the supply number of houses.")
    zone_id = fields.Many2one(
        'res.zone', string='Zone', required=True, ondelete='restrict', help="Parent zone")
    district_id = fields.Many2one(
        'res.district', string='District', related='zone_id.district_id', store=True, readonly=True,
        help="Parent district (computed from zone)")
    region_id = fields.Many2one(
        'res.region', string='Region', related='zone_id.region_id', store=True, readonly=True,
        help="Parent region (computed from zone)")
    company_id = fields.Many2one(
        'res.company', string='Company', related='zone_id.company_id', store=True, readonly=True)
    active = fields.Boolean(default=True, help="Uncheck to archive this sub-zone")
    village_ids = fields.One2many(
        'res.village', 'sub_zone_id', string='Villages/Neighbourhoods',
        help="Villages/Neighbourhoods under this sub-zone")
    village_count = fields.Integer(compute='_compute_village_count')
    assigned_collector_ids = fields.Many2many(
        'hr.employee', 'res_sub_zone_collector_rel', 'sub_zone_id', 'employee_id',
        string='Assigned Collectors', domain=[('is_collector', '=', True)],
        help="Collectors assigned to this sub-zone. Will be auto-assigned to all villages in this sub-zone.")
    assigned_technician_ids = fields.Many2many(
        'hr.employee', 'res_sub_zone_technician_rel', 'sub_zone_id', 'employee_id',
        string='Assigned Technicians', domain=[('is_technician', '=', True)],
        help="Technicians assigned to this sub-zone. Will be auto-assigned to all villages in this sub-zone.")

    _name_zone_uniq = models.Constraint(
        'UNIQUE(name, zone_id)', 'This sub-zone already exists in the zone.')

    @api.depends('village_ids')
    def _compute_village_count(self):
        for rec in self:
            rec.village_count = len(rec.village_ids)


class ResVillage(models.Model):
    _name = 'res.village'
    _description = 'Village / Neighbourhood'
    _order = 'zone_id, name'

    name = fields.Char(
        string='Village/Neighbourhood Name', required=True,
        help="Village or neighbourhood name identifier")
    zone_id = fields.Many2one(
        'res.zone', string='Zone', required=True, ondelete='restrict', help="Parent zone")
    sub_zone_id = fields.Many2one(
        'res.sub.zone', string='Sub-Zone', domain="[('zone_id', '=', zone_id)]",
        ondelete='set null', help="Parent sub-zone (optional)")
    district_id = fields.Many2one(
        'res.district', string='District', related='zone_id.district_id', store=True, readonly=True,
        help="Parent district (computed from zone)")
    region_id = fields.Many2one(
        'res.region', string='Region', related='zone_id.region_id', store=True, readonly=True,
        help="Parent region (computed from zone)")
    company_id = fields.Many2one(
        'res.company', string='Company', related='zone_id.company_id', store=True, readonly=True)
    active = fields.Boolean(default=True, help="Uncheck to archive this village/neighbourhood")
    assigned_collector_ids = fields.Many2many(
        'hr.employee', 'res_village_collector_rel', 'village_id', 'employee_id',
        string='Assigned Collectors', compute='_compute_assignees', store=True,
        help="Collectors auto-assigned from sub-zone.")
    assigned_technician_ids = fields.Many2many(
        'hr.employee', 'res_village_technician_rel', 'village_id', 'employee_id',
        string='Assigned Technicians', compute='_compute_assignees', store=True,
        help="Technicians auto-assigned from sub-zone.")

    _name_zone_uniq = models.Constraint(
        'UNIQUE(name, zone_id)', 'This village/neighbourhood already exists in the zone.')

    @api.depends('sub_zone_id.assigned_collector_ids', 'sub_zone_id.assigned_technician_ids')
    def _compute_assignees(self):
        for rec in self:
            rec.assigned_collector_ids = rec.sub_zone_id.assigned_collector_ids
            rec.assigned_technician_ids = rec.sub_zone_id.assigned_technician_ids

    @api.onchange('sub_zone_id')
    def _onchange_sub_zone_id(self):
        if self.sub_zone_id:
            self.zone_id = self.sub_zone_id.zone_id

    @api.constrains('zone_id', 'sub_zone_id')
    def _check_sub_zone_zone(self):
        for rec in self:
            if rec.sub_zone_id and rec.sub_zone_id.zone_id != rec.zone_id:
                raise ValidationError(_("The sub-zone must belong to the village's zone."))


class ResTransformer(models.Model):
    _name = 'res.transformer'
    _description = 'Transformer'
    _order = 'name'

    name = fields.Char(string='Transformer Name', required=True, help="Transformer name identifier")
    capacity = fields.Float(string='Capacity (KVA)', help="Transformer capacity in KVA")
    location = fields.Char(help="Physical location of the transformer")
    latitude = fields.Float(digits=(10, 7), help="Latitude coordinate for transformer location")
    longitude = fields.Float(digits=(10, 7), help="Longitude coordinate for transformer location")
    village_id = fields.Many2one(
        'res.village', string='Village / Neighbourhood',
        help="Village or neighbourhood where the customer is located")
    zone_id = fields.Many2one(
        'res.zone', string='Zone', compute='_compute_zone', store=True, readonly=False,
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
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True, help="Uncheck to archive this transformer")
    house_ids = fields.One2many('res.house', 'transformer_id', string='Houses')
    house_count = fields.Integer(
        compute='_compute_house_count', help="Number of houses connected to this transformer")

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

    @api.depends('house_ids')
    def _compute_house_count(self):
        for rec in self:
            rec.house_count = len(rec.house_ids)

    def action_view_houses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Houses'), 'res_model': 'res.house',
            'view_mode': 'list,form', 'domain': [('transformer_id', '=', self.id)],
        }
