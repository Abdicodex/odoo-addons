from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseRequestMakeRfq(models.TransientModel):
    _name = 'purchase.request.make.rfq'
    _description = 'Create RFQs from a Purchase Requisition'

    request_id = fields.Many2one('purchase.request', required=True, readonly=True)
    partner_ids = fields.Many2many(
        'res.partner', string='Vendors', required=True,
        help="One RFQ is created for each vendor so quotes can be compared.")
    subject = fields.Char(
        string='Subject', required=True,
        help="What the RFQ is for, printed on the document.")
    deadline = fields.Datetime(
        string='Submission Deadline', required=True,
        default=lambda self: fields.Datetime.now() + timedelta(days=7))
    validity_days = fields.Integer(string='Quotation Validity (days)', default=90)
    quotation_details = fields.Text(
        string='Quotation Details to Include',
        help="One item per line; printed as bullet points on the RFQ.")
    line_ids = fields.One2many(
        'purchase.request.make.rfq.line', 'wizard_id', string='Items')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        request = self.env['purchase.request'].browse(
            res.get('request_id') or self.env.context.get('default_request_id'))
        if request and 'subject' in fields_list:
            first = request.line_ids[:1].description or ''
            res['subject'] = ' '.join(first.split())[:120]
        if request and 'line_ids' in fields_list:
            res['line_ids'] = [(0, 0, {
                'request_line_id': line.id,
                'product_id': line._get_rfq_product().id,
            }) for line in request.line_ids]
        return res

    def action_create_rfqs(self):
        self.ensure_one()
        request = self.request_id
        if request.state not in ('approved', 'rfq_created'):
            raise UserError(_("Only approved requisitions can be turned into RFQs."))
        # keep only products the buyer chose on purpose; defaults are re-resolved when needed
        for line in self.line_ids:
            item = line.request_line_id
            if line.product_id and line.product_id != item._get_rfq_product():
                item.product_id = line.product_id
        # one RFQ reference; each vendor gets its own quotation under it (RFQ-1, RFQ-2, ...)
        group = self.env['purchase.request.rfq'].create({
            'request_id': request.id,
            'subject': self.subject,
            'deadline': self.deadline,
            'validity_days': self.validity_days,
            'quotation_details': self.quotation_details,
        })
        orders = self.env['purchase.order']
        for index, partner in enumerate(self.partner_ids, 1):
            vals = request._prepare_rfq_vals(partner)
            vals.update({
                'rfq_group_id': group.id,
                'name': f"{group.name}-{index}",
                'date_order': self.deadline,
            })
            orders |= self.env['purchase.order'].create(vals)
        request.state = 'rfq_created'
        vendors = ", ".join(self.partner_ids.mapped('name'))
        group.message_post(body=_("Sent to: %s.", vendors))
        request.message_post(body=_(
            "RFQ %(rfq)s sent to: %(vendors)s.", rfq=group.name, vendors=vendors))
        return group.action_open()


class PurchaseRequestMakeRfqLine(models.TransientModel):
    _name = 'purchase.request.make.rfq.line'
    _description = 'Item to include in the RFQs'

    wizard_id = fields.Many2one('purchase.request.make.rfq', required=True, ondelete='cascade')
    request_line_id = fields.Many2one('purchase.request.line', required=True, readonly=True)
    item_no = fields.Integer(related='request_line_id.item_no')
    description = fields.Text(related='request_line_id.description')
    quantity = fields.Float(string='Quantity', compute='_compute_quantity')
    product_id = fields.Many2one(
        'product.product', string='Product', domain=[('purchase_ok', '=', True)],
        help="Optional. Left as the default service product unless the item needs a "
             "specific product.")

    @api.depends('request_line_id.product_qty', 'request_line_id.frequency')
    def _compute_quantity(self):
        for line in self:
            line.quantity = line.request_line_id.product_qty * line.request_line_id.frequency
