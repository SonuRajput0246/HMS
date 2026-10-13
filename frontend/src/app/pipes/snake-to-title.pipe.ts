import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'snakeToTitle'
})
export class SnakeToTitlePipe implements PipeTransform {

  transform(value: string | null | undefined): string {
    if (!value) return '';

    return value
      .replace(/_/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, char => char.toUpperCase());
  }
}
