import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { InstanceService } from '../../core/config/instance.service';

/**
 * Shown when AuthGuard denies a route for lack of permission.
 *
 * This route previously did not exist. AuthGuard redirected to
 * `/unauthorized-access`, which fell through to `**` and rendered the 404
 * page -- so "you are not allowed to see this" and "this page does not exist"
 * looked identical, and users filed the wrong kind of bug report.
 *
 * Distinct from the 404 on purpose: 404 means the URL is wrong, 403 means the
 * URL is right and the account is not allowed. They need different copy.
 */
@Component({
  selector: 'app-unauthorized-access',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="container">
      <h1 class="error-code">403</h1>
      <div class="details">
        <h3>You don't have access to this page</h3>
        <h5>
          Your account doesn't include permission for this section.
          Ask an administrator if you think you should have it.
        </h5>
        <button type="button" class="home-btn" [routerLink]="homeUrl">
          Go to home
        </button>
      </div>
    </div>
  `,
  styles: [`
    .container {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      text-align: center;
      gap: 1rem;
      padding: 2rem;
    }
    .error-code {
      font-size: 6rem;
      font-weight: 700;
      margin: 0;
      color: #c0392b;
    }
    .details h3 { margin: 0; }
    .details h5 {
      margin: 0 0 1.5rem;
      font-weight: 400;
      color: #666;
    }
    .home-btn {
      padding: 0.6rem 1.4rem;
      cursor: pointer;
    }
  `]
})
export class UnauthorizedAccessComponent {

  /** Leads to the active instance's dashboard, not a hardcoded /hms path. */
  homeUrl = inject(InstanceService).homeUrl;

}