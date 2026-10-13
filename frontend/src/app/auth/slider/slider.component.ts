import { Component, inject } from '@angular/core';
import { CommonService } from '../../services/common.service';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { LoginSlide } from '../../models/ICommon.model';

@Component({
  selector: 'app-slider',
  templateUrl: './slider.component.html',
  styleUrl: './slider.component.scss'
})
export class SliderComponent {

  private _common = inject(CommonService);
  private _snackbar = inject(CustomSnackbarService);

  slides: LoginSlide[] = [];


  ngOnInit(): void {
    this.getLoginSlider();
  }

  trackByIndex(index: number): number {
    return index;
  }

  private getLoginSlider() {
    this._common.getLoginSliderData().subscribe((respdata: any) => {
      if (respdata && respdata.status) {
        this.slides = respdata.data || [];
      } else {
        this._snackbar.openSnackBar(respdata.message || 'Failed to get slider data', 'error');
      }
    })
  }

}
