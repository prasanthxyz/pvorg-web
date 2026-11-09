import { createStore } from "./store";

export type Appearance = "system" | "light" | "dark";

const KEY = "pvorg.appearance";

function stored(): Appearance {
  const value = localStorage.getItem(KEY);
  return value === "system" || value === "light" || value === "dark" ? value : "dark";
}

/** Dark is the default, as in the other apps (SPEC §6.5). */
export const appearance = createStore<Appearance>(stored());

const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

function apply(): void {
  const choice = appearance.get();
  const resolved = choice === "system" ? (systemDark.matches ? "dark" : "light") : choice;
  document.documentElement.dataset.theme = resolved;
}

export function setAppearance(choice: Appearance): void {
  localStorage.setItem(KEY, choice);
  appearance.set(choice);
}

appearance.subscribe(apply);
systemDark.addEventListener("change", apply);
apply();
