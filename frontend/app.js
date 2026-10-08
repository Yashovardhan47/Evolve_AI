import { icon } from "./icons.js";
import {
  esc,
  btn,
  tag,
  dateLabel,
  addDays,
  field,
  textArea,
  selectField,
} from "./ui.js";
const app = document.querySelector("#app"),
  modal = document.querySelector("#modal");
let user,
  state,
  experiments = [],
  notices = [],
  route = "today",
  authTab = "register",
  toastTimer;
let taskFilter = "today",
  taskArea = "all",
  taskQuery = "";
const domains = [
  "physical",
  "mental",
  "financial",
  "productivity",
  "social",
  "learning",
];
const labels = {
  today: "Dashboard",
  profile: "My profile",
  checkin: "Daily check-in",
  tasks: "My tasks",
  goals: "Goals & habits",
  wellbeing: "Mind & body",
  finance: "Money",
  experiments: "Personal experiments",
  insights: "Growth insights",
  notifications: "Reminders",
  settings: "Your preferences",
};
let authConfig = { google_enabled: false },
  refreshPending;
const money = (cents) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: state?.profile.currency || "INR",
    maximumFractionDigits: 2,
  }).format(cents / 100);
function toast(message) {
  const node = document.querySelector("#toast");
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove("show"), 4500);
}
async function api(path, method = "GET", data) {
  const request = () =>
    fetch(`/api${path}`, {
      method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Evolve-Request": "1" },
      body: data === undefined ? undefined : JSON.stringify(data),
    });
  let response = await request();
  const renewable =
    !path.startsWith("/auth/") ||
    path === "/auth/me" ||
    (path === "/auth/google/start" && data?.intent !== "login");
  if (response.status === 401 && renewable) {
    if (!refreshPending)
      refreshPending = fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-Evolve-Request": "1" },
      }).finally(() => {
        refreshPending = null;
      });
    if ((await refreshPending).ok) response = await request();
  }
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(
      "The server could not complete your request. Please try again.",
    );
  }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth")) {
      user = null;
      showAuth();
    }
    const detail = body.detail;
    throw new Error(
      Array.isArray(detail)
        ? detail.map((e) => `${e.loc.at(-1)}: ${e.msg}`).join(". ")
        : detail || "Request failed",
    );
  }
  return body;
}
function googleButton() {
  return (
    btn(
      "Continue with Google",
      "google-login",
      "light",
      authConfig.google_enabled
        ? ""
        : 'disabled title="Google sign-in is not configured on this server"',
    ) +
    (!authConfig.google_enabled
      ? '<p class="small muted" style="margin-top:12px">Google sign-in is not enabled on this server yet. You can create an account with email and password.</p>'
      : "")
  );
}
function accountAccess() {
  if (user.demo) return "";
  const a = user.auth || {};
  return `<section class="card section-gap"><h2>Account sign-in</h2><p class="small muted" style="margin:14px 0">${a.has_password ? "Email and password are available for this account." : "This account uses Google sign-in."} ${a.google_linked ? "Google is connected." : "Google is not connected."}</p>${!a.google_linked && a.has_password ? btn("Connect my Google account", "google-link", "light", a.google_enabled ? "" : 'disabled title="Google sign-in is not configured on this server"') : ""}${!a.google_enabled ? '<div class="form-note">Google sign-in has not been enabled on this server.</div>' : ""}<p class="small muted" style="margin-top:14px">${a.google_linked ? "Your connected Google account can sign you into this workspace." : "To connect Google, confirm your password and choose the account with the same email address."}</p></section>`;
}
async function startGoogle(intent = "login", password = "") {
  const result = await api("/auth/google/start", "POST", { intent, password });
  const target = new URL(result.url);
  if (
    target.origin !== "https://accounts.google.com" ||
    target.pathname !== "/o/oauth2/v2/auth"
  )
    throw new Error("Unable to open Google sign-in.");
  window.location.assign(target.href);
}
function heading(title, description, actions = "", eyebrow = "YOUR WORKSPACE") {
  return `<div class="page-heading"><div><span class="eyebrow">${eyebrow}</span><h1>${esc(title)}</h1><p>${esc(description)}</p></div><div class="btn-row">${actions}</div></div>`;
}
function empty(title, text, action = "", button = "") {
  return `<div class="empty">${icon("spark")}<h3>${esc(title)}</h3><p>${esc(text)}</p>${action ? btn(button, action) : ""}</div>`;
}
const brand = `<div class="brand"><div class="brand-mark">e</div><span>Evolve<span> AI</span><small>PERSONAL DEVELOPMENT OS</small></span></div>`;
function showAuth(error = "") {
  route = "today";
  app.innerHTML = `<div class="auth"><section class="auth-story">${brand}<div><div class="eyebrow">BUILD A LIFE THAT FITS YOU</div><h1>A little more<br>intentional.<br><em>Every day.</em></h1><p>A place to understand your patterns, choose your next step, and grow at a pace you can sustain.</p></div><div><div class="auth-dimensions"><span>${icon("wellbeing")} Mind & body</span><span>${icon("finance")} Financial awareness</span><span>${icon("goals")} Goals & consistency</span><span>${icon("insights")} Personal growth</span></div><p class="fine">Your goals. Your pace. Your data.</p></div></section><main class="auth-form" id="main"><div><div class="mini-brand">${brand}</div><h2>${authTab === "register" ? "Your next chapter starts here." : "Welcome back."}</h2><p>${authTab === "register" ? "Create your personal workspace and start with one achievable change." : "Pick up where you left off. A fresh start counts, too."}</p><div class="auth-tabs"><button class="${authTab === "register" ? "active" : ""}" data-action="auth-register">Create account</button><button class="${authTab === "login" ? "active" : ""}" data-action="auth-login">Sign in</button></div><form data-form="auth"><div class="form-error">${error ? `<div class="error" role="alert">${esc(error)}</div>` : ""}</div>${authTab === "register" ? field("Your name", "name", "text", "", 'required minlength="2" maxlength="80" autocomplete="name"') : ""}${field("Email address", "email", "email", "", 'required maxlength="254" autocomplete="email"')}${field("Password", "password", "password", "", "required " + (authTab === "register" ? 'minlength="10" autocomplete="new-password"' : 'autocomplete="current-password"') + ' maxlength="128"')}${authTab === "register" ? '<div class="small muted" style="margin:-8px 0 20px">Use at least 10 characters. This account stores personal records.</div>' : ""}<button class="button" type="submit">${authTab === "register" ? "Create my workspace" : "Sign in"}</button></form><div class="divider">OR CONTINUE WITH</div>${googleButton()}<div class="divider">OR EXPLORE FIRST</div>${btn("Try an interactive demo", "demo", "light")}<p class="fine">The demo uses fictional records in a separate, temporary account. Personal development guidance is educational and does not replace professional health or financial advice.</p></div></main></div>`;
}
function layout() {
  const unread = notices.filter((n) => !n.read).length;
  app.innerHTML = `<div class="shell"><aside class="sidebar">${brand}<div class="nav-label">YOUR DAILY PRACTICE</div><nav class="nav" aria-label="Main navigation">${Object.entries(
    labels,
  )
    .map(
      ([key, label]) =>
        `<button data-action="nav" data-route="${key}" class="${route === key ? "active" : ""}" ${route === key ? 'aria-current="page"' : ""}>${icon(key)}${label}${key === "notifications" && unread ? `<span class="badge">${unread}</span>` : ""}</button>`,
    )
    .join(
      "",
    )}</nav><div class="side-note">${icon("spark")} Progress, at your pace.<p>Choose a small step.<br>Learn from what happens.<br>Begin again when you need to.</p></div><div class="side-user"><div class="avatar">${esc(user.name.slice(0, 1).toUpperCase())}</div><div><span class="small">${esc(user.name)}</span><small>${user.demo ? "Demo workspace" : "Personal workspace"}</small></div><button data-action="logout" aria-label="Sign out">${icon("logout")}</button></div></aside><div class="workspace"><header class="topbar">${btn(icon("menu"), "menu", "light mobile-menu", 'aria-label="Open navigation"')}<span class="crumb">Your workspace / <strong>${labels[route]}</strong></span><div class="top-actions"><span class="date">${new Date(`${state.day}T12:00:00`).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "long" })}</span><button class="icon-button" data-action="nav" data-route="notifications" aria-label="Reminders, ${unread} unread">${icon("notifications")}${unread ? '<span class="unread-dot"></span>' : ""}</button><button class="avatar avatar-button" data-action="nav" data-route="profile" aria-label="Open my profile">${esc(user.name.slice(0, 1).toUpperCase())}</button></div></header>${user.demo ? '<div class="demo-banner"><span>Demo workspace · Fictional records. This account expires after 24 hours.</span><button data-action="create-real">Create my account</button></div>' : ""}<main id="main" class="content" tabindex="-1">${view()}<div class="footer-note"><span>Evolve AI · Small steps, meaningful change.</span><span>Self-reported patterns and educational guidance. You choose what works for you.</span></div></main></div></div>`;
}
async function refresh(render = true) {
  state = await api("/state");
  if (route === "experiments") experiments = await api("/experiments");
  notices = await api("/notifications");
  if (render) layout();
}
async function navigate(next) {
  route = labels[next] ? next : "today";
  location.hash = route;
  try {
    await refresh();
    document.querySelector("#main").focus({ preventScroll: true });
    window.scrollTo(0, 0);
  } catch (e) {
    toast(e.message);
  }
}
function ring(value, label, dark = false) {
  const pct = Math.min(100, Math.max(0, value));
  return `<svg class="focus-ring" viewBox="0 0 100 100" role="img" aria-label="${esc(label)}: ${Math.round(value)} percent"><circle cx="50" cy="50" r="43" fill="none" stroke="${dark ? "#344650" : "#e6eeea"}" stroke-width="6"/><circle cx="50" cy="50" r="43" fill="none" stroke="${dark ? "#c9f27d" : "#356951"}" stroke-width="6" stroke-linecap="round" stroke-dasharray="${pct * 2.702} 270.2" transform="rotate(-90 50 50)"/><text class="ring-text" x="50" y="48" text-anchor="middle">${Math.round(value)}%</text><text class="ring-label" x="50" y="64" text-anchor="middle">${esc(label)}</text></svg>`;
}
function chart(key = "tasks", max = 100) {
  const dates = Array.from({ length: 7 }, (_, i) => addDays(state.day, i - 6));
  const points = dates.map((day, i) => {
    const row = state.checkins.find((c) => c.day === day);
    let value = null;
    if (row) {
      const d = row.data;
      value =
        key === "tasks"
          ? d.planned_tasks > 0 && d.completed_tasks != null
            ? (100 * d.completed_tasks) / d.planned_tasks
            : null
          : (d[key] ?? null);
    }
    return {
      day,
      value,
      x: 42 + i * 54,
      y: value == null ? null : 158 - (130 * value) / max,
    };
  });
  if (!points.some((p) => p.value !== null))
    return empty(
      "Your trend starts with a check-in",
      "Record a few days to see your pattern. Missing days stay missing.",
      "nav-checkin",
      "Make a check-in",
    );
  let segments = [],
    current = [];
  for (const p of points) {
    if (p.value === null) {
      if (current.length) segments.push(current);
      current = [];
    } else current.push(p);
  }
  if (current.length) segments.push(current);
  const summary = points
    .map(
      (p) =>
        `${dateLabel(p.day)} ${p.value === null ? "not recorded" : Math.round(p.value) + (key === "tasks" ? " percent" : " out of 5")}`,
    )
    .join(", ");
  return `<svg class="weekly-chart" viewBox="0 0 390 195" role="img" aria-label="${esc(summary)}"><title>Last seven days: ${key === "tasks" ? "task completion" : esc(key)}</title>${[0, max / 2, max].map((v) => `<line x1="42" x2="370" y1="${158 - (v / max) * 130}" y2="${158 - (v / max) * 130}" stroke="#e3eae7" stroke-dasharray="3 4"/><text x="30" y="${162 - (v / max) * 130}" text-anchor="end" font-size="12" fill="#73858d">${v}${key === "tasks" ? "%" : ""}</text>`).join("")}${segments.map((s) => `<polyline fill="none" stroke="#356951" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="${s.map((p) => `${p.x},${p.y}`).join(" ")}"/>`).join("")}${points
    .filter((p) => p.value !== null)
    .map(
      (p) =>
        `<circle cx="${p.x}" cy="${p.y}" r="4" fill="#c9f27d" stroke="#356951" stroke-width="2"><title>${dateLabel(p.day)}: ${Math.round(p.value)}</title></circle>`,
    )
    .join(
      "",
    )}${points.map((p) => `<text x="${p.x}" y="184" text-anchor="middle" font-size="12" fill="#73858d">${new Date(`${p.day}T12:00:00`).toLocaleDateString("en", { weekday: "short" })}</text>`).join("")}</svg><div class="chart-caption"><span class="legend">${key === "tasks" ? "Completed / planned tasks" : "Self-reported " + esc(key)}</span><span>Gaps = no recorded value</span></div>`;
}
function metric(label, value, note, key) {
  return `<article class="card metric ${key}"><div class="label"><span class="icon-box">${icon(key === "physical" ? "wellbeing" : key === "mental" ? "sun" : key === "financial" ? "finance" : "goals")}</span>${label}</div><strong>${esc(value)}</strong><small>${esc(note)}</small></article>`;
}
function planItems() {
  if (!state.actions.length)
    return empty(
      "A plan that fits today",
      "Set your priorities, add a check-in and generate a short plan.",
      "plan",
      "Build today’s plan",
    );
  return state.actions
    .map(
      (a) =>
        `<div class="plan-item ${a.status}"><button class="plan-check ${a.status === "done" ? "done" : ""}" data-action="action-toggle" data-id="${a.id}" aria-label="${a.status === "done" ? "Undo" : "Complete"} ${esc(a.title)}">${a.status === "done" ? icon("check") : ""}</button><div class="body"><div class="plan-meta">${tag(a.domain)}<span>${a.minutes} min</span></div><h3>${esc(a.title)}</h3><p class="plan-reason">${esc(a.reason)}</p><div class="plan-bottom"><span>${esc(a.confidence)}</span>${a.status === "done" ? `<span>Was this useful?</span><button class="text-button" data-action="action-feedback" data-id="${a.id}" data-helpful="true" aria-pressed="${a.helpful === 1}">${a.helpful === 1 ? "✓ " : ""}Yes</button><button class="text-button" data-action="action-feedback" data-id="${a.id}" data-helpful="false" aria-pressed="${a.helpful === 0}">${a.helpful === 0 ? "✓ " : ""}Not today</button>` : a.status === "skipped" ? "<span>Skipped for today</span>" : `<button class="text-button" data-action="action-skip" data-id="${a.id}">Skip today</button>`}</div></div></div>`,
    )
    .join("");
}
function goalList(compact = false) {
  const goals = state.goals
    .filter((g) => !compact || g.progress < 100)
    .sort((a, b) => a.target_date.localeCompare(b.target_date));
  if (!goals.length)
    return empty(
      "Give your next step a direction",
      "Choose a goal and a specific action you can begin.",
      "add-goal",
      "Add a goal",
    );
  return goals
    .slice(0, compact ? 3 : 100)
    .map(
      (g) =>
        `<div class="goal-item"><div class="row"><span>${compact ? esc(g.title) : tag(g.domain)}</span><span class="muted">${g.progress}%</span></div>${!compact ? `<h3 class="title">${esc(g.title)}</h3><p>Next step: ${esc(g.next_step)}</p>` : ""}<div class="track"><span style="width:${g.progress}%"></span></div><small>${g.progress === 100 ? "Complete · " : ""}Target ${dateLabel(g.target_date)}${!compact ? " " + g.target_date.slice(0, 4) : ""}</small>${!compact ? `<div class="btn-row">${btn("Update progress", "goal-progress", "light compact", `data-id="${g.id}"`)}${btn(icon("edit"), "edit-goal", "ghost compact", `data-id="${g.id}" aria-label="Edit ${esc(g.title)}"`)}${btn(icon("trash"), "delete-goal", "ghost compact", `data-id="${g.id}" aria-label="Delete ${esc(g.title)}"`)}</div>` : ""}</div>`,
    )
    .join("");
}
function habitList() {
  if (!state.habits.length)
    return empty(
      "Make consistency easier",
      "Start with a daily habit small enough to repeat.",
      "add-habit",
      "Add a habit",
    );
  return state.habits
    .map(
      (h) =>
        `<div class="habit"><button class="plan-check ${h.done_today ? "done" : ""}" data-action="habit-toggle" data-id="${h.id}" aria-label="${h.done_today ? "Undo" : "Complete"} ${esc(h.title)}">${h.done_today ? icon("check") : ""}</button><div class="details"><span class="small">${esc(h.title)}</span><small>${esc(h.domain)} · ${h.streak} day streak</small><div class="week-dots">${Array.from(
          { length: 7 },
          (_, i) => {
            const d = addDays(state.day, i - 6);
            return `<span class="${h.days.includes(d) ? "on" : ""}" title="${d}: ${h.days.includes(d) ? "done" : "not recorded"}">${new Date(`${d}T12:00:00`).toLocaleDateString("en", { weekday: "narrow" })}</span>`;
          },
        ).join(
          "",
        )}</div></div>${btn(icon("trash"), "delete-habit", "ghost compact", `data-id="${h.id}" aria-label="Delete ${esc(h.title)}"`)}</div>`,
    )
    .join("");
}
function todayView() {
  const c = state.today_checkin;
  const progress = state.task_summary;
  const completion = progress.planned_today
    ? Math.round((100 * progress.completed_today) / progress.planned_today)
    : null;
  const done = state.actions.filter((a) => a.status === "done").length;
  const planned = state.actions.filter((a) => a.status !== "skipped").length;
  return `${heading(`A little progress, ${user.name.split(" ")[0]}.`, state.profile.aspiration ? "Your direction: " + state.profile.aspiration : "Choose what matters today. Leave room for the life around it.", btn(`${icon("plus")} Daily check-in`, "nav-checkin", "light"), state.day === todayLocal() ? "TODAY, AT YOUR PACE" : "YOUR PERSONAL DAY")} ${dashboardProfile()}<div class="grid four">${metric("Physical wellbeing", c?.sleep_hours != null ? `${c.sleep_hours} h` : "—", c?.sleep_hours != null ? "Sleep logged last night" : "Add sleep to your check-in", "physical")}${metric("Mental wellbeing", c?.mood != null ? `${c.mood} / 5` : "—", c?.mood != null ? "Your self-reported mood" : "How are you feeling today?", "mental")}${metric("Money this month", money(state.finance.net_cents), "Logged income minus expenses", "financial")}${metric("Task progress", completion !== null ? `${completion}%` : "—", completion !== null ? `${progress.completed_today} of ${progress.planned_today} scheduled tasks` : "Add a task to plan your day", "productivity")}</div>${dailyTasks()}<div class="grid main section-gap"><div><section class="focus-card"><div><span class="eyebrow">YOUR NEXT SMALL STEP</span><h2>${c ? "A plan for the day you’re having." : "Start with how you’re doing."}</h2><p>${c ? `${state.profile.daily_minutes} minutes set aside for development. ${state.evidence_days} recent check-in days to learn from.` : "A quick check-in gives your plan context. You can leave any question blank."}</p><div class="btn-row">${btn(state.actions.length ? "Refresh my plan" : "Build my plan", "plan", "lime")}${btn("Adjust my priorities", "nav-settings", "ghost")}</div></div>${ring(planned ? (100 * done) / planned : 0, "plan done", true)}</section><section class="card section-gap"><div class="card-header"><div><h2>Your action plan</h2><p class="muted">Small enough to start. Flexible enough to change.</p></div><span class="small muted">${state.actions.filter((a) => a.status === "pending").reduce((s, a) => s + a.minutes, 0)} min left</span></div>${planItems()}</section></div><div class="grid"><section class="card"><div class="card-header"><div><h2>Your week, in perspective</h2><p class="muted">Self-reported task counts · last 7 days</p></div>${icon("insights")}</div>${chart()}<div class="insight">${icon("spark")}<p>${state.evidence_days < 7 ? "A few more check-ins will help reveal your personal patterns." : "Look for patterns over several days. One difficult day does not define your progress."}</p></div></section><section class="card"><div class="card-header"><h2>Goals in motion</h2><button class="text-button" data-action="nav" data-route="goals">View all</button></div>${goalList(true)}</section></div></div><section class="card section-gap"><div class="card-header"><div><h2>Make room for your habits</h2><p class="muted">A small repeatable action is a useful place to begin.</p></div>${btn(`${icon("plus")} Add habit`, "add-habit", "light compact")}</div>${habitList()}</section>`;
}
function todayLocal() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: state.profile.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

const taskStarters = [
  ["physical", "Take a comfortable movement break", "Movement", 10],
  ["mental", "Write one thing that went well today", "Reflection", 5],
  ["financial", "Record today's spending", "Money awareness", 5],
  [
    "productivity",
    "Make progress on my most important task",
    "Daily focus",
    20,
  ],
  ["social", "Check in with someone I care about", "Connection", 10],
  ["learning", "Practice a skill I am interested in", "Learning", 15],
];
function taskList(items, compact = false) {
  if (!items.length)
    return empty(
      "Make space for what matters",
      "Add a task from any life area. Choose its date when you are ready.",
      "add-task",
      "Add my task",
    );
  return items
    .map((t) => {
      const available =
        t.done ||
        (t.active &&
          (t.recurrence !== "none"
            ? t.due_today
            : !t.due_date || t.due_date <= state.day));
      const schedule = !t.active
        ? "Paused"
        : t.done
          ? t.recurrence === "none"
            ? `Completed ${dateLabel(t.completed_day)}`
            : "Completed today"
          : t.overdue
            ? `Overdue · ${dateLabel(t.due_date)}`
            : t.due_today
              ? "Today"
              : t.next_due
                ? dateLabel(t.next_due)
                : "No date yet";
      return `<article class="task-row ${t.done ? "task-done" : ""}"><button class="plan-check ${t.done ? "done" : ""}" data-action="task-toggle" data-id="${t.id}" ${available ? "" : "disabled"} aria-label="${t.done ? "Undo" : "Complete"} ${esc(t.title)}">${t.done ? icon("check") : ""}</button><div class="task-body"><h3>${esc(t.title)}</h3><div class="task-meta">${tag(t.domain)}<span>${t.minutes} min</span><span class="${t.overdue ? "negative" : ""}">${schedule}</span>${t.priority === "high" ? '<span class="task-priority">High priority</span>' : ""}${t.recurrence !== "none" ? `<span>${{ daily: "Daily", weekdays: "Weekdays", weekly: "Weekly" }[t.recurrence]}</span>` : ""}</div>${t.interest ? `<p class="small muted">Interest: ${esc(t.interest)}</p>` : ""}${!compact && t.notes ? `<p class="small task-notes">${esc(t.notes)}</p>` : ""}<div class="task-controls">${btn(t.recurrence !== "none" ? "Edit routine" : "Edit", "edit-task", "light compact", `data-id="${t.id}"`)}${!t.done && t.recurrence === "none" ? btn("Move to tomorrow", "task-tomorrow", "ghost compact", `data-id="${t.id}"`) : ""}${!compact ? btn("Delete", "delete-task", "ghost compact", `data-id="${t.id}" aria-label="Delete ${esc(t.title)}"`) : ""}</div></div></article>`;
    })
    .join("");
}
function filteredTasks() {
  return state.tasks.filter(
    (t) =>
      (taskArea === "all" || t.domain === taskArea) &&
      (!taskQuery ||
        `${t.title} ${t.interest} ${t.notes}`
          .toLowerCase()
          .includes(taskQuery.toLowerCase())) &&
      {
        today: t.due_today,
        inbox: t.active && !t.done && !t.due_date,
        upcoming: t.active && !t.done && t.next_due > state.day,
        completed: t.done,
        all: true,
      }[taskFilter],
  );
}
function dailyTasks() {
  const p = state.task_summary,
    suggested = state.actions
      .filter((a) => a.status !== "skipped")
      .reduce((sum, a) => sum + a.minutes, 0);
  const over = p.committed_minutes + suggested - state.profile.daily_minutes;
  return `<section class="card section-gap"><div class="card-header"><div><h2>My tasks today</h2><p class="muted">${p.completed_today} of ${p.planned_today} complete · ${p.remaining_minutes} min remaining</p></div>${btn(`${icon("plus")} Add task`, "add-task", "light compact")}</div>${taskList(state.tasks.filter((t) => t.due_today).slice(0, 4), true)}<div class="form-note">${over > 0 ? `Tasks and suggestions total ${p.committed_minutes + suggested} min, ${over} min above your daily development time. Move a task or adjust your available time.` : "Your tasks reserve time first. Suggestions use the time left in your daily development budget."}</div><button class="text-button" data-action="nav-tasks">View all my tasks</button></section>`;
}
function tasksView() {
  const p = state.task_summary;
  return `${heading("Make today your own.", "Plan the things you care about, across every part of your life.", btn(`${icon("plus")} Add my task`, "add-task"))}<div class="grid three">${metric("Today’s tasks", `${p.completed_today} / ${p.planned_today}`, "Completed from today’s scheduled tasks", "productivity")}${metric("Time still planned", `${p.remaining_minutes} min`, "Estimates you set for today’s tasks", "physical")}${metric("Steps this week", p.week_completions, "Recorded task completions · last 7 days", "learning")}</div><div class="grid main section-gap task-grid"><section class="card"><div class="task-tabs" role="group" aria-label="Task view">${[
    ["today", "Today"],
    ["inbox", "No date"],
    ["upcoming", "Upcoming"],
    ["completed", "Completed"],
    ["all", "All tasks"],
  ]
    .map(
      ([key, label]) =>
        `<button data-action="task-filter" data-filter="${key}" aria-pressed="${taskFilter === key}" class="${taskFilter === key ? "active" : ""}">${label}</button>`,
    )
    .join(
      "",
    )}</div><div class="grid two task-search">${selectField("Life area", "task-area", [["all", "All areas"], ...domains], taskArea)}${field("Search tasks or interests", "task-search", "search", taskQuery, 'maxlength="150" placeholder="Search your tasks"')}</div><div id="task-list">${taskList(filteredTasks())}</div></section><div><section class="card"><h2>A small start in any area</h2><p class="small muted" style="margin:12px 0 20px">Choose an idea, then make it yours before saving.</p><div class="task-starters">${taskStarters.map(([d, title]) => `<button data-action="task-starter" data-domain="${d}">${tag(d)}<span>${esc(title)}</span>${icon("plus")}</button>`).join("")}</div></section><section class="card section-gap"><h2>Your week across life areas</h2><p class="small muted" style="margin:12px 0">Task completions, not a wellbeing score. You choose the balance that fits your life.</p>${domains.map((d) => `<div class="stat-pair">${tag(d)}<strong>${p.week_by_domain[d]}</strong></div>`).join("")}<div class="form-note">Recurring tasks return on their scheduled day. Completed occurrences stay in your record. Pause a routine whenever you need a break.</div></section></div></div>`;
}
function taskDialog(existing, starter) {
  const t = existing || {
    title: starter?.[1] || "",
    domain: starter?.[0] || "learning",
    interest: starter?.[2] || "",
    minutes: starter?.[3] || 10,
    priority: "normal",
    due_date: state.day,
    recurrence: "none",
    active: true,
  };
  openDialog(
    existing ? "Edit my task" : "Add something that matters to me",
    dialogForm(
      "task",
      `${field("Task title", "title", "text", t.title, 'required minlength="2" maxlength="150" placeholder="What would you like to do?"')}<div class="grid two">${selectField("Life area", "domain", domains, t.domain)}${selectField("Priority", "priority", ["low", "normal", "high"], t.priority)}</div>${field("Interest or activity (optional)", "interest", "text", t.interest || "", 'maxlength="80" placeholder="Cricket, journaling, saving, Python…"')}<div class="grid two">${field("Date / routine start (optional)", "due_date", "date", t.due_date || "")}${field("Estimated minutes", "minutes", "number", t.minutes, 'required min="1" max="480"')}</div>${selectField(
        "Repeat",
        "recurrence",
        [
          ["none", "One time"],
          ["daily", "Every day"],
          ["weekdays", "Weekdays (Mon–Fri)"],
          ["weekly", "Weekly on the start day"],
        ],
        t.recurrence,
      )}${textArea("Why it matters / my next step (optional)", "notes", t.notes || "", 'maxlength="1000" placeholder="Choose a small step you can actually start."')}<label class="field-inline"><input type="checkbox" name="active" ${t.active ? "checked" : ""}>Task / routine is active</label><div class="form-note">A repeating routine needs a start date. Leave a one-time task undated to keep it in “No date”. Editing a routine changes future scheduling; recorded completions are retained.</div>`,
      "Save task",
      existing ? `data-id="${t.id}"` : "",
    ),
  );
}
function taskPayload(t) {
  return {
    title: t.title,
    domain: t.domain,
    interest: t.interest || "",
    notes: t.notes || "",
    priority: t.priority,
    minutes: Number(t.minutes),
    due_date: t.due_date || null,
    recurrence: t.recurrence,
    active: Boolean(t.active),
  };
}
document.addEventListener("input", (e) => {
  if (e.target.id === "task-search") {
    taskQuery = e.target.value;
    document.querySelector("#task-list").innerHTML = taskList(filteredTasks());
  }
});
document.addEventListener("change", (e) => {
  if (e.target.id === "task-area") {
    taskArea = e.target.value;
    document.querySelector("#task-list").innerHTML = taskList(filteredTasks());
  }
});
function scale(label, name, current) {
  return `<div class="field"><span id="label-${name}">${label}</span><div class="scale" role="group" aria-labelledby="label-${name}">${[1, 2, 3, 4, 5].map((n) => `<label><input type="radio" name="${name}" value="${n}" ${current === n ? "checked" : ""} aria-label="${label}, ${n} out of 5">${n}</label>`).join("")}</div><small>${name === "stress" ? "1 = low · 5 = high" : "1 = low · 5 = high"} · leave blank to skip</small></div>`;
}
function checkinView() {
  const c = state.today_checkin || {};
  return `${heading("How is today feeling?", "A reflection, not a test. Share only what you want to track.")}<div class="grid main"><section class="card"><form data-form="checkin"><div class="form-error"></div><div class="card-header"><h2>Mind & energy</h2><span class="domain">${dateLabel(state.day)}</span></div><div class="checkin-scores">${scale("Mood", "mood", c.mood)}${scale("Energy", "energy", c.energy)}${scale("Stress", "stress", c.stress)}${scale("Focus", "focus", c.focus)}</div><div class="grid two">${field("Sleep last night (hours)", "sleep_hours", "number", c.sleep_hours ?? "", 'min="0" max="24" step="0.1"')}${field("Movement today (minutes)", "movement_minutes", "number", c.movement_minutes ?? "", 'min="0" max="600" step="1"')}${field("Tasks planned today", "planned_tasks", "number", c.planned_tasks ?? "", 'min="0" max="100" step="1"')}${field("Tasks completed today", "completed_tasks", "number", c.completed_tasks ?? "", 'min="0" max="100" step="1"')}</div>${textArea("What helped, or got in the way?", "reflection", c.reflection || "", 'maxlength="1500" placeholder="Optional: a small win, a challenge, or something to try tomorrow…"')}<button type="submit" class="button">${c && Object.keys(c).length ? "Update today’s check-in" : "Save my check-in"}</button><p class="small muted" style="margin-top:14px">Saving updates your plan. Completed actions stay completed.</p></form></section><div><section class="card"><div class="card-header"><h2>Keep the full picture</h2>${icon("sun")}</div><p class="small muted">These are your observations. The app uses them to offer small, optional actions, with no diagnosis or single personality grade.</p><div class="stat-pair"><div><span class="small">Your recent sleep average</span><small>${state.baselines.sleep_hours.observations} previous check-ins</small></div><strong>${state.baselines.sleep_hours.mean ?? "—"}${state.baselines.sleep_hours.mean != null ? " h" : ""}</strong></div><div class="stat-pair"><div><span class="small">Your recent mood average</span><small>${state.baselines.mood.observations} previous check-ins</small></div><strong>${state.baselines.mood.mean ?? "—"}${state.baselines.mood.mean != null ? " / 5" : ""}</strong></div><div class="form-note">No need to catch up perfectly. Check in with the day you have.</div></section><section class="card section-gap"><h2>Recent reflections</h2>${
    state.checkins.length
      ? state.checkins
          .slice(-4)
          .reverse()
          .map(
            (r) =>
              `<div class="stat-pair"><div><span class="small">${dateLabel(r.day)}</span><p class="small muted">${esc(r.data.reflection || "Check-in saved without a reflection.")}</p></div>${btn(icon("trash"), "delete-checkin", "ghost compact", `data-day="${r.day}" aria-label="Delete check-in for ${r.day}"`)}</div>`,
          )
          .join("")
      : empty("A clear starting point", "Your first check-in will appear here.")
  }</section></div></div>`;
}
function goalsView() {
  return `${heading("Turn intentions into next steps.", "Define the direction. Keep the next action specific and achievable.", btn(`${icon("plus")} Add goal`, "add-goal"))}<div class="grid main"><section class="card"><div class="card-header"><h2>Your goals</h2><span class="small muted">${state.goals.filter((g) => g.progress === 100).length} complete</span></div>${goalList()}</section><section class="card"><div class="card-header"><div><h2>Your daily habits</h2><p class="muted">Log the action after you do it.</p></div>${btn(icon("plus"), "add-habit", "light compact", 'aria-label="Add a habit"')}</div>${habitList()}<div class="form-note">Habit completion and goal progress are separate. You decide how much closer an action took you to your goal.</div></section></div>`;
}
function wellbeingView() {
  const c = state.today_checkin || {};
  return `${heading("Listen to your patterns.", "Track energy, mood, sleep and movement against your own recent observations.", btn("Make a check-in", "nav-checkin"))}<div class="grid four">${metric("Sleep", c.sleep_hours != null ? `${c.sleep_hours} h` : "—", `Recent average: ${state.baselines.sleep_hours.mean ?? "not enough data"}`, "physical")}${metric("Movement", c.movement_minutes != null ? `${c.movement_minutes} min` : "—", "Movement you chose to log", "physical")}${metric("Mood", c.mood != null ? `${c.mood} / 5` : "—", "Self-reported, not a diagnosis", "mental")}${metric("Energy", c.energy != null ? `${c.energy} / 5` : "—", "Today’s self-reported energy", "mental")}</div><div class="grid two section-gap"><section class="card"><div class="card-header"><h2>Mood over your week</h2>${icon("wellbeing")}</div>${chart("mood", 5)}</section><section class="card"><div class="card-header"><h2>Focus over your week</h2>${icon("insights")}</div>${chart("focus", 5)}</section></div><div class="grid two section-gap"><section class="card"><h2>Actions that support you</h2>${
    state.actions.some((a) => ["mental", "physical"].includes(a.domain))
      ? state.actions
          .filter((a) => ["mental", "physical"].includes(a.domain))
          .map(
            (a) =>
              `<div class="stat-pair"><div>${tag(a.domain)}<h3 style="margin-top:10px">${esc(a.title)}</h3><p class="small muted" style="margin-top:8px">${esc(a.reason)}</p></div></div>`,
          )
          .join("")
      : empty(
          "Start with your current state",
          "Check in and refresh your plan to get suggestions that fit today.",
          "nav-checkin",
          "Check in",
        )
  }</section><section class="card"><h2>Wellbeing, with perspective</h2><p class="small muted" style="margin-top:16px">There is no ideal personality score here. Mood and energy are signals you report, and routines are choices you can adjust.</p><div class="form-note">If distress persists or affects daily life, support from a qualified professional or someone you trust can be a useful next step. This workspace does not monitor emergencies.</div><h3>Beyond mind & body</h3><p class="small muted" style="margin-top:10px">Communication, confidence and learning can become goals with concrete steps, such as practicing a short introduction, listening attentively, or developing a skill.</p>${btn("Set a personal goal", "add-goal", "light", 'style="margin-top:18px"')}</section></div>`;
}
function financeView() {
  const f = state.finance;
  return `${heading("Know where your money goes.", "A clear record of what you enter. Review spending without judging yourself.", btn(`${icon("plus")} Add transaction`, "add-transaction"))}<div class="grid three">${metric("Recorded income", money(f.income_cents), `Month: ${f.month}`, "financial")}${metric("Recorded expenses", money(f.expense_cents), "Includes only your entered transactions", "financial")}${metric("Recorded net", money(f.net_cents), "Income − expenses · not bank balance", "financial")}</div><div class="grid main section-gap"><section class="card"><div class="card-header"><div><h2>Your transactions</h2><p class="muted">Most recent first · ${state.profile.currency}</p></div></div>${f.transactions.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Date</th><th>Category / note</th><th>Amount</th><th></th></tr></thead><tbody>${f.transactions.map((t) => `<tr><td>${dateLabel(t.day)}<br><small class="muted">${t.day.slice(0, 4)}</small></td><td>${esc(t.category)}${t.note ? `<br><small class="muted">${esc(t.note)}</small>` : ""}</td><td class="${t.kind === "income" ? "positive" : "negative"}">${t.kind === "income" ? "+" : "−"}${money(t.amount_cents)}</td><td>${btn(icon("trash"), "delete-transaction", "ghost compact", `data-id="${t.id}" aria-label="Delete ${esc(t.category)} transaction"`)}</td></tr>`).join("")}</tbody></table></div>` : empty("Begin with one transaction", "Record an income or expense to make the picture clearer.", "add-transaction", "Add transaction")}</section><div><section class="card"><div class="card-header"><div><h2>Monthly category budgets</h2><p class="muted">Reusable limits · this month’s spending</p></div>${btn(icon("plus"), "add-budget", "light compact", 'aria-label="Set a budget"')}</div>${f.budgets.length ? f.budgets.map((b) => `<div class="budget-row"><div class="row"><strong>${esc(b.category)}</strong><span>${money(b.spent_cents)} / ${money(b.amount_cents)}</span></div><div class="track ${b.remaining_cents < 0 ? "orange" : ""}"><span style="width:${b.amount_cents ? Math.min(100, (b.spent_cents / b.amount_cents) * 100) : b.spent_cents ? 100 : 0}%"></span></div><small>${money(Math.abs(b.remaining_cents))} ${b.remaining_cents < 0 ? "over budget" : "remaining"}</small><button class="text-button" data-action="remove-budget" data-category="${esc(b.category)}">Remove budget</button></div>`).join("") : empty("Give spending a boundary", "Set a category budget you can revisit.", "add-budget", "Set a budget")}</section><div class="notice section-gap">Categories must match between transactions and budgets. These records are for awareness; they do not connect to a bank or recommend investments.</div></div></div>`;
}
function experimentsView() {
  return `${heading("Discover what works for you.", "Compare two everyday routines with balanced, randomized daily assignments.", btn(`${icon("plus")} New experiment`, "add-experiment"))}${
    experiments.length
      ? `<div class="grid two">${experiments
          .map((e) => {
            const todayLog = e.logs.some((l) => l.day === state.day);
            return `<section class="card"><div class="card-header"><div><h2>${esc(e.title)}</h2><p class="muted">${e.days} days · ${e.logs.length} sessions logged</p></div>${btn(icon("trash"), "delete-experiment", "ghost compact", `data-id="${e.id}" aria-label="Delete ${esc(e.title)} experiment"`)}</div><div class="experiment-options">${["A", "B"].map((arm) => `<div><div class="arm">Routine ${arm}</div><h3>${esc(arm === "A" ? e.option_a : e.option_b)}</h3><strong>${e.stats[arm].mean_focus ?? "—"}<small>mean focus / 5</small></strong><small>${e.stats[arm].sessions} sessions · ${e.stats[arm].completion_rate ?? "—"}% completion</small></div>`).join("")}</div><div class="schedule" aria-label="Daily assignments">${e.schedule.map((s) => `<span class="${s.arm === "B" ? "arm-b" : ""} ${s.day === state.day ? "current" : ""}" title="${s.day}: Routine ${s.arm}">${dateLabel(s.day)} · ${s.arm}</span>`).join("")}</div>${e.today_assignment ? `<div class="form-note">Today: routine ${e.today_assignment} · ${esc(e.today_assignment === "A" ? e.option_a : e.option_b)}. ${todayLog ? "Today’s result is saved." : "Record your result after the session."}</div>${btn(todayLog ? "Update today’s result" : "Log today’s result", "experiment-log", "light", `data-id="${e.id}"`)}` : '<div class="form-note">The scheduled days are finished. Your results remain available.</div>'}<p class="small muted" style="margin-top:20px">${esc(e.confidence)}. ${e.focus_difference_a_minus_b !== null ? `Mean focus difference (A − B): ${e.focus_difference_a_minus_b}. ` : ""}${esc(e.note)}</p></section>`;
          })
          .join("")}</div>`
      : `<section class="card">${empty("Try a small personal experiment", "For example: studying in the morning compared with the evening. Use similar tasks and record focus and completion.", "add-experiment", "Design an experiment")}</section>`
  }<div class="form-note section-gap">Compare ordinary productivity, learning or organization routines. A small personal experiment offers clues, not proof that one routine will work forever.</div>`;
}
function insightsView() {
  const rated = state.action_history.filter(
    (a) => a.status === "done" && a.helpful !== null,
  );
  const helpful = rated.filter((a) => a.helpful === 1).length;
  const groups = {};
  rated.forEach((a) => {
    groups[a.key] ??= { title: a.title, total: 0, helpful: 0 };
    groups[a.key].total++;
    groups[a.key].helpful += a.helpful;
  });
  return `${heading("Your growth has a history.", "Use recorded evidence to adjust your next step. Patterns are clues, not verdicts.")}<div class="grid three">${metric("Recent check-in days", state.evidence_days, "Within the last 14 calendar days", "productivity")}${metric("Completed actions", state.action_history.filter((a) => a.status === "done").length, "Across all saved plans", "productivity")}${metric("Actions rated useful", rated.length ? `${Math.round((100 * helpful) / rated.length)}%` : "—", `${helpful} useful out of ${rated.length} rated actions`, "mental")}</div><div class="grid two section-gap"><section class="card"><div class="card-header"><h2>Consistency over time</h2>${icon("insights")}</div>${chart()}<div class="form-note">You can return after a gap. Missing entries are never counted as failures.</div></section><section class="card"><h2>What your feedback teaches the plan</h2>${
    Object.keys(groups).length
      ? Object.values(groups)
          .map(
            (g) =>
              `<div class="stat-pair"><div><span class="small">${esc(g.title)}</span><small>${g.total} rated completions</small></div><strong>${Math.round((100 * g.helpful) / g.total)}%</strong></div>`,
          )
          .join("")
      : empty(
          "Your feedback makes the difference",
          "Complete a suggested action and tell us whether it was useful.",
        )
  }<div class="form-note">Helpful feedback changes the priority of similar suggestions. Early recommendations still rely on your selected priorities and recorded context.</div></section></div><section class="card section-gap"><div class="card-header"><div><h2>Connections in your logged days</h2><p class="muted">At least 7 paired observations are needed to show a connection.</p></div>${icon("spark")}</div>${state.associations.length ? `<div class="grid three">${state.associations.map((a) => `<div class="form-note"><h3>${esc(a.x.replaceAll("_", " "))} & ${esc(a.y.replaceAll("_", " "))}</h3><p style="margin-top:8px">Correlation: ${a.correlation} · ${a.observations} days</p><p style="margin-top:8px">${esc(a.note)}</p></div>`).join("")}</div>` : empty("More observations, clearer context", "Consistent check-ins make your own baseline more useful. No connection is inferred from missing values.")}</section><section class="card section-gap"><div class="card-header"><div><h2>Explore a practical “what if”</h2><p class="muted">Change your inputs to compare time and money. This is an arithmetic scenario.</p></div></div><form data-form="scenario"><div class="form-error"></div><div class="grid three">${field("Extra focus sessions this week", "focus_sessions", "number", 3, 'min="0" max="14" required')}${field("Minutes per session", "minutes_per_session", "number", 25, 'min="5" max="120" required')}${field(`Reduce monthly spending (${state.profile.currency})`, "expense_reduction", "number", 0, `min="0" max="${state.finance.expense_cents / 100}" step="0.01" required`)}</div><button class="button light" type="submit">Compare this scenario</button><div id="scenario-result" aria-live="polite"></div></form></section>`;
}
function notificationsView() {
  return `${heading("A nudge when it helps.", "Your check-ins, goal dates and category budgets can trigger reminders.", btn("Reminder preferences", "nav-settings", "light"))}<section class="card">${notices.length ? notices.map((n) => `<div class="notification ${n.read ? "" : "unread"}">${icon("notifications")}<div class="body"><h3>${esc(n.title)}</h3><p>${esc(n.body)}</p><small>${new Date(n.created_at).toLocaleString("en-IN", { timeZone: state.profile.timezone })}</small></div>${!n.read ? btn("Mark read", "read-notification", "light compact", `data-id="${n.id}"`) : '<span class="small muted">Read</span>'}</div>`).join("") : empty("You’re up to date", "Relevant reminders will appear here when enabled.")}</section><div class="notice section-gap">Reminders refresh while this app is open. Browser notifications also need your permission and an open tab. Email, mobile push and reminders with the app closed are not connected yet.</div>`;
}
function personalView() {
  const p = state.profile.personal || {},
    name = p.display_name || user.name;
  const location = [p.city, p.country].filter(Boolean).join(", ");
  return `${heading("Your profile, your direction.", "Share the details that help you reflect on the life you want to build.", btn("Open my dashboard", "nav-today", "light"))}
  <div class="grid main profile-layout"><section class="card"><form data-form="personal"><div class="form-error"></div><div class="card-header"><div><h2>Personal details</h2><p class="muted">Your name is required. Everything else is optional.</p></div>${icon("profile")}</div>
  <div class="grid two">${field("Full name", "display_name", "text", name, 'required minlength="2" maxlength="80" autocomplete="name"')}${field("Age (optional)", "age", "number", p.age ?? "", 'min="1" max="120" step="1"')}${field("Contact number (optional)", "phone", "tel", p.phone || "", 'maxlength="30" autocomplete="tel"')}${field("City", "city", "text", p.city || "", 'maxlength="100" autocomplete="address-level2"')}${field("Country", "country", "text", p.country || "", 'maxlength="100" autocomplete="country-name"')}${field("Occupation / current role", "occupation", "text", p.occupation || "", 'maxlength="150" placeholder="Student, analyst, designer…"')}</div>
  ${field("Education / field of study", "education", "text", p.education || "", 'maxlength="200" placeholder="Your program or learning background"')}${field("Interests & hobbies", "interests", "text", p.interests || "", 'maxlength="300" placeholder="Reading, cricket, learning Python…"')}${textArea("About you", "about", p.about || "", 'maxlength="1000" placeholder="A few words about your background and what matters to you."')}
  <div class="profile-divider"><h2>Personal development context</h2><p class="small muted">Reflect in your own words. These fields do not generate a personality grade.</p></div>
  ${textArea("What would you like to become or change?", "aspiration", state.profile.aspiration || "", 'maxlength="500" placeholder="For example: communicate confidently and build a steady study routine."')}${textArea("Strengths you want to build on", "strengths", p.strengths || "", 'maxlength="500" placeholder="What already works well for you?"')}${textArea("Challenges or barriers", "challenges", p.challenges || "", 'maxlength="500" placeholder="What tends to get in the way?"')}${textArea("Your usual routine", "routine", p.routine || "", 'maxlength="500" placeholder="Work or study hours, commitments, and time available for yourself."')}
  <div class="form-note">${user.demo ? "This temporary demo account uses fictional records. Use sample details while exploring." : "These details are private to your account and included in your data export. Leave anything blank that you do not want to store."} Your name and direction appear on the dashboard. Your priorities, goals and check-ins guide recommendations.</div>
  <div class="btn-row"><button type="submit" class="button">Save my profile</button>${btn("View dashboard", "nav-today", "light")}</div></form></section>
  <div><section class="card profile-summary"><div class="avatar profile-avatar">${esc(name.slice(0, 1).toUpperCase())}</div><h2>${esc(name)}</h2><p class="muted">${esc(p.occupation || "Your personal development workspace")}</p>${location ? `<p class="small muted">${esc(location)}</p>` : ""}<div class="stat-pair"><div><span class="small">Account email</span><small>${user.demo ? "Demo account · no real authentication" : esc(user.email)}</small></div></div>${p.education ? `<div class="stat-pair"><div><span class="small">Education</span><small>${esc(p.education)}</small></div></div>` : ""}${p.interests ? `<div class="stat-pair"><div><span class="small">Interests</span><small>${esc(p.interests)}</small></div></div>` : ""}
  <div class="profile-divider"><h3>Your direction</h3><p class="small muted">${esc(state.profile.aspiration || "Add a direction to keep your next steps connected to what matters.")}</p></div></section>
  <section class="card section-gap"><h2>How your dashboard fits you</h2><p class="small muted" style="margin-top:14px">Your dashboard brings together your profile, chosen priorities, goals, habits and daily observations.</p><div class="tag-picks" style="margin-top:18px">${state.profile.priorities.map(tag).join("")}</div><div class="stat-pair"><span class="small">Daily development time</span><strong>${state.profile.daily_minutes} min</strong></div><div class="btn-row" style="margin-top:20px">${btn("Adjust preferences", "nav-settings", "light")}${btn("Add a goal", "add-goal", "light")}</div></section></div></div>`;
}
function dashboardProfile() {
  const p = state.profile.personal || {},
    detail = [p.occupation, p.city].filter(Boolean).join(" · ");
  return `<section class="dashboard-profile"><div class="avatar">${esc(user.name.slice(0, 1).toUpperCase())}</div><div class="body"><span class="small"><strong>Your profile</strong>${detail ? " · " + esc(detail) : ""}</span><p class="small muted">${detail ? "Your next steps belong to the direction you chose." : "Add your background, interests and personal development context."}</p></div>${btn(detail ? "View profile" : "Edit my profile", "nav-profile", "light compact")}</section>`;
}

function settingsView() {
  const p = state.profile;
  return `${heading("Build around your life.", "Tell your workspace what matters and how much time you want to give it.")}<div class="grid main"><section class="card"><form data-form="profile"><div class="form-error"></div><h2 style="margin-bottom:22px">Your direction</h2>${textArea("What would you like to become or change?", "aspiration", p.aspiration, 'maxlength="500" placeholder="For example: a consistent learner with more energy and financial clarity."')}<div class="field"><span>Areas you want to prioritize</span><div class="tag-picks">${domains.map((d) => `<label><input type="checkbox" name="priorities" value="${d}" ${p.priorities.includes(d) ? "checked" : ""}>${d}</label>`).join("")}</div><small>Choose at least one. Social and learning goals support communication and personal growth.</small></div>${field("Daily development time (minutes)", "daily_minutes", "number", p.daily_minutes, 'required min="5" max="240"')}<div class="grid two">${field("Timezone", "timezone", "text", p.timezone, 'required placeholder="Asia/Kolkata" maxlength="60"')}${selectField("Currency", "currency", ["INR", "USD", "EUR", "GBP"], p.currency)}</div><p class="small muted" style="margin:-6px 0 20px">Currency is locked while financial records exist to avoid relabeling amounts.</p><label class="field-inline"><input type="checkbox" name="reminders" ${p.reminders ? "checked" : ""}>Enable in-app reminders</label>${field("Daily check-in reminder hour (0–23)", "reminder_hour", "number", p.reminder_hour, 'required min="0" max="23"')}<button type="submit" class="button">Save my preferences</button></form></section><div><section class="card"><h2>Your data, your choice</h2><p class="small muted" style="margin-top:14px">Your records belong to your account. Export your tasks, check-ins, finances, goals and feedback whenever you need them.</p><div class="btn-row" style="margin-top:20px">${btn(`${icon("download")} Export my data`, "export", "light")}</div><div class="form-note">The plan uses transparent rules, recent personal baselines and your usefulness feedback. It is not a clinically validated assessment or a trained model that predicts health outcomes.</div>${btn("Enable browser reminders", "browser-reminders", "light")}</section><section class="card section-gap"><h2>Help shape a better workspace</h2><form data-form="feedback" style="margin-top:20px"><div class="form-error"></div>${selectField(
    "How useful has Evolve been?",
    "rating",
    [
      [5, "5 — Very useful"],
      [4, "4 — Useful"],
      [3, "3 — Mixed"],
      [2, "2 — Not very useful"],
      [1, "1 — Not useful"],
    ],
    5,
  )}${textArea("What worked, or what should improve?", "message", "", 'maxlength="2000"')}<button class="button light" type="submit">Share feedback</button></form></section>${accountAccess()}<section class="card section-gap"><h2>Delete this workspace</h2><p class="small muted" style="margin:14px 0 18px">Deleting your account permanently removes its records and sessions.</p>${btn(user.demo ? "Delete demo workspace" : "Delete my account", "delete-account", "danger")}</section></div></div>`;
}
function view() {
  return {
    today: todayView,
    profile: personalView,
    checkin: checkinView,
    tasks: tasksView,
    goals: goalsView,
    wellbeing: wellbeingView,
    finance: financeView,
    experiments: experimentsView,
    insights: insightsView,
    notifications: notificationsView,
    settings: settingsView,
  }[route]();
}
function openDialog(title, body) {
  modal.innerHTML = `<div class="dialog-head"><h2 id="dialog-title">${esc(title)}</h2><button data-action="close-dialog" aria-label="Close dialog">${icon("close")}</button></div>${body}`;
  modal.showModal();
}
function dialogForm(kind, body, submit = "Save", attrs = "") {
  return `<form data-form="${kind}" ${attrs}><div class="form-error"></div>${body}<div class="btn-row"><button type="submit" class="button">${submit}</button>${btn("Cancel", "close-dialog", "light")}</div></form>`;
}
function goalDialog(existing) {
  const g = existing || {
    domain: "productivity",
    target_date: addDays(state.day, 30),
    progress: 0,
  };
  openDialog(
    existing ? "Edit your goal" : "Give your goal a next step",
    dialogForm(
      "goal",
      `${field("Goal", "title", "text", g.title || "", 'required minlength="2" maxlength="150"')}${selectField("Development area", "domain", domains, g.domain)}${field("Target date", "target_date", "date", g.target_date, "required")}${textArea("One concrete next action", "next_step", g.next_step || "", 'required minlength="2" maxlength="250" placeholder="For example: outline the introduction for my presentation."')}${field("Progress (%)", "progress", "number", g.progress, 'required min="0" max="100"')}`,
      "Save goal",
      existing ? `data-id="${existing.id}"` : "",
    ),
  );
}
function cents(value) {
  if (!/^\d+(\.\d{1,2})?$/.test(String(value)))
    throw new Error("Enter a positive amount with at most two decimal places.");
  const [whole, decimal = ""] = String(value).split(".");
  const result = Number(whole) * 100 + Number(decimal.padEnd(2, "0"));
  if (!Number.isSafeInteger(result)) throw new Error("Amount is too large.");
  return result;
}
let clickBusy = false;
document.addEventListener("click", async (event) => {
  const node = event.target.closest("[data-action]");
  if (!node) return;
  const action = node.dataset.action;
  if (action === "close-dialog") {
    modal.close();
    return;
  }
  if (action === "menu") {
    document.querySelector(".shell").classList.toggle("menu-open");
    return;
  }
  if (action === "auth-register" || action === "auth-login") {
    authTab = action.slice(5);
    showAuth();
    return;
  }
  if (action === "nav") {
    await navigate(node.dataset.route);
    return;
  }
  if (action.startsWith("nav-")) {
    await navigate(action.slice(4));
    return;
  }
  if (action === "add-goal") {
    goalDialog();
    return;
  }
  if (
    action === "add-task" ||
    action === "edit-task" ||
    action === "task-starter"
  ) {
    taskDialog(
      action === "edit-task"
        ? state.tasks.find((t) => t.id === +node.dataset.id)
        : null,
      action === "task-starter"
        ? taskStarters.find((t) => t[0] === node.dataset.domain)
        : null,
    );
    return;
  }
  if (action === "task-filter") {
    taskFilter = node.dataset.filter;
    layout();
    document
      .querySelector(`.task-tabs [data-filter="${taskFilter}"]`)
      .focus({ preventScroll: true });
    return;
  }
  if (action === "edit-goal") {
    goalDialog(state.goals.find((g) => g.id === +node.dataset.id));
    return;
  }
  if (action === "goal-progress") {
    const g = state.goals.find((g) => g.id === +node.dataset.id);
    openDialog(
      "Update your progress",
      dialogForm(
        "progress",
        `<p class="small muted" style="margin-bottom:18px">${esc(g.title)}</p>${field("Progress (%)", "progress", "number", g.progress, 'required min="0" max="100"')}`,
        "Update progress",
        `data-id="${g.id}"`,
      ),
    );
    return;
  }
  if (action === "add-habit") {
    openDialog(
      "A habit small enough to repeat",
      dialogForm(
        "habit",
        `${field("Habit", "title", "text", "", 'required minlength="2" maxlength="120" placeholder="Read five pages"')}${selectField("Development area", "domain", domains, "learning")}`,
        "Add habit",
      ),
    );
    return;
  }
  if (action === "add-transaction") {
    openDialog(
      "Record a transaction",
      dialogForm(
        "transaction",
        `${selectField(
          "Type",
          "kind",
          [
            ["expense", "Expense"],
            ["income", "Income"],
          ],
          "expense",
        )}${field(`Amount (${state.profile.currency})`, "amount", "number", "", 'required min="0.01" step="0.01" max="1000000000"')}${field("Date", "day", "date", state.day, `required max="${state.day}"`)}${field("Category", "category", "text", "", 'required maxlength="60" list="categories" placeholder="Food"')}<datalist id="categories">${[...new Set(["Food", "Housing", "Transport", "Learning", "Health", "Income", ...state.finance.budgets.map((b) => b.category)])].map((c) => `<option value="${esc(c)}">`).join("")}</datalist>${field("Note (optional)", "note", "text", "", 'maxlength="250"')}`,
        "Save transaction",
      ),
    );
    return;
  }
  if (action === "add-budget") {
    openDialog(
      "Set a monthly category budget",
      dialogForm(
        "budget",
        `${field("Category (match your transactions)", "category", "text", "", 'required maxlength="60"')}${field(`Monthly limit (${state.profile.currency})`, "amount", "number", "", 'required min="0" step="0.01" max="1000000000"')}<div class="form-note">Saving an existing category replaces its limit. The limit repeats each month.</div>`,
        "Save budget",
      ),
    );
    return;
  }
  if (action === "add-experiment") {
    openDialog(
      "Compare two everyday routines",
      dialogForm(
        "experiment",
        `${field("Question you want to explore", "title", "text", "", 'required minlength="2" maxlength="150" placeholder="When is my study focus better?"')}${field("Routine A", "option_a", "text", "", 'required minlength="2" maxlength="100" placeholder="Study in the morning"')}${field("Routine B", "option_b", "text", "", 'required minlength="2" maxlength="100" placeholder="Study in the evening"')}${field("Duration (days)", "days", "number", 14, 'required min="6" max="28"')}<div class="form-note">Daily assignments are randomized. Keep tasks similar and log focus, completion and session duration.</div>`,
        "Create experiment",
      ),
    );
    return;
  }
  if (action === "experiment-log") {
    const e = experiments.find((e) => e.id === +node.dataset.id),
      log = e.logs.find((l) => l.day === state.day);
    openDialog(
      "Log today’s experiment result",
      dialogForm(
        "experiment-log",
        `<div class="form-note">Routine ${e.today_assignment}: ${esc(e.today_assignment === "A" ? e.option_a : e.option_b)}</div>${selectField(
          "Focus during the session",
          "focus",
          [
            [1, "1 — Low"],
            [2, "2"],
            [3, "3"],
            [4, "4"],
            [5, "5 — High"],
          ],
          log?.focus || 3,
        )}${field("Session length (minutes)", "minutes", "number", log?.minutes || 25, 'required min="1" max="480"')}<label class="field-inline"><input type="checkbox" name="completed" ${log?.completed ? "checked" : ""}>I completed the task I planned</label>${textArea("Notes (optional)", "note", log?.note || "", 'maxlength="500"')}`,
        "Save result",
        `data-id="${e.id}"`,
      ),
    );
    return;
  }
  if (action === "google-link") {
    openDialog(
      "Connect my Google account",
      dialogForm(
        "google-link",
        `<p class="small muted" style="margin-bottom:18px">Confirm your password, then choose the Google account matching ${esc(user.email)}.</p>${field("Confirm account password", "password", "password", "", 'required autocomplete="current-password" maxlength="128"')}`,
        "Continue to Google",
      ),
    );
    return;
  }
  if (action === "delete-account") {
    if (!user.demo && user.auth && !user.auth.has_password) {
      openDialog(
        "Permanently delete this workspace?",
        `<p class="small muted" style="margin-bottom:18px">Confirm with your connected Google account to permanently delete this workspace and all its records.</p><div class="btn-row">${btn("Confirm deletion with Google", "google-delete", "danger")}${btn("Keep my account", "close-dialog", "light")}</div>`,
      );
      return;
    }

    openDialog(
      "Permanently delete this workspace?",
      dialogForm(
        "delete-account",
        `<div class="notice" style="margin-bottom:20px">All tasks, check-ins, financial records, goals, habits, experiments and feedback for this account will be deleted.</div>${user.demo ? "" : field("Confirm your password", "password", "password", "", 'required autocomplete="current-password" maxlength="128"')}`,
        "Delete permanently",
      ),
    );
    return;
  }
  if (clickBusy) return;
  clickBusy = true;
  const disabledBefore = node.disabled;
  node.disabled = true;
  try {
    if (action === "google-login" || action === "google-delete") {
      await startGoogle(action === "google-delete" ? "delete" : "login");
    } else if (action === "demo") {
      user = await api("/auth/demo", "POST", {});
      route = "today";
      await refresh();
    } else if (action === "logout" || action === "create-real") {
      await api("/auth/logout", "POST", {});
      user = null;
      authTab = action === "create-real" ? "register" : "login";
      location.hash = "";
      showAuth();
    } else if (action === "plan") {
      await api("/plan", "POST", {});
      await refresh();
      toast("Your plan now fits your current context.");
    } else if (action === "task-toggle") {
      const t = state.tasks.find((t) => t.id === +node.dataset.id);
      await api(`/tasks/${t.id}/completion`, "PUT", { complete: !t.done });
      await refresh();
      toast(
        t.done
          ? "Task completion removed."
          : "Your step is recorded. Your plan now fits your tasks.",
      );
    } else if (action === "task-tomorrow") {
      const t = state.tasks.find((t) => t.id === +node.dataset.id);
      await api(
        `/tasks/${t.id}`,
        "PUT",
        taskPayload({ ...t, due_date: addDays(state.day, 1), active: true }),
      );
      await refresh();
      toast("Moved to tomorrow. Make space for the day you have.");
    } else if (action === "habit-toggle") {
      const h = state.habits.find((h) => h.id === +node.dataset.id);
      await api(`/habits/${h.id}/log`, "PUT", { complete: !h.done_today });
      await refresh();
      toast(
        h.done_today ? "Habit completion removed." : "A small step recorded.",
      );
    } else if (
      action === "action-toggle" ||
      action === "action-skip" ||
      action === "action-feedback"
    ) {
      const a = state.actions.find((a) => a.id === +node.dataset.id);
      const data =
        action === "action-feedback"
          ? { status: "done", helpful: node.dataset.helpful === "true" }
          : {
              status:
                action === "action-skip"
                  ? "skipped"
                  : a.status === "done"
                    ? "pending"
                    : "done",
            };
      await api(`/actions/${a.id}`, "PATCH", data);
      await refresh();
      if (action === "action-feedback")
        toast("Feedback saved for future plans.");
    } else if (
      [
        "delete-goal",
        "delete-task",
        "delete-habit",
        "delete-transaction",
        "delete-experiment",
        "delete-checkin",
        "remove-budget",
      ].includes(action)
    ) {
      const mappings = {
        "delete-goal": `/goals/${node.dataset.id}`,
        "delete-task": `/tasks/${node.dataset.id}`,
        "delete-habit": `/habits/${node.dataset.id}`,
        "delete-transaction": `/finance/transactions/${node.dataset.id}`,
        "delete-experiment": `/experiments/${node.dataset.id}`,
        "delete-checkin": `/checkins/${node.dataset.day}`,
        "remove-budget": `/finance/budgets/${encodeURIComponent(node.dataset.category)}`,
      };
      openDialog(
        "Remove this record?",
        `<p class="small muted" style="margin-bottom:20px">This removes the selected record. The rest of your workspace stays in place.</p><div class="btn-row">${btn("Remove record", "confirm-delete", "danger", `data-path="${esc(mappings[action])}"`)}${btn("Keep it", "close-dialog")}</div>`,
      );
    } else if (action === "confirm-delete") {
      await api(node.dataset.path, "DELETE");
      modal.close();
      await refresh();
      toast("Record removed.");
    } else if (action === "read-notification") {
      await api(`/notifications/${node.dataset.id}/read`, "PATCH", {});
      await refresh();
    } else if (action === "export") {
      const data = await api("/export");
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = "evolve-data.json";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast("Your export is ready.");
    } else if (action === "browser-reminders") {
      if (!("Notification" in window))
        throw new Error("This browser does not support notifications.");
      const permission = await Notification.requestPermission();
      toast(
        permission === "granted"
          ? "Browser reminders enabled while this tab is open."
          : "You can keep using in-app reminders.",
      );
    }
  } catch (e) {
    toast(e.message);
  } finally {
    clickBusy = false;
    if (node.isConnected) node.disabled = disabledBefore;
  }
});
document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-form]");
  if (!form) return;
  event.preventDefault();
  if (form.dataset.busy) return;
  form.dataset.busy = "1";
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  const f = new FormData(form),
    data = Object.fromEntries(f);
  const kind = form.dataset.form;
  form.querySelector(".form-error").innerHTML = "";
  try {
    if (kind === "google-link") {
      await startGoogle("link", data.password);
      return;
    }
    if (kind === "auth") {
      user = await api(
        `/auth/${authTab}`,
        "POST",
        authTab === "register"
          ? data
          : { email: data.email, password: data.password },
      );
      route = authTab === "register" ? "profile" : "today";
      location.hash = route;
      await refresh();
      return;
    }
    if (kind === "checkin") {
      const values = { reflection: data.reflection };
      [
        "mood",
        "energy",
        "stress",
        "focus",
        "sleep_hours",
        "movement_minutes",
        "planned_tasks",
        "completed_tasks",
      ].forEach((k) => {
        if (data[k] !== undefined && data[k] !== "")
          values[k] = Number(data[k]);
      });
      await api("/checkins", "PUT", values);
      await navigate("today");
      toast("Check-in saved. Your plan has been updated.");
      return;
    }
    if (kind === "personal") {
      const { aspiration, age, ...details } = data;
      user = await api("/personal-details", "PUT", {
        personal: { ...details, age: age === "" ? null : Number(age) },
        aspiration,
      });
      await refresh();
      document.querySelector("#main").focus({ preventScroll: true });
      window.scrollTo(0, 0);
      toast("Your profile is saved and your dashboard is updated.");
      return;
    }
    if (kind === "profile") {
      await api("/profile", "PUT", {
        ...data,
        personal: state.profile.personal || {},
        daily_minutes: +data.daily_minutes,
        reminder_hour: +data.reminder_hour,
        reminders: f.has("reminders"),
        priorities: f.getAll("priorities"),
      });
      user = await api("/auth/me");
      await refresh();
      toast("Preferences saved. Refresh your plan to apply them.");
      return;
    }
    if (kind === "scenario") {
      const result = await api("/scenario", "POST", {
        focus_sessions: +data.focus_sessions,
        minutes_per_session: +data.minutes_per_session,
        expense_reduction_cents: cents(data.expense_reduction),
      });
      form.querySelector("#scenario-result").innerHTML =
        `<div class="comparison"><div><span class="eyebrow">CURRENT RECORDED NET</span><strong>${money(result.current_net_cents)}</strong></div><div class="after"><span class="eyebrow">YOUR SCENARIO</span><strong>${money(result.scenario_net_cents)}</strong></div></div><p class="small muted">${result.added_focus_minutes} additional minutes set aside this week. ${esc(result.note)}</p>`;
      return;
    }
    if (kind === "feedback") {
      await api("/feedback", "POST", {
        rating: +data.rating,
        message: data.message,
      });
      form.reset();
      toast("Thank you. Your feedback is saved.");
      return;
    }
    if (kind === "delete-account") {
      await api("/account", "DELETE", { password: data.password || "" });
      modal.close();
      user = null;
      authTab = "register";
      showAuth();
      toast("Your workspace and records were deleted.");
      return;
    }
    if (kind === "goal")
      await api(
        form.dataset.id ? `/goals/${form.dataset.id}` : "/goals",
        form.dataset.id ? "PUT" : "POST",
        { ...data, progress: +data.progress },
      );
    if (kind === "task")
      await api(
        form.dataset.id ? `/tasks/${form.dataset.id}` : "/tasks",
        form.dataset.id ? "PUT" : "POST",
        taskPayload({ ...data, active: f.has("active") }),
      );
    if (kind === "progress")
      await api(`/goals/${form.dataset.id}`, "PATCH", {
        progress: +data.progress,
      });
    if (kind === "habit") await api("/habits", "POST", data);
    if (kind === "transaction")
      await api("/finance/transactions", "POST", {
        day: data.day,
        kind: data.kind,
        amount_cents: cents(data.amount),
        category: data.category,
        note: data.note,
      });
    if (kind === "budget")
      await api("/finance/budgets", "PUT", {
        category: data.category,
        amount_cents: cents(data.amount),
      });
    if (kind === "experiment")
      await api("/experiments", "POST", { ...data, days: +data.days });
    if (kind === "experiment-log")
      await api(`/experiments/${form.dataset.id}/log`, "PUT", {
        focus: +data.focus,
        completed: f.has("completed"),
        minutes: +data.minutes,
        note: data.note,
      });
    modal.close();
    await refresh();
    document.querySelector("#main").focus({ preventScroll: true });
    toast("Saved to your workspace.");
  } catch (e) {
    form.querySelector(".form-error").innerHTML =
      `<div class="error" role="alert">${esc(e.message)}</div>`;
    form.querySelector(".error").scrollIntoView({ block: "nearest" });
  } finally {
    delete form.dataset.busy;
    if (button.isConnected) button.disabled = false;
  }
});
window.addEventListener("hashchange", () => {
  const next = location.hash.slice(1);
  if (user && labels[next] && next !== route) navigate(next);
});
modal.addEventListener("click", (e) => {
  if (e.target === modal) {
    const box = modal.getBoundingClientRect();
    if (
      e.clientX < box.left ||
      e.clientX > box.right ||
      e.clientY < box.top ||
      e.clientY > box.bottom
    )
      modal.close();
  }
});
async function poll() {
  if (!user || document.hidden) return;
  try {
    const latest = await api("/notifications");
    const old = JSON.stringify(notices);
    notices = latest;
    const seenKey = `evolve-reminders-${user.id}`;
    let seen;
    try {
      seen = JSON.parse(localStorage.getItem(seenKey) || "[]");
    } catch {
      seen = [];
    }
    for (const n of latest.filter((n) => !n.read && !seen.includes(n.id))) {
      if ("Notification" in window && Notification.permission === "granted")
        new Notification("Evolve · A small nudge", {
          body: "A reminder is ready in your personal workspace.",
        });
      seen.push(n.id);
    }
    localStorage.setItem(seenKey, JSON.stringify(seen.slice(-200)));
    if (
      route === "notifications" &&
      old !== JSON.stringify(latest) &&
      !modal.open
    )
      layout();
    if (state.day !== todayLocal()) await refresh();
  } catch {
    /* The next refresh reconnects; never overwrite a form. */
  }
}
setInterval(poll, 30000);
async function start() {
  const params = new URLSearchParams(location.search),
    errorCode = params.get("auth_error");
  const messages = {
    "google-cancelled": "Google sign-in was cancelled. You can try again.",
    "google-unavailable":
      "Google sign-in could not be completed. Please try again or use your password.",
    "account-exists":
      "An account already uses this email. Sign in with your password, then connect Google in Your preferences.",
    "different-account":
      "Choose the Google account matching your existing account.",
    "expired-session":
      "Your sign-in session expired. Sign in again before connecting Google.",
  };
  const message = messages[errorCode];
  if (params.has("auth") || params.has("auth_error"))
    history.replaceState(null, "", location.pathname + location.hash);
  try {
    authConfig = await api("/auth/config");
  } catch {
    showAuth("Could not reach the server. Reload to try again.");
    return;
  }
  try {
    user = await api("/auth/me");
    route = labels[location.hash.slice(1)] ? location.hash.slice(1) : "today";
    await refresh();
    if (message) toast(message);
    if (params.get("auth") === "google-linked")
      toast("Google is connected to your account.");
  } catch (e) {
    showAuth(message || (e.message.includes("sign in") ? "" : e.message));
    if (params.get("auth") === "account-deleted")
      toast("Your account and its records were deleted.");
  }
}
start();
