import { Pipe, PipeTransform } from '@angular/core';

import { toAmount } from '../models/ICms.model';

/**
 * Formats a money string as a currency amount.
 *
 * The backend sends Decimal columns as strings precisely so the value survives
 * the JSON round trip intact. This pipe is the single place that turns one into
 * something displayable, so every screen shows the same format and no component
 * does its own rounding.
 *
 * `code` is the ISO currency. The app currently trades in INR.
 */
@Pipe({
  name: 'currencyInr',
  standalone: false
})
export class CurrencyInrPipe implements PipeTransform {

  transform(
    value: string | number | null | undefined,
    showSymbol: boolean = true,
    decimals: number = 2
  ): string {
    const amount = toAmount(value);

    // Grouped thousands with a fixed 2dp, e.g. 1234567.5 -> "12,34,567.50".
    // toAmount already coerced anything unparseable to 0, so a null or a
    // malformed backend value shows a clean 0.00 rather than "NaN".
    const grouped = amount.toLocaleString('en-IN', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });

    return showSymbol ? `₹ ${grouped}` : grouped;
  }
}