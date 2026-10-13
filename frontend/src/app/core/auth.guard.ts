import { Injectable } from '@angular/core';
import { ActivatedRouteSnapshot, Router } from '@angular/router';
import { CommonService } from '../services/common.service';
import { STORAGE_KEYS } from './config/storage-keys';


@Injectable({
  providedIn: 'root'
})
export class AuthGuard {
    constructor(private router: Router) {}

    canActivate(route: ActivatedRouteSnapshot): boolean {

        const token = sessionStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);

        if (!token) {
            sessionStorage.clear();
            this.router.navigate(['/auth/login'], { replaceUrl: true });
            return false;
        }

        const menuId = route.data?.['menuId'];
        if (!menuId) {
            return true;
        }

        const userData = localStorage.getItem(STORAGE_KEYS.USER_DATA);
        if (!userData) {
            this.router.navigate(['/auth/login'], { replaceUrl: true });
            return false;
        }

        const userProfile = JSON.parse(userData);
        const hasAccess = userProfile?.menu_access?.some(
            (x: any) => x.module_id === menuId
        );

        if (!hasAccess) {
            this.router.navigate(['/unauthorized-access'], { replaceUrl: true });
            return false;
        }

        return true;
    }
}