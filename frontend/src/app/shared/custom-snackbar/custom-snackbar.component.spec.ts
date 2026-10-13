import { TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { convertToParamMap, ActivatedRoute } from '@angular/router';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MAT_SNACK_BAR_DATA } from '@angular/material/snack-bar';
import { of as observableOf } from 'rxjs';
import { SharedModule } from '../../shared/shared.module';
import { AppConfig } from '../../core/config/config';

import { CustomSnackbarComponent } from './custom-snackbar.component';

describe('CustomSnackbarComponent', () => {
  /// ActivatedRoute is injected by anything that reads route state. The
  /// tests below are not about navigation; this only satisfies the injector.
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

  let component: CustomSnackbarComponent;

  /// Read lazily, at the moment the component is constructed, so each test can
  /// choose its payload. TestBed.overrideProvider cannot be used here: the
  /// AppConfig seed in beforeEach already instantiates the module, and
  /// overriding after that is an error.
  let snackData: unknown = null;

  /// Build the component against a specific MAT_SNACK_BAR_DATA payload, the
  /// way MatSnackBar would when CustomSnackbarService opens it.
  function createWith(data: unknown): CustomSnackbarComponent {
    snackData = data;
    const f = TestBed.createComponent(CustomSnackbarComponent);
    f.detectChanges();
    return f.componentInstance;
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SharedModule, RouterTestingModule, NoopAnimationsModule],
      declarations: [CustomSnackbarComponent],
      providers: [
        /// Real backend module first so the app's own interceptors are in the
        /// chain, then the testing backend over it so nothing escapes to the
        /// network.
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: activatedRouteStub },
        /// MAT_SNACK_BAR_DATA has no default provider -- Material supplies it
        /// only when opening a snack bar, so a TestBed that builds the
        /// component directly has to provide it too.
        { provide: MAT_SNACK_BAR_DATA, useFactory: () => snackData },
      ],
    }).compileComponents();

    /// Services read BASE_URL from AppConfig in their constructor and
    /// AppConfig throws when the key is missing.
    TestBed.inject(AppConfig).set('BASE_URL', 'http://localhost:5000');
  });

  it('should create', () => {
    component = createWith({ icon: 'info', message: 'Saved' });
    expect(component).toBeTruthy();
  });

  it('should map the injected data onto the icon and message', () => {
    component = createWith({ icon: 'error', message: 'Could not save' });

    expect(component.icon).toBe('error');
    expect(component.message).toBe('Could not save');
  });

  /// CustomSnackbarService can be opened with a plain string, which carries no
  /// icon. The component must fall back rather than render "undefined" or
  /// leave the binding empty against an object that has no such key.
  it('should fall back to empty strings when the payload has no icon or message', () => {
    component = createWith(undefined);

    expect(component.icon).toBe('');
    expect(component.message).toBe('');
  });
});