from datetime import timedelta

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
    subject = fields.Char(
        string='Subject', tracking=True,
        help="What the RFQ is for, printed under 'Subject' on the document.")
    deadline = fields.Datetime(
        string='Submission Deadline', required=True, tracking=True,
        default=lambda self: fields.Datetime.now() + timedelta(days=7),
        help="Vendors must send their quotation on or before this date.")
    validity_days = fields.Integer(
        string='Quotation Validity (days)', default=90,
        help="Printed in the compliance checklist: how long a quotation must stay valid.")
    submission_email = fields.Char(
        string='Submit Quotations To',
        default=lambda self: self.env.company.procurement_email or self.env.company.email)
    quotation_details = fields.Text(
        string='Quotation Details to Include',
        help="One item per line; printed as bullet points under 'Additional Information'.")
    awarded_order_id = fields.Many2one(
        'purchase.order', string='Awarded Order', copy=False, readonly=True)
    awarded_partner_id = fields.Many2one(
        related='awarded_order_id.partner_id', string='Awarded Vendor')
    comparison = fields.Html(compute='_compute_comparison', sanitize=False)

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

    def write(self, vals):
        result = super().write(vals)
        if 'deadline' in vals:
            for rec in self:
                rec.order_ids.filtered(lambda o: o.state in OPEN_ORDER_STATES).write(
                    {'date_order': rec.deadline})
        return result

    def action_print(self):
        """Print the RFQ document for every vendor."""
        self.ensure_one()
        return self.env.ref('purchase.report_purchase_quotation').report_action(self.order_ids)

    def _prepare_pdf_data(self, order):
        """Plain values for the printed Request for Quotation to one vendor."""
        self.ensure_one()
        from ..report import rfq_pdf  # lazy: reportlab is only needed when printing
        company = self.company_id.sudo()
        partner = order.partner_id
        request = self.request_id.sudo()

        def local(value):
            return fields.Datetime.context_timestamp(self, value) if value else None

        to_lines = []
        if partner.parent_id:
            to_lines.append(partner.parent_id.name)
        to_lines.append(partner.name)
        for part in (partner._display_address(without_name=True) or '').split('\n'):
            part = part.strip()
            if part and part not in to_lines:
                to_lines.append(part)

        company_place = ', '.join(filter(None, [company.street, company.street2, company.city]))
        deadline = local(self.deadline or order.date_order)
        items = []
        for line in order.order_line.filtered(lambda l: not l.display_type):
            item = line.purchase_request_line_id.sudo()
            uom = getattr(line, 'uom_id', None) or getattr(line, 'product_uom_id', None)
            items.append({
                'description': (item.description if item else '') or line.name or '',
                'qty': line.product_qty,
                'uom': (item.unit if item else '') or (uom.name if uom else ''),
            })
        project = request.project_id
        return {
            'title': 'REQUEST FOR QUOTATION',
            'logo': [value for value in (company.logo, getattr(company, 'logo_web', False)) if value],
            'to_lines': to_lines,
            'from_lines': [value for value in (
                company.name, company_place, company.email, company.phone) if value],
            'subject': self.subject or '',
            'info_rows': [
                ('RFQ No', order.name),
                ('Requisition Ref', request.name),
                ('Project Name', project.name or project.code or ''),
                ('Delivery Location', request.location_id.name or ''),
                ('RFQ Date', rfq_pdf.fmt_long_date(local(order.create_date))),
                ('Submission Deadline', rfq_pdf.fmt_short_date(deadline)),
            ],
            'submission_email': self.submission_email or company.procurement_email or company.email,
            'deadline_text': rfq_pdf.fmt_short_date(deadline),
            'currency': order.currency_id.name or '',
            'items': items,
            'details': [line.strip() for line in (self.quotation_details or '').splitlines()
                        if line.strip()],
            'requirements': [
                'Minimum Technical Specifications',
                'Delivery Lead Time',
                'Validity of quotation should be %s days' % (self.validity_days or 90),
            ],
        }

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
