#-*- coding:utf-8 -*-
from openerp.osv import fields, osv

class hr_employee(osv.osv):
    _inherit = "hr.employee"

    _columns = {
        # we need this field for it all to work, so make it compulsory
        'address_home_id': fields.many2one('res.partner', 'Home Address', required=True),
    }

hr_employee()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
