import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { CommonService } from '../../services/common.service';
import { IUserMenuAccess } from '../../models/IUser.model';

import { CmsMenuItem, cmsMenuFor } from '../cms-menu';

/**
 * The CMS sidebar.
 *
 * Reads the signed-in user's menu_access and shows only what this deployment
 * can actually navigate to. See cms-menu.ts for why it cannot render the access
 * list directly.
 *
 * Deliberately NOT a reuse of hms/layout/sidenav: that one navigates to
 * ['hms/' + route_path], and /hms is canMatch-gated, so every link it built
 * would 404 here.
 */
@Component({
  selector: 'app-cms-sidenav',
  templateUrl: './cms-sidenav.component.html',
  styleUrl: './cms-sidenav.component.scss'
})
export class CmsSidenavComponent {

  private _common = inject(CommonService);
  private _router = inject(Router);

  /** One row per navigable destination this role may reach. */
  menu: CmsMenuItem[] = [];

  /**
   * Modules the role holds that have no CMS screen.
   *
   * Not rendered. Held so the gap is inspectable rather than silent -- a role
   * granted TEMPLATE with no template screen is a real shortfall, and a menu
   * that quietly disagrees with the role editor is how it goes unnoticed.
   */
  hiddenModuleNames: string[] = [];

  constructor() {
    const access = this._common.getMenuAccess() as IUserMenuAccess[] | null;

    this.menu = cmsMenuFor(access);

    const navigable = new Set(this.menu.map(item => item.moduleName));
    this.hiddenModuleNames = (access ?? [])
      .map(item => item.module_name)
      .filter(name => !navigable.has(name));
  }

  /** Path of a row, absolute, for routerLink. */
  urlFor(item: CmsMenuItem): string[] {
    return ['/cms', item.entry.path];
  }

  /** Programmatic navigation, for the keyboard path. */
  go(item: CmsMenuItem): void {
    this._router.navigate(this.urlFor(item));
  }
}