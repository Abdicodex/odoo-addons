from odoo import fields, models


class PurchaseRequestProject(models.Model):
    _name = 'purchase.request.project'
    _description = 'Requisition Project'
    _order = 'code'
    _rec_name = 'code'
    _rec_names_search = ['code', 'name']

    code = fields.Char(required=True)
    name = fields.Char(string='Description')
    active = fields.Boolean(default=True)
    budget_ids = fields.One2many('purchase.request.budget', 'project_id', string='Budget Codes')

    _code_uniq = models.Constraint('UNIQUE(code)', 'The project code must be unique.')


class PurchaseRequestBudget(models.Model):
    _name = 'purchase.request.budget'
    _description = 'Requisition Budget Code'
    _order = 'project_id, code'
    _rec_name = 'code'
    _rec_names_search = ['code', 'description']

    code = fields.Char(required=True)
    description = fields.Char(string='Description')
    project_id = fields.Many2one(
        'purchase.request.project', string='Project', required=True, ondelete='cascade', index=True)
    active = fields.Boolean(default=True)

    _code_project_uniq = models.Constraint(
        'UNIQUE(project_id, code)', 'This budget code already exists for the project.')


class PurchaseRequestFund(models.Model):
    _name = 'purchase.request.fund'
    _description = 'Requisition Fund'
    _order = 'code'
    _rec_name = 'code'
    _rec_names_search = ['code', 'name']

    code = fields.Char(required=True)
    name = fields.Char(string='Description')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('UNIQUE(code)', 'The fund code must be unique.')


class PurchaseRequestLocation(models.Model):
    _name = 'purchase.request.location'
    _description = 'Requisition Location'
    _order = 'code'
    _rec_name = 'code'
    _rec_names_search = ['code', 'name']

    code = fields.Char(required=True)
    name = fields.Char(string='Description')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('UNIQUE(code)', 'The location code must be unique.')


class PurchaseRequestDepartment(models.Model):
    _name = 'purchase.request.department'
    _description = 'Requisition Department'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint('UNIQUE(name)', 'The department name must be unique.')
