# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
	if not filters: filters = {}

	columns = get_columns()
	attendance_data = get_attendance(filters)

	data = []
	for attendance in attendance_data:
		employee_name = '<a href="#Form/Employee/{0}" style="font-weight: bold;">{1}</a>'.format(attendance.employee, attendance.employee_name)
		attendance_date = '<a href="#Form/Attendance/{0}" style="font-weight: bold;">{1}</a>'.format(attendance.name, attendance.attendance_date)
		total_time = attendance.swipe_out_time - attendance.swipe_in_time;
		row = [employee_name, attendance_date, attendance.swipe_in_time, attendance.swipe_out_time, total_time]
		data.append(row)

	return columns, data


def get_columns():
	return [
		_("Employee Name") + "::140",
		_("Date") + "::100",
		_("In Time") + "::100",
		_("Out Time") + "::100",
		_("Total Time") + "::100",
		_("Status") + "::100"
	]

def get_attendance(filters):
	conditions = " attendance_date between %(from_date)s and %(to_date)s "

	if filters.get("employee"): conditions += " and employee = %(employee)s "
	
	attendance_data = frappe.db.sql("""select name, attendance_date, employee, employee_name, swipe_in_time, swipe_out_time, status 
										from tabAttendance where %s order by attendance_date desc""" %conditions, filters, as_dict=1)

	return attendance_data
	