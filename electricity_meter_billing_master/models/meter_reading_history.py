from odoo import api, fields, models


class MeterReadingHistory(models.Model):
    _name = 'meter.reading.history'
    _description = 'Meter Reading History'
    _order = 'date desc, id desc'

    house_id = fields.Many2one(
        'res.house', string='Supply Number', required=True, ondelete='cascade', index=True,
        help="House for which meter reading was updated")
    house_name = fields.Char(
        string='Supply Number', related='house_id.name', store=True, readonly=True,
        help="Auto-generated supply number in format: ZONE_CODE-SUB_ZONE_PREFIX-SEQ")
    partner_id = fields.Many2one(
        'res.partner', string='Customer', related='house_id.partner_id', store=True, readonly=True,
        help="Customer associated with this house")
    customer_type_id = fields.Many2one(
        'customer.type', string='Customer Type', related='house_id.customer_type_id', store=True,
        readonly=True, help="Type of customer (e.g., Residential, Commercial, Industrial)")
    village_id = fields.Many2one(
        'res.village', string='Village', related='house_id.village_id', store=True, readonly=True,
        help="Village or neighbourhood where the customer is located")
    sub_zone_id = fields.Many2one(
        'res.sub.zone', string='Sub-Zone', related='house_id.sub_zone_id', store=True, readonly=True,
        help="Auto-filled based on selected Village/Neighbourhood")
    zone_id = fields.Many2one(
        'res.zone', string='Zone', related='house_id.zone_id', store=True, readonly=True,
        help="Auto-filled based on selected Village/Neighbourhood")
    district_id = fields.Many2one(
        'res.district', string='District', related='house_id.district_id', store=True, readonly=True,
        help="Auto-filled based on selected Zone")
    region_id = fields.Many2one(
        'res.region', string='Region', related='house_id.region_id', store=True, readonly=True,
        help="Auto-filled based on selected District")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)
    date = fields.Datetime(
        string='Date & Time', required=True, default=fields.Datetime.now,
        help="Date and time when meter reading was updated")
    meter_number = fields.Char(string='Old Meter No.', help="Unique meter identification number")
    new_meter_number = fields.Char(string='New Meter No.', help="Unique meter identification number")
    previous_reading = fields.Float(
        digits=(12, 2), required=True, help="Previous meter reading value")
    new_reading = fields.Float(digits=(12, 2), required=True, help="New meter reading value")
    difference = fields.Float(
        digits=(12, 2), compute='_compute_difference', store=True, readonly=True,
        help="Difference between new and previous reading")
    reason_id = fields.Many2one(
        'reason.master', string='Reason', domain="[('reason_type', '=', 'meter_update')]",
        help="Reason for updating the meter reading")
    remarks = fields.Text(help="Additional remarks or notes")
    user_id = fields.Many2one(
        'res.users', string='Updated By', required=True, default=lambda self: self.env.user,
        help="User who updated the meter reading")

    @api.depends('new_reading', 'previous_reading')
    def _compute_difference(self):
        for rec in self:
            rec.difference = rec.new_reading - rec.previous_reading
