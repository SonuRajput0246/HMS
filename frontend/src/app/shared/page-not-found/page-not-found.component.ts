import { Component, inject } from '@angular/core';
import { InstanceService } from '../../core/config/instance.service';

@Component({
  selector: 'app-page-not-found',
  templateUrl: './page-not-found.component.html',
  styleUrl: './page-not-found.component.scss'
})
export class PageNotFoundComponent {

  /** Where "Go to home" should lead on the instance that is actually running. */
  homeUrl = inject(InstanceService).homeUrl;

}