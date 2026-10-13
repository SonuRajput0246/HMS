import { Pipe, PipeTransform } from '@angular/core';

/**
 * Coerce a money value to a number for arithmetic.
 *
 * The backend sends Decimal columns as strings precisely so the value survives
 * the JSON round trip intact, so anything doing arithmetic on money has to
 * parse first. Anything unparseable -- null, undefined, a malformed backend
 * value -- becomes 0 rather than NaN, because NaN poisons every total it
 * touches and surfaces as a blank cell rather than an error.
 */
export function toAmount(value: string | number | null | undefined): number {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : 0;
  }
  if (value === null || value === undefined || value === '') {
    return 0;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

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