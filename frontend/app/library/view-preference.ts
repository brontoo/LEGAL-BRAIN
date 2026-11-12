/** Hydration-safe external preference store; storage failures retain session choice. */
export type LibraryView = "list" | "grid";
const VIEW_KEY = "library.view";
const CHANGE_EVENT = "library-view-change";
let sessionChoice: LibraryView | null = null;

export function readView(): LibraryView {
  if (sessionChoice) return sessionChoice;
  try {
    return window.localStorage.getItem(VIEW_KEY) === "grid" ? "grid" : "list";
  } catch {
    return "list";
  }
}
export function serverView(): LibraryView { return "list"; }
export function subscribeView(notify: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === VIEW_KEY || event.key === null) {
      sessionChoice = null;
      notify();
    }
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener(CHANGE_EVENT, notify);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(CHANGE_EVENT, notify);
  };
}
export function changeView(next: LibraryView): void {
  sessionChoice = next;
  try { window.localStorage.setItem(VIEW_KEY, next); } catch {
    // A blocked storage API must not prevent switching the current view.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}
