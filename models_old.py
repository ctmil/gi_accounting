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

