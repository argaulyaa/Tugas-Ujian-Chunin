"use strict";
// ponytail: aggregate existing logs in-browser; paginate/server-aggregate if storage grows large.
function aggregateVisits(logs, period, selected) {
  const day = 86400000;
  const date = new Date(selected + "T00:00:00Z");
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(selected) ||
    !Number.isFinite(+date) ||
    date.toISOString().slice(0, 10) !== selected ||
    !["day", "week", "month", "year"].includes(period) ||
    !Array.isArray(logs)
  )
    throw new Error("Periode tidak valid.");
  let start = +date,
    length = 24;
  if (period === "week") {
    start -= ((date.getUTCDay() + 6) % 7) * day;
    length = 7;
  }
  if (period === "month") {
    start = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1);
    length = new Date(
      Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0),
    ).getUTCDate();
  }
  if (period === "year") {
    start = Date.UTC(date.getUTCFullYear(), 0, 1);
    length = 12;
  }
  const points = Array.from({ length }, (_, i) => ({
    label:
      period === "day"
        ? String(i).padStart(2, "0") + ":00"
        : period === "year"
          ? String(i + 1).padStart(2, "0")
          : new Date(start + i * day).toISOString().slice(0, 10),
    count: 0,
  }));
  for (const row of logs) {
    if (
      !row ||
      typeof row.timestamp !== "string" ||
      !/(Z|[+-]\d{2}:\d{2})$/.test(row.timestamp)
    )
      throw new Error("Timestamp log tidak valid.");
    const time = Date.parse(row.timestamp) + 7 * 3600000;
    if (!Number.isFinite(time)) throw new Error("Timestamp log tidak valid.");
    const shifted = new Date(time);
    const i =
      period === "year"
        ? shifted.getUTCMonth()
        : Math.floor((time - start) / (period === "day" ? 3600000 : day));
    if (period === "year" && shifted.getUTCFullYear() !== date.getUTCFullYear())
      continue;
    if (i >= 0 && i < length) points[i].count++;
  }
  return points;
}
