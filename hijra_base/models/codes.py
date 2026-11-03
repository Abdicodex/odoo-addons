from odoo import fields, models


class HijraProject(models.Model):
    _name = 'hijra.project'
    _description = 'HIJRA Project'
    _order = 'code'
    _rec_name = 'code'
    _rec_names_search = ['code', 'name']

    code = fields.Char(required=True)
    name = fields.Char(string='Description')
    active = fields.Boolean(default=True)
    budget_ids = fields.One2many('hijra.budget', 'project_id', string='Budget Codes')

    _code_uniq = models.Constraint('UNIQUE(code)', 'The project code must be unique.')


class HijraBudget(models.Model):
    _name = 'hijra.budget'
    _description = 'HIJRA Budget Code'
    _order = 'project_id, code'
    _rec_names_search = ['name', 'code']

    project_id = fields.Many2one(
        'hijra.project', string='Project', required=True, ondelete='cascade', index=True)
    code = fields.Char(string='Budget Code', required=True)
    name = fields.Char(string='Category', required=True)
    active = fields.Boolean(default=True)

    _code_project_uniq = models.Constraint(
        'UNIQUE(project_id, code)', 'This budget code already exists for the project.')


class HijraFund(models.Model):
    _name = 'hijra.fund'
    _description = 'HIJRA Fund'
    _order = 'code'
    _rec_name = 'code'
    _rec_names_search = ['code', 'name']

    code = fields.Char(required=True)
    name = fields.Char(string='Description')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('UNIQUE(code)', 'The fund code must be unique.')


class HijraLocation(models.Model):
    _name = 'hijra.location'
    _description = 'HIJRA Location'
    _order = 'name'
    _rec_names_search = ['name', 'code']

    code = fields.Char(required=True)
    name = fields.Char(string='Description', required=True)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint('UNIQUE(code)', 'The location code must be unique.')
