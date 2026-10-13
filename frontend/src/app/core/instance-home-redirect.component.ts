import { AfterViewInit, Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { InstanceService } from './config/instance.service';

/**
 * Sends the bare `/` to whichever dashboard this deployment runs.
 *
 * A component, not a guard: `redirectTo` accepts only a static string, and a
 * route carrying nothing but `canActivate` is rejected during bootstrap with
 * NG04014, which validates every route eagerly and requires one of component /
 * loadComponent / redirectTo / children / loadChildren.
 *
 * The navigation is deferred to ngAfterViewInit rather than run in the
 * constructor. Navigating during construction happens mid-activation, while
 * the router is still finishing the previous navigation; that cancels it and
 * leaves the URL blank until the new navigation is picked up. Running after the
 * view is initialised means the router is idle.
 *
 * `replaceUrl` keeps the dashboard out of history, so Back leaves the app
 * instead of returning to `/` and bouncing here again.
 */
@Component({
  selector: 'app-instance-home-redirect',
  standalone: true,
  template: ''
})
export class InstanceHomeRedirectComponent implements AfterViewInit {

  private router = inject(Router);
  private instance = inject(InstanceService);

  ngAfterViewInit(): void {
    this.router.navigateByUrl(this.instance.homeUrl, { replaceUrl: true });
  }

}