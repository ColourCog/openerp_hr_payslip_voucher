#-*- coding:utf-8 -*-

import time
from openerp import netsvc

from openerp.osv import fields, osv
from openerp import pooler
from openerp.tools.translate import _


class hr_payslip_line(osv.osv):
    _inherit = 'hr.payslip.line'

    _columns = {
        'voucher_id': fields.many2one('account.voucher', 'Payment voucher', readonly=True),
    }

hr_payslip_line()


class hr_payslip(osv.osv):
    '''
    Pay Slip
    '''
    _inherit = 'hr.payslip'
    _description = 'Pay Slip'


    def _get_default_journal(self, cr, uid, context=None):
        model_data = self.pool.get('ir.model.data')
        res = model_data.search(cr, uid, [('name', '=', 'expenses_journal')])
        if res:
            return model_data.browse(cr, uid, res[0]).res_id
        return False

    _defaults = {
        'journal_id': _get_default_journal,
    }


    def cancel_sheet(self, cr, uid, ids, context=None):
        voucher_pool = self.pool.get('account.voucher')
        voucher_ids = []
        voucher_to_cancel = []
        for slip in self.browse(cr, uid, ids, context=context):
            for line in slip.details_by_salary_rule_category:
                if line.voucher_id:
                    voucher_ids.append(line.voucher_id.id)
                    if line.voucher_id.state == 'posted':
                        voucher_to_cancel.append(line.voucher_id.id)
        voucher_pool.cancel_voucher(cr, uid, voucher_to_cancel, context=context)
        voucher_pool.unlink(cr, uid, voucher_ids, context=context)
        return super(hr_payslip, self).cancel_sheet(cr, uid, ids, context=context)

    def _add_default_partner(self, cr, uid, ids, context):
        move_line_obj = self.pool.get('account.move.line')
        for slip_id in self.browse(cr, uid, ids, context=context):
            default_partner_id = slip_id.employee_id.address_home_id.id
            if slip_id.move_id:
                for line in slip_id.move_id.line_id:
                    if not line.partner_id:
                        move_line_obj.write(cr, uid, [line.id], {'partner_id': default_partner_id})
        return True

    def _create_voucher(self, cr, uid, line_ids, context):
        if not context:
            context = {}
        voucher_obj = self.pool.get('account.voucher')
        line_obj = self.pool.get('hr.payslip.line')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id

        for line in line_obj.browse(cr, uid, line_ids, context=context):
            ctx = context.copy()
            ctx.update({'account_period_prefer_normal': True})
            if not line.slip_id.employee_id.address_home_id:
                raise osv.except_osv(
                    _('Linked Partner Missing!'),
                    _("Payslip voucher creation requires '%s' to have a valid Home Adress!" % line.slip_id.employee_id.name))
            name = _('Payslip of %s') % (line.slip_id.employee_id.name)
            credit_account_id = line.salary_rule_id.account_credit.id
            default_partner_id = line.slip_id.employee_id.address_home_id.id
            partner_id = line.salary_rule_id.register_id.partner_id and line.salary_rule_id.register_id.partner_id.id or default_partner_id
            amt = line.slip_id.credit_note and -line.total or line.total
            move_line_id = move_line_obj.search(
                    cr,
                    uid,
                    [
                        ('move_id','=', line.slip_id.move_id.id),
                        ('name','=',line.name)],
                    context=ctx)[0]
            voucher = {
                'journal_id': line.salary_rule_id.bank_id.journal_id.id,
                'company_id': company_id,
                'partner_id': partner_id,
                'type': 'payment',
                'name': name,
                'account_id': line.salary_rule_id.bank_id.journal_id.default_credit_account_id.id,
                'amount': amt > 0.0 and amt or 0.0,
                'date': context.get('voucher_date', line.slip_id.date_to),
                'date_due': line.slip_id.date_to,
                'period_id': period_obj.find(
                    cr,
                    uid,
                    line.slip_id.date_to,
                    context=ctx)[0]
                }

            vl = (0, 0, {
                'name': line.name,
                'move_line_id': move_line_id,
                'reconcile': True,
                'amount': amt > 0.0 and amt or 0.0,
                'account_id': credit_account_id,
                'type': amt > 0.0 and 'dr' or 'cr',
                })
            voucher['line_ids'] = [vl]
            voucher_id = voucher_obj.create(cr, uid, voucher, context=ctx)
            move_id = voucher_obj.browse(cr, uid, voucher_id, context=ctx).move_id.id
            # post the journal entry if 'Skip 'Draft' State for Manual Entries' is checked
            if line.salary_rule_id.bank_id.journal_id.entry_posted:
                move_obj.button_validate(cr, uid, [move_id], context)
            line_obj.write(cr, uid, [line.id], {'voucher_id': voucher_id})
        return True

    def process_sheet(self, cr, uid, ids, context=None):
        make_voucher_for_ids = []
        super(hr_payslip, self).process_sheet(cr, uid, ids, context=context)

        for slip in self.browse(cr, uid, ids, context=context):
            for line in slip.details_by_salary_rule_category:
                # Check if we must and can create a voucher for this
                # line and cache it for later
                if line.salary_rule_id.make_voucher:
                    if not line.salary_rule_id.bank_id:
                        raise osv.except_osv(
                            _('Missing Bank!'),
                            _("Rule '%s' requests a voucher to be created but there is no payment bank defined!" % line.salary_rule_id.name))
                    make_voucher_for_ids.append(line.id)
        # fix missing partner_id for move lines
        self._add_default_partner(cr, uid, ids,context=context)
        if make_voucher_for_ids:
            self._create_voucher(cr, uid, make_voucher_for_ids, context=context)
        return True

hr_payslip()

class hr_salary_rule(osv.osv):
    _inherit = 'hr.salary.rule'
    _columns = {
        'make_voucher':fields.boolean('Create Voucher', help=_("If this is checked, a payment voucher will be created using this rule's credit account ")),
        'bank_id': fields.many2one('res.partner.bank', 'Payment Bank',help=_("The Bank wich will be used to pay the voucher")),
    }
hr_salary_rule()

class hr_payslip_confirm(osv.osv_memory):
    """
    This wizard will confirm the all the selected draft invoices
    """

    _name = "hr.payslip.confirm"
    _description = "Confirm the selected playslips"

    _columns = {
        'voucher_date': fields.date('Pay on the'),
    }

    _defaults = {
        'voucher_date': time.strftime('%Y-%m-01'),
    }

    def confirm_slips(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        pool_obj = pooler.get_pool(cr.dbname)
        slip_obj = pool_obj.get('hr.payslip')
        slips = slip_obj.read(cr, uid, context['active_ids'], ['state'], context=context)

        context.update({
            'voucher_date': self.browse(cr,uid,ids)[0].voucher_date,
            })

        for record in slips:
            slip_obj.hr_verify_sheet(cr, uid, [record['id']],context=context)
            slip_obj.process_sheet(cr, uid, [record['id']],context=context)
        return {'type': 'ir.actions.act_window_close'}

hr_payslip_confirm()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
