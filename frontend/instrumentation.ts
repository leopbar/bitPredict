export async function register() {
  if (typeof localStorage !== "undefined" && typeof localStorage.getItem !== "function") {
    const noopStorage: Storage = {
      getItem: () => null,
      setItem: () => undefined,
      removeItem: () => undefined,
      clear: () => undefined,
      length: 0,
      key: () => null,
    };
    try {
      Object.defineProperty(globalThis, "localStorage", {
        value: noopStorage,
        writable: true,
        configurable: true,
      });
    } catch {
      // ignore
    }
  }
}
