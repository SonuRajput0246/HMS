import { Component, inject, OnInit } from '@angular/core';
import { INavigationaBar } from '../../../models/ICommon.model';
import { Router } from '@angular/router';
import { IUserProfile } from '../../../models/IAuth.model';
import { UserAccountService } from '../../../services/user-account.service';
import { STORAGE_KEYS } from '../../../core/config/storage-keys';

@Component({
  selector: 'app-view-profile',
  templateUrl: './view-profile.component.html',
  styleUrl: './view-profile.component.scss'
})
export class ViewProfileComponent implements OnInit {

  private _router = inject(Router);
  private _accountService = inject(UserAccountService);

  navData: INavigationaBar[] = [];
  profile: IUserProfile = {};

  readonly avatar = 'assets/images/profile/Avtar_Profile2.jfif';

  ngOnInit(): void {
    this.initNavigation();
    this.loadProfile();

    // stay in sync with a save made on /hms/profile/edit
    this._accountService.user$.subscribe((user) => {
      if (user) {
        this.profile = user;
      }
    });
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      { displayValue: 'Profile', isClickable: false, isDashboard: false, redirectValue: '/hms/profile' }
    ];
  }

  private loadProfile(): void {
    // prefer the cached in-memory user, else fall back to storage
    let user: IUserProfile = {};
    this._accountService.user$.subscribe((u) => {
      if (u) {
        user = u;
      }
    }).unsubscribe();

    if (Object.keys(user).length === 0) {
      const stored = localStorage.getItem(STORAGE_KEYS.USER_DATA);
      if (stored) {
        try {
          user = JSON.parse(stored);
        } catch {
          user = {};
        }
      }
    }

    this.profile = user;
  }

  get fullName(): string {
    const name = `${this.profile.first_name || ''} ${this.profile.last_name || ''}`.trim();
    return name || 'Your profile';
  }

  onEdit(): void {
    this._router.navigate(['hms/profile/edit']);
  }

}
