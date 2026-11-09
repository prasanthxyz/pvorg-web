import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Settings } from "../api/types";
import { Button, IconButton, Kbd, Segmented } from "../components/controls";
import { PageHeader } from "../components/feedback";
import { openCleanup } from "../components/CleanupDialog";
import { appearance, setAppearance, type Appearance } from "../state/appearance";
import { dataVersion, showError, showToast } from "../state/feedback";
import { commandKey, reloadLibrary } from "../state/status";
import { useStore } from "../state/store";

export default function SettingsPage() {
  const choice = useStore(appearance);
  const version = useStore(dataVersion);
  const [settings, setSettings] = useState<Settings | null>(null);

  useEffect(() => {
    document.title = "Settings – pvorg";
    let cancelled = false;
    api.settings().then((s) => !cancelled && setSettings(s)).catch((e) => showError("Couldn’t Load Settings", e));
    return () => {
      cancelled = true;
    };
  }, [version]);

  const mod = commandKey();
  const shortcuts: [string, string[]][] = [
    ["Go to Viewer", ["V"]],
    ["Go to Filters", ["C"]],
    ["Contact sheet / video", ["P"]],
    ["Previous / next combination", ["B", "N"]],
    ["Exclude Pairing", ["⌫"]],
    ["Play / pause (video)", ["Space"]],
    ["Skip back / forward 10 s (video)", ["←", "→"]],
    ["Jump to 0%…90% (video)", ["0", "…", "9"]],
    ["Undo / redo", [`${mod}Z`, mod === "⌘" ? "⇧⌘Z" : "Ctrl+Shift+Z"]],
    ["Library: select all / deselect all", [`${mod}A`, "Esc"]],
    ["Library: delete selected", [`${mod}⌫`]],
    ["Mapping: save changes", [`${mod}S`]],
  ];

  return (
    <div className="settings">
      <PageHeader title="Settings" />
      <div className="page-scroll">
        <div className="settings__content">
          <section className="settings-group" aria-labelledby="settings-appearance">
            <h2 id="settings-appearance" className="settings-group__title">Appearance</h2>
            <div className="settings-row">
              <div className="settings-row__text">
                <span className="settings-row__label" id="appearance-label">Theme</span>
                <span className="settings-row__note">The viewer stage stays dark in every appearance.</span>
              </div>
              <Segmented<Appearance>
                label="Appearance"
                value={choice}
                onChange={setAppearance}
                options={[
                  { value: "system", label: "System" },
                  { value: "light", label: "Light" },
                  { value: "dark", label: "Dark" },
                ]}
              />
            </div>
          </section>

          <section className="settings-group" aria-labelledby="settings-library">
            <h2 id="settings-library" className="settings-group__title">Library</h2>
            <PathRow label="Configuration file" path={settings?.configPath ?? null} />
            <PathRow label="Videos folder" path={settings?.videosPath ?? null} />
            <PathRow label="Galleries folder" path={settings?.galleriesPath ?? null} />
            <div className="settings-row settings-row--actions">
              <span className="settings-row__note">
                Set <code>PVORG_CONFIG</code> before starting the server to use a different library.
              </span>
              <span className="settings-row__buttons">
                <Button icon="refresh" onClick={() => void reloadLibrary()}>Reload Library</Button>
                <Button icon="cleanup" onClick={openCleanup}>Clean Up Stale Entries…</Button>
              </span>
            </div>
          </section>

          <section className="settings-group" aria-labelledby="settings-keys">
            <h2 id="settings-keys" className="settings-group__title">Keyboard Shortcuts</h2>
            <p className="settings-group__note">Shortcuts pause while you type in a search field.</p>
            <dl className="shortcut-list">
              {shortcuts.map(([action, keys]) => (
                <div key={action} className="shortcut-list__row">
                  <dt>{action}</dt>
                  <dd>
                    {keys.map((k) => (k === "…" ? <span key={k} aria-hidden="true">…</span> : <Kbd key={k}>{k}</Kbd>))}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </div>
    </div>
  );
}

function PathRow({ label, path }: { label: string; path: string | null }) {
  const copy = async () => {
    if (!path) return;
    try {
      await navigator.clipboard.writeText(path);
      showToast("Copied path");
    } catch (error) {
      showError("Couldn’t Copy the Path", error);
    }
  };
  return (
    <div className="settings-row">
      <div className="settings-row__text">
        <span className="settings-row__label">{label}</span>
        <span className="settings-row__path" title={path ?? undefined}>
          <MiddleTruncate text={path ?? "—"} />
        </span>
      </div>
      <IconButton icon="copy" label={`Copy ${label.toLowerCase()} path`} disabled={!path} onClick={() => void copy()} />
    </div>
  );
}

/** Paths truncate in the middle so the file name stays visible (SPEC §8.4). */
export function MiddleTruncate({ text }: { text: string }) {
  const cut = Math.max(0, text.length - Math.min(28, Math.floor(text.length / 2)));
  return (
    <span className="middle-truncate">
      <span className="middle-truncate__start">{text.slice(0, cut)}</span>
      <span className="middle-truncate__end">{text.slice(cut)}</span>
    </span>
  );
}
