from odoo import _, fields, models
from odoo.exceptions import UserError


class PurchaseRequestReject(models.TransientModel):
    _name = 'purchase.request.reject'
    _description = 'Reject a Purchase Request'

    request_id = fields.Many2one('purchase.request', required=True, readonly=True)
    reason = fields.Text(string='Reason', required=True)

    def action_reject(self):
        self.ensure_one()
        request = self.request_id
        if request.state != 'to_approve':
            raise UserError(_("Only requests waiting for approval can be rejected."))
        request._close_approval_activities()
        request.write({
            'state': 'rejected',
            'approver_id': self.env.user.id,
            'decision_date': fields.Datetime.now(),
            'rejection_reason': self.reason,
        })
        request.message_post(body=_("Request rejected: %s", self.reason))
        return {'type': 'ir.actions.act_window_close'}
