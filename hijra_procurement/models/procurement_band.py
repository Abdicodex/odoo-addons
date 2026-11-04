from odoo import api, fields, models


class ProcurementBand(models.Model):
    """What a purchase of a given value needs (from the HIJRA procurement manual, section 2.2).

    Editable by the procurement manager: the manual does not say exactly when the committee is
    needed, so the limits are settings, not code.
    """
    _name = 'procurement.band'
    _description = 'Procurement Band'
    _order = 'min_amount'

    name = fields.Char(required=True)
    min_amount = fields.Float(
        string='From Amount', required=True,
        help="The band applies from this value up to the next band's start.")
    method = fields.Char(string='Request Document', help="RFQ, ITB or RFP.")
    min_invitations = fields.Integer(
        string='Vendors to Invite', default=1,
        help="Minimum number of vendors that get the request (the manual's table).")
    min_quotes = fields.Integer(
        string='Quotes Needed', default=1,
        help="Minimum number of quotations received; fewer needs a written justification.")
    committee_required = fields.Boolean(string='Committee Review')
    observer_required = fields.Boolean(
        string='Observer Invited',
        help="A representative of the partner organisation (Concern Worldwide) is invited to the session.")
    award_statement_required = fields.Boolean(
        string='Statement of Award',
        help="The manual requires a Statement of Award cleared by the head of office above this value.")
    active = fields.Boolean(default=True)

    @api.model
    def _band_for(self, amount):
        return self.search([('min_amount', '<=', amount or 0.0)], order='min_amount desc', limit=1)
