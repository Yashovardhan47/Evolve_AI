const paths = {
  tasks: "M8 3h8v4H8z M6 5H4v16h16V5h-2 M8 11l2 2 4-4 M8 17h8",
  profile: "M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M4 21v-3a8 8 0 0 1 16 0v3",
  today: "M3 10l9-7 9 7v10H3z M9 20v-7h6v7",
  checkin: "M8 3h8v4H8z M6 5H4v16h16V5h-2 M8 12l2 2 5-5 M8 18h8",
  goals: "M20 12a8 8 0 1 1-8-8 M16 12a4 4 0 1 1-4-4 M12 12l9-9 M16 3h5v5",
  wellbeing: "M20 4c-4-4-8 2-8 2S8 0 4 4c-5 5 8 16 8 16S25 9 20 4",
  finance: "M3 6h18v15H3z M3 6V3h14v3 M16 12h5v5h-5z",
  experiments: "M9 3h6 M10 3v6L4 19q-1 2 2 2h12q3 0 2-2L14 9V3 M7 15h10",
  insights: "M4 20V4 M4 20h17 M8 16l4-6 4 2 5-8",
  notifications: "M6 9a6 6 0 0 1 12 0v6l2 3H4l2-3z M10 21h4",
  settings:
    "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z",
  check: "M5 12l4 4L19 6",
  plus: "M12 4v16 M4 12h16",
  close: "M5 5l14 14 M19 5L5 19",
  logout: "M9 4H4v16h5 M14 8l5 4-5 4 M8 12h11",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l2 2 M17 17l2 2 M19 5l-2 2 M7 17l-2 2",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 7v5l3 2",
  spark: "M12 3l2 7 7 2-7 2-2 7-2-7-7-2 7-2z",
  menu: "M4 6h16 M4 12h16 M4 18h16",
  trash: "M3 6h18 M6 6l1 15h10l1-15 M9 6V3h6v3 M10 10v7 M14 10v7",
  download: "M12 3v12 M7 10l5 5 5-5 M4 17v4h16v-4",
  edit: "M14 4l6 6 M4 20l5-1L21 7l-4-4L5 15z",
};
export const icon = (key) =>
  `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[key] || paths.spark}"/></svg>`;
