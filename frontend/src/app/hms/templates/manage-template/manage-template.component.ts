import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild, inject } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize } from 'rxjs/operators';
import { debounceTime } from 'rxjs/operators';
import { Subscription, forkJoin } from 'rxjs';

import { TemplateService } from '../../../services/template.service';
import { CommonService } from '../../../services/common.service';
import { CustomSnackbarService } from '../../../shared/custom-snackbar/custom-snackbar.service';
import { IEnumOption, INavigationaBar } from '../../../models/ICommon.model';
import { ITemplateDetail, ITemplatePreview } from '../../../models/IAdmin.model';


/**
 * Realistic sample values for the live preview.
 *
 * Keyed by the `template_variable` option_key. A variable with no entry here
 * previews as `[name]` -- which is the point of the fallback in
 * buildSampleContext: a newly seeded variable shows up in the preview without
 * anyone editing this file.
 */
const SAMPLE_VALUES: { [key: string]: string } = {
  user_name: 'John Doe',
  user_email: 'john.doe@example.com',
  otp: '123456',
  expiry_minutes: '10',
  company_name: 'HMS',
  room_number: 'A-204',
  reservation_number: 'RSV-000123',
  check_in_date: '2026-10-05',
  check_out_date: '2026-10-07',
  amount: '4,250.00',
  invoice_number: 'INV-000456'
};

@Component({
  selector: 'app-manage-template',
  templateUrl: './manage-template.component.html',
  styleUrl: './manage-template.component.scss'
})
export class ManageTemplateComponent implements AfterViewInit, OnDestroy {

  private fb = inject(FormBuilder);
  private _templateService = inject(TemplateService);
  private _commonService = inject(CommonService);
  private _snackbar = inject(CustomSnackbarService);
  private _router = inject(Router);
  private AR = inject(ActivatedRoute);

  @ViewChild('previewFrame') previewFrame?: ElementRef<HTMLIFrameElement>;
  @ViewChild('previewHost') previewHost?: ElementRef<HTMLElement>;

  /// Tracks the form subscription so it is torn down with the component.
  private formSub?: Subscription;

  navData: INavigationaBar[] = [];
  templateForm!: FormGroup;

  isLoading = false;
  isPageLoad = false;
  isEditMode = false;

  templateObj: ITemplateDetail = {} as ITemplateDetail;
  channel: string = 'email';

  /// Preview state
  preview: ITemplatePreview | null = null;
  isPreviewLoading = false;

  /// Variables the author has attached to this template.
  variables: string[] = [];

  /// Candidate names offered in the variable picker, from the
  /// `template_variable` enum definition. `{{ }}` tokens are matched against
  /// this list for suggestions, but custom names are still allowed -- the
  /// backend does not require every token to be a known option.
  knownVariables: string[] = [];

  /// New variable typed into the picker.
  newVariable = '';

  /// Delivery channels, from the `template_channel` enum definition.
  /// Previously a hardcoded array of two; the keys are the same values the
  /// backend validates against, so a mismatch here showed up as a 400 on save.
  channels: IEnumOption[] = [];

  /// The option flagged is_default, used as the initial channel. Falls back to
  /// the first option so the control is never empty before the API responds.
  /// Public because the failure note in the template names the channel that
  /// will be used, so the author can see what they are about to save.
  defaultChannel = '';

  isEnumLoading = false;

  ngOnInit(): void {
    this.initNavigation();
    this.createForm();

    const templateId = Number(this.AR.snapshot.paramMap.get('id'));
    if (templateId) {
      this.isEditMode = true;
      /// Sequencing, not just aesthetics: the stored channel is patched into the
      /// form after the options load, so loading them in parallel would let the
      /// enum default overwrite the row's actual channel.
      this.fetchEnumOptions(() => this.getTemplateById(templateId));
      this.navData = [
        ...this.navData,
        { displayValue: 'Edit Template', isClickable: false, isDashboard: false }
      ];
    } else {
      this.navData = [
        ...this.navData,
        { displayValue: 'Add Template', isClickable: false, isDashboard: false }
      ];
      /// Add mode has no stored row to race with, so the default can be applied
      /// as soon as it is known.
      this.fetchEnumOptions();
    }

    /// Refresh the preview shortly after typing stops.
    this.formSub = this.templateForm.valueChanges
      .pipe(debounceTime(450))
      .subscribe(() => this.runPreview());
  }

  ngAfterViewInit(): void {
    /// The initial preview can land before the iframe exists.
    setTimeout(() => this.fitPreviewFrameIfReady());
  }

  ngOnDestroy(): void {
    this.formSub?.unsubscribe();
  }

  private initNavigation(): void {
    this.navData = [
      { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/hms/dashboard' },
      {
        displayValue: 'Template Management',
        isClickable: true,
        isDashboard: false,
        redirectValue: '/hms/templates'
      }
    ];
  }

  /**
   * Load the two enum-driven lists: delivery channels and placeholder names.
   *
   * Generic on purpose -- one helper serves both, so adding a channel or a
   * variable is a seeder change with no frontend edit.
   *
   * A failure here is non-fatal. The form still works: the channel control
   * falls back to the default channel and the variable picker accepts typed
   * names, because custom placeholders are allowed anyway. Blocking the editor
   * over a dropdown would be a worse outcome than a missing suggestion.
   */
  private fetchEnumOptions(then?: () => void): void {
    this.isEnumLoading = true;

    forkJoin({
      channels: this._commonService.getEnumOptions('template_channel'),
      variables: this._commonService.getEnumOptions('template_variable')
    })
      .pipe(finalize(() => this.isEnumLoading = false))
      .subscribe({
        next: ({ channels, variables }) => {
          this.channels = channels?.status ? (channels.data || []) : [];
          this.knownVariables = variables?.status
            ? (variables.data || []).map((o: IEnumOption) => o.option_key)
            : [];

          const defaultOption = this.channels.find(c => c.is_default) || this.channels[0];
          this.defaultChannel = defaultOption?.option_key || 'email';

          /// Only apply the default when the author has not already chosen.
          /// In edit mode `then` patches the row's own channel afterwards, which
          /// must win over the default.
          const current = this.templateForm?.get('channel')?.value;
          if (!current || !this.channels.some(c => c.option_key === current)) {
            this.templateForm?.get('channel')?.setValue(this.defaultChannel);
            this.channel = this.defaultChannel;
            this.applyChannelRules();
          }

          then?.();
        },
        error: () => {
          /// Leave `channels` empty so the toggle renders nothing rather than a
          /// misleading partial control, but keep the placeholder default so the
          /// form and preview still submit a valid channel. `then` still runs:
          /// a failed enum lookup must not stop the author editing the template.
          this.channels = [];
          this.knownVariables = [];
          this.defaultChannel = 'email';
          then?.();
        }
      });
  }

  /// Icon for a channel option, with a fallback. `icon` is null for enums that
  /// do not define one, and <mat-icon> renders an empty box for a null name.
  channelIcon(option: IEnumOption): string {
    return option?.icon || 'mail';
  }

  private createForm(): void {
    this.templateForm = this.fb.group({
      code: ['', [Validators.required, Validators.pattern(/^[A-Z][A-Z0-9_]*$/)]],
      name: ['', Validators.required],
      description: [''],
      /// Starts on the placeholder value; replaced with the enum's is_default once
      /// the options arrive (see fetchEnumOptions).
      channel: ['email', Validators.required],
      subject_template: [''],
      title_template: [''],
      message_template: ['', Validators.required],
      is_active: [true]
    });

    /// The required-field rules for subject vs title depend on the channel,
    /// so they are applied imperatively rather than baked into createForm().
    this.templateForm.get('channel')?.valueChanges.subscribe((value) => {
      this.channel = value || this.defaultChannel || 'email';
      this.applyChannelRules();
      this.runPreview();
    });

    /// The channel control does not emit on creation, so the subscription above
    /// never fires for the default value. Apply the rules once up front,
    /// otherwise an "Add Template" page starts with no validators on either
    /// subject_template or title_template.
    this.applyChannelRules();
  }

  private applyChannelRules(): void {
    const subjectCtrl = this.templateForm.get('subject_template');
    const titleCtrl = this.templateForm.get('title_template');

    if (!subjectCtrl || !titleCtrl) return;

    if (this.channel === 'email') {
      subjectCtrl.setValidators([Validators.required]);
      titleCtrl.clearValidators();
    } else {
      titleCtrl.setValidators([Validators.required]);
      subjectCtrl.clearValidators();
    }

    subjectCtrl.updateValueAndValidity({ emitEvent: false });
    titleCtrl.updateValueAndValidity({ emitEvent: false });
  }

  private getTemplateById(templateId: number): void {
    this.isPageLoad = true;
    this._templateService.getTemplateById(templateId)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.templateObj = res.data;
            this.variables = [...(this.templateObj.variables || [])];

            this.templateForm.patchValue({
              code: this.templateObj.code,
              name: this.templateObj.name,
              description: this.templateObj.description || '',
              /// The stored channel, not the enum default: the author must be
              /// editing the row they opened, and is_system rows keep their
              /// channel locked server-side.
              channel: this.templateObj.channel || this.defaultChannel || 'email',
              subject_template: this.templateObj.subject_template || '',
              title_template: this.templateObj.title_template || '',
              message_template: this.templateObj.message_template,
              is_active: this.templateObj.is_active
            });

            /// `channel` is read back from the patched form so the toggle and the control
            /// agree. The valueChanges subscription already fired on patchValue.
            this.channel = this.templateForm.get('channel')?.value || 'email';
            this.applyChannelRules();
            this.runPreview();
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch template', 'error');
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(
            err.error?.message || 'An error occurred while fetching template', 'error');
        }
      });
  }

  // ---------------------------------------------------------------
  //  Variables
  // ---------------------------------------------------------------

  addVariable(name?: string): void {
    const value = (name ?? this.newVariable).trim();

    if (!value) return;
    if (this.variables.includes(value)) {
      this._snackbar.openSnackBar(`'${value}' is already a variable`, 'error');
      return;
    }

    this.variables.push(value);
    this.newVariable = '';
    this.runPreview();
  }

  removeVariable(name: string): void {
    this.variables = this.variables.filter(v => v !== name);
    this.runPreview();
  }

  /// Token names found in the body that are not on the variables list. The
  /// backend rejects these on save, so surface them before the user submits.
  undeclaredVariables(): string[] {
    const found = this.detectVariables();
    return found.filter(name => !this.variables.includes(name));
  }

  private detectVariables(): string[] {
    const fields = [
      this.templateForm.get('subject_template')?.value,
      this.templateForm.get('title_template')?.value,
      this.templateForm.get('message_template')?.value
    ];

    const found: string[] = [];
    const pattern = /\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g;

    fields.forEach((text) => {
      if (!text) return;
      let match: RegExpExecArray | null;
      while ((match = pattern.exec(text)) !== null) {
        if (!found.includes(match[1])) {
          found.push(match[1]);
        }
      }
    });

    return found;
  }

  // ---------------------------------------------------------------
  //  Preview
  // ---------------------------------------------------------------

  runPreview(): void {
    if (!this.templateForm) return;

    const value = this.templateForm.value;

    if (!value.message_template) {
      this.preview = null;
      return;
    }

    this.isPreviewLoading = true;

    this._templateService.previewTemplate({
      channel: value.channel || this.defaultChannel || 'email',
      subject_template: value.subject_template || '',
      title_template: value.title_template || '',
      message_template: value.message_template || '',
      sample_context: this.buildSampleContext(),
      variables: this.variables
    })
      .pipe(finalize(() => this.isPreviewLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.preview = res.data;
            /// srcdoc swaps asynchronously, so fit once the frame settles.
            setTimeout(() => this.fitPreviewFrameIfReady());
          }
        },
        error: () => {
          /// Preview is a convenience. Never block editing on a preview error.
          this.preview = null;
        }
      });
  }

  /// Fit the preview iframe to the panel with no inner scrollbars.
  ///
  /// Two problems this solves:
  ///  1. The email layout uses a fixed 600px table, wider than the preview
  ///     column, so the frame scrolled horizontally.
  ///  2. Sizing the frame to its content removed the vertical scroll, but the
  ///     panel around it still scrolled, leaving two bars stacked together.
  ///
  /// So: suppress overflow inside the frame, measure the real content size,
  /// then scale the frame down to fit the column. One scroll container (the
  /// panel), no horizontal bar at all, and the whole email stays visible.
  /// Template `(load)` handler -- called with the live element refs.
  fitPreviewFrame(frame: HTMLIFrameElement, host: HTMLElement): void {
    this.applyPreviewFit(frame, host);
  }

  /// Fit using the ViewChild refs, for calls outside the template handler.
  private fitPreviewFrameIfReady(): void {
    const frame = this.previewFrame?.nativeElement;
    const host = this.previewHost?.nativeElement;
    if (frame && host) {
      this.applyPreviewFit(frame, host);
    }
  }

  /// Size the preview iframe to its content, with no internal scrollbars.
  ///
  /// The email layout uses a fixed 600px table. Instead of scaling it down,
  /// the frame gets the email's natural size and `.preview-content` handles
  /// scrolling both axes -- so the subject stays pinned above and the card has
  /// exactly one vertical and one horizontal scrollbar, matching the form
  /// card's scrollbar styling.
  private applyPreviewFit(frame: HTMLIFrameElement, host: HTMLElement): void {
    if (!frame || !host) return;

    try {
      const doc = frame.contentDocument || frame.contentWindow?.document;
      if (!doc?.body || !doc.head) return;

      /// srcdoc reloads the document on every change, so the override has to
      /// be re-applied each time rather than set once.
      ///
      /// `font-size` is bumped for legibility. This only affects inherited
      /// body copy: the email's own explicit pixel sizes (the OTP block, the
      /// small footer) are left alone.
      const style = doc.createElement('style');
      style.textContent =
        'html,body{margin:0!important;padding:0!important;' +
        'overflow:hidden!important;background:#fff}' +
        'body{font-size:15px;line-height:1.55}';
      doc.head.appendChild(style);

      const contentWidth = Math.max(
        doc.body.scrollWidth,
        doc.documentElement?.scrollWidth || 0,
        280
      );
      const contentHeight = Math.max(
        doc.body.scrollHeight,
        doc.documentElement?.scrollHeight || 0,
        120
      );

      /// Render at the email's natural size, no transform. The 600px width is
      /// what gives `.preview-content` something to scroll horizontally.
      frame.style.width = `${contentWidth}px`;
      frame.style.height = `${contentHeight}px`;
      frame.style.transform = 'none';

      host.style.height = `${contentHeight}px`;
      host.style.width = `${contentWidth}px`;
    } catch {
      /// Cross-origin or mid-navigation. The CSS fallbacks keep it usable.
    }
  }

  // ---------------------------------------------------------------
  //  Save
  // ---------------------------------------------------------------

  insertUpdateTemplate(): void {
    this.applyChannelRules();

    if (this.templateForm.invalid) {
      this.templateForm.markAllAsTouched();
      this._snackbar.openSnackBar('Please complete the required fields', 'error');
      return;
    }

    const undeclared = this.undeclaredVariables();
    if (undeclared.length) {
      this._snackbar.openSnackBar(
        `Add these as variables before saving: ${undeclared.join(', ')}`, 'error');
      return;
    }

    const value = this.templateForm.value;
    const selectedChannel = value.channel || this.defaultChannel || 'email';
    const isEmail = selectedChannel === 'email';

    /// Send null, not '', for the field that does not apply to this channel.
    /// The backend rejects a populated field from the wrong channel.
    const payload = {
      id: this.templateObj?.id || 0,
      code: value.code,
      name: value.name,
      description: value.description || null,
      channel: selectedChannel,
      subject_template: isEmail ? (value.subject_template || null) : null,
      title_template: isEmail ? null : (value.title_template || null),
      message_template: value.message_template,
      variables: this.variables,
      sample_context: this.templateObj.sample_context || {},
      is_active: value.is_active,
      is_deleted: false
    };

    this.isLoading = true;
    this._templateService.upsertTemplate(payload)
      .pipe(finalize(() => this.isLoading = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this._snackbar.openSnackBar(res?.message || 'Template saved successfully', 'success');
            this._router.navigate(['hms/templates']);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to save template', 'error');
          }
        },
        error: (err) => {
          this._snackbar.openSnackBar(
            err.error?.message || 'An error occurred while saving template', 'error');
        }
      });
  }

  onBack(): void {
    this._router.navigate(['hms/templates']);
  }

  /// True when the stored code must not be edited (seeded row).
  isCodeLocked(): boolean {
    return this.isEditMode && !!this.templateObj.is_system;
  }

  isEmail(): boolean {
    return this.channel === 'email';
  }

  /**
   * Label for a channel key, from the loaded enum options.
   *
   * Falls back to the raw key so a template whose channel is not (or no longer)
   * an active option still renders something readable rather than an empty cell.
   */
  channelLabel(channel?: string | null): string {
    if (!channel) return '—';
    const found = this.channels.find(c => c.option_key === channel);
    return found?.option_label || channel;
  }

  /**
   * Sample values for the preview, one per known variable.
   *
   * Keyed off the loaded `template_variable` options so a newly seeded variable
   * previews as `[name]` instead of rendering blank. The explicit map below wins
   * where it has an entry.
   */
  private buildSampleContext(): { [key: string]: any } {
    const stored = this.templateObj.sample_context || {};

    const context: { [key: string]: any } = {};

    this.knownVariables.forEach(name => {
      context[name] = SAMPLE_VALUES[name] ?? stored[name] ?? `[${name}]`;
    });

    this.variables.forEach(name => {
      if (!(name in context)) {
        context[name] = stored[name] !== undefined ? stored[name] : `[${name}]`;
      }
    });

    return context;
  }
}