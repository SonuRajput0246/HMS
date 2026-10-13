import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, NavigationEnd, Router } from '@angular/router';
import { INavigationaBar } from '../../../models/ICommon.model';
import { filter } from 'rxjs/operators';
import { InstanceService } from '../../../core/config/instance.service';


@Component({
  selector: 'app-inventory-dashboard',
  templateUrl: './inventory-dashboard.component.html',
  styleUrl: './inventory-dashboard.component.scss'
})
export class InventoryDashboardComponent implements OnInit {

  private _router = inject(Router)
  private AR = inject(ActivatedRoute)
private _instance = inject(InstanceService)

  navData: INavigationaBar[] = [];
  selectedTabIndex = 0;


  ngOnInit(): void {
    this.initNavigation();
    this.updateBreadcrumbs();
    this.setCurrentTabBasedOnUrl(this._router.url);
    this.listenToRouteChanges();
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: this._instance.homeUrl },
      { displayValue: 'Inventory Management', isClickable: false, isDashboard: false }
    ];
  }


  onTabChange(index: number) {

    if (index === this.selectedTabIndex) {
      return;
    }
    const targetRoute =
      index === 0 ? 'list-category' : 'list-inventory';

    this._router.navigate([targetRoute], { relativeTo: this.AR });
  }

  // private setCurrentTabBasedOnUrl(url: string): void {
  //   if (url.includes('list-inventory')) {
  //     this.selectedTabIndex = 1;
  //   } else {
  //     this.selectedTabIndex = 0;
  //   }
  // }

  // private listenToRouteChanges(): void {
  //   this._router.events
  //     .pipe(
  //       filter((event): event is NavigationEnd => event instanceof NavigationEnd))
  //     .subscribe((event) => {
  //       // this.setCurrentTabBasedOnUrl(event.urlAfterRedirects);
  //       this.selectedTabIndex = event.urlAfterRedirects.includes('list-inventory') || event.urlAfterRedirects.includes('manage-inventory') ? 1 : 0;

  //       this.updateBreadcrumbs();
  //     });
  // }


  private setCurrentTabBasedOnUrl(url: string): void {
    // We check if the current URL contains any of the keywords associated with Tab 1
    const inventoryKeywords = ['list-inventory', 'add-inventory', 'update-inventory'];
    const isInventoryTab = inventoryKeywords.some(keyword => url.includes(keyword));

    this.selectedTabIndex = isInventoryTab ? 1 : 0;
  }

  private listenToRouteChanges(): void {
    this._router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd)
      )
      .subscribe((event) => {
        // Reuse the logic here to keep things consistent
        this.setCurrentTabBasedOnUrl(event.urlAfterRedirects);
        this.updateBreadcrumbs();
      });
  }

  private updateBreadcrumbs(): void {
    const baseCrumbs: INavigationaBar[] = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: this._instance.homeUrl },
      { displayValue: 'Inventory Management', isClickable: false, isDashboard: false }
    ];

    let route = this.AR.firstChild;
    while (route?.firstChild) {
      route = route.firstChild;
    }

    const childLabel = route?.snapshot.data['breadcrumb'];
    
    if (childLabel) {
      this.navData = [
        ...baseCrumbs,
        { displayValue: childLabel, isClickable: false, isDashboard: false }
      ]
    } else {
      this.navData = baseCrumbs;
    }
  }



}
