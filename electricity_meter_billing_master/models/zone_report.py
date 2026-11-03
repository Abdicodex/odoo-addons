from odoo import api, fields, models


class ResZoneReport(models.Model):
    """One row per zone with its financial position (kept in step with the zones).

    The amounts are worked out from the posted customer invoices and received
    payments of the customers who have a house in the zone, so they follow the
    accounting entries; nothing is typed in by hand.
    """
    _name = 'res.zone.report'
    _description = 'Zone Report'
    _order = 'name'

    zone_id = fields.Many2one(
        'res.zone', string='Zone', required=True, ondelete='cascade', index=True,
        help="Zone reference")
    name = fields.Char(
        string='Zone Name', related='zone_id.name', store=True, readonly=True,
        help="Zone name identifier")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Currency', readonly=True)
    active = fields.Boolean(default=True, help="Uncheck to archive this zone report")
    opening_amount = fields.Monetary(
        string='Opening Balance', compute='_compute_amounts', currency_field='currency_id',
        help="Opening balance for current period")
    current_month_billed = fields.Monetary(
        compute='_compute_amounts', currency_field='currency_id',
        help="Total amount billed in current month")
    current_month_paid = fields.Monetary(
        compute='_compute_amounts', currency_field='currency_id',
        help="Total amount paid in current month")
    total_due_amount = fields.Monetary(
        string='Total Due Amount', compute='_compute_amounts', currency_field='currency_id',
        help="Total outstanding amount for this zone")

    _zone_uniq = models.Constraint('UNIQUE(zone_id)', 'A zone can only have one report line.')

    @api.depends_context('uid')
    def _compute_amounts(self):
        # sudo: the zone figures are summaries; users need not have accounting rights to see them
        Move = self.env['account.move'].sudo()
        Payment = self.env['account.payment'].sudo()
        start = fields.Date.context_today(self).replace(day=1)
        for rec in self:
            partners = rec.zone_id.house_ids.partner_id
            billed = paid = due = 0.0
            if partners:
                invoices = Move.search([
                    ('partner_id', 'in', partners.ids),
                    ('move_type', 'in', ('out_invoice', 'out_refund')),
                    ('state', '=', 'posted'),
                    ('company_id', '=', rec.company_id.id),
                ])
                due = sum(invoices.mapped('amount_residual_signed'))
                billed = sum(invoices.filtered(
                    lambda m: m.invoice_date and m.invoice_date >= start).mapped('amount_total_signed'))
                payments = Payment.search([
                    ('partner_id', 'in', partners.ids),
                    ('partner_type', '=', 'customer'),
                    ('payment_type', '=', 'inbound'),
                    ('move_id.state', '=', 'posted'),
                    ('date', '>=', start),
                    ('company_id', '=', rec.company_id.id),
                ])
                paid = sum(payments.mapped('amount_company_currency_signed'))
            rec.current_month_billed = billed
            rec.current_month_paid = paid
            rec.total_due_amount = due
            # opening + billed - paid = due
            rec.opening_amount = due - billed + paid

    @api.model
    def _ensure_for_zones(self, zones):
        """Create the missing report lines for these zones."""
        existing = self.sudo().with_context(active_test=False).search(
            [('zone_id', 'in', zones.ids)]).zone_id
        for zone in zones - existing:
            self.sudo().create({'zone_id': zone.id, 'company_id': (zone.company_id or self.env.company).id})
