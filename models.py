# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.osv import osv
from openerp.exceptions import except_orm, ValidationError
from StringIO import StringIO
import urllib2, httplib, urlparse, gzip, requests, json
import openerp.addons.decimal_precision as dp
import logging
import datetime
from openerp.fields import Date as newdate
from datetime import datetime, timedelta, date
from dateutil import relativedelta
#Get the logger
_logger = logging.getLogger(__name__)

class account_journal(models.Model):
	_inherit = 'account.journal'

	is_debit_note = fields.Boolean('Nota de Debito')


class res_branch(models.Model):
	_inherit = 'res.branch'

	@api.one
	@api.constrains('point_of_sale')
	def _check_unique_constraint(self):
        	if len(self.search([('point_of_sale', '=', self.point_of_sale)])) > 1:
                	raise ValidationError("Punto de venta ya existente")

	point_of_sale = fields.Integer('Punto de Venta')

class account_responsabilities_mapping(models.Model):
	_name = 'account.responsabilities.mapping'
	_description = 'Mapping de responsabilidades'

	name = fields.Char('Nombre')
	responsability_id = fields.Many2one('afip.responsability',string='Responsabilidad AFIP',required=True)
	journal_id = fields.Many2one('account.journal',string='Diario',domain=[('type','in',['sale','sale_refund'])])
	journal_type = fields.Selection(selection=[('sale', 'Sale'),('sale_refund','Sale Refund')],related='journal_id.type')
	point_of_sale = fields.Integer('Point of Sale',related='journal_id.point_of_sale')
	is_debit_note = fields.Boolean('Nota de Debito',related='journal_id.is_debit_note')


class account_invoice(models.Model):
        _inherit = 'account.invoice'

	point_of_sale = fields.Integer('Punto de Venta')
	is_debit_note = fields.Boolean('Nota de Debito',related='journal_id.is_debit_note')

        @api.model
        def create(self, vals):
                context = self.env.context
                uid = context.get('uid',False)
                if uid:
                        user = self.env['res.users'].browse(uid)
                        if user.branch_id:
                                vals['point_of_sale'] = user.branch_id.point_of_sale
                return super(account_invoice,self).create(vals)

	@api.multi
	def onchange_partner_id(self, type, partner_id, date_invoice=False,payment_term=False,\
		 partner_bank_id=False, company_id=False):
		res = super(account_invoice, self).onchange_partner_id(type,partner_id,date_invoice,payment_term,partner_bank_id,company_id)
                context = self.env.context
                uid = context.get('uid',False)
                if uid and partner_id:
			journal_type = context.get('journal_type','sale_refund')
			debit_note = context.get('debit_note',False)
                        user = self.env['res.users'].browse(uid)
			point_of_sale = user.branch_id.point_of_sale
			partner = self.env['res.partner'].browse(partner_id)
			if partner.responsability_id:
				resp_id = partner.responsability_id.id
				resp = self.env['account.responsabilities.mapping'].search([('responsability_id','=',resp_id),\
					('point_of_sale','=',point_of_sale),('journal_type','=',journal_type),\
					('is_debit_note','=',debit_note)])
				if resp:
					res['value']['journal_id'] = resp.journal_id.id
		return res
		
class account_movimientos_caja(models.Model):
	_name = 'account.movimientos.caja'
	_description = 'Movimientos de caja'

	@api.one
	def compute_account_movimientos_caja(self):
		for journal in self.journal_ids:
			account_move_lines = self.env['account.move.line'].search([('journal_id','=',journal.id),('date','=',self.date)])
			for account_move_line in account_move_lines:
				vals = {
					'caja_journal_id': journal.id,		
					'account_move_line_id': account_move_line.id
					}	
				return_id = self.env['account.movimientos.caja.journal.lineas'].create(vals)
		import pdb;pdb.set_trace()
	        return self.env['report'].get_action(self, 'gi_accounting.report_movimientos_caja')


	date = fields.Date('Fecha a reportar',default=date.today(),required=True)
	journal_ids = fields.One2many(comodel_name='account.movimientos.caja.journal',inverse_name='caja_id')


class account_movimientos_caja_journal(models.Model):
	_name = 'account.movimientos.caja.journal'
	_description = 'Movimientos de caja journal'

	caja_id = fields.Many2one('account.movimientos.caja')
	journal_id = fields.Many2one('account.journal',string="Métodos de Pago",domain=['|',('type','=','cash'),('type','=','bank')])
	move_lines = fields.One2many(comodel_name='account.movimientos.caja.journal.lineas',inverse_name='caja_journal_id')

class account_movimientos_caja_journal_lineas(models.Model):
	_name = 'account.movimientos.caja.journal.lineas'
	_description = 'Movimientos de caja journal lineas'

	caja_journal_id = fields.Many2one('account.movimientos.caja.journal')
	account_move_line_id = fields.Many2one('account.move.line')
