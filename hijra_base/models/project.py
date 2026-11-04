from odoo import fields, models


class ProjectTask(models.Model):
    """In HIJRA's setup a task of a project is a budget line of that project.

    The task name is the budget category; the budget code is kept next to it so it can be
    printed on requisitions, purchase orders and payment vouchers.
    """
    _inherit = 'project.task'

    budget_code = fields.Char(
        string='Budget Code', index='btree_not_null', copy=False,
        help="Code of the budget line, e.g. BG260-00-8116. Tasks with a code can be "
             "picked as the budget line on requisitions and payments.")

    _budget_code_uniq = models.Constraint(
        'UNIQUE(project_id, budget_code)', 'This budget code already exists in the project.')
