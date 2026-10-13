import { Component, inject, OnInit, Inject } from '@angular/core';
import { MatTableDataSource } from '@angular/material/table';
import { finalize } from 'rxjs/operators';

import { ISearchRequest, IGenricGrid, INavigationaBar } from '../../models/ICommon.model';
import { IOrderSummary } from '../../models/ICms.model';
import { CmsOrderService } from '../../services/cms/order.service';
import { CustomSnackbarService } from '../../shared/custom-snackbar/custom-snackbar.service';
import { ConfirmationService } from '../../services/confirmation.service';
import { MatDialog, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { Router } from '@angular/router';

@Component({
  selector: 'app-order-list',
  standalone: false,
  templateUrl: './order-list.component.html',
  styleUrl: './order-list.component.scss'
})
export class OrderListComponent implements OnInit {
  private _orderService = inject(CmsOrderService);
  private _snackbar = inject(CustomSnackbarService);
  private _confirmService = inject(ConfirmationService);
  private _router = inject(Router);
  private _dialog = inject(MatDialog);

  // State
  isPageLoad = false;
  searchValue = '';
  orderList: IOrderSummary[] = [];
  pageDet: IGenricGrid = { total_docs: 0, limit: 10 };
  displayedColumns: string[] = ['sr', 'order_number', 'reference_label', 'ordered_at', 'item_count', 'total_amount', 'payment_status', 'status', 'actions'];
  dataSource = new MatTableDataSource<IOrderSummary>();

  /** Exposed for the template's total-pages maths. */
  Math = Math;

  navData: INavigationaBar[] = [
    { displayValue: 'Home', isClickable: true, isDashboard: false, redirectValue: '/cms/dashboard' },
    { displayValue: 'Order Management', isClickable: false, isDashboard: false }
  ];

  requestData: ISearchRequest = {
    page_number: 1,
    page_size: 10,
    search_value: ''
  } as ISearchRequest;

  // Filters
  statusFilter = '';
  paymentStatusFilter = '';
  tableIdFilter: number | null = null;
  customerIdFilter: number | null = null;
  fromDate: Date | null = null;
  toDate: Date | null = null;

  ORDER_STATUSES = [
    'pending', 'confirmed', 'preparing', 'ready', 'served', 'cancelled', 'completed'
  ];
  PAYMENT_STATUSES = ['pending', 'partial', 'paid', 'refunded', 'failed'];

  ngOnInit(): void {
    this.loadInitialData();
  }

  private loadInitialData(): void {
    this.fetchOrderList();
  }

  private fetchOrderList(): void {
    this.isPageLoad = true;

    const payload: any = {
      page_number: this.requestData.page_number,
      page_size: this.requestData.page_size,
      search_value: this.searchValue || null,
      status: this.statusFilter || null,
      payment_status: this.paymentStatusFilter || null,
      table_id: this.tableIdFilter,
      customer_id: this.customerIdFilter,
      from_date: this.fromDate ? this.formatDate(this.fromDate) : null,
      to_date: this.toDate ? this.formatDate(this.toDate) : null
    };

    this._orderService.getOrders(payload)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status) {
            this.orderList = res.data || [];
            this.pageDet.total_docs = res.meta?.total_records || 0;
            this.pageDet.limit = this.requestData.page_size!;
            this.dataSource.data = this.orderList;
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch orders', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'An error occurred while fetching orders';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  private formatDate(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  onPaginateChange(e: any): void {
    this.requestData.page_number = e.pageIndex + 1;
    this.requestData.page_size = e.pageSize;
    this.fetchOrderList();
  }

  applyFilter(): void {
    if (this.searchValue.length >= 3 || this.searchValue.length === 0) {
      this.requestData.page_number = 1;
      this.fetchOrderList();
    }
  }

  clearFilter(): void {
    this.searchValue = '';
    this.statusFilter = '';
    this.paymentStatusFilter = '';
    this.tableIdFilter = null;
    this.customerIdFilter = null;
    this.fromDate = null;
    this.toDate = null;
    this.requestData.page_number = 1;
    this.fetchOrderList();
  }

  onStatusFilterChange(): void {
    this.requestData.page_number = 1;
    this.fetchOrderList();
  }

  onPaymentStatusFilterChange(): void {
    this.requestData.page_number = 1;
    this.fetchOrderList();
  }

  onDateFilterChange(): void {
    this.requestData.page_number = 1;
    this.fetchOrderList();
  }

  onRowClick(order: IOrderSummary): void {
    this.openOrderDetail(order.id);
  }

  private openOrderDetail(orderId: number): void {
    this.isPageLoad = true;
    this._orderService.getOrderById(orderId)
      .pipe(finalize(() => this.isPageLoad = false))
      .subscribe({
        next: (res) => {
          if (res?.status && res.data) {
            this.openOrderDetailDialog(res.data);
          } else {
            this._snackbar.openSnackBar(res?.message || 'Failed to fetch order details', 'error');
          }
        },
        error: (err) => {
          const msg = err.error?.message || 'Failed to fetch order details';
          this._snackbar.openSnackBar(msg, 'error');
        }
      });
  }

  private openOrderDetailDialog(order: any): void {
    const dialogRef = this._dialog.open(OrderDetailDialogComponent, {
      width: '800px',
      maxHeight: '90vh',
      data: order,
      panelClass: 'order-detail-dialog'
    });

    dialogRef.afterClosed().subscribe(() => {
      // Refresh list when dialog closes
      this.fetchOrderList();
    });
  }

  onCancelOrder(order: any): void {
    this._confirmService.confirmWithReason(
      'Cancel Order',
      `Are you sure you want to cancel order ${order.order_number}?`
    ).then((result) => {
      if (result.confirmed) {
        this.isPageLoad = true;
        this._orderService.cancelOrder(order.id, result.reason)
          .pipe(finalize(() => this.isPageLoad = false))
          .subscribe({
            next: (res) => {
              if (res?.status) {
                this._snackbar.openSnackBar(res.message || 'Order cancelled successfully', 'success');
                this.fetchOrderList();
              } else {
                this._snackbar.openSnackBar(res?.message || 'Failed to cancel order', 'error');
              }
            },
            error: (err) => {
              const msg = err.error?.message || 'Failed to cancel order';
              this._snackbar.openSnackBar(msg, 'error');
            }
          });
      }
    });
  }

  goToTable(tableId: number): void {
    this._router.navigate(['/cms/pos']);
  }

  getStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      pending: 'Pending',
      confirmed: 'Confirmed',
      preparing: 'Preparing',
      ready: 'Ready',
      served: 'Served',
      cancelled: 'Cancelled',
      completed: 'Completed'
    };
    return labels[status] || status;
  }

  getPaymentStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      pending: 'Pending',
      partial: 'Partial',
      paid: 'Paid',
      refunded: 'Refunded',
      failed: 'Failed'
    };
    return labels[status] || status;
  }

  getStatusClass(status: string): string {
    const classes: Record<string, string> = {
      pending: 'st-pending',
      confirmed: 'st-confirmed',
      preparing: 'st-preparing',
      ready: 'st-ready',
      served: 'st-served',
      cancelled: 'st-cancelled',
      completed: 'st-completed'
    };
    return classes[status] || 'st-default';
  }

  getPaymentStatusClass(status: string): string {
    const classes: Record<string, string> = {
      pending: 'st-pending',
      partial: 'st-partial',
      paid: 'st-paid',
      refunded: 'st-refunded',
      failed: 'st-failed'
    };
    return classes[status] || 'st-default';
  }
}

// Dialog Component for Order Detail
@Component({
  selector: 'app-order-detail-dialog',
  standalone: false,
  templateUrl: './order-detail-dialog.component.html'
})
export class OrderDetailDialogComponent {
  constructor(
    public dialogRef: MatDialogRef<OrderDetailDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: any,
    private _orderService: CmsOrderService,
    private _snackbar: CustomSnackbarService
  ) {}

  close(): void {
    this.dialogRef.close();
  }

  printBill(): void {
    this._orderService.getBill(this.data.id).subscribe({
      next: (res) => {
        if (res?.status && res.data) {
          this.openPrintWindow(res.data);
        }
      }
    });
  }

  private openPrintWindow(bill: any): void {
    const printHtml = this.generateBillHtml(bill);
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(printHtml);
      printWindow.document.close();
      printWindow.focus();
      setTimeout(() => printWindow.print(), 250);
    }
  }

  private generateBillHtml(bill: any): string {
    const itemsHtml = bill.items?.map((item: any) => `
      <tr>
        <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">${item.item_name}</td>
        <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: center;">${item.quantity}</td>
        <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: right;">₹ ${Number(item.unit_price).toFixed(2)}</td>
        <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: right;">₹ ${Number(item.total_price).toFixed(2)}</td>
      </tr>
    `).join('') || '';

    const paymentsHtml = bill.payments?.map((p: any) => `
      <tr>
        <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">${p.payment_method}</td>
        <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: right;">₹ ${Number(p.amount).toFixed(2)}</td>
        <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">${p.paid_at ? new Date(p.paid_at).toLocaleString() : '-'}</td>
      </tr>
    `).join('') || '';

    return `
      <html>
        <head>
          <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .header { text-align: center; margin-bottom: 20px; }
            .details { margin-bottom: 20px; }
            .details div { margin: 4px 0; }
            table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid #e2e8f0; }
            th { background: #f2f6fc; font-weight: 600; }
            .totals { text-align: right; margin-top: 20px; }
            .total-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0; }
            .grand-total { font-weight: bold; font-size: 1.1em; border-top: 2px solid #003366; }
            .footer { text-align: center; margin-top: 30px; color: #64748b; font-size: 0.9em; }
            @media print { .no-print { display: none; } }
          </style>
        </head>
        <body onload="window.print()">
          <div class="header">
            <h2>${bill.table?.table_name || 'Walk-in'}</h2>
            <p>Order: ${bill.order_number} | ${bill.reference_label}</p>
          </div>
          <div class="details">
            <div><strong>Ordered:</strong> ${bill.ordered_at ? new Date(bill.ordered_at).toLocaleString() : '-'}</p>
            <div><strong>Type:</strong> ${bill.order_type}</div>
          </div>
          <table>
            <thead>
              <tr><th>Item</th><th style="text-align:center">Qty</th><th style="text-align:right">Price</th><th style="text-align:right">Total</th></tr>
            </thead>
            <tbody>${itemsHtml}</tbody>
          </table>
          <div class="totals">
            <div class="total-row"><span>Subtotal:</span><span>₹ ${bill.totals.item_subtotal}</span></div>
            <div class="total-row"><span>Tax:</span><span>₹ ${bill.totals.tax_amount}</span></div>
            <div class="total-row"><span>Discount:</span><span>₹ ${bill.totals.discount_amount}</span></div>
            <div class="total-row grand-total"><span>Total:</span><span>₹ ${bill.totals.total_amount}</span></div>
          </div>
          <table style="width:100%; margin-top:20px;">
            <thead><tr><th>Method</th><th style="text-align:right">Amount</th><th>Time</th></tr></thead>
            <tbody>${paymentsHtml}</tbody>
          </table>
          <div class="footer">Thank you for visiting!</div>
        </body>
      </html>
    `;
  }
}