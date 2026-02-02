declare const describe: (name: string, fn: () => void) => void;
declare const it: (name: string, fn: () => void | Promise<void>) => void;
declare const test: (name: string, fn: () => void | Promise<void>) => void;
declare const expect: any;
declare const beforeEach: (fn: () => void | Promise<void>) => void;
declare const afterEach: (fn: () => void | Promise<void>) => void;
declare const beforeAll: (fn: () => void | Promise<void>) => void;
declare const afterAll: (fn: () => void | Promise<void>) => void;

declare namespace jest {
  type Mock<T = any> = {
    (...args: any[]): T;
    mock: { calls: any[] };
    mockReturnValue: (value: any) => any;
    mockReturnValueOnce: (value: any) => any;
    mockResolvedValue: (value: any) => any;
    mockResolvedValueOnce: (value: any) => any;
    mockRejectedValue: (value: any) => any;
    mockRejectedValueOnce: (value: any) => any;
    mockImplementation: (fn: (...args: any[]) => any) => any;
    mockImplementationOnce?: (fn: (...args: any[]) => any) => any;
  };
  type MockedFunction<T extends (...args: any[]) => any> = Mock<ReturnType<T>> & T;
}

declare const jest: {
  fn: (...args: any[]) => any;
  mock: any;
  doMock: (...args: any[]) => any;
  useFakeTimers: (...args: any[]) => void;
  useRealTimers: () => void;
  runAllTimers: () => void;
  clearAllTimers: () => void;
  advanceTimersByTime: (ms: number) => void;
  advanceTimersByTimeAsync: (ms: number) => Promise<void>;
  clearAllMocks: () => void;
  resetAllMocks: () => void;
  spyOn: (...args: any[]) => any;
};
