from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_amount

OPEN_ORDER_STATES = ('draft', 'sent', 'to approve')


class PurchaseRequestRfq(models.Model):
    """One RFQ reference for a requisition, sent to several vendors.

    Each vendor gets its own purchase order (Odoo allows only one vendor per
    order); this record groups them under a single reference so the buyer can
    compare the quotations and award the one to buy from.
    """
    _name = 'purchase.request.rfq'
    _description = 'Requisition RFQ'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(
        string='RFQ Reference', required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New'))
    request_id = fields.Many2one(
        'purchase.request', string='Requisition', required=True, index=True,
        ondelete='restrict', tracking=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('awarded', 'Awarded'),
        ('cancelled', 'Cancelled'),
    ], default='open', required=True, copy=False, tracking=True)
    order_ids = fields.One2many('purchase.order', 'rfq_group_id', string='Quotations')
    vendor_ids = fields.Many2many('res.partner', string='Vendors', compute='_compute_vendor_ids')
    order_count = fields.Integer(compute='_compute_vendor_ids')
    subject = fields.Char(string='Subject', compute='_compute_subject')
    deadline = fields.Datetime(
        string='Submission Deadline', compute='_compute_deadline', store=True)
    awarded_order_id = fields.Many2one(
        'purchase.order', string='Awarded Order', copy=False, readonly=True)
    awarded_partner_id = fields.Many2one(
        related='awarded_order_id.partner_id', string='Awarded Vendor')
    comparison = fields.Html(compute='_compute_comparison', sanitize=False)

    @api.depends('order_ids.rfq_subject')
    def _compute_subject(self):
        for rec in self:
            rec.subject = rec.order_ids.sorted('id')[:1].rfq_subject

    @api.depends('order_ids.date_order')
    def _compute_deadline(self):
        for rec in self:
            dates = [date for date in rec.order_ids.mapped('date_order') if date]
            rec.deadline = min(dates) if dates else False

    @api.depends('order_ids.partner_id')
    def _compute_vendor_ids(self):
        for rec in self:
            rec.vendor_ids = rec.order_ids.partner_id
            rec.order_count = len(rec.order_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.request.rfq') or _('New')
        return super().create(vals_list)

    @api.depends(
        'order_ids.partner_id', 'order_ids.state', 'order_ids.amount_untaxed',
        'order_ids.order_line.price_unit', 'order_ids.order_line.product_qty',
        'request_id.line_ids')
    def _compute_comparison(self):
        for rec in self:
            rec.comparison = rec._build_comparison()

    def _build_comparison(self):
        """HTML table: one row per requisition item, one column per vendor."""
        self.ensure_one()
        orders = self.order_ids.sorted('id')
        if not orders:
            return False
        env = self.env
        live = {o.id: o.amount_untaxed for o in orders if o.state != 'cancel' and o.amount_untaxed}
        lowest = min(live.values()) if live else None

        def money(amount, order):
            return escape(format_amount(env, amount, order.currency_id))

        head = Markup('').join(
            Markup('<th class="text-end">%s<br/><small class="text-muted">%s</small></th>')
            % (order.partner_id.display_name, order.name) for order in orders)
        rows = []
        for item in self.request_id.line_ids.sorted('sequence'):
            cells = []
            for order in orders:
                line = order.order_line.filtered(lambda l: l.purchase_request_line_id == item)[:1]
                if line:
                    cells.append(
                        Markup('<td class="text-end">%s<br/><small class="text-muted">%s</small></td>')
                        % (money(line.price_unit, order), money(line.price_subtotal, order)))
                else:
                    cells.append(Markup('<td></td>'))
            rows.append(
                Markup('<tr><td>%s</td>%s</tr>') % (item.description or '', Markup('').join(cells)))
        totals = []
        for order in orders:
            cheapest = lowest is not None and live.get(order.id) == lowest
            totals.append(
                Markup('<td class="text-end fw-bold%s">%s</td>')
                % (' text-success' if cheapest else '', money(order.amount_untaxed, order)))
        footer = Markup('<tr><td class="fw-bold">%s</td>%s</tr>') % (
            _("Total (untaxed)"), Markup('').join(totals))
        return (
            Markup('<table class="table table-sm table-bordered"><thead><tr><th>%s</th>%s</tr></thead>'
                   '<tbody>%s%s</tbody></table>'
                   '<p class="text-muted"><small>%s</small></p>')
            % (_("Item"), head, Markup('').join(rows), footer,
               _("Unit price and amount per item. The lowest total is shown in green.")))

    def action_print(self):
        """Print the RFQ document for every vendor."""
        self.ensure_one()
        report = self.env.ref('purchase.report_purchase_quotation')
        return report.with_context(discard_logo_check=True).report_action(self.order_ids)

    def action_open(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }

    def action_cancel(self):
        for rec in self:
            if rec.state != 'open':
                raise UserError(_("Only an open RFQ can be cancelled."))
            rec.order_ids.filtered(lambda o: o.state in OPEN_ORDER_STATES).button_cancel()
            rec.state = 'cancelled'
            rec.message_post(body=_("RFQ cancelled."))
