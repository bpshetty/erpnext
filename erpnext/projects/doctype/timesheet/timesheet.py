# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

import json
from datetime import timedelta
from erpnext.controllers.queries import get_match_cond
from frappe.utils import flt, time_diff_in_hours, get_datetime, getdate, cint, get_datetime_str, nowdate, nowtime, to_timedelta
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

class OverlapError(frappe.ValidationError): pass
class OverProductionLoggedError(frappe.ValidationError): pass

class Timesheet(Document):
	def validate_duplicate_record(self):
		existing = frappe.db.sql("""select name from `tabTimesheet` where employee = %s and timesheet_date = %s
			and name != %s and docstatus < 2""",
			(self.employee, self.timesheet_date, self.name))
		if existing:
			frappe.throw(_("Timesheet for employee {0} on {1} already exists in the system.").format(self.employee_name, self.timesheet_date))

	def validate_time_against_attendance(self):
		attendance = frappe.db.sql("""select swipe_in_time, swipe_out_time from `tabAttendance` where employee = %s and att_date = %s and docstatus < 2""",
							(self.employee, self.timesheet_date), as_dict=True)
		if not attendance:
			frappe.throw(_("Attendance data for employee {0} on {1} does not exists in the system, hence cannot save this timesheet.").format(self.employee_name, self.timesheet_date))
			
		swipe_in_time = attendance[0].swipe_in_time
		swipe_out_time = attendance[0].swipe_out_time
		
		today = nowdate()
		if getdate(self.timesheet_date) == getdate(today):
			swipe_out_time = nowtime()
			
		total_attendance_hours = round(float((to_timedelta(swipe_out_time) - to_timedelta(swipe_in_time)).total_seconds()) / 3600, 2)
		total_timesheet_hours = self.total_hours
		
		if (total_timesheet_hours > total_attendance_hours):
			frappe.throw(_("Total hours entered against all activities for {0} is greater than your Total working hours for the day.").format(self.timesheet_date))
	
	def onload(self):
		self.get("__onload").maintain_bill_work_hours_same = frappe.db.get_single_value('HR Settings', 'maintain_bill_work_hours_same')

	def validate(self):
		self.set_employee_name()
		self.validate_duplicate_record()
		self.set_status()
		self.calculate_total_amounts()
		self.validate_time_against_attendance()

	def set_employee_name(self):
		if self.employee and not self.employee_name:
			self.employee_name = frappe.db.get_value('Employee', self.employee, 'employee_name')

	def calculate_total_amounts(self):
		self.total_hours = 0.0

		for d in self.get("time_logs"):
			self.total_hours += flt(d.hours)

	def set_status(self):
		self.status = {
			"0": "Draft",
			"1": "Submitted",
			"2": "Cancelled"
		}[str(self.docstatus or 0)]

	def before_cancel(self):
		self.set_status()

	def on_cancel(self):
		self.update_task_and_project()

	def on_submit(self):
		self.validate_mandatory_fields()
		self.update_task_and_project()

	def validate_mandatory_fields(self):
		for data in self.time_logs:
			if not data.activity_type and self.employee:
				frappe.throw(_("Row {0}: Activity Type is mandatory.").format(data.idx))

			if flt(data.hours) == 0.0:
				frappe.throw(_("Row {0}: Hours value must be greater than zero.").format(data.idx))

	def update_task_and_project(self):
		for data in self.time_logs:
			if data.task:
				task = frappe.get_doc("Task", data.task)
				task.update_time_and_costing()
				task.save()

			elif data.project:
				frappe.get_doc("Project", data.project).update_project()

@frappe.whitelist()
def get_projectwise_timesheet_data(project, parent=None):
	cond = ''
	if parent:
		cond = "and parent = %(parent)s"

	return frappe.db.sql("""select name, parent, hours 
			from `tabTimesheet Detail` where docstatus=1 and project = %(project)s {0} and billable = 1
			and sales_invoice is null""".format(cond), {'project': project, 'parent': parent}, as_dict=1)

@frappe.whitelist()
def get_timesheet(doctype, txt, searchfield, start, page_len, filters):
	if not filters: filters = {}

	condition = ""
	if filters.get("project"):
		condition = "and tsd.project = %(project)s"

	return frappe.db.sql("""select distinct tsd.parent from `tabTimesheet Detail` tsd,
			`tabTimesheet` ts where 
			ts.status in ('Submitted', 'Payslip') and tsd.parent = ts.name and 
			tsd.docstatus = 1 
			and tsd.parent LIKE %(txt)s {condition}
			order by tsd.parent limit %(start)s, %(page_len)s"""
			.format(condition=condition), {
				"txt": "%%%s%%" % frappe.db.escape(txt),
				"start": start, "page_len": page_len, 'project': filters.get("project")
			})

@frappe.whitelist()
def get_timesheet_data(name, project):
	if project and project!='':
		data = get_projectwise_timesheet_data(project, name)
	else:
		data = frappe.get_all('Timesheet', 
			fields = ["total_hours"], filters = {'name': name})

	return {
		'total_hours': data[0].total_hours,
		'timesheet_detail': data[0].name if project and project!= '' else None
	}

@frappe.whitelist()
def make_sales_invoice(source_name, target=None):
	target = frappe.new_doc("Sales Invoice")
	timesheet = frappe.get_doc('Timesheet', source_name)

	target.append('timesheets', {
		'time_sheet': timesheet.name,
		'billing_hours': flt(timesheet.total_billable_hours) - flt(timesheet.total_billed_hours),
		'billing_amount': flt(timesheet.total_billable_amount) - flt(timesheet.total_billed_amount)
	})

	target.run_method("calculate_billing_amount_for_timesheet")

	return target

@frappe.whitelist()
def make_salary_slip(source_name, target_doc=None):
	target = frappe.new_doc("Salary Slip")
	set_missing_values(source_name, target)	
	target.run_method("get_emp_and_leave_details")

	return target

def set_missing_values(time_sheet, target):
	doc = frappe.get_doc('Timesheet', time_sheet)
	target.employee = doc.employee
	target.employee_name = doc.employee_name
	target.salary_slip_based_on_timesheet = 1
	target.start_date = doc.start_date
	target.end_date = doc.end_date
	target.posting_date = doc.modified

@frappe.whitelist()
def get_attendance_data(employee, att_date):
	att_data = frappe.db.get_values("Attendance", {"employee": employee,
									"att_date": att_date}, ["swipe_in_time", "swipe_out_time"], as_dict=True)
	if att_data:
		swipe_in_time = att_data[0].swipe_in_time
		swipe_out_time = att_data[0].swipe_out_time
		
		today = nowdate()
		if getdate(att_date) == getdate(today):
			swipe_out_time = nowtime()
			
		total_attendance_hours = round(float((to_timedelta(swipe_out_time) - to_timedelta(swipe_in_time)).total_seconds()) / 3600, 2)

	return {total_attendance_hours} if att_data else {}

@frappe.whitelist()
def get_events(start, end, filters=None):
	"""Returns events for Gantt / Calendar view rendering.
	:param start: Start date-time.
	:param end: End date-time.
	:param filters: Filters (JSON).
	"""
	filters = json.loads(filters)

	conditions = get_conditions(filters)
	return frappe.db.sql("""select `tabTimesheet Detail`.name as name, 
			`tabTimesheet Detail`.docstatus as status, `tabTimesheet Detail`.parent as parent,
			from_time as start_date, hours, activity_type, project, to_time as end_date, 
			CONCAT(`tabTimesheet Detail`.parent, ' (', ROUND(hours,2),' hrs)') as title 
		from `tabTimesheet Detail`, `tabTimesheet` 
		where `tabTimesheet Detail`.parent = `tabTimesheet`.name 
			and `tabTimesheet`.docstatus < 2 
			and (from_time <= %(end)s and to_time >= %(start)s) {conditions} {match_cond}
		""".format(conditions=conditions, match_cond = get_match_cond('Timesheet')), 
		{
			"start": start,
			"end": end
		}, as_dict=True, update={"allDay": 0})

def get_conditions(filters):
	conditions = []
	abbr = {'employee': 'tabTimesheet', 'project': 'tabTimesheet Detail'}
	for key in filters:
		if filters.get(key):
			conditions.append("`%s`.%s = '%s'"%(abbr.get(key), key, filters.get(key)))

	return " and {}".format(" and ".join(conditions)) if conditions else ""
