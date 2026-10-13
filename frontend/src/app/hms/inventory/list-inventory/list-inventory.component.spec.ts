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
 * This component is mounted by both products. hms/inventory ships it on the
 * hotel menu ids; cms/inventory/cms-inventory-routing.module.ts mounts the very
 * same class on the cafe module ids.
 *
 * That sharing is why every link in here has to be instance-aware. `onEdit`
 * once navigated to a literal 'hms/inventory/update-inventory', and because
 * /hms is canMatch-gated to HMS, the edit form was unreachable in the cafe
 * deployment -- the list rendered and every edit click landed on the 404.
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
   * Build the component against a given product.
   *
   * The instance type has to be in AppConfig before the component is created,
   * because InstanceService.prefix is read during field initialisation.
   *
   * The real Router is kept and only `navigate` is spied on. Substituting a
   * stub Router instead breaks RouterLink, which needs createUrlTree and
   * serializeUrl to resolve a template link -- so a stub would let a broken
   * routerLink pass unnoticed.
   */
  async function createFor(instanceType: 'HMS' | 'CMS'): Promise<void> {
    TestBed.resetTestingModule();

    const config = new AppConfig();
    config.set('BASE_URL', 'http://localhost:5000');
    config.set('INSTANCE_TYPE', instanceType);

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
    await createFor('HMS');
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  describe('instance-aware navigation', () => {

    it('edits an item under /hms on a hotel deployment', async () => {
      await createFor('HMS');

      component.onEdit({ id: 5 } as any);

      expect(router.navigate).toHaveBeenCalledWith(['hms/inventory/update-inventory', 5]);
    });

    /// The regression. Before this was fixed the path was the literal string
    /// 'hms/inventory/update-inventory' regardless of product.
    it('edits an item under /cms on a cafe deployment', async () => {
      await createFor('CMS');

      component.onEdit({ id: 5 } as any);

      expect(router.navigate).toHaveBeenCalledWith(['cms/inventory/update-inventory', 5]);
      expect(router.navigate).not.toHaveBeenCalledWith(
        jasmine.arrayContaining(['hms/inventory/update-inventory', 5])
      );
    });

    it('exposes the same prefix to the template for the Add button', async () => {
      await createFor('CMS');
      expect(component.invBase).toBe('cms/inventory');

      await createFor('HMS');
      expect(component.invBase).toBe('hms/inventory');
    });

    /// The Add and Back links live in the template as routerLink, which is a
    /// separate defect from the TypeScript one and was missed by fixing only
    /// the navigate() calls.
    ///
    /// Asserted through the RouterLink directive's resolved UrlTree rather than
    /// an href attribute: the control is a <button>, and RouterLink only writes
    /// href onto an <a>, so there is no href to read.
    it('resolves the Add link within the active product, not a literal /hms', async () => {
      await createFor('CMS');
      fixture.detectChanges();

      const button = fixture.debugElement.query(By.css('button[mat-raised-button]'));
      expect(button).withContext('the Add Inventory control should be present').toBeTruthy();

      const link = button.injector.get(RouterLink);
      const resolved = link.urlTree?.toString();

      expect(resolved).toBe('/cms/inventory/add-inventory');
      expect(resolved).not.toContain('/hms/');
    });

    it('resolves the same Add link under /hms on a hotel deployment', async () => {
      await createFor('HMS');
      fixture.detectChanges();

      const link = fixture.debugElement
        .query(By.css('button[mat-raised-button]'))
        .injector.get(RouterLink);

      expect(link.urlTree?.toString()).toBe('/hms/inventory/add-inventory');
    });
  });
});