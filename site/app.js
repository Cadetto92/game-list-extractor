"use strict";

const PLATFORM_ORDER = ["epic", "gog", "steam"];
const PLATFORM_NAMES = { epic: "Epic", gog: "GOG", steam: "Steam" };
const DEVICE_NAMES = { windows: "Windows", android: "Android" };

const state = { lists: [], tab: "all", device: "all", query: "" };
const $ = (id) => document.getElementById(id);

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function safeUrl(url) {
  return /^https:\/\//.test(url || "") ? url : null;
}

async function load() {
  try {
    const index = await (await fetch("data/index.json")).json();
    state.lists = await Promise.all(
      index.lists.map(async (name) => (await fetch("data/" + name)).json())
    );
  } catch (error) {
    $("summary").textContent = "";
    const box = $("error");
    box.hidden = false;
    box.textContent = "Could not load the game lists.";
    return;
  }
  render();
}

// One entry per title; "All" merges the same title across lists.
function visibleGames() {
  const merged = new Map();
  for (const list of state.lists) {
    if (state.tab !== "all" && list.platform !== state.tab) continue;
    if (state.tab === "epic" && state.device !== "all" && list.device !== state.device) continue;
    for (const game of list.games) {
      const key = game.title.trim().toLowerCase();
      if (!merged.has(key)) merged.set(key, { game, labels: new Set() });
      const entry = merged.get(key);
      entry.labels.add(
        list.platform === "epic" ? "Epic (" + DEVICE_NAMES[list.device] + ")" : PLATFORM_NAMES[list.platform]
      );
      if (!entry.game.url && game.url) entry.game = game;
    }
  }
  const q = state.query.trim().toLowerCase();
  return [...merged.entries()]
    .filter(([key]) => key.includes(q))
    .map(([, entry]) => entry)
    .sort((a, b) => a.game.title.localeCompare(b.game.title, undefined, { sensitivity: "base" }));
}

function countFor(platform) {
  const titles = new Set();
  for (const list of state.lists) {
    if (platform === "all" || list.platform === platform) {
      list.games.forEach((g) => titles.add(g.title.trim().toLowerCase()));
    }
  }
  return titles.size;
}

function button(label, selected, onClick, attr) {
  const b = el("button", label);
  b.type = "button";
  b.setAttribute(attr, String(selected));
  b.addEventListener("click", onClick);
  return b;
}

function render() {
  const platforms = PLATFORM_ORDER.filter((p) => state.lists.some((l) => l.platform === p));
  const dates = state.lists.map((l) => l.extract_date).sort();
  $("summary").textContent =
    countFor("all") + " games · last updated " + (dates[dates.length - 1] || "n/a");

  const tabs = $("tabs");
  tabs.replaceChildren(
    ...["all", ...platforms].map((p) =>
      button(
        (p === "all" ? "All" : PLATFORM_NAMES[p]) + " (" + countFor(p) + ")",
        state.tab === p,
        () => { state.tab = p; state.device = "all"; render(); },
        "aria-selected"
      )
    )
  );
  tabs.querySelectorAll("button").forEach((b) => b.setAttribute("role", "tab"));

  const devices = $("devices");
  devices.hidden = state.tab !== "epic";
  if (!devices.hidden) {
    const epicDevices = state.lists.filter((l) => l.platform === "epic").map((l) => l.device);
    devices.replaceChildren(
      ...["all", ...epicDevices].map((d) =>
        button(d === "all" ? "All" : DEVICE_NAMES[d], state.device === d,
          () => { state.device = d; render(); }, "aria-pressed")
      )
    );
  }

  const games = visibleGames();
  $("count").textContent = games.length + " games";
  $("platform-head").hidden = state.tab !== "all" && state.tab !== "epic";

  const rows = games.map(({ game, labels }) => {
    const tr = el("tr");
    const title = el("td");
    const href = safeUrl(game.url);
    if (href) {
      const a = el("a", game.title);
      a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
      title.append(a);
    } else {
      title.textContent = game.title;
    }
    tr.append(title, el("td", [game.developer, game.category].filter(Boolean).join(" · ")));
    const chips = el("td");
    labels.forEach((label) => chips.append(el("span", label, "chip")));
    chips.hidden = state.tab !== "all" && state.tab !== "epic";
    tr.append(chips);
    return tr;
  });
  $("rows").replaceChildren(...rows);
}

$("search").addEventListener("input", (event) => { state.query = event.target.value; render(); });
load();
