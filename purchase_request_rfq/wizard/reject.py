from odoo import _, fields, models
from odoo.exceptions import UserError


class PurchaseRequestReject(models.TransientModel):
    _name = 'purchase.request.reject'
    _description = 'Reject a Purchase Requisition'

    request_id = fields.Many2one('purchase.request', required=True, readonly=True)
    reason = fields.Text(string='Reason', required=True)

    def action_reject(self):
        self.ensure_one()
        request = self.request_id
        if request.state != 'to_approve':
            raise UserError(_("Only requisitions waiting for approval can be rejected."))
        request.activity_unlink(['mail.mail_activity_data_todo'])
        request.write({
            'state': 'rejected',
            'decision_by_id': self.env.user.id,
            'decision_date': fields.Datetime.now(),
            'rejection_reason': self.reason,
        })
        request.message_post(body=_("Requisition rejected: %s", self.reason))
        return {'type': 'ir.actions.act_window_close'}
