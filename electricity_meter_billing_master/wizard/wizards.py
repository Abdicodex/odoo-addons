from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HouseActivateWizard(models.TransientModel):
    _name = 'house.activate.wizard'
    _description = 'Activate House'

    house_id = fields.Many2one(
        'res.house', string='House', required=True, readonly=True, help="House to be activated")
    activation_reason_id = fields.Many2one(
        'reason.master', string='Activation Reason', required=True,
        domain="[('reason_type', '=', 'activation')]", help="Reason for activating the house")
    activation_remark = fields.Text(help="Optional remarks for activation")

    def action_confirm(self):
        self.ensure_one()
        house = self.house_id
        if house.state == 'active':
            raise UserError(_("This house is already active."))
        house.write({
            'state': 'active',
            'activation_date': fields.Datetime.now(),
            'activation_reason_id': self.activation_reason_id.id,
            'activation_remark': self.activation_remark,
        })
        house.message_post(body=_(
            "House activated. Reason: %s", self.activation_reason_id.name))
        return {'type': 'ir.actions.act_window_close'}


class HouseDeactivateWizard(models.TransientModel):
    _name = 'house.deactivate.wizard'
    _description = 'Deactivate House'

    house_id = fields.Many2one(
        'res.house', string='House', required=True, readonly=True, help="House to be deactivated")
    deactivation_reason_id = fields.Many2one(
        'reason.master', string='Deactivation Reason', required=True,
        domain="[('reason_type', '=', 'deactivation')]", help="Reason for deactivating the house")
    deactivation_remark = fields.Text(help="Optional remarks for deactivation")

    def action_confirm(self):
        self.ensure_one()
        house = self.house_id
        if house.state != 'active':
            raise UserError(_("Only an active house can be deactivated."))
        house.write({
            'state': 'inactive',
            'deactivation_date': fields.Datetime.now(),
            'deactivation_reason_id': self.deactivation_reason_id.id,
            'deactivation_remark': self.deactivation_remark,
        })
        house.message_post(body=_(
            "House deactivated. Reason: %s", self.deactivation_reason_id.name))
        return {'type': 'ir.actions.act_window_close'}


class MeterReadingUpdateWizard(models.TransientModel):
    _name = 'meter.reading.update.wizard'
    _description = 'Update Meter Reading'

    house_id = fields.Many2one(
        'res.house', string='House', required=True, readonly=True,
        help="House for which meter reading will be updated")
    current_reading = fields.Float(
        digits=(12, 2), readonly=True, help="Current meter reading")
    meter_number = fields.Char(help="Unique meter identification number")
    new_meter_number = fields.Char(
        help="Fill in only when the meter is replaced; the reading may then start again from a lower value.")
    new_reading = fields.Float(
        digits=(12, 2), required=True, help="New meter reading to be updated")
    reason_id = fields.Many2one(
        'reason.master', string='Reason', required=True,
        domain="[('reason_type', '=', 'meter_update')]",
        help="Reason for updating the meter reading")
    remarks = fields.Text(help="Optional remarks for this meter reading update")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        house = self.env['res.house'].browse(
            res.get('house_id') or self.env.context.get('default_house_id'))
        if house:
            res.setdefault('current_reading', house.billed_reading)
            res.setdefault('meter_number', house.meter_number)
        return res

    def action_confirm(self):
        self.ensure_one()
        house = self.house_id
        if not house.can_update_meter_reading:
            raise UserError(_("The meter reading can only be updated on an active, metered house."))
        replaced = bool(self.new_meter_number and self.new_meter_number != house.meter_number)
        if not replaced and self.new_reading < house.billed_reading:
            raise UserError(_(
                "The new reading (%(new)s) cannot be lower than the current reading (%(old)s) "
                "unless the meter is replaced. Enter the new meter number if it was replaced.",
                new=self.new_reading, old=house.billed_reading))
        self.env['meter.reading.history'].create({
            'house_id': house.id,
            'company_id': house.company_id.id,
            'previous_reading': house.billed_reading,
            'new_reading': self.new_reading,
            'meter_number': house.meter_number,
            'new_meter_number': self.new_meter_number if replaced else False,
            'reason_id': self.reason_id.id,
            'remarks': self.remarks,
        })
        values = {'billed_reading': self.new_reading}
        if replaced:
            values['meter_number'] = self.new_meter_number
        house.write(values)
        return {'type': 'ir.actions.act_window_close'}


class MeterReadingHistoryReportWizard(models.TransientModel):
    _name = 'meter.reading.history.report.wizard'
    _description = 'Meter Reading History Report'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(
        string='From Date', required=True, default=lambda self: fields.Date.context_today(self).replace(day=1),
        help="Start date for the report")
    date_to = fields.Date(
        string='To Date', required=True, default=fields.Date.context_today,
        help="End date for the report")

    def _get_history(self):
        self.ensure_one()
        return self.env['meter.reading.history'].search([
            ('company_id', '=', self.company_id.id),
            ('date', '>=', fields.Datetime.to_datetime(self.date_from)),
            ('date', '<', fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)),
        ], order='date, id')

    def action_print(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("The start date must be before the end date."))
        report = self.env.ref('electricity_meter_billing_master.action_report_meter_reading_history')
        return report.report_action(self, config=False)
