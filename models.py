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

class res_branch(models.Model):
	_inherit = 'res.branch'

	@api.one
	@api.constraint('point_of_sale')
	def _check_unique_constraint(self):
        	if len(self.search(['point_of_sale', '=', self.point_of_sale])) > 1:
                	raise ValidationError("Punto de venta ya existente")

	point_of_sale = fields.Integer('Punto de Venta')
