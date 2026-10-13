import { Component, inject, Inject } from '@angular/core';
import { INavigationaBar } from '../../../models/ICommon.model';
import { Router } from '@angular/router';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent {

	dashboardCards = [
	{
		title: 'Total Users',
		value: 128,
		route: '/hms/users',
		cssClass: 'users-card',
		icon: 'group'
	},
	{
		title: 'Total Rooms',
		value: 56,
		route: '/hms/rooms',
		cssClass: 'revenue-card',
		icon: 'meeting_room'
	},
	{
		title: 'Occupied Rooms',
		value: 25,
		route: '',
		cssClass: 'expired-card',
		icon: 'meeting_room'
	},
	{
		title: 'Available Rooms',
		value: 31,
		route: '',
		cssClass: 'reports-card',
		icon: 'meeting_room'
	},
	{
		title: 'Active Reservations',
		value: 23,
		route: '/hms/reservations',
		cssClass: 'orders-card',
		icon: 'event_available'
	},
	{
		title: 'Pending Payments',
		value: 7,
		route: '/hms/payments',
		cssClass: 'alerts-card',
		icon: 'payments'
	}
	];


	private _router = inject(Router)

	navData: INavigationaBar[] = [];

	ngOnInit(): void {
		this.initNavigation();
	}

	private initNavigation(): void {
		this.navData = [
			{ displayValue: 'Home', isClickable: false, isDashboard: false, redirectValue: '/hms/dashboard' }
		];
	}

	navigate(route: string): void {
		this._router.navigate([route]);
	}

}