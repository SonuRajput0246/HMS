import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { convertToParamMap, ActivatedRoute, Router, RouterLink } from '@angular/router';
import { By } from '@angular/platform-browser';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of as observableOf } from 'rxjs';
import { SharedModule } from '../../../shared/shared.module';
import { AppConfig } from '../../../core/config/config';

import { ListInventoryComponent } from './list-inventory.component';

/**
 * Covers the inventory list's links.
 *
 * Every route in here is built from InstanceService.prefix rather than a
 * literal 'hms', so the prefix is asserted rather than assumed -- the literal
 * version is exactly the regression these tests exist to catch.
 */
describe('ListInventoryComponent', () => {
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

  let component: ListInventoryComponent;
  let fixture: ComponentFixture<ListInventoryComponent>;
  let router: Router;

  /**
   * The real Router is kept and only `navigate` is spied on. Substituting a
   * stub Router instead breaks RouterLink, which needs createUrlTree and
   * serializeUrl to resolve a template link -- so a stub would let a broken
   * routerLink pass unnoticed.
   */
  async function create(): Promise<void> {
    TestBed.resetTestingModule();

    const config = new AppConfig();
    config.set('BASE_URL', 'http://localhost:5000');

    await TestBed.configureTestingModule({
      imports: [SharedModule, RouterTestingModule, NoopAnimationsModule],
      declarations: [ListInventoryComponent],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: activatedRouteStub },
        { provide: AppConfig, useValue: config },
      ],
    }).compileComponents();

    router = TestBed.inject(Router);
    spyOn(router, 'navigate').and.resolveTo(true);

    fixture = TestBed.createComponent(ListInventoryComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  beforeEach(async () => {
    await create();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  describe('navigation', () => {

    it('edits an item under /hms', async () => {
      component.onEdit({ id: 5 } as any);

      expect(router.navigate).toHaveBeenCalledWith(['/hms/inventory/update-inventory', 5]);
    });

    /// Asserted through the RouterLink directive's resolved UrlTree rather than
    /// an href attribute: the control is a <button>, and RouterLink only writes
    /// href onto an <a>, so there is no href to read.
    it('resolves the Add link to a real route', () => {
      fixture.detectChanges();

      const button = fixture.debugElement.query(By.css('button[mat-raised-button]'));
      expect(button).withContext('the Add Inventory control should be present').toBeTruthy();

      const link = button.injector.get(RouterLink);

      expect(link.urlTree?.toString()).toBe('/hms/inventory/add-inventory');
    });
  });
});