from odoo import _, fields, models
from odoo.exceptions import UserError

OPEN_ORDER_STATES = ('draft', 'sent', 'to approve')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_request_id = fields.Many2one(
        'purchase.request', string='Purchase Request', readonly=True, copy=False,
        index='btree_not_null')
    rfq_group_id = fields.Many2one(
        'purchase.request.rfq', string='RFQ Reference', readonly=True, copy=False,
        index='btree_not_null', ondelete='set null')

    # Printed on the Request for Quotation (the submission deadline is Odoo's own
    # "Order Deadline", date_order).
    rfq_subject = fields.Char(
        string='Subject', help="What the RFQ is for, printed under 'Subject' on the document.")
    rfq_project_id = fields.Many2one('project.project', string='Project')
    rfq_budget_id = fields.Many2one(
        'project.task', string='Budget Line',
        domain="[('project_id', '=', rfq_project_id), ('budget_code', '!=', False)]")
    rfq_date = fields.Date(
        string='RFQ Date', default=fields.Date.context_today, copy=False,
        help="The date printed on the Request for Quotation. Change it when the document is back-dated.")
    rfq_location_id = fields.Many2one('hijra.location', string='Delivery Location')
    rfq_validity_days = fields.Integer(
        string='Quotation Validity (days)', default=90,
        help="Printed in the compliance checklist: how long a quotation must stay valid.")
    rfq_quotation_details = fields.Text(
        string='Quotation Details to Include',
        help="One item per line; printed as bullet points under 'Additional Information'.")

    def _prepare_rfq_pdf_data(self):
        """Plain values for the printed Request for Quotation (see report/rfq_pdf.py)."""
        self.ensure_one()
        from ..report import rfq_pdf  # lazy: reportlab is only needed when printing

        company = self.company_id.sudo()
        partner = self.partner_id
        request = self.purchase_request_id.sudo()

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
        deadline = local(self.date_order)
        items = []
        for line in self.order_line.filtered(lambda l: not l.display_type):
            item = line.purchase_request_line_id.sudo()
            uom = getattr(line, 'uom_id', None) or getattr(line, 'product_uom_id', None)
            items.append({
                'description': (item.description if item else '') or line.name or '',
                'qty': line.product_qty,
                'uom': (item.unit if item else '') or (uom.name if uom else ''),
            })
        project = self.rfq_project_id.sudo()
        rows = [('RFQ No', self.name)]
        if request:
            rows.append(('Requisition Ref', request.name))
        rows += [
            ('Project Name', project.name or ''),
            ('Delivery Location', self.rfq_location_id.sudo().name or ''),
            ('RFQ Date', rfq_pdf.fmt_long_date(self.rfq_date or local(self.create_date))),
            ('Submission Deadline', rfq_pdf.fmt_short_date(deadline)),
        ]
        return {
            'title': 'REQUEST FOR QUOTATION',
            'logo': [value for value in (company.logo, getattr(company, 'logo_web', False)) if value],
            'to_lines': to_lines,
            'from_lines': [value for value in (
                company.name, company_place, company.email, company.phone) if value],
            'subject': self.rfq_subject or '',
            'info_rows': rows,
            'submission_email': rfq_pdf.SUBMISSION_EMAIL,
            'deadline_text': rfq_pdf.fmt_short_date(deadline),
            'currency': self.currency_id.name or '',
            'items': items,
            'details': [line.strip() for line in (self.rfq_quotation_details or '').splitlines()
                        if line.strip()],
            'requirements': [
                'Minimum Technical Specifications',
                'Delivery Lead Time',
                'Validity of quotation should be %s days' % (self.rfq_validity_days or 90),
            ],
        }

    def action_award_order(self):
        """Buy from this vendor: confirm its order and cancel the other quotations."""
        self.ensure_one()
        group = self.rfq_group_id
        if not group:
            raise UserError(_("This order does not belong to an RFQ."))
        if not self.env.user.has_group('purchase.group_purchase_user'):
            raise UserError(_("Only purchase users can award an RFQ."))
        if group.state != 'open':
            raise UserError(_("This RFQ has already been awarded or cancelled."))
        if self.state not in ('draft', 'sent'):
            raise UserError(_("Only a quotation that is still open can be awarded."))
        others = (group.order_ids - self).filtered(lambda order: order.state in OPEN_ORDER_STATES)
        self.button_confirm()
        others.button_cancel()
        group.write({'state': 'awarded', 'awarded_order_id': self.id})
        message = _("Awarded to %(vendor)s (%(order)s).", vendor=self.partner_id.name, order=self.name)
        group.message_post(body=message)
        group.request_id.message_post(body=_("RFQ %(rfq)s: %(message)s", rfq=group.name, message=message))
        return True

    def action_open_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    purchase_request_line_id = fields.Many2one(
        'purchase.request.line', string='Requisition Item', copy=False,
        index='btree_not_null', ondelete='set null')
