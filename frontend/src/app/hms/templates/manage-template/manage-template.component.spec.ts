import { TestBed, ComponentFixture } from '@angular/core/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { SharedModule } from '../../../shared/shared.module';
import { AppConfig } from '../../../core/config/config';

import { ManageTemplateComponent } from './manage-template.component';

describe('ManageTemplateComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ManageTemplateComponent],
      imports: [RouterTestingModule, HttpClientTestingModule, NoopAnimationsModule, SharedModule]
    }).compileComponents();

    /// TemplateService reads BASE_URL in its constructor and AppConfig throws
    /// when the key is absent, so seed it before the component is created.
    TestBed.inject(AppConfig).set('BASE_URL', 'http://localhost:5000');
  });

  afterEach(() => {
    TestBed.inject(HttpTestingController).verify();
  });

  /**
   * Create the component and let it settle.
   *
   * ngOnInit fires two requests -- getEnumOptions for template_channel and for
   * template_variable, joined by forkJoin. Tests that assert form behaviour
   * still have to account for them, because the strict verify() in afterEach
   * treats an unanswered request as a failure. That strictness is the point: an
   * unflushed request usually means the code under test made a call the test
   * did not know about.
   *
   * So rather than loosen verify(), every pending request is answered here.
   */
  function createComponent(): ComponentFixture<ManageTemplateComponent> {
    const fixture = TestBed.createComponent(ManageTemplateComponent);
    fixture.detectChanges();

    const http = TestBed.inject(HttpTestingController);
    for (const request of http.match(() => true)) {
      request.flush({ status: true, data: [] });
    }
    // Let the forkJoin callback land before the test reads the component.
    fixture.detectChanges();
    return fixture;
  }

  it('should create', () => {
    const fixture = createComponent();
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should default to the email channel and require a subject', () => {
    const component = createComponent().componentInstance;

    expect(component.isEmail()).toBe(true);

    component.templateForm.patchValue({ message_template: '<p>x</p>' });
    expect(component.templateForm.get('subject_template')?.hasError('required')).toBe(true);
  });

  it('should swap the required field when the channel changes', () => {
    const fixture = createComponent();
    const component = fixture.componentInstance;

    component.templateForm.get('channel')?.setValue('in_app');
    fixture.detectChanges();

    expect(component.isEmail()).toBe(false);
    expect(component.templateForm.get('title_template')?.hasError('required')).toBe(true);
  });

  it('should add and remove variables without duplicates', () => {
    const component = createComponent().componentInstance;

    component.addVariable('user_name');
    component.addVariable('otp');
    expect(component.variables).toEqual(['user_name', 'otp']);

    /// Adding the same name twice must not duplicate it.
    component.addVariable('otp');
    expect(component.variables).toEqual(['user_name', 'otp']);

    component.removeVariable('otp');
    expect(component.variables).toEqual(['user_name']);
  });

  it('should report placeholders that are used but not declared', () => {
    const component = createComponent().componentInstance;

    component.variables = ['user_name'];
    component.templateForm.patchValue({
      message_template: '<p>{{ user_name }} code {{ otp }}</p>'
    });

    expect(component.undeclaredVariables()).toEqual(['otp']);
  });

  it('should report no undeclared placeholders when all are declared', () => {
    const component = createComponent().componentInstance;

    component.variables = ['user_name', 'otp'];
    component.templateForm.patchValue({
      message_template: '<p>{{ user_name }} code {{ otp }}</p>'
    });

    expect(component.undeclaredVariables()).toEqual([]);
  });

  it('should ignore tokens that are not bare identifiers', () => {
    const component = createComponent().componentInstance;

    component.variables = [];
    component.templateForm.patchValue({
      message_template: '<p>{{ a.b }} {{ 1+1 }} {% raw %}</p>'
    });

    /// The renderer leaves these alone, so they must not be reported as
    /// missing variables -- otherwise saving would be blocked by noise.
    expect(component.undeclaredVariables()).toEqual([]);
  });

  it('should supply a sample value for every declared variable', () => {
    const component = createComponent().componentInstance;

    component.variables = ['user_name', 'brand_new_variable'];
    const context = component['buildSampleContext']();

    expect(context['user_name']).toBeTruthy();
    expect(context['brand_new_variable']).toBe('[brand_new_variable]');
  });
});