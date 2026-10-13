import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { MediaMatcher } from '@angular/cdk/layout';
import { NavigationEnd, Router, ActivatedRouteSnapshot } from '@angular/router';
import { filter } from 'rxjs';
import { CommonService } from '../../services/common.service';
import { Subscription } from 'rxjs';

/**
 * The CMS application shell: sidebar, title bar, and the routed screen.
 *
 * The CMS had no shell at all. HMS has hms/layout for this, but reusing it
 * would have dragged the hotel chrome and its hardcoded 'hms/' navigation into
 * the cafe product, so this is a small purpose-built equivalent.
 *
 * Wraps everything except POS and KDS, which stay full-bleed because a cashier
 * and a chef use them continuously and the chrome would cost them vertical
 * space. See cms-routing.module.ts.
 */
@Component({
  selector: 'app-cms-layout',
  templateUrl: './cms-layout.component.html',
  styleUrl: './cms-layout.component.scss'
})
export class CmsLayoutComponent implements OnInit, OnDestroy {

  private _common = inject(CommonService);
  private _router = inject(Router);
  private _subscription = new Subscription();

  /** CommonService exposes the name, not the whole profile record. */
  userName = '';
  isMobile = false;

  /** Taken from the deepest active route's `data.breadcrumb`. */
  breadcrumb = '';

  constructor(media: MediaMatcher) {
    this.userName = this._common.getUserFullName();
    // Single breakpoint, matching the HMS shell. The sidenav is a temporary
    // overlay below it and a permanent column above it.
    this.isMobile = !media.matchMedia('(min-width: 768px)').matches;
  }

  ngOnInit(): void {
    this.breadcrumb = this.readBreadcrumb();
    this._subscription.add(
      this._router.events
        .pipe(filter(event => event instanceof NavigationEnd))
        .subscribe(() => this.breadcrumb = this.readBreadcrumb())
    );
  }

  ngOnDestroy(): void {
    this._subscription.unsubscribe();
  }

  /**
   * Deepest route's breadcrumb.
   *
   * Parent and child routes both carry one -- /cms/inventory sets
   * 'Inventory Management' and /cms/inventory/list-category sets 'Category
   * List'. The deepest wins, which is what the reader expects.
   */
  private readBreadcrumb(): string {
    let route: ActivatedRouteSnapshot | null = this._router.routerState.snapshot.root;
    let breadcrumb = '';
    while (route) {
      const value = route.data?.['breadcrumb'];
      if (value) {
        breadcrumb = value;
      }
      route = route.firstChild;
    }
    return breadcrumb;
  }

  goHome(): void {
    this._router.navigate(['/cms', 'dashboard']);
  }
}