import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { convertToParamMap, ActivatedRoute } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of as observableOf } from 'rxjs';
import { SharedModule } from '../../shared/shared.module';
import { AppConfig } from '../../core/config/config';

import { ForgotPasswordComponent } from './forgot-password.component';

describe('ForgotPasswordComponent', () => {
  /// ActivatedRoute is injected by anything that reads route state. The
  /// scaffold only needs it to exist; the components under test are not
  /// exercised for navigation here.
  const activatedRouteStub = {
    snapshot: {
      paramMap: convertToParamMap({ id: '0' }),
      queryParamMap: convertToParamMap({}),
      url: ['/'],
      params: {},
      queryParams: {},
      data: {},
    },
    paramMap: observableOf(convertToParamMap({ id: '0' })),
    queryParamMap: observableOf(convertToParamMap({})),
    params: observableOf({}),
    queryParams: observableOf({}),
    url: observableOf(['/']),
    data: observableOf({}),
  };
  let component: ForgotPasswordComponent;
  let fixture: ComponentFixture<ForgotPasswordComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SharedModule, RouterTestingModule, NoopAnimationsModule],
      declarations: [ForgotPasswordComponent],
      providers: [
        /// Real backend module first so the app's own interceptors are in the
        /// chain, then the testing backend over it so nothing escapes to the
        /// network. Several of these components call a service in ngOnInit.
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: activatedRouteStub },
      ],
    })
    .compileComponents();
    
    /// Services read BASE_URL from AppConfig in their constructor and
    /// AppConfig throws when the key is missing.
    TestBed.inject(AppConfig).set('BASE_URL', 'http://localhost:5000');
    fixture = TestBed.createComponent(ForgotPasswordComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
