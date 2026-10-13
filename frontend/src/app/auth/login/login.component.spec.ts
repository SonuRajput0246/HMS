import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { convertToParamMap, ActivatedRoute } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { of as observableOf } from 'rxjs';
import { SharedModule } from '../../shared/shared.module';
import { AppConfig } from '../../core/config/config';

import { AuthModule } from '../auth.module';
import { LoginComponent } from './login.component';

describe('LoginComponent', () => {
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
  let component: LoginComponent;
  let fixture: ComponentFixture<LoginComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SharedModule, RouterTestingModule, NoopAnimationsModule, AuthModule],
      /// AuthModule already declares LoginComponent, so it must not be
      /// declared again here -- Angular rejects the duplicate. Importing the
      /// real module is what supplies <app-slider>, which the login template
      /// renders and which the bare scaffold had no way to resolve.
      schemas: [CUSTOM_ELEMENTS_SCHEMA],
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
    fixture = TestBed.createComponent(LoginComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
