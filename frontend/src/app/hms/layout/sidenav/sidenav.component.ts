import { MediaMatcher } from '@angular/cdk/layout';
import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { CommonService } from '../../../services/common.service';
import { IUserMenuAccess, IUserProfile } from '../../../models/IUser.model';
import { Router } from '@angular/router';


@Component({
  selector: 'app-sidenav',
  templateUrl: './sidenav.component.html',
  styleUrl: './sidenav.component.scss'
})
export class SidenavComponent {

  private _router = inject(Router);

  authUser: IUserProfile = {} as IUserProfile;

  mobileQuery: MediaQueryList;
  private _mobileQueryListener: () => void;
  menuItems: any;

  constructor(
    changeDetectorRef: ChangeDetectorRef,
    media: MediaMatcher,
    private _common: CommonService
  ) {
    this.mobileQuery = media.matchMedia('(min-width: 768px)');
    this._mobileQueryListener = () => changeDetectorRef.detectChanges();
    this.mobileQuery.addListener(this._mobileQueryListener);
    this.menuItems = this._common.getMenuAccess();
  }

  ngOnDestroy(): void {
    this.mobileQuery.removeListener(this._mobileQueryListener);
  }

  onMenuLoad(item: IUserMenuAccess) {
    if (item.route_path) {
      this._router.navigate(['hms/' + item.route_path])
      this.ResetMenu(item);
    }

    
  }


  ResetMenu(item: any) {
    if (this.authUser && this.authUser.menu_access) {
      this.authUser.menu_access.forEach(element => {
        element.extraBoolValue = false;
      })
    }
    item.extraBoolValue = true;
  }


  
}
