/** Storage may be unavailable in embedded browsers; it must not prevent editing a farm. */
export function readPreference(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}
export function writePreference(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* The current selection still works. */
  }
}
