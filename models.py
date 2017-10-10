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
		account_lines = self.env['account.move.line.date'].search([('account_id','=',self.default_debit_account_id.id),('date','<=',date)])
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
	fiscal_printer_id = fields.Many2one('fpoc.fiscal_printer',string='Impresora Fiscal')

class account_responsabilities_mapping(models.Model):
	_name = 'account.responsabilities.mapping'
	_description = 'Mapping de responsabilidades'

	name = fields.Char('Nombre')
	responsability_id = fields.Many2one('afip.responsability',string='Responsabilidad AFIP',required=True)
	journal_id = fields.Many2one('account.journal',string='Diario',domain=[('type','in',['sale','sale_refund'])])
	journal_type = fields.Selection(selection=[('sale', 'Sale'),('sale_refund','Sale Refund')],related='journal_id.type')
	point_of_sale = fields.Integer('Point of Sale',related='journal_id.point_of_sale')
	#point_of_sale = fields.Char('Point of Sale',related='journal_id.point_of_sale')
	is_debit_note = fields.Boolean('Nota de Debito',related='journal_id.is_debit_note')


class account_invoice(models.Model):
        _inherit = 'account.invoice'

	@api.multi
	def test_wizard(self):
		test_tree = self.env['wizard.test.tree'].create({'name': 'Mi nombre'})
		partner_ids = self.env['res.partner'].search([('supplier','=',True)])
		for partner in partner_ids:
			vals_line = {
				'invoice_id': self.id,
				'header_id': test_tree.id,
				'partner_id': partner.id,
				'selected': 'no'
				}
			line_id = self.env['wizard.test.tree.line'].create(vals_line)
                return {'type': 'ir.actions.act_window',
                        'name': 'Test Wizard',
                        'res_model': 'wizard.test.tree',
                        'res_id': test_tree.id,
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'nodestroy': True,
                        }



	@api.one
	def _compute_sale_order_id(self):
		if self.origin:
			sale_order = self.env['sale.order'].search([('name','=',self.origin)])
			if sale_order:
				self.sale_order_id = sale_order.id

	point_of_sale = fields.Integer('Punto de Venta')
	is_debit_note = fields.Boolean('Nota de Debito',related='journal_id.is_debit_note')
	sale_order_id = fields.Many2one('sale.order',string='Pedido de ventas',compute=_compute_sale_order_id)
	
        @api.model
        def create(self, vals):
		#date_invoice = vals.get('date_invoice',None)
		#if not date_invoice:
		#	raise ValidationError('Debe ingresar la fecha de la factura')
                context = self.env.context
                uid = context.get('uid',False)
		user = None
                if uid:
                        user = self.env['res.users'].browse(uid)
                        if user.branch_id:
                                vals['point_of_sale'] = user.branch_id.point_of_sale
		else:
			origin = vals.get('origin',False)
			if origin:
				order = self.env['sale.order'].search([('name','=',origin)])
				if order:
					user = order.user_id
			else:
				user = self.env['res.users'].browse(1)
		if user:
			vals['branch_id'] = user.branch_id.id
		#caja_id = self.env['account.caja.diaria'].search([('branch_id','=',user.branch_id.id),('date','=',date_invoice),('state','=','open')])
		#if not caja_id:
		#	raise ValidationError('No hay caja abierta para la sucursal.\nContacte al administrador')
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


	@api.multi
	def unlink(self):
		for caja in self:
			if  self.state != 'draft':
				raise ValidationError('No se puede borrar una caja ya  abierta')
		return super(account_caja_diaria, self).unlink()

	@api.one
	def open_account_movimientos_caja(self):
		self.state = 'open'
		res=[0.1,
             0.25,
             0.5,
             1.0,
             2.0,
             5.0,
             10.0,
             20.0,
             50.0,
             100.0,
             200.0,
             500.0]
		money_ids=self.env['account.caja.diaria.money'].search([('caja_id','=',self.id)])
		for money in money_ids:
			money.unlink()
		for val in res:
			self.env['account.caja.diaria.money'].create({'value':val,'caja_id':self.id})
	#	if self.fiscal_printer_id:
	#		fp = self.fiscal_printer_id
	#		if fp.printerStatus != 'Unknown':
	#			if 'Jornada fiscal cerrada' in fp.fiscalStatus:
	#				fp.open_fiscal_journal()
	#			else:
	#				raise ValidationError('No se puede abrir la caja debido a que la impresora fiscal\ntiene status fiscal incorrecto.\nContacte administrador')
	#		else:
	#			raise ValidationError('No se puede abrir la caja debido a que\nla impresora fiscal no tiene status')


	@api.one
	def compute_account_movimientos_caja_old(self):
		account_move_lines = self.env['account.'].search([('date','=',self.date),('branch_id','=',self.branch_id.id)])
		journal_amounts = {}
		for move_line in account_move_lines:	
			if move_line.journal_id.type in ['cash','bank']:
				if move_line.debit > 0 and move_line.partner_id:
					account_move = move_line.move_id
					credit_line = None
					invoice_id = None
					invoices = self.env['account.invoice'].search([('partner_id','=',move_line.partner_id.id),\
						('state','in',['open','paid']),('date_invoice','<=',self.date),('branch_id','=',self.branch_id.id)])
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
						'credit': move_line.credit,
						}
					if invoice_id:
						vals['invoice'] = invoice_id
					voucher_id = None
					vouchers = self.env['account.voucher'].search([('partner_id','=',move_line.partner_id.id),\
						('state','=',['posted']),('date','=',self.date),('branch_id','=',self.branch_id.id)])
					for voucher in vouchers:
						if voucher.nro_cupon != '':
							if move_line.id in voucher.move_ids.ids:
								voucher_id = voucher
					if voucher_id and voucher_id.nro_cupon:
						vals['cupon'] = voucher_id.nro_cupon
					#saldo = move_line.journal_id._get_account_balance(self.date)
					journal_amts = journal_amounts.get(move_line.journal_id.id,[0,0])
					journal_amounts[move_line.journal_id.id] = [journal_amts[0] + move_line.debit, journal_amts[1] + move_line.credit]
					return_id = self.env['account.caja.diaria.journal.lineas'].create(vals)
		self.state = 'done'
		for key, value in journal_amounts.iteritems():
			vals = {
				'caja_id': self.id,
				'journal_id': key,
				'debit': value[0],
				'credit': value[1],
				}
			journal = self.env['account.journal'].browse(key)
			yesterday = fields.Date.from_string(self.date) - timedelta(days=1)
			vals['previous_balance'] = journal._get_account_balance(yesterday)
			vals['end_balance'] = journal._get_account_balance(self.date)
			return_id = self.env['account.caja.diaria.journal'].create(vals)
		if self.fiscal_printer_id:
			fp = self.fiscal_printer_id
			if fp.printerStatus != 'Unknown':
				if 'Jornada fiscal abierta' in fp.fiscalStatus:
					fp.close_fiscal_journal()
				else:
					raise ValidationError('No se puede cerrar la caja debido a que la impresora fiscal\ntiene status fiscal incorrecto.\nContacte administrador')
			else:
				raise ValidationError('No se puede abrir la caja debido a que\nla impresora fiscal no tiene status')
		#import pdb;pdb.set_trace()
	        #return self.env['report'].get_action(self, 'gi_accounting.report_movimientos_caja')

	@api.one
	def compute_account_movimientos_caja(self):
		invoice_ids=self.env['account.caja.diaria.journal'].search([('caja_id','=',self.id)])
		for invoice in invoice_ids:
			invoice.unlink()
		voucher_ids=self.env['account.caja.diaria.voucher'].search([('caja_id','=',self.id)])
		for voucher in voucher_ids:
			voucher.unlink()
		#self.env['account.caja.diaria.voucher'].unlink(voucher_ids)
		vouchers = self.env['account.voucher'].search([('state','in',['posted']),('date','=',self.date),('branch_id','=',self.branch_id.id)])
		
		
		print 'vouchers?', vouchers
		journals={}
		for voucher in vouchers:
			if voucher.journal_id.id in journals:
					journals[voucher.journal_id.id]=journals[voucher.journal_id.id]+voucher.amount
			else:
					journals[voucher.journal_id.id]=voucher.amount
		for journal in journals:
			self.env['account.caja.diaria.voucher'].create({'caja_id':self.id, 'journal_id':journal, 'amount': journals[journal]}) 
		invoices = self.env['account.invoice'].search([('state','in',['open','paid']),('date_invoice','=',self.date),('branch_id','=',self.branch_id.id)])
		invoice_journals={}
		for invoice in invoices:
			if invoice.journal_id.id in invoice_journals:
					invoice_journals[invoice.journal_id.id]=invoice_journals[invoice.journal_id.id]+invoice.amount_total
			else:
					invoice_journals[invoice.journal_id.id]=invoice.amount_total
		print 'journals?', journals
		for journal in invoice_journals:
			if invoice_journals[journal]>0:
				self.env['account.caja.diaria.journal'].create({'caja_id':self.id, 'journal_id':journal, 'amount': invoice_journals[journal]})
		print 'invoices?', invoice_journals

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
	voucher_ids = fields.One2many(comodel_name='account.caja.diaria.voucher',inverse_name='caja_id')
	money_ids = fields.One2many(comodel_name='account.caja.diaria.money',inverse_name='caja_id')
	

	_sql_constraints = [('account_caja_diaria','UNIQUE (date,branch_id)','Caja ya existe')]

class account_caja_diaria_journal(models.Model):
	_name = 'account.caja.diaria.journal'
	_description = 'Sumarized table for journals'

	caja_id = fields.Many2one('account.caja.diaria')
	journal_id = fields.Many2one('account.journal')
	amount = fields.Float('Monto')

class account_caja_diaria_voucher(models.Model):
	_name = 'account.caja.diaria.voucher'
	_description = 'Sumarized table for vouchers'

	caja_id = fields.Many2one('account.caja.diaria')
	journal_id = fields.Many2one('account.journal')
	amount = fields.Float('Total')
	
class account_caja_diaria_journal_lineas(models.Model):
	_name = 'account.caja.diaria.journal.lineas'
	_description = 'Movimientos de caja journal lineas'

	caja_id = fields.Many2one('account.caja.diaria',string='Caja')
	caja_journal_id = fields.Many2one('account.journal',string='Método de Pago')
	account_move_line_id = fields.Many2one('account.move.line',string='Mov Contable')
	account_id = fields.Many2one('account.account',string='Cuenta Contable')
	partner_id = fields.Many2one('res.partner',string='Cliente')
	invoice = fields.Many2one('account.invoice',string='Factura')
	cupon = fields.Char('Cupón')
	debit = fields.Float('Débito')	
	credit = fields.Float('Crédito')	

class account_caja_diaria_money(models.Model):
	_name = 'account.caja.diaria.money'
	_description = 'Movimientos de caja journal lineas'

	@api.one
	def _compute_amount(self):
		self.amount = self.quantity * self.value  
		return self.amount
    
	caja_id = fields.Many2one('account.caja.diaria',string='Caja')
	value = fields.Float('Value')
	quantity = fields.Float('Quantity')
	amount = fields.Float(compute='_compute_amount', string='Amount')
	
	
class account_cierre_z(models.Model):
	_name = 'account.cierre.z'
	_description = 'Cierre Z'
	branch_id = fields.Many2one('res.branch',string='Sucursal',required=True)
	name = fields.Char('Numero')
	fecha = fields.Datetime('Fecha')
	state = fields.Selection(selection=[('draft','Borrador'),('open','Open'),('close','Cerrado')],default='draft')
	cierre= fields.Char('Numero Cierre')
	point_of_sale= fields.Char('Punto de Venta')
	doc_fiscales_monto= fields.Float('Venta Diaria')
	doc_fiscales_iva= fields.Float('Iva Diario')
	doc_fiscales_no_gravados=fields.Float('Conceptos no gravados')
	doc_fiscales_percepciones=fields.Float('Percepciones')
	doc_fiscales_ultimo_a=fields.Integer('Ultimo Ticket A')
	doc_fiscales_ultimo_b=fields.Integer('Ultimo Ticket B')
	doc_fiscales_emitidos=fields.Integer('Emitidos')
	doc_fiscales_cancelados=fields.Integer('Cancelados')
	doc_no_fiscales_emitidos=fields.Integer('No Fiscales Emitidos')
	doc_no_fiscales_homologados_emitidos=fields.Integer('No Fiscales Homologados Emitidos')
	doc_nc_monto= fields.Float('Credito Diario')
	doc_nc_iva= fields.Float('Iva Diario')
	doc_nc_no_gravados=fields.Float('Conceptos no gravados')
	doc_nc_percepciones=fields.Float('Percepciones')
	doc_nc_ultimo_a=fields.Integer('Ultimo Nota de Credito A')
	doc_nc_ultimo_b=fields.Integer('Ultimo Nota de Credito B')
	doc_nc_emitidos=fields.Integer('Emitidos')
	disc_alic_iva = fields.Float('Alicuota Iva')
	disc_monto_venta = fields.Float('Monto Venta')
	disc_monto_iva = fields.Float('Monto Iva')
	disc_monto_no_gravados = fields.Float('Monto Conceptos no Gravados')
	disc_monto_percepciones = fields.Float('Monto Percepciones')
	disc_nc_alic_iva = fields.Float('Alicuota Iva')
	disc_nc_monto_venta = fields.Float('Monto Venta')
	disc_nc_monto_iva = fields.Float('Monto Iva')
	disc_nc_monto_no_gravados = fields.Float('Monto Conceptos no Gravados')
	disc_nc_monto_percepciones = fields.Float('Monto Percepciones')
       
