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

import { SliderComponent } from './slider.component';

describe('SliderComponent', () => {
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
  let component: SliderComponent;
  let fixture: ComponentFixture<SliderComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SharedModule, RouterTestingModule, NoopAnimationsModule],
      declarations: [SliderComponent],
      /// <swiper-container> and <swiper-slide> are custom elements from the
      /// swiper package, not Angular components or directives -- there is no
      /// SwiperModule in package.json and no reference to swiper anywhere in
      /// the TypeScript. AuthModule resolves them the same way, with
      /// CUSTOM_ELEMENTS_SCHEMA, so the spec has to match it or the template
      /// fails to compile.
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
    fixture = TestBed.createComponent(SliderComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
