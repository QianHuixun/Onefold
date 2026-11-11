const hhmm = new Intl.DateTimeFormat("zh-CN", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function clock(iso: string | null): string {
  if (!iso) return "";
  return hhmm.format(new Date(iso));
}

export function dayKey(iso: string): string {
  return new Date(iso).toDateString();
}

export function dayLabel(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return "今天";
  const y = new Date(now);
  y.setDate(now.getDate() - 1);
  if (d.toDateString() === y.toDateString()) return "昨天";
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日`;
}

export function todayLabel(d: Date = new Date()): string {
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日 · 星期${["日", "一", "二", "三", "四", "五", "六"][d.getDay()]}`;
}

export function fullDate(d: Date = new Date()): string {
  const week = ["日", "一", "二", "三", "四", "五", "六"][d.getDay()];
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日 · 星期${week}`;
}

export function shortTime(iso: string | null): string {
  if (!iso) return "";
  return `${dayLabel(iso)} ${clock(iso)}`;
}
