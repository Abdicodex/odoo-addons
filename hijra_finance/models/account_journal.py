from odoo import _, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def open_action(self):
        """The name of a bank or cash card on the accounting dashboard (and its Transactions
        button) lists that bank's transactions, one line each, instead of the reconciliation."""
        self.ensure_one()
        if self.type in ('bank', 'cash', 'credit') and not self.env.context.get('action_name'):
            return self.finance_action_open_transactions()
        return super().open_action()

    def finance_action_open_transactions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hijra_finance.finance_transaction_action')
        action.update({
            'name': self.display_name,
            'domain': [('journal_id', '=', self.id)],
            'context': {'default_journal_id': self.id},
        })
        return action

    def finance_action_new(self, transaction_type='expense'):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Transaction'),
            'res_model': 'finance.transaction',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {'default_journal_id': self.id, 'default_transaction_type': transaction_type},
        }

    def finance_action_new_expense(self):
        return self.finance_action_new('expense')

    def finance_action_new_income(self):
        return self.finance_action_new('income')

    def om_action_new_transaction(self):
        """The New Transaction button of the dashboard opens the transaction form."""
        return self.finance_action_new('expense')
