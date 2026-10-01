export const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export const btn = (text, action, variant = "light", extra = "") =>
  `<button class="button ${variant}" data-action="${action}" ${extra}>${text}</button>`;
export const tag = (domain) =>
  `<span class="domain ${domain}">${esc(domain)}</span>`;
export const dateLabel = (day) =>
  new Date(`${day}T12:00:00`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
  });
export const addDays = (day, n) => {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
export const field = (label, name, type = "text", value = "", attr = "") =>
  `<div class="field"><label for="${name}">${label}</label><input id="${name}" name="${name}" type="${type}" value="${esc(value)}" ${attr}></div>`;
export const textArea = (label, name, value = "", attr = "") =>
  `<div class="field"><label for="${name}">${label}</label><textarea id="${name}" name="${name}" ${attr}>${esc(value)}</textarea></div>`;
export const selectField = (label, name, options, value) =>
  `<div class="field"><label for="${name}">${label}</label><select id="${name}" name="${name}">${options
    .map((o) => {
      const [v, l] = Array.isArray(o)
        ? o
        : [o, o[0].toUpperCase() + o.slice(1)];
      return `<option value="${esc(v)}" ${v === value ? "selected" : ""}>${esc(l)}</option>`;
    })
    .join("")}</select></div>`;
