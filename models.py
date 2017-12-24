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
	branch_id = fields.Many2one('res.branch',string='Branch')
    

class res_branch(models.Model):
	_inherit = 'res.branch'

	@api.one
	@api.constrains('point_of_sale')
	def _check_unique_constraint(self):
        	if len(self.search([('point_of_sale', '=', self.point_of_sale)])) > 1:
                	raise ValidationError("Punto de venta ya existente")

	point_of_sale = fields.Integer('Punto de Venta')
	fiscal_printer_id = fields.Many2one('fpoc.fiscal_printer',string='Impresora Fiscal')
	invoice_journal_ids = fields.One2many(comodel_name='account.journal',inverse_name='branch_id',string='Journals',domain=[('type','in',['sale','sale_refund'])])

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
	
	
	@api.multi
	def check_accounting(self):
		check=True
		mod_obj = self.env['ir.model.data']
		document_number= self.partner_id.document_number
		document_type = self.partner_id.document_type_id.id
		responsability_id = self.partner_id.responsability_id.id
		doc_cuit_id = self.env['afip.document_type'].search([('name','=ilike','CUIT')])[0]
		print 'doc type?',document_type,doc_cuit_id 
		m =False
		if not responsability_id:
			m = 'responsability Type is Wrong. Please verify the Afip Responsability Type before.'
		if not m and not document_number:
			m = 'Doc Number is wrong!. Please verify the number before continue.'
		else:
			if not m :
				_number =0 
				try:
					_number=int(document_number)
				except:
					pass
				if _number <=1000000:
					m = 'Doc Number is wrong!. Please verify the number before continue. The value is too low!'
		if not m and not document_type:
			m = 'Doc Type is wrong. Please verify the doc before continue.'
		if doc_cuit_id.id == document_type:
			if not self.partner_id.check_vat_ar(document_number):
				m = 'VAT Number is wrong. Please verify the number before continue.'
		if m:
			raise osv.except_osv(_('Error'), _(m))
			check=False
		return check
        
        
	@api.multi
	def invoice_validate(self):
		if self.check_accounting():
			return self.write({'state': 'open'})
        
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
    
class account_caja(models.Model):
	_name = 'account.box'
	_description = 'Box'
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	
	@api.one
	@api.depends('boxname')
	def _box_name_get(self):

		for box in self:
			name = box.boxname
			if box.branch_id.name:
				name = box.branch_id.name + ' / ' + name
			self.name=name

	name = fields.Char(compute='_box_name_get', string='Name', store=True)
	boxname = fields.Char('Nombre', track_visibility='onchange')
	branch_id = fields.Many2one('res.branch',string='Sucursal',required=True)
	diaria_ids = fields.One2many(comodel_name='account.caja.diaria',inverse_name='box_id')
	journal_id = fields.Many2one('account.journal', string='Diario de Efectivo')
	notes = fields.Text('Notas', track_visibility='onchange')
	#box_type = fields.Selection(selection=[('mostrador','Mostrador'),('recaudadora','Recaudadora'),('orden','Orden')],default='mostrador')
	
	@api.multi
	def unlink(self):
		for caja in self:
			if  self.diaria_ids:
				raise ValidationError('No se puede borrar una caja con cajas diarias')
		return super(account_caja, self).unlink()
	
class account_caja_diaria(models.Model):
	_name = 'account.caja.diaria'
	_description = 'Caja Diaria'
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	_order = 'date desc, id desc'
	
	@api.multi
	def unlink(self):
		for caja in self:
			if  self.state != 'draft':
				raise ValidationError('No se puede borrar una caja ya  abierta')
		return super(account_caja_diaria, self).unlink()

	@api.one
	def close(self):
		self.write({'state':'done'})

	@api.one
	def reopen(self):
		self.write({'state':'open'})
        
	@api.one
	def open_account_movimientos_caja(self):
		self.state = 'open'
		money_ids=self.env['account.caja.diaria.money'].search([('caja_id','=',self.id)])
		if not money_ids:
			money_res=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0]
			for val in money_res:
				self.env['account.caja.diaria.money'].create({'value':val,'caja_id':self.id})




	@api.one
	def compute_account_movimientos_caja(self):
		money_ids=self.env['account.caja.diaria.money'].search([('caja_id','=',self.id)])
		if not money_ids:
			money_res=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0]
			for val in money_res:
				self.env['account.caja.diaria.money'].create({'value':val,'caja_id':self.id})

		invoice_ids=self.env['account.caja.diaria.journal'].search([('caja_id','=',self.id)])
		for invoice in invoice_ids:
			invoice.unlink()
		voucher_ids=self.env['account.caja.diaria.voucher'].search([('caja_id','=',self.id)])
		for voucher in voucher_ids:
			voucher.unlink()
		transfer_ids=self.env['account.caja.diaria.transfer'].search([('caja_id','=',self.id)])
		for transfer in transfer_ids:
			transfer.unlink()
		daily_ids=self.env['account.caja.diaria.close'].search([('caja_id','=',self.id)])
		for daily in daily_ids:
			daily.unlink()
		#self.env['account.caja.diaria.voucher'].unlink(voucher_ids)
		vouchers = self.env['account.voucher'].search([('state','in',['posted']),('date','=',self.date),('branch_id','=',self.branch_id.id)])
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
			amount= invoice.amount_total 
			if invoice.journal_id.type in ['sale_refund']:
				amount= -invoice.amount_total 
			if invoice.journal_id.id in invoice_journals:
					invoice_journals[invoice.journal_id.id]=invoice_journals[invoice.journal_id.id]+amount
			else:
					invoice_journals[invoice.journal_id.id]=amount
		for journal in invoice_journals:
			if invoice_journals[journal]!=0:
				self.env['account.caja.diaria.journal'].create({'caja_id':self.id, 'journal_id':journal, 'amount': invoice_journals[journal]})
		transfers = self.env['account.box.transfer'].search([('state','in',['done']),('date','=',self.date),('box_id','=',self.box_id.id)])
		transferences={}
		
		for transfer in transfers:
			self.env['account.caja.diaria.transfer'].create({'caja_id':self.id, 'transfer_id':transfer.id})
		dailys = self.env['account.cierre.z'].search([('state','in',['close']),('fecha','=',self.date),('branch_id','=',self.branch_id.id)])
		print 'dailys?', dailys
		for daily in dailys:
			self.env['account.caja.diaria.close'].create({'caja_id':self.id, 
                                                 'daily_id':daily.id, 'doc_fiscales_monto': daily.doc_fiscales_monto,
                                                 'doc_nc_monto': daily.doc_nc_monto})


	@api.one
	@api.depends('money_ids')
	def _compute_amount(self):
		self.amount = 0.0
		for money in self.money_ids:
			self.amount = self.amount + money.quantity * money.value  
		return self.amount

	@api.one
	@api.depends('voucher_ids')
	def _compute_amount_voucher(self):
		self.amount_voucher = 0.0
		for voucher in self.voucher_ids:
			self.amount_voucher = self.amount_voucher + voucher.amount  
		self._amount_voucher=self.amount_voucher
		return self.amount_voucher
    
	@api.one
	@api.depends('voucher_ids')
	def _compute_amount_voucher_cash(self):
		self._amount_voucher = 0.0
		for voucher in self.voucher_ids:
			if voucher.journal_id.code == 'EFE':
				self._amount_voucher = self._amount_voucher + voucher.amount  
		return self._amount_voucher
    
	@api.one
	@api.depends('journal_ids')
	def _compute_amount_journals(self):
		self.amount_journals = 0.0
		for journal in self.journal_ids:
			self.amount_journals = self.amount_journals + journal.amount  
		self._amount_journals=self.amount_journals
		return self.amount_journals

	@api.one
	@api.depends('date')
	def _compute_period(self):
		print 'compute_periods'
		args = [('date_start', '<=' ,self.date), ('date_stop', '>=', self.date)]
		context = self.env.context
		if context.get('company_id', False):
			args.append(('company_id', '=', context['company_id']))
		else:
			uid = context.get('uid',False)
			user = None
			if uid:
				user = self.env['res.users'].browse(uid)
				company_id = user.company_id.id
				args.append(('company_id', '=', company_id))
		period_ids = self.env['account.period'].search(args)
		print 'args?',args,period_ids
		self.period_id=period_ids and period_ids[0].id


	@api.one
	@api.depends('transfer_ids')
	def _compute_amount_transfer_negative(self):
		self.amount_transfer = 0.0
		for transfer in self.transfer_ids:
			self._amount_transfer = self._amount_transfer + transfer.amount  
		self._amount_transfer=-self._amount_transfer
		return self._amount_transfer
    
	@api.one
	@api.depends('transfer_ids')
	def _compute_amount_transfer(self):
		self.amount_transfer = 0.0
		for transfer in self.transfer_ids:
			self.amount_transfer = self.amount_transfer + transfer.amount  
		return self.amount_transfer

	@api.one
	@api.depends('transfer_ids','money_ids','voucher_ids','journal_ids','amount_initial')
	def _compute_difference(self):
		self.amount_difference = 0.0
		amount = 0.0
		for money in self.money_ids:
		    amount = amount + money.quantity * money.value  
		amount_transfer = 0.0
		for transfer in self.transfer_ids:
		    amount_transfer = amount_transfer + transfer.amount  
		self.amount_difference = self.amount_initial -amount - amount_transfer + self._amount_voucher
		return self.amount_difference
                
	@api.model
	def create(self,vals):
		box_id=vals['box_id']
		if box_id:
			box=self.env['account.caja.diaria'].search([('box_id','=',box_id),('state','in',('draft','open'))])
			if box and len(box)>0:
				raise ValidationError('No puede crear una nueva caja diaria teniendo otras en estado borrador o abierto')
		return super(account_caja_diaria, self).create(vals)

	def _get_branch(self):
		context = self.env.context
		uid = context.get('uid',None)
		if uid:
			user = self.env['res.users'].browse(uid)
			if user.branch_id:
				branch_id = user.branch_id.id
				return branch_id
		return None
    
	def _get_user(self):
		context = self.env.context
		uid = context.get('uid',None)
		if uid:
			user = self.env['res.users'].browse(uid)
			return user.id
		return None    
	#@api.one
	#@api.depends('box_id')
	#def _get_initial(self):
		#box_id = self.box_id and self.box_id.id
		#if box_id:
			#box=self.env['account.caja.diaria'].search([('box_id','=',box_id),('state','=','close')],limit=1,order='id desc')
			#self.initial=box.amount
			#return self.initial
		#return 0
		
	state = fields.Selection(selection=[('draft','Borrador'),('open','Open'),('done','Cerrado')],default='draft',track_visibility='onchange')
	partner_id = fields.Many2one('res.partner',string='Cliente')
	date = fields.Date('Fecha',default=date.today(),required=True,track_visibility='onchange')
	branch_id = fields.Many2one('res.branch',string='Sucursal',required=True,default=_get_branch,track_visibility='onchange')
	box_id = fields.Many2one('account.box',string='Caja',track_visibility='onchange',required=True)
	line_ids = fields.One2many(comodel_name='account.caja.diaria.journal.lineas',inverse_name='caja_id')
	journal_ids = fields.One2many(comodel_name='account.caja.diaria.journal',inverse_name='caja_id')
	voucher_ids = fields.One2many(comodel_name='account.caja.diaria.voucher',inverse_name='caja_id')
	transfer_ids = fields.One2many(comodel_name='account.caja.diaria.transfer',inverse_name='caja_id')
	money_ids = fields.One2many(comodel_name='account.caja.diaria.money',inverse_name='caja_id')
	close_ids = fields.One2many(comodel_name='account.caja.diaria.close',inverse_name='caja_id')
	vale_ids = fields.One2many(comodel_name='account.caja.vale',inverse_name='caja_id')
	manager_id = fields.Many2one('res.users',string='Manager',track_visibility='onchange',required=True)
	amount_initial = fields.Float('Initial Amount',track_visibility='onchange')
	_amount_initial = fields.Float('Initial Amount',related='amount_initial')
	amount_final = fields.Float('Final Amount')
	period_id = fields.Many2one(compute='_compute_period', comodel_name='account.period',string='Period',store=True)
	amount_difference = fields.Float(compute='_compute_difference', string='Difference Amount',store=True)
	amount = fields.Float(compute='_compute_amount', string='Money Amount',store=True, track_visibility='always')
	amount_voucher = fields.Float(compute='_compute_amount_voucher', string='Voucher Amount',store=True)    
	amount_journals = fields.Float(compute='_compute_amount_journals', string='Billing Amount',store=True) 
	amount_transfer = fields.Float(compute='_compute_amount_transfer', string='Transfers Amount',store=True)
	_amount = fields.Float('Amount',related='amount')
	_amount_voucher = fields.Float(compute='_compute_amount_voucher_cash', string='Voucher Amount',store=True) 
	_amount_journals = fields.Float('Journal Amount',related='amount_journals') 
	_amount_transfer = fields.Float(compute='_compute_amount_transfer_negative', string='Transfers Amount',store=True)
	notes = fields.Text('Notas', track_visibility='onchange')
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
	

class account_caja_diaria_close(models.Model):
	_name = 'account.caja.diaria.close'
	_description = 'Sumarized table for daily close'

	caja_id = fields.Many2one('account.caja.diaria')
	daily_id = fields.Many2one('account.cierre.z')
	doc_fiscales_monto = fields.Float('Venta Total')
	doc_nc_monto= fields.Float('Credito Total')
	
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
	fecha = fields.Date('Fecha')
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
	_order = 'fecha desc,id desc'
  
class account_caja_transferencia(models.Model):
	_name = 'account.caja.diaria.transfer'
	_description = 'Transferencia de Cajas'
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	
	caja_id = fields.Many2one('account.caja.diaria')
	transfer_id = fields.Many2one('account.box.transfer')
	amount = fields.Float('Amount',related='transfer_id.amount')
	state = fields.Selection(selection=[('draft','Borrador'),('open','Abierto'),('done','Realizado'),('canceled','Cancelado')],related='transfer_id.state')
	box_dst = fields.Many2one('account.box','Box Destination',related='transfer_id.box_dst')
	date = fields.Date('Fecha',related='transfer_id.date')
	notes = fields.Text('Notas',related='transfer_id.notes')

	
class account_box_transfer(models.Model):
	_name = 'account.box.transfer'
	_description = 'Box Transfer'
	_inherit = ['mail.thread', 'ir.needaction_mixin']

	@api.model
	def create(self, vals):
		sequence=self.env['ir.sequence'].get('account.box.transfer')
		if not sequence:
			raise ValidationError('No esta definida la secuencia')
		if vals.get('name','/')=='/':
			vals['name']=sequence
		return super(account_box_transfer, self).create(vals)
    
	@api.multi
	def unlink(self):
		for transferencia in self:
			if  self.state != 'draft':
				raise ValidationError('No se puede borrar una transferencia ya abierta')
		return super(account_box_transfer, self).unlink()
	name = fields.Char('Name',track_visibility='always')
	state = fields.Selection(selection=[('draft','Borrador'),('open','Abierto'),('done','Realizado'),('canceled','Cancelado')],default='draft',track_visibility='always')
	date = fields.Date('Fecha',default=date.today(),required=True)
	box_id = fields.Many2one('account.box',string='Caja Origen')
	box_dst = fields.Many2one('account.box',string='Caja Destino')
	amount= fields.Float('Importe',track_visibility='onchange')
	notes = fields.Text('Notas', track_visibility='onchange')
	branch_id = fields.Many2one('res.branch', string='Sucursal', related='box_id.branch_id')
    
	
class account_caja_vale(models.Model):
	_name = 'account.caja.vale'
	_description = 'Caja Vale'
	_inherit = ['mail.thread', 'ir.needaction_mixin']
	
	@api.model
	def create(self, vals):
		sequence=self.env['ir.sequence'].get('account.caja.vale')
		if not sequence:
			raise ValidationError('No esta definida la secuencia')
		if vals.get('name','/')=='/':
			vals['name']=sequence
		return super(account_caja_vale, self).create(vals)
	
	@api.multi
	def unlink(self):
		for vale in self:
			if  self.state != 'draft':
				raise ValidationError('No se puede borrar un vale abierto')
		return super(account_caja_vale, self).unlink()

	name = fields.Char('Name',track_visibility='always')
	state = fields.Selection(selection=[('draft','Borrador'),('open','Open'),('done','Cerrado')],default='draft',track_visibility='always')
	date = fields.Date('Fecha',default=date.today(),required=True,track_visibility='always')
	caja_id = fields.Many2one('account.caja.diaria',string='Caja')
	user_id = fields.Many2one('res.users', string='Usuario', required=True, track_visibility='onchange')
	amount= fields.Float('Importe',track_visibility='onchange')
	notes = fields.Text('Notas', track_visibility='onchange')
	branch_id = fields.Many2one('res.branch', string='Sucursal', related='user_id.branch_id')


