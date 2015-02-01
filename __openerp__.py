{
    "name" : "Employee Payslip Voucher",
    "version" : "1.0", 
    "category" : "Human Resources", 
    "sequence": 60,
    "complexity" : "normal", 
    "author" : "ColourCog.com", 
    "website" : "http://colourcog.com", 
    "depends" : [
        "base", 
        "account_voucher",
        "hr_payroll_account",
        "account_accountant",
    ], 
    "summary" : "Create payment vouchers for employees", 
    "description" : """
Employee Payslip Voucher
========================
This module enables employees to be paid using standard vouchers/checks.

    """,
    "data" : [ 
        "hr_payslip_voucher_view.xml",
    ], 
    "application": False, 
    "installable": True
}

