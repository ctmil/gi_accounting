# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (C) 2012 OpenERP - Team de Localización Argentina.
# https://launchpad.net/~openerp-l10n-ar-localization
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import osv,fields
from openerp import models, api, tools
from openerp.exceptions import Warning

#class account_move_line(osv.osv):
#	_inherit = 'account.move.line'

	#def reconcile_partial(self, cr, uid, ids, type='auto', context=None, writeoff_acc_id=False, writeoff_period_id=False, writeoff_journal_id=False):
	#	res = super(account_move_line, self).reconcile_partial(cr,uid, ids, 'auto', context, writeoff_acc_id, writeoff_period_id, writeoff_journal_id)
	#	invoices = []
	#	journal_id = None
	#	amount = 0
	#	account_move = None
	#	move_line_credit = None
	#	for move_line_id in ids:
	#		move_line = self.pool.get('account.move.line').browse(cr,uid,move_line_id)
	#		if move_line.invoice:
	#			invoices.append(move_line.invoice)
	#		if move_line.credit > 0:
	#			journal_id = move_line.journal_id
	#			amount = amount + move_line.credit
	#			move_line_credit = move_line
	#		account_move = move_line.move_id
	#	if len(invoices) == 1 and journal_id:
	#		journal_present = False	
	#		sale_order = invoices[0].sale_order_id
	#		amount_invoice = 0
	#		amount_journal = 0
	#		if sale_order and sale_order.payment:
	#			# Controla el medio de pago
	#			amount_so = 0
	#			for payment_line in sale_order.payment:
	#				if payment_line.journal_id.id == journal_id.id:
	#					journal_present = True
	#					amount_journal = payment_line.amount
	#			if not journal_present:
	#				raise Warning('El medio de pago no está presente en el pedido de ventas')				
	#			# Controla el monto	
	#			#other_payments = invoices[0].payment_ids
	#			#amount_invoice = amount
	#			#for othp in other_payments:
	#			#	if othp.id in ids:
	#			#		continue
	#			#	if othp.journal_id.id == journal_id.id:
	#			#		amount_invoice = amount_invoice + othp.debit
	#			voucher_id = self.pool.get('account.voucher').search(cr,uid,[('move_ids','=',move_line_credit.id)])
	#			if voucher_id:
	#				voucher = self.pool.get('account.voucher').browse(cr,uid,voucher_id)
	#				voucher_amount = voucher.amount
	#				if voucher_amount > amount_journal:
	#					raise Warning('El monto ingresado supera al monto estipulado en el pedido de ventas')
	#				other_payments = invoices[0].payment_ids
	#				for othp in other_payments:
	#					if othp.id in ids:
	#						continue
	#					if othp.journal_id.id == journal_id.id:
	#						amount_invoice = amount_invoice + othp.credit
	#				if (amount_invoice + voucher_amount) > amount_journal:
	#					raise Warning('El monto ingresado junto con los montos ya pagados\nsuperan al monto estipulado en el pedido de ventas')

class sale_order(models.Model):
	_name = 'sale.order'
	_inherit = 'sale.order'

	@api.v7
	def _prepare_invoice(self, cr, uid, order, lines, context=None):
        	"""
	        """
        	if context is None:
	            context = {}
        	invoice_vals = super(sale_order, self)._prepare_invoice(
	            cr, uid, order, lines, context)

        	partner_obj = self.pool.get('res.partner')
	        partner_id = invoice_vals['partner_id']
        	company_id = invoice_vals['company_id']

		partner = partner_obj.browse(cr,uid,partner_id)
		#import pdb;pdb.set_trace()

	        #journal_ids = partner_obj.prefered_journals(
        	#    cr, uid, [partner_id], 'out_invoice',
	        #    {'company_id': company_id}
        	#)

	        #if not journal_ids or not journal_ids[partner_id]:
        	#    raise Warning('Please define sales journal for this company:'
                #	          ' "%s" (id:%d).' %
                #        	  (order.company_id.name, order.company_id.id))

                user = self.pool.get('res.users').browse(cr,uid,uid)
                point_of_sale = user.branch_id.point_of_sale

                resp_id = partner.responsability_id.id
                resp = self.pool.get('account.responsabilities.mapping').search(cr,uid,[('responsability_id','=',resp_id),\
                                 ('point_of_sale','=',point_of_sale),('journal_type','=','sale'),\
                                 ('is_debit_note','=',False)])
                if resp:
			resp_obj = self.pool.get('account.responsabilities.mapping').browse(cr,uid,resp)
		        invoice_vals['journal_id'] = resp_obj.journal_id.id
	        return invoice_vals

sale_order()



class account_move_line_day(osv.osv):
        _name = "account.move.line.date"
        _description = "Account Move Line Date"
        _auto = False

        _columns = {
                'account_id': fields.many2one('account.account','Product'),
                'date': fields.date('Date'),
                'state': fields.char('State'),
                'debit': fields.float('Debit'),
                'credit': fields.float('Credit'),
                }

        def init(self, cr):
                tools.sql.drop_view_if_exists(cr, 'account_move_line_date')
                cr.execute("""
                        create view account_move_line_date as 
				select max(a.id) as id,a.account_id as account_id,a.date as date,a.state,
					sum(a.debit) as debit,sum(a.credit) as credit from account_move_line a
					group by 2,3,4
                        """)


class account_caja_diaria_journal_view(osv.osv):
        _name = "account.caja.diaria.journal.view"
        _description = "Account Caja Diaria Journal Vie"
        _auto = False

        _columns = {
                'caja_id': fields.many2one('account.caja.diaria','Caja'),
                'journal_id': fields.many2one('account.journal','Método de Pago'),
                'debit': fields.float('Qty'),
                }

        def init(self, cr):
                tools.sql.drop_view_if_exists(cr, 'account_caja_diaria_journal_view')
                cr.execute("""
                        create view account_caja_diaria_journal_view as 
                                select max(a.id) as id,a.caja_id as caja_id,a.caja_journal_id as journal_id,
					sum(debit) as debit
                                        from account_caja_diaria_journal_lineas a group by 2,3
                        """)


class account_invoice(osv.osv):
	_inherit = 'account.invoice'

	def write(self, cr, uid, ids, vals, context=None):
                res = super(account_invoice, self).write(cr,uid, ids, vals, context)
		if 'state' in vals.keys():
			if vals['state'] == 'open':
				for invoice_id in ids:
					invoice = self.pool.get('account.invoice').browse(cr,uid,invoice_id)
					move_line_voucher = None
					for move_line in invoice.move_id.line_id:
						if move_line.debit > 0:
							move_line_voucher = move_line
					if invoice.sale_order_id:
						if invoice.sale_order_id.payment:
							for payment_line in invoice.sale_order_id.payment:
								vals_voucher = {
									'partner_id': invoice.partner_id.id,
									'reference': payment_line.sale_id.name + ' - ' + payment_line.journal_id.name,
									'amount': payment_line.final_amount,
									'type': 'receipt',
									'account_id': payment_line.journal_id.default_debit_account_id.id,
									}
								voucher_id = self.pool.get('account.voucher').create(cr,uid,vals_voucher)			
								vals_voucher_line = {
									'voucher_id': voucher_id,
									'account_id': invoice.account_id.id,
									'amount': payment_line.final_amount,
									'amount_original': payment_line.final_amount,
									'move_line_id': move_line_voucher.id,
									'display_name': payment_line.sale_id.name + ' - ' + payment_line.journal_id.name,
									'partner_id': invoice.partner_id.id,
									'type': 'cr'
									}
								voucher_line_id = self.pool.get('account.voucher.line').create(cr,uid,vals_voucher_line)

		return res
