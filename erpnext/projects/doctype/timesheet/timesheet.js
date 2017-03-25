// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt
cur_frm.add_fetch('employee', 'employee_name', 'employee_name');

frappe.ui.form.on("Timesheet", {
	setup: function(frm) {
		frm.fields_dict.employee.get_query = function() {
			return {
				filters:{
					'status': 'Active'
				}
			}
		}

		frm.fields_dict['time_logs'].grid.get_field('task').get_query = function(frm, cdt, cdn) {
			child = locals[cdt][cdn];
			return{
				filters: {
					'project': child.project,
					'status': ["!=", "Closed"]
				}
			}
		}

		frm.fields_dict['time_logs'].grid.get_field('project').get_query = function() {
			return{
				filters: {
					'company': frm.doc.company
				}
			}
		}
	},

	onload: function(frm){
		if (frm.doc.__islocal && frm.doc.time_logs) {
			calculate_time_and_amount(frm);
		}
		if(frm.doc.__islocal) cur_frm.set_value("timesheet_date", get_today());
	},

	refresh: function(frm) {
		get_attendance_data(frm);
	},

	timesheet_date: function(frm){
		get_attendance_data(frm);
	},
	
	employee: function(frm){
		get_attendance_data(frm);
	}
	
})

frappe.ui.form.on("Timesheet Detail", {
	time_logs_remove: function(frm) {
		calculate_time_and_amount(frm);
	},

	hours: function(frm, cdt, cdn) {
		calculate_time_and_amount(frm);
	}
});

var calculate_time_and_amount = function(frm) {
	var tl = frm.doc.time_logs || [];
	total_working_hr = 0;
	for(var i=0; i<tl.length; i++) {
		if (tl[i].hours) {
			total_working_hr += tl[i].hours;
		}
	}

	cur_frm.set_value("total_hours", total_working_hr);
}

var get_attendance_data = function(frm) {
	if (!frm.doc.employee || !frm.doc.timesheet_date)
		return;
	
	frappe.call({
		method: "erpnext.projects.doctype.timesheet.timesheet.get_attendance_data",
		args: {
			employee: frm.doc.employee,
			att_date: frm.doc.timesheet_date
		},
		callback: function(r){
			if(r.message){
				cur_frm.set_value('total_att_hours', r.message['total_att_hours']);
			}
		}
	});
}