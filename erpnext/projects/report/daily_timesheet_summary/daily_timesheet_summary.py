# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.desk.reportview import build_match_conditions

def execute(filters=None):
	if not filters:
		filters = {}

	columns = get_column()
	conditions = get_conditions(filters)
	data = get_data(conditions, filters)

	return columns, data

def get_column():
	return [_("Timesheet") + ":Link/Timesheet:120", _("Employee") + "::150", _("Employee Name") + "::150", 
		_("Date") + "::140", _("Activity Type") + "::120", _("Hours") + "::70", 
		_("Project") + ":Link/Project:120", _("Task") + ":Link/Task:150", _("Status") + "::70"]

def get_data(conditions, filters):
	time_sheet = frappe.db.sql(""" select `tabTimesheet`.name, `tabTimesheet`.employee, `tabTimesheet`.employee_name,
		`tabTimesheet`.timesheet_date, `tabTimesheet Detail`.activity_type, `tabTimesheet Detail`.hours,
		`tabTimesheet Detail`.project, `tabTimesheet Detail`.task,
		`tabTimesheet`.status from `tabTimesheet Detail`, `tabTimesheet` where
		`tabTimesheet Detail`.parent = `tabTimesheet`.name and %s order by `tabTimesheet`.name"""%(conditions), filters, as_list=1)

	return time_sheet

def get_conditions(filters):
	conditions = "`tabTimesheet`.docstatus = 1"
	if filters.get("timesheet_date"):
		conditions += " and `tabTimesheet`.timesheet_date = timesheet_date"
	
	match_conditions = build_match_conditions("Timesheet")
	if match_conditions:
		conditions += " and %s" % match_conditions

	return conditions