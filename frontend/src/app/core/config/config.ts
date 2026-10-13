// import { Injectable } from '@angular/core';
// import { InitialService } from '../../services/initial.service';

// @Injectable({
//     providedIn: 'root'
// })

// export class AppConfig {

//   constructor(private _initial: InitialService) {}

//   get(key: string): string {
//     if (key === 'BASE_URL') {
//       if (!this._initial.baseUrl) {
//         throw new Error('BASE_URL not initialized');
//       }
//       return this._initial.baseUrl;
//     }
//     throw new Error(`Unknown config key: ${key}`);
//   }
// }


import { Injectable } from '@angular/core';

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
