import { Injectable } from '@angular/core';

/**
 * Runtime configuration store.
 *
 * `InitialService` populates this during APP_INITIALIZER, before anything can
 * read it. `get` throws for an unknown key rather than returning undefined: a
 * missing required value means startup is genuinely broken, and failing at the
 * point of use beats a silent undefined that surfaces three screens later.
 */
@Injectable({
  providedIn: 'root'
})
export class AppConfig {

  private config: Record<string, any> = {};

  set(key: string, value: any): void {
    this.config[key] = value;
  }

  get<T = any>(key: string): T {
    if (!(key in this.config)) {
      throw new Error(`Config key "${key}" is not initialized`);
    }
    return this.config[key];
  }
}