const DEDAULT_KEY = 'local';

export const localStg = {
  get<T>(key: string): T | null {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as T;
    } catch {
      return raw as unknown as T;
    }
  },
  set(key: string, value: unknown) {
    localStorage.setItem(key, JSON.stringify(value));
  },
  remove(key: string) {
    localStorage.removeItem(key);
  },
  clear() {
    localStorage.clear();
  }
};

export const sessionStg = {
  get<T>(key: string): T | null {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as T;
    } catch {
      return raw as unknown as T;
    }
  },
  set(key: string, value: unknown) {
    sessionStorage.setItem(key, JSON.stringify(value));
  },
  remove(key: string) {
    sessionStorage.removeItem(key);
  }
};

export { DEDAULT_KEY };
