import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, RouterLink } from '@angular/router';
import { RouterTestingModule } from '@angular/router/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { By } from '@angular/platform-browser';
import { SharedModule } from '../../shared/shared.module';
import { CommonService } from '../../services/common.service';

import { CmsSidenavComponent } from './cms-sidenav.component';

/**
 * The sidebar is the thing that had to be built. What matters is not that it
 * renders, but that every row it renders is a row the cafe can actually open.
 */
describe('CmsSidenavComponent', () => {

  function access(moduleName: string, over: Record<string, unknown> = {}) {
    return {
      module_id: 1,
      module_name: moduleName,
      module_display_name: moduleName.replace(/_/g, ' ').toLowerCase(),
      menu_parent_code: 0,
      icon: `${moduleName.toLowerCase()}.png`,
      route_path: moduleName.toLowerCase(),
      has_child_menu: false,
      accessList: [],
      ...over,
    };
  }

  let fixture: ComponentFixture<CmsSidenavComponent>;
  let component: CmsSidenavComponent;
  let router: Router;

  /**
   * Build against a fake menu_access.
   *
   * CommonService reads localStorage, so the stub replaces it wholesale rather
   * than writing storage that would leak between tests.
   */
  async function createWith(accessList: unknown[]): Promise<void> {
    TestBed.resetTestingModule();

    await TestBed.configureTestingModule({
      imports: [SharedModule, RouterTestingModule, NoopAnimationsModule],
      declarations: [CmsSidenavComponent],
      providers: [
        {
          provide: CommonService,
          useValue: { getMenuAccess: () => accessList, getUserFullName: () => '' },
        },
      ],
    }).compileComponents();

    router = TestBed.inject(Router);
    spyOn(router, 'navigate').and.resolveTo(true);

    fixture = TestBed.createComponent(CmsSidenavComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  /** The routerLink paths actually rendered, in order. */
  function renderedPaths(): string[] {
    return fixture.debugElement
      .queryAll(By.css('.cms-menu-item'))
      .map(el => el.injector.get(RouterLink).urlTree?.toString() ?? '');
  }

  beforeEach(async () => {
    await createWith([access('DASHBOARD'), access('ORDER'), access('INVENTORY_MANAGEMENT')]);
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('renders one row per reachable screen', () => {
    expect(component.menu.length).toBe(3);
    expect(fixture.nativeElement.querySelectorAll('.cms-menu-item').length).toBe(3);
  });

  /**
   * The regression this component exists to prevent.
   *
   * Super Admin and Admin hold role_module_access rows for the hotel's modules
   * as well, because the access list is built without an instance filter. Those
   * five links all pointed into a canMatch-gated tree.
   */
  it('never renders a module belonging to the other instance', async () => {
    await createWith([
      access('DASHBOARD'),
      access('ROOM'),
      access('RESERVATIONS'),
      access('GUEST'),
      access('FOLIO'),
      access('HOUSEKEEPING'),
    ]);

    const names = component.menu.map(item => item.moduleName);

    expect(names).toEqual(['DASHBOARD']);
    expect(component.hiddenModuleNames).toEqual([
      'ROOM', 'RESERVATIONS', 'GUEST', 'FOLIO', 'HOUSEKEEPING',
    ]);
  });

  it('never renders a CMS module that has no screen', async () => {
    await createWith([access('DASHBOARD'), access('TEMPLATE'), access('ROLE'), access('USER_MANAGEMENT')]);

    expect(component.menu.map(item => item.moduleName)).toEqual(['DASHBOARD']);
    expect(component.hiddenModuleNames).toEqual(['TEMPLATE', 'ROLE', 'USER_MANAGEMENT']);
  });

  it('says so rather than showing an empty bar when the role has nothing', async () => {
    await createWith([access('ROOM')]);

    expect(component.menu.length).toBe(0);
    expect(fixture.nativeElement.textContent).toContain('No sections are available');
  });

  it('survives a missing or malformed stored user', async () => {
    await createWith(null as unknown as unknown[]);
    expect(component.menu).toEqual([]);

    await createWith(undefined as unknown as unknown[]);
    expect(component.menu).toEqual([]);
  });

  it('uses the label from the database', async () => {
    await createWith([access('ORDER', { module_display_name: 'Ring Up' })]);

    expect(fixture.nativeElement.textContent).toContain('Ring Up');
  });

  it('navigates to the CMS path, never an hms one', () => {
    const order = component.menu.find(item => item.moduleName === 'ORDER')!;

    component.go(order);

    expect(router.navigate).toHaveBeenCalledWith(['/cms', 'orders']);
  });

  it('builds every routerLink under /cms', () => {
    for (const path of renderedPaths()) {
      expect(path.startsWith('/cms/')).withContext(`link was ${path}`).toBe(true);
      expect(path).not.toContain('/hms');
    }
  });
});