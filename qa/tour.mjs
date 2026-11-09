#!/usr/bin/env node
/**
 * pvorg-web screenshot tour and end-to-end checks (SPEC §14 verification).
 *
 *   node qa/tour.mjs [--out /tmp/pvorg-web-tour] [--only desktop-dark] [--no-e2e]
 *
 * Every run starts from a fresh copy of the fixture library, so it never touches
 * ~/pvorg.json or a real library:
 *   1. builds the fixture template once (scripts/make-fixture.sh → /tmp/pvorg-web-template),
 *   2. copies it to /tmp/pvorg-web-run and starts the backend on port 8765 with
 *      PVORG_CONFIG / PVORG_CACHE_DIR pointing there,
 *   3. screenshots every page and state in Light and Dark at 1440×900 and 390×844,
 *   4. runs the end-to-end checks (including hiding the sidebar), and fails on any console
 *      error or warning.
 *
 * Requires a built frontend (cd frontend && npm run build) and the backend venv.
 */
import { chromium } from "@playwright/test";
import { spawn, execFileSync } from "node:child_process";
import { cpSync, createWriteStream, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const option = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : fallback;
};
const OUT = option("--out", "/tmp/pvorg-web-tour");
const ONLY = option("--only", null);
const E2E = !args.includes("--no-e2e");
const TEMPLATE = "/tmp/pvorg-web-template";
const RUN = "/tmp/pvorg-web-run";
const CACHE = "/tmp/pvorg-web-cache";
const PORT = 8765;
const BASE = `http://127.0.0.1:${PORT}`;
const CONFIG = join(RUN, "pvorg.json");
const VIDEOS = join(RUN, "videos");

const VIEWPORTS = { desktop: { width: 1440, height: 900 }, narrow: { width: 390, height: 844 } };
const THEMES = ["light", "dark"];

const consoleProblems = [];
const results = [];
let shots = 0;
let lastPage = null;

function check(name, ok, detail = "") {
  results.push({ name, ok, detail });
  console.log(`${ok ? "  ✓" : "  ✗"} ${name}${detail && !ok ? ` — ${detail}` : ""}`);
}

// ---------------------------------------------------------------- fixture + server

function prepareLibrary() {
  if (!existsSync(join(TEMPLATE, "pvorg.json"))) {
    console.log("Building fixture template…");
    execFileSync(join(ROOT, "scripts/make-fixture.sh"), [TEMPLATE], { stdio: "inherit" });
  }
  rmSync(RUN, { recursive: true, force: true });
  cpSync(TEMPLATE, RUN, { recursive: true });
  writeFileSync(CONFIG, readFileSync(CONFIG, "utf8").replaceAll(TEMPLATE, RUN));
}

function startServer(port, config) {
  const python = join(ROOT, "backend/.venv/bin/python");
  const child = spawn(python, ["-c", "import main; main.run()"], {
    cwd: join(ROOT, "backend"),
    env: { ...process.env, PVORG_CONFIG: config, PVORG_CACHE_DIR: CACHE, PVORG_PORT: String(port) },
    stdio: ["ignore", "ignore", "pipe"],
  });
  const log = createWriteStream(join(OUT, `server-${port}.log`));
  child.stderr.pipe(log);
  return child;
}

async function api(path, body, method = body === undefined ? "GET" : "POST") {
  const response = await fetch(`${BASE}${path}`, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${method} ${path} → ${response.status}`);
  return response.json();
}

async function waitFor(fn, timeout = 120_000, interval = 150) {
  const start = Date.now();
  for (;;) {
    try {
      const value = await fn();
      if (value) return value;
    } catch {
      /* not yet */
    }
    if (Date.now() - start > timeout) throw new Error("Timed out");
    await new Promise((r) => setTimeout(r, interval));
  }
}

const statusOf = (base = BASE) => fetch(`${base}/api/status`).then((r) => r.json());
const ready = () => waitFor(async () => (await statusOf()).phase === "ready");

/** Move the viewer to the first combination matching `predicate`. */
async function gotoCombination(predicate) {
  const { total } = await api("/api/viewer");
  for (let index = 0; index < total; index += 1) {
    const viewer = await api("/api/viewer/move", { index });
    if (viewer.current && predicate(viewer.current)) return viewer;
  }
  throw new Error("No matching combination");
}

/** JSON text with object keys sorted, for comparing content regardless of formatting. */
function canonical(text) {
  const sort = (v) => Array.isArray(v) ? v.map(sort)
    : v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, sort(v[k])])) : v;
  return JSON.stringify(sort(JSON.parse(text)));
}

// ---------------------------------------------------------------- browser helpers

async function newPage(browser, viewport, theme) {
  const context = await browser.newContext({
    viewport: VIEWPORTS[viewport],
    deviceScaleFactor: viewport === "narrow" ? 2 : 1,
    hasTouch: viewport === "narrow",
    colorScheme: theme,
  });
  await context.addInitScript((t) => {
    if (!localStorage.getItem("pvorg.appearance")) localStorage.setItem("pvorg.appearance", t);
  }, theme);
  const page = await context.newPage();
  lastPage = page;
  const label = `${viewport}-${theme}`;
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      consoleProblems.push(`[${label}] ${message.type()}: ${message.text()} (${page.url()})`);
    }
  });
  page.on("pageerror", (error) => consoleProblems.push(`[${label}] pageerror: ${error.message}`));
  return page;
}

async function open(page, path) {
  await page.goto(`${BASE}${path}`);
  await page.locator("#page-title").first().waitFor();
  await settle(page);
}

async function settle(page, extra = 250) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  // Let lazy thumbnails decode and fade in.
  await page
    .waitForFunction(() => [...document.images].filter((i) => i.loading === "lazy" && i.getBoundingClientRect().top < innerHeight)
      .every((i) => i.complete), null, { timeout: 5000 })
    .catch(() => undefined);
  await page.waitForTimeout(extra);
}

function shooter(page, prefix) {
  let n = 0;
  return async (name, options = {}) => {
    n += 1;
    const file = join(OUT, `${prefix}-${String(n).padStart(2, "0")}-${name}.png`);
    await page.screenshot({ path: file, ...options });
    shots += 1;
  };
}

const mod = "ControlOrMeta";

// ---------------------------------------------------------------- the tour

async function tour(browser, viewport, theme) {
  const page = await newPage(browser, viewport, theme);
  const shot = shooter(page, `${viewport}-${theme}`);
  const desktop = viewport === "desktop";
  console.log(`Tour ${viewport} ${theme}`);

  // Viewer: contact sheet, then video.
  await api("/api/filters/reset", {});
  await gotoCombination((c) => c.video.filename === "acme-jane_doe-harbor_lights.mp4");
  await open(page, "/");
  await page.waitForTimeout(600);
  await shot("viewer-contact-sheet");

  await page.keyboard.press("p");
  await page.locator("video").waitFor();
  await page.waitForFunction(() => (document.querySelector("video")?.readyState ?? 0) >= 2);
  await page.keyboard.press("4");
  await page.evaluate(() => document.querySelector("video")?.pause());
  await page.waitForTimeout(300);
  if (desktop) {
    const scrubber = page.getByRole("slider", { name: "Playback position" });
    const box = await scrubber.boundingBox();
    await page.mouse.move(box.x + box.width * 0.6, box.y + box.height / 2);
    await page.waitForTimeout(400);
  }
  await shot("viewer-video");
  await page.mouse.move(5, 5);

  // Context menu and Exclude Pairing toast (then undo, restoring pvorg.json).
  if (desktop) {
    await page.keyboard.press("p");
    await page.locator(".stage__media").click({ button: "right", position: { x: 200, y: 200 } });
    await page.getByRole("menu").waitFor();
    await shot("viewer-context-menu");
    await page.keyboard.press("Escape");
  }
  await page.keyboard.press("Backspace");
  await page.locator(".toast").waitFor();
  await page.waitForTimeout(400);
  await shot("viewer-exclude-toast");
  await page.keyboard.press(`${mod}+z`);
  await page.waitForTimeout(400);

  // Unplayable video (.avi) and an empty gallery.
  await gotoCombination((c) => c.video.extension === "avi");
  await open(page, "/");
  await page.keyboard.press("p");
  await page.getByText("Can’t Play This Video").waitFor();
  await page.waitForTimeout(300);
  await shot("viewer-unplayable");

  await gotoCombination((c) => c.gallery.images.length === 0);
  await open(page, "/");
  await page.waitForTimeout(300);
  await shot("viewer-empty-gallery");

  // No matching combinations.
  await api("/api/filters", { galleries: [] }, "PUT");
  await open(page, "/");
  await shot("viewer-no-matches");
  await api("/api/filters/reset", {});

  // Filters.
  await api("/api/filters", { studios: ["acme", "globex", "hooli"], tags: ["outdoor"] }, "PUT");
  await open(page, "/filters");
  await shot("filters");
  await page.getByRole("searchbox", { name: "Filter names" }).fill("ja");
  await page.waitForTimeout(150);
  await shot("filters-search");
  await api("/api/filters/reset", {});

  // Library.
  await open(page, "/library");
  await shot("library");
  if (desktop) {
    await page.locator(".card__media").nth(2).hover();
    await page.waitForTimeout(700);
    await shot("library-hover-preview");
    await page.mouse.move(5, 5);
  }
  await page.locator(".card__button").nth(0).click();
  await page.locator(".card__button").nth(3).click();
  await page.waitForTimeout(200);
  await shot("library-selection");
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.locator("dialog[open]").waitFor();
  await page.waitForTimeout(250);
  await shot("library-delete-confirm");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Deselect All" }).click();
  await page.getByRole("button", { name: "Show Files" }).click();
  await page.locator("dialog[open]").waitFor();
  await page.waitForTimeout(250);
  await shot("library-skipped-files");
  await page.keyboard.press("Escape");
  await page.getByRole("searchbox", { name: "Search videos" }).fill("zzz");
  await page.waitForTimeout(150);
  await shot("library-no-results");
  await page.getByRole("searchbox", { name: "Search videos" }).fill("");

  // Gallery Mapping with pending changes and the column menu.
  await open(page, "/mapping/galleries");
  await shot("gallery-mapping");
  await page.getByRole("radio", { name: "All" }).check({ force: true });
  await page.waitForTimeout(150);
  const cells = page.locator(".matrix__cell-button");
  await cells.nth(0).click();
  await cells.nth(10).click();
  await cells.nth(10).click();
  await cells.nth(21).click();
  await page.locator(".matrix__column-button").nth(1).click();
  await page.getByRole("menu").waitFor();
  await shot("gallery-mapping-pending-menu");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Revert" }).click();
  await page.locator("dialog[open]").waitFor();
  await page.waitForTimeout(250);
  await shot("gallery-mapping-revert-confirm");
  await page.getByRole("button", { name: "Discard Changes" }).click();

  // Tag Mapping.
  await open(page, "/mapping/tags");
  await shot("tag-mapping");

  // Settings and Clean Up Stale Entries.
  await open(page, "/settings");
  await shot("settings");
  await page.getByRole("button", { name: "Clean Up Stale Entries…" }).click();
  await page.locator("dialog[open]").waitFor();
  await page.waitForTimeout(250);
  await shot("cleanup");
  await page.keyboard.press("Escape");

  if (!desktop) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.locator("dialog.drawer[open]").waitFor();
    await page.waitForTimeout(350);
    await shot("navigation-drawer");
    await page.keyboard.press("Escape");
  } else {
    await page.getByRole("button", { name: "More" }).click();
    await page.getByRole("menu").waitFor();
    await shot("more-menu");
    await page.keyboard.press("Escape");
  }

  if (desktop) {
    // Sidebar hidden (SPEC §4.1): the page takes the whole window.
    await gotoCombination((c) => c.video.filename === "acme-jane_doe-harbor_lights.mp4");
    await open(page, "/");
    await page.getByRole("button", { name: "Hide Sidebar" }).click();
    await page.waitForTimeout(400);
    await page.mouse.move(5, 300);
    await shot("sidebar-hidden-viewer");
    await page.keyboard.press("p");
    await page.locator("video").waitFor();
    await page.waitForFunction(() => (document.querySelector("video")?.readyState ?? 0) >= 2);
    await page.keyboard.press("4");
    await page.evaluate(() => document.querySelector("video")?.pause());
    await page.waitForTimeout(300);
    await shot("sidebar-hidden-viewer-video");
    await open(page, "/library");
    await shot("sidebar-hidden-library");
    await open(page, "/mapping/galleries");
    await page.getByRole("radio", { name: "All" }).check({ force: true });
    await page.locator(".matrix__cell-button").nth(0).click();
    await page.locator(".matrix__cell-button").nth(21).click();
    await page.mouse.move(5, 300);
    await page.waitForTimeout(150);
    await shot("sidebar-hidden-mapping-pending");
    await page.getByRole("button", { name: "Revert" }).click();
    await page.getByRole("button", { name: "Discard Changes" }).click();
    await page.getByRole("button", { name: "Show Sidebar" }).click();
    await page.waitForTimeout(400);
  }

  await page.goto(`${BASE}/nowhere`);
  await page.getByText("Page Not Found").waitFor();
  await shot("not-found");

  await page.context().close();
}

// ---------------------------------------------------------------- end-to-end checks

async function e2e(browser) {
  console.log("End-to-end checks");
  const page = await newPage(browser, "desktop", "dark");
  await api("/api/filters/reset", {});

  // Typing always wins: letters typed in a search field reach the field.
  await open(page, "/library");
  const search = page.getByRole("searchbox", { name: "Search videos" });
  await search.click();
  await page.keyboard.type("vcnp");
  check("letters typed into search reach the field", (await search.inputValue()) === "vcnp");
  check("typing V/C in search does not navigate", new URL(page.url()).pathname === "/library");
  await page.keyboard.press("Escape");
  check("Esc clears the search field", (await search.inputValue()) === "");

  // Viewer keys are scoped to the viewer.
  const before = (await api("/api/viewer")).position;
  await page.locator("#page-title").click();
  await page.keyboard.press("n");
  check("N outside the viewer does nothing", (await api("/api/viewer")).position === before);
  await page.keyboard.press("v");
  await page.waitForURL(`${BASE}/`);
  check("V goes to the Viewer", new URL(page.url()).pathname === "/");
  await page.keyboard.press("c");
  await page.waitForURL(`${BASE}/filters`);
  check("C goes to Filters", new URL(page.url()).pathname === "/filters");
  await page.keyboard.press("v");
  await page.waitForURL(`${BASE}/`);
  await settle(page);
  await page.keyboard.press("n");
  await waitFor(async () => (await api("/api/viewer")).position === before + 1, 5000);
  check("N in the viewer goes to the next combination", (await api("/api/viewer")).position === before + 1);
  await page.keyboard.press("b");
  await waitFor(async () => (await api("/api/viewer")).position === before, 5000).catch(() => undefined);
  await page.locator(".viewer__position").getByText(`${before + 1} of`).waitFor();
  check("B goes back", (await api("/api/viewer")).position === before);
  await page.keyboard.press(" ");
  check("Space in contact-sheet mode doesn’t switch to video", (await page.locator("video").count()) === 0);

  // Exclude Pairing + undo returns pvorg.json to its exact content and order.
  const original = readFileSync(CONFIG, "utf8");
  const start = await api("/api/viewer");
  const { filename } = start.current.video;
  const gallery = start.current.gallery.name;
  await page.keyboard.press("Backspace");
  await page.locator(".toast").getByText("Undo").waitFor();
  await waitFor(() => readFileSync(CONFIG, "utf8") !== original, 5000).catch(() => undefined);
  const excluded = JSON.parse(readFileSync(CONFIG, "utf8"));
  const after = await api("/api/viewer");
  check("Exclude Pairing records the exclusion in pvorg.json",
    excluded.videoRelations[filename]?.excludedGalleries?.includes(gallery) === true);
  check("Exclude Pairing removes exactly one combination in place",
    after.total === start.total - 1 && after.position === start.position);
  await page.locator(".toast").getByRole("button", { name: "Undo" }).click();
  const sameContent = () => canonical(readFileSync(CONFIG, "utf8")) === canonical(original);
  await waitFor(sameContent, 5000).catch(() => undefined);
  // The fixture's pvorg.json is hand-formatted, so the first undo restores its content;
  // once pvorg has written the file, later undos restore it byte for byte.
  check("Undo (toast) restores pvorg.json’s original content", sameContent());
  const undone = await api("/api/viewer");
  check("Undo puts the pairing back in the same place",
    undone.total === start.total && undone.current?.video.filename === filename && undone.current?.gallery.name === gallery);
  const written = readFileSync(CONFIG, "utf8");
  await page.keyboard.press("Backspace");
  await waitFor(() => readFileSync(CONFIG, "utf8") !== written, 5000).catch(() => undefined);
  await page.keyboard.press(`${mod}+z`);
  await waitFor(() => readFileSync(CONFIG, "utf8") === written, 5000).catch(() => undefined);
  check("Undo (⌘/Ctrl+Z) restores pvorg.json byte for byte", readFileSync(CONFIG, "utf8") === written);
  await page.keyboard.press(`${mod}+Shift+z`);
  await waitFor(() => readFileSync(CONFIG, "utf8") !== written, 5000).catch(() => undefined);
  check("Redo excludes the pairing again",
    JSON.parse(readFileSync(CONFIG, "utf8")).videoRelations[filename]?.excludedGalleries?.includes(gallery) === true);
  await page.keyboard.press(`${mod}+z`);
  await waitFor(() => readFileSync(CONFIG, "utf8") === written, 5000).catch(() => undefined);

  // Mapping: pending changes survive navigation, badge, ⌘S saves.
  await open(page, "/mapping/tags");
  await page.getByRole("radio", { name: "All" }).check({ force: true });
  const row = page.locator(".matrix tbody tr:not([aria-hidden])").first();
  const rowTitle = (await row.locator(".matrix__title").textContent()).trim();
  const target = (await api("/api/mapping/tags")).rows.find((r) => r.title === rowTitle);
  const firstTag = (await api("/api/mapping/tags")).columns[0];
  const savedState = target.states[0];
  await row.locator(".matrix__cell-button").first().click();
  check("an edited cell is marked unsaved", (await row.locator(".tri.is-modified").count()) === 1);
  check("the sidebar badge counts unsaved changes",
    (await page.locator(".sidebar .nav__badge").first().textContent())?.trim() === "1");
  await page.getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: /Tag Mapping/ }).click();
  await page.locator(".matrix").waitFor();
  check("unsaved changes survive navigation", (await page.locator(".tri.is-modified").count()) === 1);
  await page.locator("#page-title").click();
  await page.keyboard.press(`${mod}+s`);
  await page.locator(".toast").getByText("Saved 1 change").waitFor();
  const savedConfig = JSON.parse(readFileSync(CONFIG, "utf8"));
  const relation = savedConfig.videoRelations[target.filename] ?? {};
  const expected = { u: "tags", y: "excludedTags", n: null }[savedState];
  check("⌘/Ctrl+S saves the cell to pvorg.json",
    savedState === "n" ? !relation.tags?.includes(firstTag) && !relation.excludedTags?.includes(firstTag)
      : relation[expected]?.includes(firstTag) === true);
  check("saving clears the badge", (await page.locator(".sidebar .nav__badge").count()) === 0);

  // Delete confirmation: named, Cancel is the default, then delete removes every asset.
  await open(page, "/library");
  const victim = "umbrella-sam_lee-market_day.mp4";
  await page.getByRole("searchbox", { name: "Search videos" }).fill("market");
  await page.locator(".card__button").first().click();
  await page.locator("#page-title").click();
  await page.keyboard.press(`${mod}+Backspace`);
  const dialog = page.locator("dialog[open]");
  await dialog.waitFor();
  check("delete confirmation names the video", (await dialog.locator("h2").textContent()) === "Delete “Market Day”?");
  check("Cancel is the default button", (await page.evaluate(() => document.activeElement?.textContent)) === "Cancel");
  await page.keyboard.press("Enter");
  await dialog.waitFor({ state: "detached" }).catch(() => undefined);
  await page.waitForTimeout(200);
  check("Enter on the default button cancels", existsSync(join(VIDEOS, victim)));
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.locator("dialog[open]").getByRole("button", { name: "Delete “Market Day”" }).click();
  await page.locator(".toast").getByText("Deleted 1 video").waitFor();
  check("delete removes the video and its contact sheet and sprites",
    !existsSync(join(VIDEOS, victim)) && !existsSync(join(VIDEOS, "img", `${victim}.jpg`))
      && !existsSync(join(VIDEOS, "sprite", `${victim}_sprite.jpg`)) && !existsSync(join(VIDEOS, "sprite", `${victim}_sprite.vtt`)));
  check("delete removes the cached metadata",
    !Object.keys(JSON.parse(readFileSync(join(VIDEOS, "cache.json"), "utf8"))).includes(victim));

  // Accessibility smoke checks.
  for (const path of ["/", "/filters", "/library", "/mapping/galleries", "/settings"]) {
    await open(page, path);
    const unnamed = await page.evaluate(() =>
      [...document.querySelectorAll("button, a[href], input, [role=slider], [role=radio]")]
        .filter((el) => el.getClientRects().length && !el.closest("[aria-hidden=true]"))
        .filter((el) => {
          const label = el.getAttribute("aria-label") || el.textContent?.trim() || el.getAttribute("title")
            || (el.id && document.querySelector(`label[for="${el.id}"]`)) || el.closest("label")?.textContent?.trim();
          return !label;
        }).map((el) => el.outerHTML.slice(0, 80)));
    check(`every control on ${path} has an accessible name`, unnamed.length === 0, unnamed.join(", "));
  }
  await page.context().close();
}

// ---------------------------------------------------------------- hiding the sidebar

async function sidebarChecks(browser) {
  console.log("Sidebar checks");
  const page = await newPage(browser, "desktop", "dark");
  await api("/api/filters/reset", {});
  // A playable video, not whatever the shuffle lands on (the fixture's .avi can't play).
  await gotoCombination((c) => c.video.filename === "acme-jane_doe-harbor_lights.mp4");
  await open(page, "/");
  const mac = await page.evaluate(() =>
    /mac/i.test(navigator.userAgentData?.platform ?? navigator.platform));
  const shortcut = mac ? "Control+Meta+s" : "Control+Backslash";
  const toggle = page.locator("#sidebar-toggle");
  const geometry = () => page.evaluate(() => {
    const sidebar = document.querySelector(".sidebar").getBoundingClientRect();
    return {
      sidebarRight: Math.round(sidebar.right),
      mainLeft: Math.round(document.querySelector(".main").getBoundingClientRect().left),
      stage: Math.round(document.querySelector(".stage")?.getBoundingClientRect().width ?? 0),
      visibility: getComputedStyle(document.querySelector(".sidebar")).visibility,
      stored: localStorage.getItem("pvorg.sidebar"),
    };
  });
  const settled = () => page.waitForTimeout(350);

  const shown = await geometry();
  check("the sidebar is shown by default", shown.mainLeft >= 240 && shown.visibility === "visible", JSON.stringify(shown));
  check("the toggle leads the page header",
    await page.evaluate(() => document.querySelector(".page-header")?.firstElementChild?.id === "sidebar-toggle"));
  check("the toggle is labeled Hide Sidebar, expanded, and controls the sidebar",
    (await toggle.getAttribute("aria-label")) === "Hide Sidebar" && (await toggle.getAttribute("aria-expanded")) === "true"
      && (await toggle.getAttribute("aria-controls")) === "sidebar" && (await page.locator("#sidebar").count()) === 1);
  check("the toggle's tooltip names the shortcut", (await toggle.getAttribute("title")) === `Hide Sidebar (${mac ? "⌃⌘S" : "Ctrl+\\"})`);
  check("the sidebar animates over about 0.2 s",
    await page.evaluate(() => getComputedStyle(document.querySelector(".shell")).transitionDuration === "0.2s"));

  // The video element survives hiding and showing (no re-mount, playback position kept).
  await page.keyboard.press("p");
  await page.locator("video").waitFor();
  await page.waitForFunction(() => (document.querySelector("video")?.readyState ?? 0) >= 2);
  await page.evaluate(() => {
    const video = document.querySelector("video");
    video.pause();
    video.currentTime = 3;
    video.dataset.probe = "same";
  });
  await page.waitForFunction(() => Math.abs(document.querySelector("video").currentTime - 3) < 0.2);
  await toggle.click();
  await settled();
  const hidden = await geometry();
  check("Hide Sidebar gives the page the whole window",
    hidden.mainLeft === 0 && hidden.sidebarRight <= 0 && hidden.visibility === "hidden", JSON.stringify(hidden));
  check("the viewer stage grows into the freed width", hidden.stage >= shown.stage + 180, `${shown.stage} → ${hidden.stage}`);
  check("the toggle then reads Show Sidebar, collapsed",
    (await toggle.getAttribute("aria-label")) === "Show Sidebar" && (await toggle.getAttribute("aria-expanded")) === "false");
  check("the hidden sidebar is inert", await page.evaluate(() => document.querySelector("#sidebar").inert === true));
  check("hiding keeps the same video element and position", await page.evaluate(() => {
    const video = document.querySelector("video");
    return video?.dataset.probe === "same" && Math.abs(video.currentTime - 3) < 0.2;
  }));
  await page.keyboard.press("p");

  await page.reload();
  await page.locator("#page-title").waitFor();
  check("the hidden sidebar survives a reload",
    (await geometry()).mainLeft === 0 && (await toggle.getAttribute("aria-label")) === "Show Sidebar");

  await page.locator("#page-title").click();
  await page.keyboard.press(shortcut);
  await settled();
  check(`${mac ? "⌃⌘S" : "Ctrl+\\"} shows the sidebar`, (await geometry()).mainLeft >= 240);
  await page.keyboard.press(shortcut);
  await settled();
  check(`${mac ? "⌃⌘S" : "Ctrl+\\"} hides it again`, (await geometry()).mainLeft === 0);
  check("the choice is stored in local storage", (await geometry()).stored === "hidden");
  await page.keyboard.press(shortcut);
  await settled();

  // The shortcut works while typing (it's a modified key) and leaves the field's text alone.
  await open(page, "/library");
  const search = page.getByRole("searchbox", { name: "Search videos" });
  await search.click();
  await search.fill("ja");
  await page.keyboard.press(shortcut);
  await settled();
  check("the shortcut works while typing in a search field",
    (await geometry()).mainLeft === 0 && (await search.inputValue()) === "ja");
  await page.keyboard.press(shortcut);
  await settled();
  await search.fill("");

  // Focus inside the sidebar moves to the toggle when the sidebar hides.
  await page.getByRole("link", { name: "Filters" }).focus();
  await page.keyboard.press(shortcut);
  await settled();
  check("hiding with focus in the sidebar moves focus to the toggle",
    await page.evaluate(() => document.activeElement?.id === "sidebar-toggle"));
  await page.keyboard.press("Enter");
  await settled();
  check("Enter on the focused toggle shows the sidebar again", (await geometry()).mainLeft >= 240);

  // The More menu offers Hide Sidebar too.
  await page.getByRole("button", { name: "More" }).click();
  const item = page.getByRole("menuitem", { name: /Hide Sidebar/ });
  check("the More menu has Hide Sidebar", (await item.count()) === 1);
  await item.click();
  await settled();
  check("Hide Sidebar from the More menu hides it and focuses the toggle",
    (await geometry()).mainLeft === 0 && await page.evaluate(() => document.activeElement?.id === "sidebar-toggle"));

  // Unsaved mapping changes put a dot on Show Sidebar.
  await open(page, "/mapping/tags");
  check("no dot without unsaved changes", (await page.locator(".sidebar-toggle__dot").count()) === 0);
  await page.getByRole("radio", { name: "All" }).check({ force: true });
  await page.locator(".matrix__cell-button").first().click();
  check("unsaved mapping changes put a dot on Show Sidebar",
    (await page.locator(".sidebar-toggle__dot").count()) === 1
      && (await toggle.getAttribute("aria-label")) === "Show Sidebar, unsaved mapping changes");
  await open(page, "/");
  check("the dot shows on every page", (await page.locator(".sidebar-toggle__dot").count()) === 1);
  await toggle.click();
  await settled();
  check("no dot while the sidebar (and its badge) shows",
    (await page.locator(".sidebar-toggle__dot").count()) === 0 && (await page.locator(".sidebar .nav__badge").count()) === 1);
  await open(page, "/mapping/tags");
  await page.getByRole("button", { name: "Revert" }).click();
  await page.getByRole("button", { name: "Discard Changes" }).click();

  // Reduced motion: hiding is instant.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await toggle.click();
  const instant = await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() =>
    resolve(Math.round(document.querySelector(".main").getBoundingClientRect().left)))));
  check("with reduced motion the sidebar hides instantly", instant === 0, `main at ${instant}px`);
  await page.emulateMedia({ reducedMotion: "no-preference" });

  // Narrow screens keep the drawer; the hidden setting doesn't apply.
  await page.setViewportSize(VIEWPORTS.narrow);
  await open(page, "/library");
  check("narrow: no sidebar toggle", !(await toggle.isVisible()));
  check("narrow: the top bar and menu button still show",
    await page.getByRole("button", { name: "Open navigation" }).isVisible());
  await page.locator("#page-title").click();
  await page.keyboard.press(shortcut);
  check("narrow: the shortcut leaves the setting alone", (await geometry()).stored === "hidden");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.locator("dialog.drawer[open]").waitFor();
  check("narrow: the drawer lists the pages", await page.locator("dialog.drawer").getByRole("link", { name: "Library" }).isVisible());
  await page.locator("dialog.drawer").getByRole("button", { name: "More" }).click();
  check("narrow: the drawer's More menu has no Hide Sidebar",
    (await page.getByRole("menuitem", { name: /Sidebar/ }).count()) === 0);
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.setViewportSize(VIEWPORTS.desktop);
  await page.waitForTimeout(200);
  check("back at desktop width, the sidebar is still hidden", (await geometry()).mainLeft === 0);
  await page.context().close();
}

// ---------------------------------------------------------------- startup states

async function startupStates(browser) {
  console.log("Startup states");
  for (const theme of THEMES) {
    for (const viewport of Object.keys(VIEWPORTS)) {
      if (ONLY && ONLY !== `${viewport}-${theme}`) continue;
      const page = await newPage(browser, viewport, theme);
      const shot = shooter(page, `${viewport}-${theme}-startup`);
      // Reload shows the progress screen while the library is rescanned.
      await page.route("**/api/status", async (route) => {
        const response = await route.fetch();
        const json = await response.json();
        await route.fulfill({ response, json: { ...json, phase: "loading", step: "Preparing Previews",
          detail: "12 of 26 · hooli-li_wei-neon_alley.mp4", fraction: 0.46 } });
      });
      await page.goto(`${BASE}/`);
      await page.getByRole("progressbar").waitFor();
      await shot("progress");
      await page.unroute("**/api/status");
      await page.route("**/api/status", async (route) => {
        const response = await route.fetch();
        const json = await response.json();
        await route.fulfill({ response, json: { ...json, phase: "error", configPath: "/Users/you/pvorg.json",
          error: "The file “/Users/you/pvorg.json” couldn’t be found." } });
      });
      await page.goto(`${BASE}/`);
      await page.getByText("Couldn’t Load Your Library").waitFor();
      await shot("error");
      await page.context().close();
    }
  }
}

// ---------------------------------------------------------------- main

async function main() {
  if (!existsSync(join(ROOT, "frontend/dist/index.html"))) throw new Error("Build the frontend first: cd frontend && npm run build");
  rmSync(OUT, { recursive: true, force: true });
  mkdirSync(OUT, { recursive: true });
  prepareLibrary();
  const server = startServer(PORT, CONFIG);
  const browser = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required"] });
  try {
    await ready();
    const status = await statusOf();
    check("server reached ready on the fixture library", status.library.videos > 20, JSON.stringify(status.library));

    // A real startup error, from a server pointed at a missing file.
    const broken = startServer(PORT + 1, "/tmp/pvorg-web-run/missing.json");
    const failed = await waitFor(async () => {
      const s = await statusOf(`http://127.0.0.1:${PORT + 1}`);
      return s.phase === "error" && s;
    }, 20_000).finally(() => broken.kill());
    check("a missing pvorg.json reports a startup error", /couldn’t be found/.test(failed.error ?? ""), failed.error);

    for (const theme of THEMES) {
      for (const viewport of Object.keys(VIEWPORTS)) {
        if (ONLY && ONLY !== `${viewport}-${theme}`) continue;
        await tour(browser, viewport, theme);
      }
    }
    await startupStates(browser);
    if (E2E) {
      await e2e(browser);
      await sidebarChecks(browser);
    }
  } catch (error) {
    await lastPage?.screenshot({ path: join(OUT, "failure.png") }).catch(() => undefined);
    console.error(consoleProblems.join("\n"));
    throw error;
  } finally {
    await browser.close();
    server.kill();
  }

  check("no console errors or warnings", consoleProblems.length === 0, `\n    ${consoleProblems.join("\n    ")}`);
  const failedChecks = results.filter((r) => !r.ok);
  console.log(`\n${shots} screenshots in ${OUT}`);
  console.log(`${results.length - failedChecks.length} of ${results.length} checks passed`);
  process.exit(failedChecks.length ? 1 : 0);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
