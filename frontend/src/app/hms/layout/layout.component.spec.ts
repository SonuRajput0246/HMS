import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { convertToParamMap, ActivatedRoute } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of as observableOf } from 'rxjs';
import { SharedModule } from '../../shared/shared.module';
import { AppConfig } from '../../core/config/config';

import { HmsModule } from '../hms.module';
import { LayoutComponent } from './layout.component';

describe('LayoutComponent', () => {
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
  let component: LayoutComponent;
  let fixture: ComponentFixture<LayoutComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SharedModule, RouterTestingModule, NoopAnimationsModule, HmsModule],
      /// HmsModule already declares LayoutComponent, so it must not be declared
      /// again here -- Angular rejects the duplicate. Importing the real module
      /// is what supplies <app-topnav> and <app-sidenav>, both of which the
      /// layout template renders.
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
    fixture = TestBed.createComponent(LayoutComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
