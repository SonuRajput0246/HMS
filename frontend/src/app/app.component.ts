import { Component } from '@angular/core';
import { CommonService } from './services/common.service';
import { InitialService } from './services/initial.service';
import { IAppSetting } from './models/IAppSettings.model';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {
  title = 'frontend';

}
