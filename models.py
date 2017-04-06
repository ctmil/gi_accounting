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

	@api.model
	def _get_account_balance(self,date):
		return_value = 0
		yesterday = fields.Date.from_string(date) - timedelta(days=1)
		account_lines = self.env['account.move.line.date'].search([('account_id','=',self.default_debit_account_id.id),('date','<=',yesterday)])
		for account_line in account_lines:
			return_value = return_value + (account_line.debit - account_line.credit)
		return return_value


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
		
class account_caja_diaria(models.Model):
	_name = 'account.caja.diaria'
	_description = 'Caja Diaria'

	@api.one
	def open_account_movimientos_caja(self):
		self.state = 'open'


	@api.one
	def compute_account_movimientos_caja(self):
		account_move_lines = self.env['account.move.line'].search([('date','=',self.date)])
		journal_amounts = {}
		for move_line in account_move_lines:	
			if move_line.journal_id.type in ['cash','bank']:
				if move_line.debit > 0 and move_line.partner_id:
					account_move = move_line.move_id
					credit_line = None
					invoice_id = None
					invoices = self.env['account.invoice'].search([('partner_id','=',move_line.partner_id.id),\
						('state','in',['open','paid']),('date_invoice','<=',self.date)])
					for invoice in invoices:
						for payment_line in invoice.payment_ids:
							if payment_line.move_id.id == move_line.move_id.id:
								invoice_id = invoice.id
								break
						if invoice_id:
							break		
					vals = {
						'caja_id': self.id,		
						'caja_journal_id': move_line.journal_id.id,		
						'account_move_line_id': move_line.id,
						'account_id': move_line.account_id.id,
						'partner_id': move_line.partner_id.id,
						'debit': move_line.debit,
						}
					if invoice_id:
						vals['invoice'] = invoice_id
					#saldo = move_line.journal_id._get_account_balance(self.date)
					journal_amount = journal_amounts.get(move_line.journal_id.id,0)
					journal_amounts[move_line.journal_id.id] = journal_amount + move_line.debit
					return_id = self.env['account.caja.diaria.journal.lineas'].create(vals)
		self.state = 'done'
		for key, value in journal_amounts.iteritems():
			vals = {
				'caja_id': self.id,
				'journal_id': key,
				'debit': value,
				}
			journal = self.env['account.journal'].browse(key)
			vals['previous_balance'] = journal._get_account_balance(self.date)
			return_id = self.env['account.caja.diaria.journal'].create(vals)
		#import pdb;pdb.set_trace()
	        #return self.env['report'].get_action(self, 'gi_accounting.report_movimientos_caja')


	@api.model
	def create(self,vals):
		user = self.env['res.users'].browse(self.env.context['uid'])
		vals['partner_id'] = user.partner_id.id
	        return super(account_caja_diaria, self).create(vals)
		
	state = fields.Selection(selection=[('draft','Borrador'),('open','Open'),('done','Cerrado')],default='draft')
	partner_id = fields.Many2one('res.partner',string='Cliente')
	date = fields.Date('Fecha',default=date.today(),required=True)
	branch_id = fields.Many2one('res.branch',string='Sucursal',required=True)
	line_ids = fields.One2many(comodel_name='account.caja.diaria.journal.lineas',inverse_name='caja_id')
	journal_ids = fields.One2many(comodel_name='account.caja.diaria.journal',inverse_name='caja_id')

	_sql_constraints = [('account_caja_diaria','UNIQUE (date,branch_id)','Caja ya existe')]

class account_caja_diaria_journal(models.Model):
	_name = 'account.caja.diaria.journal'
	_description = 'Sumarized table for journals'

	caja_id = fields.Many2one('account.caja.diaria')
	journal_id = fields.Many2one('account.journal')
	debit = fields.Float('Débitos')
	debit = fields.Float('Créditos')
	previous_balance = fields.Float('Saldo Anterior')
	end_balance = fields.Float('Saldo Final')



class account_caja_diaria_journal_lineas(models.Model):
	_name = 'account.caja.diaria.journal.lineas'
	_description = 'Movimientos de caja journal lineas'

	caja_id = fields.Many2one('account.caja.diaria',string='Caja')
	caja_journal_id = fields.Many2one('account.journal',string='Método de Pago')
	account_move_line_id = fields.Many2one('account.move.line',string='Mov Contable')
	account_id = fields.Many2one('account.account',string='Cuenta Contable')
	partner_id = fields.Many2one('res.partner',string='Cliente')
	invoice = fields.Many2one('account.invoice',string='Factura')
	debit = fields.Float('Débito')	
