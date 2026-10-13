import { Component, inject, Input, OnChanges, SimpleChanges } from '@angular/core';
import { Router } from '@angular/router';
import { INavigationaBar } from '../../models/ICommon.model';



@Component({
  selector: 'app-navigation-bar',
  templateUrl: './navigation-bar.component.html',
  styleUrl: './navigation-bar.component.scss'
})
export class NavigationBarComponent implements OnChanges {

  private _router = inject(Router);

  @Input() navData?: INavigationaBar[];

  isDashboard?: boolean;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['navData']?.currentValue?.length) {
      this.isDashboard = changes['navData'].currentValue[0].isDashboard;
    }
  }

  OnNavClick(item: INavigationaBar) {
    if (item.isClickable && item.redirectValue) {
      this._router.navigateByUrl(item.redirectValue);
    }
  }
}

