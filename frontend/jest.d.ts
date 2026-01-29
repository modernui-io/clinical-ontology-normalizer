declare const describe: (name: string, fn: () => void) => void;
declare const it: (name: string, fn: () => void | Promise<void>) => void;
declare const test: (name: string, fn: () => void | Promise<void>) => void;
declare const expect: any;
declare const beforeEach: (fn: () => void | Promise<void>) => void;
declare const afterEach: (fn: () => void | Promise<void>) => void;
declare const beforeAll: (fn: () => void | Promise<void>) => void;
declare const afterAll: (fn: () => void | Promise<void>) => void;

declare namespace jest {
  type Mock<T = any> = (...args: any[]) => T;
}

declare const jest: {
  fn: (...args: any[]) => any;
  mock: any;
  useFakeTimers: (...args: any[]) => void;
  runAllTimers: () => void;
  advanceTimersByTime: (ms: number) => void;
  clearAllMocks: () => void;
  resetAllMocks: () => void;
  spyOn: (...args: any[]) => any;
};
