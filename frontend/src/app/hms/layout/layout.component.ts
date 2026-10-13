import { MediaMatcher } from '@angular/cdk/layout';
import { ChangeDetectorRef, Component } from '@angular/core';


@Component({
  selector: 'app-layout',
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.scss'
})
export class LayoutComponent {
  mobileQuery: MediaQueryList;

  private _mobileQueryListerner: () => void;

  constructor(
    changeDetectorRef: ChangeDetectorRef,
    media: MediaMatcher
  ) {
    this.mobileQuery = media.matchMedia('(min-width: 768px)');
    this._mobileQueryListerner = () => changeDetectorRef.detectChanges();
    this.mobileQuery.addListener(this._mobileQueryListerner);
  }

  ngOnDestroy(): void {
    this.mobileQuery.removeListener(this._mobileQueryListerner);
  }

}
