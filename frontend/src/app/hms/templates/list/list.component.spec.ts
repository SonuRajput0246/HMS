import { TestBed } from '@angular/core/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { SharedModule } from '../../../shared/shared.module';
import { AppConfig } from '../../../core/config/config';

import { ListTemplateComponent } from './list.component';

describe('ListTemplateComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ListTemplateComponent],
      imports: [RouterTestingModule, HttpClientTestingModule, NoopAnimationsModule, SharedModule]
    }).compileComponents();

    /// TemplateService reads BASE_URL in its constructor and AppConfig throws
    /// when the key is absent, so seed it before the component is created.
    TestBed.inject(AppConfig).set('BASE_URL', 'http://localhost:5000');
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(ListTemplateComponent);
    const component = fixture.componentInstance;
    expect(component).toBeTruthy();
  });

  it('should start on page 1 with no filters applied', () => {
    const fixture = TestBed.createComponent(ListTemplateComponent);
    const component = fixture.componentInstance;
    fixture.detectChanges();

    expect(component.requestData.page_number).toBe(1);
    expect(component.requestData.search_value).toBe('');
    expect(component.channelFilter).toBe('');
    expect(component.statusFilter).toBe('');
  });

  /// Regression guard: the backend validates channel with OneOf and returns
  /// 400 for an empty string, so an unfiltered request must send null.
  it('should send channel as null, not an empty string', () => {
    const fixture = TestBed.createComponent(ListTemplateComponent);
    const component = fixture.componentInstance;
    fixture.detectChanges();

    expect(component.requestData.channel).toBeNull();
  });

  it('should map the channel filter onto the request payload', () => {
    const fixture = TestBed.createComponent(ListTemplateComponent);
    const component = fixture.componentInstance;
    fixture.detectChanges();

    component.channelFilter = 'in_app';
    component.applySelectFilter();
    expect(component.requestData.channel).toBe('in_app');

    component.channelFilter = '';
    component.applySelectFilter();
    expect(component.requestData.channel).toBeNull();
  });

  it('should map the status filter onto the request payload', () => {
    const fixture = TestBed.createComponent(ListTemplateComponent);
    const component = fixture.componentInstance;
    fixture.detectChanges();

    component.statusFilter = 'inactive';
    component.applySelectFilter();
    expect(component.requestData.is_active).toBe(false);

    component.statusFilter = '';
    component.applySelectFilter();
    expect(component.requestData.is_active).toBeNull();
  });

  it('should reset channel to null when filters are cleared', () => {
    const fixture = TestBed.createComponent(ListTemplateComponent);
    const component = fixture.componentInstance;
    fixture.detectChanges();

    component.channelFilter = 'email';
    component.statusFilter = 'inactive';
    component.applySelectFilter();

    component.clearFilter();
    expect(component.requestData.channel).toBeNull();
    expect(component.requestData.is_active).toBeNull();
    expect(component.requestData.page_number).toBe(1);
  });

  it('should label channels for the grid', () => {
    const fixture = TestBed.createComponent(ListTemplateComponent);
    const http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    /// channelLabel resolves through the enum options the component loads on
    /// init. With that request unanswered `channels` is empty and every key
    /// falls through to itself, so 'email' would come back as 'email' and the
    /// test would prove nothing.
    for (const request of http.match(() => true)) {
      request.flush({
        status: true,
        data: [
          { option_key: 'email', option_label: 'Email' },
          { option_key: 'in_app', option_label: 'In-App' },
        ],
      });
    }
    fixture.detectChanges();

    const component = fixture.componentInstance;

    expect(component.channelLabel('email')).toBe('Email');
    expect(component.channelLabel('in_app')).toBe('In-App');

    /// An absent channel renders as a plain hyphen. The assertion here used
    /// to carry a corrupted replacement character instead of '-', which is
    /// why it had never passed.
    expect(component.channelLabel(undefined)).toBe('\u2014');

    /// An unknown key falls back to itself rather than to a dash: a dead
    /// dropdown must not hide the templates an operator needs to fix.
    expect(component.channelLabel('sms')).toBe('sms');

    http.verify();
  });
});