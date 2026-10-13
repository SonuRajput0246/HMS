import { TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';

describe('AppComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RouterTestingModule, NoopAnimationsModule],
      declarations: [AppComponent],
      providers: [
        /// AppComponent injects CommonService and InitialService, which in turn
        /// need an HttpClient. The app boot sequence calls instance-config
        /// before the router is allowed to resolve any route, so this
        /// component cannot be constructed without them.
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  /// The generated scaffold asserted an <h1> reading "Hello, frontend", which
  /// this app never had -- the root template is only a <router-outlet>. The
  /// shell's one real job is to host the outlet the whole application renders
  /// into, so that is what gets asserted.
  it('should render the router outlet the app renders into', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;

    expect(compiled.querySelector('router-outlet')).toBeTruthy();
  });
});