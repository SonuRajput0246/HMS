import { TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { AppConfig } from '../core/config/config';

import { UserAccountService } from './user-account.service';

describe('UserAccountService', () => {
  let service: UserAccountService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        /// Real backend module first so the app's own interceptors are in
        /// the chain, then the testing backend layered over it so no
        /// request escapes to the network.
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    });
    /// Services read BASE_URL from AppConfig in their constructor and
    /// AppConfig throws when the key is missing, so seed it first. Same
    /// value as assets/config.json.
    TestBed.inject(AppConfig).set('BASE_URL', 'http://localhost:5000');
    service = TestBed.inject(UserAccountService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
