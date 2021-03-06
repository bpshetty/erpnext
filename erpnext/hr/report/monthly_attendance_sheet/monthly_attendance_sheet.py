# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, getdate
from frappe import msgprint, _
from calendar import monthrange
from datetime import date

def execute(filters=None):
	if not filters: filters = {}

	conditions, filters = get_conditions(filters)
	columns = get_columns(filters)
	att_map = get_attendance_list(conditions, filters)
	emp_map = get_employee_details(filters)
	holidays_list = get_holidays(filters)
	
	data = []
	for emp in sorted(emp_map):
		emp_det = emp_map.get(emp)
		emp_att_det = att_map.get(emp)
		
		if not emp_att_det:
			continue
		
		row = [emp, emp_det.employee_name, emp_det.date_of_joining]
		
		date_of_joining = emp_det.date_of_joining
		relieving_date = emp_det.relieving_date
		today = getdate()
		
		total_p = total_a = total_l = 0.0
		for day in range(filters["total_days_in_month"]):
			dateassessed = date(cint(filters.year), filters.month, day + 1)
			
			if (dateassessed > today):
				break

			att_det = emp_att_det.get(day + 1)
			if (not att_det):
				if (dateassessed in holidays_list):
					status = "Holiday"
				elif ((date_of_joining and dateassessed < date_of_joining) or (relieving_date and dateassessed > relieving_date)):
					status = "None"
				elif (is_leaveapplied(emp, dateassessed)):
					status = "On Leave"
				else:
					status = "Absent"
			else:
				status = att_det["status"]
				if (status == "Approved"):
					status = "Present";
				if (status == "Present"):
					if (att_det["total_time"].seconds < 14400):
						status = "Absent"
					elif (att_det["total_time"].seconds >= 14400 and att_det["total_time"].seconds <= 30600):
						status = "Half Day"
					
			status_map = {"Present": "P", "Absent": "A", "Half Day": "H", "On Leave": "L", "Holiday": "HL", "None": ""}
			row.append(status_map[status])

			if (status == "Present" or status == "Holiday"):
				total_p += 1
			elif status == "Absent":
				total_a += 1
			elif status == "On Leave":
				total_l += 1	
			elif status == "Half Day":
				total_p += 0.5
				total_a += 0.5
	
		row += [total_p, total_l, total_a]

		data.append(row)
	
	return columns, data

def get_columns(filters):
	columns = [
		_("Employee") + ":Link/Employee:120", _("Employee Name") + "::140", _("Date of Joining")+ "::120"
	]

	today = getdate()
	for day in range(filters["total_days_in_month"]):
		dateassessed = date(cint(filters.year), filters.month, day + 1)
		
		if (dateassessed > today):
			break
			
		columns.append(cstr(day+1) +"::20")

	columns += [_("Total Present") + ":Float:80", _("Total Leaves") + ":Float:80",  _("Total Absent") + ":Float:80"]
	return columns

def get_attendance_list(conditions, filters):
	attendance_list = frappe.db.sql("""select employee, day(attendance_date) as day_of_month,
		status, swipe_in_time, swipe_out_time from tabAttendance where docstatus = 1 %s order by employee, attendance_date""" %
		conditions, filters, as_dict=1)

	att_map = {}
	for d in attendance_list:
		att_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		att_map[d.employee][d.day_of_month] = { "status": d.status, "total_time": d.swipe_out_time - d.swipe_in_time }

	return att_map

def get_conditions(filters):
	if not (filters.get("month") and filters.get("year")):
		msgprint(_("Please select month and year"), raise_exception=1)

	filters["month"] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
		"Dec"].index(filters.month) + 1

	filters["total_days_in_month"] = monthrange(cint(filters.year), filters.month)[1]
	filters["month_startdate"] = date(cint(filters.year), filters.month, 1)
	filters["month_end_date"] = date(cint(filters.year), filters.month, filters["total_days_in_month"])

	conditions = " and month(attendance_date) = %(month)s and year(attendance_date) = %(year)s"

	if filters.get("employee"): conditions += " and employee = %(employee)s"

	return conditions, filters

def get_employee_details(filters):
	emp_map = frappe._dict()
	for d in frappe.db.sql("""select name, employee_name, designation,
							department, branch, company, date_of_joining, relieving_date
							from tabEmployee where ((date_of_joining <= %(start)s) or (date_of_joining between %(start)s and %(end)s)) 
								and ((relieving_date is null) or ((relieving_date >= %(end)s) or (relieving_date between %(start)s and %(end)s)))""", 
							{ "start": filters["month_startdate"], "end": filters["month_end_date"] }, as_dict=1):
		emp_map.setdefault(d.name, d)

	return emp_map

def get_holidays(filters):
	
	holiday_filter = {"holiday_date": (">=", filters["month_startdate"]),
				"holiday_date": ("<=", filters["month_end_date"])}
		
	holidays = frappe.get_all("Holiday", fields=["holiday_date"],
				filters=holiday_filter)

	holidays_list = []

	for holiday in holidays:
		holidays_list.append(holiday.holiday_date)
		
	return holidays_list

def is_leaveapplied(employee, dateassessed):
	leave_app_filter = [["from_date", ">=", dateassessed], ["to_date", "<=", dateassessed], ["half_day", "=", "0"], ["employee", "=", employee], ["docstatus", "=", "1"]]
		
	leave_app_data = frappe.get_list("Leave Application", "name", filters=leave_app_filter)

	return True if leave_app_data else False
	
@frappe.whitelist()
def get_attendance_years():
	year_list = frappe.db.sql_list("""select distinct YEAR(attendance_date) from tabAttendance ORDER BY YEAR(attendance_date) DESC""")
	if not year_list:
		year_list = [getdate().year]

	return "\n".join(str(year) for year in year_list)
