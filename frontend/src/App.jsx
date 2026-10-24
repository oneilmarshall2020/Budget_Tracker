import { useEffect, useState } from "react";
import {
  ArrowLeftRight,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  FileText,
  LogOut,
  Monitor,
  Moon,
  Pencil,
  Search,
  Sun,
  Trash2,
  TriangleAlert,
  Undo2,
  Upload,
  X,
} from "lucide-react";

// The backend lives behind /api on this same site (see vite.config.js), so the login
// cookie travels with every request automatically.
const BASE_URL = "/api";

// ================================================================ styles
// Reused class strings, pulled out so the markup below stays readable.
const card = "rounded-2xl border border-slate-200 bg-white p-6 shadow-sm";
const heading = "text-lg font-semibold text-slate-900";
const eyebrow = "text-xs font-medium uppercase tracking-wide text-slate-400";
const fieldLabel = "mb-1 block text-xs font-medium text-slate-500";
// The "Box" versions have no width, so you can give them one (w-44, w-auto...) without a clash.
const inputBox =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/10 disabled:bg-slate-50 disabled:text-slate-400";
const input = `${inputBox} w-full`;
const smallInputBox =
  "rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/10 disabled:bg-slate-50 disabled:text-slate-400";
const smallInput = `${smallInputBox} w-full`;
const primaryBtn =
  "rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";
const secondaryBtn =
  "rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300";
const dangerBtn =
  "rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-[#fff] transition-colors hover:bg-rose-500 disabled:cursor-not-allowed disabled:bg-rose-300 dark:disabled:bg-rose-900";
const iconBtn =
  "rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700";

// Chart colors. Each color always means the same thing everywhere on the page.
// (Blue + orange is a pair colorblind readers can still tell apart.)
// The actual colors are in index.css, with a light and a dark version of each.
const INCOME_COLOR = "var(--chart-income)";
const SPENDING_COLOR = "var(--chart-spending)";
const SPENDING_TRACK = "var(--chart-spending-track)"; // pale step of the spending color, behind meters
const OVER_COLOR = "var(--chart-over)"; // only for "over budget", always shown with an icon + words
const OVER_TRACK = "var(--chart-over-track)";
const CHART_HEIGHT = 180;

// ================================================================ constants
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const MONTHS_SHORT = MONTHS.map((name) => name.slice(0, 3));
const CURRENT_YEAR = new Date().getFullYear();
const CURRENT_MONTH = new Date().getMonth() + 1;
const YEARS = Array.from({ length: 5 }, (_, i) => CURRENT_YEAR - 3 + i);

const TYPE_LABELS = { expense: "Expense", income: "Income", transfer: "Transfer", refund: "Refund" };
const ACCOUNT_TYPE_LABELS = { savings: "Savings", chequing: "Chequing", credit_card: "Credit card" };

const EMPTY_ACCOUNT = { nickname: "", bank_name: "NCB", account_type: "savings", last_four: "" };
const EMPTY_CATEGORY = { name: "", kind: "expense" };
const EMPTY_BUDGET = { category_id: "", amount: "" };

// ================================================================ small helpers
function todayString() {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function emptyTransaction() {
  return { type: "expense", amount: "", date: todayString(), description: "", account_id: "", category_id: "" };
}

function formatMoney(n) {
  const value = Number(n || 0);
  const text = Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${value < 0 ? "−" : ""}$${text}`;
}

// 40000 -> "$40K" (for chart axes)
function formatCompact(n) {
  if (n < 1000) return `$${n}`;
  const thousands = n / 1000;
  return `$${Number.isInteger(thousands) ? thousands : thousands.toFixed(1)}K`;
}

// "2026-09-14" -> "Sep 14". Split the string ourselves: new Date("2026-09-14") is UTC
// midnight, which is still the 13th in Jamaica.
function formatDate(isoDate, withYear = false) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return `${MONTHS_SHORT[m - 1]} ${d}${withYear ? `, ${y}` : ""}`;
}

// "2026-10-15T21:36:32+00:00" -> "Oct 15" in your local time. Older setups may send the
// time without a zone; it's UTC either way, so add the "Z" that says so.
function formatDay(isoDateTime) {
  const hasZone = /(Z|[+-]\d\d:\d\d)$/i.test(isoDateTime);
  const when = new Date(hasZone ? isoDateTime : `${isoDateTime}Z`);
  return when.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// plural(1, "row") -> "1 row", plural(2, "row") -> "2 rows", plural(2, "category", "categories")
// Browser storage can be blocked (private windows), so never let it crash the app.
function readSaved(kind, key) {
  try {
    return window[kind].getItem(key);
  } catch {
    return null;
  }
}
function save(kind, key, value) {
  try {
    window[kind].setItem(key, value);
  } catch {
    // not saved: fine, it's only a convenience
  }
}

// The month you were looking at, remembered until you close the tab.
function savedPeriod() {
  try {
    const { year, month } = JSON.parse(readSaved("sessionStorage", "budget.period"));
    if (Number.isInteger(year) && month >= 1 && month <= 12) return { year, month };
  } catch {
    // nothing saved yet
  }
  return { year: CURRENT_YEAR, month: CURRENT_MONTH };
}

function plural(count, word, many = `${word}s`) {
  return `${count} ${count === 1 ? word : many}`;
}

// Move a (year, month) pair by some number of months: (2026, 1) - 1 -> (2025, 12)
function shiftMonth(year, month, delta) {
  const index = year * 12 + (month - 1) + delta;
  return { year: Math.floor(index / 12), month: (index % 12) + 1 };
}

// "" from a <select> means "none"
function toId(value) {
  return value === "" || value === null || value === undefined ? null : Number(value);
}

// Same rule as the backend's category_fits: income -> income categories,
// expense/refund -> expense categories, transfers -> no category.
function categoryFits(category, type) {
  if (!category || type === "transfer") return false;
  return type === "income" ? category.kind === "income" : category.kind === "expense";
}

// Round a chart's top value up to something clean: 33,212 -> 40,000
function niceMax(value) {
  if (value <= 0) return 1000;
  const power = 10 ** Math.floor(Math.log10(value));
  const step = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find((s) => s * power >= value);
  return step * power;
}

// ================================================================ talking to the API
// FastAPI sends errors as {"detail": "..."} or, for validation, {"detail": [{loc, msg}, ...]}.
function readError(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    const message = first.msg || "Invalid input";
    // Our own validators already name the field ("Description cannot be blank").
    if (message.startsWith("Value error, ")) return message.replace("Value error, ", "");
    const field = first.loc?.[first.loc.length - 1];
    if (typeof field !== "string") return message;
    const name = field.replace(/_id$/, "").replace(/_/g, " ");
    return `${name[0].toUpperCase()}${name.slice(1)}: ${message}`;
  }
  return `Request failed (${status})`;
}

// Called when the backend says "please log in" (status 401): your login ran out, or you
// logged out in another tab. App sets it to "go back to the login screen".
let onLoggedOut = () => {};

// One place that does fetch + JSON + error handling, so every handler stays short.
// async/await is the same as .then() chains, just read top to bottom.
async function api(path, { method = "GET", body, form } = {}) {
  const options = { method };
  if (form) {
    options.body = form; // FormData (file upload): the browser sets the headers itself
  } else if (body !== undefined) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, options);
  } catch {
    throw new Error("Can't reach the server. Is the backend running?");
  }
  const data = await response.json().catch(() => null);
  if (response.status === 401 && !path.startsWith("/auth/")) onLoggedOut();
  if (!response.ok) {
    // No JSON at all from a 5xx means Vite couldn't reach FastAPI (it isn't running).
    const message =
      data === null && response.status >= 500
        ? "Can't reach the server. Is the backend running?"
        : readError(data, response.status);
    const error = new Error(message);
    error.status = response.status; // lets the login screen tell "logged out" from "broken"
    throw error;
  }
  return data;
}

// ================================================================ small components
function Modal({ title, subtitle, onClose, wide = false, footer, children }) {
  // Close on Escape
  useEffect(() => {
    function onKey(event) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 dark:bg-black/60"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        className={`flex max-h-[90vh] w-full flex-col rounded-2xl bg-white shadow-xl ${wide ? "max-w-5xl" : "max-w-md"}`}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-4">
          <div>
            <h3 className={heading}>{title}</h3>
            {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
          </div>
          <button className={iconBtn} onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-4">{children}</div>
        {footer && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-100 px-6 py-4">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, className = "", children }) {
  return (
    <label className={`block ${className}`}>
      <span className={fieldLabel}>{label}</span>
      {children}
    </label>
  );
}

function StatTile({ label, value, note }) {
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">{value}</p>
      {note && <div className="mt-1 text-xs text-slate-500">{note}</div>}
    </div>
  );
}

function Swatch({ color }) {
  return <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />;
}

function EditButtons({ name, onEdit, onDelete }) {
  return (
    <div className="flex shrink-0 items-center">
      <button className={iconBtn} onClick={onEdit} aria-label={`Edit ${name}`}>
        <Pencil className="h-4 w-4" />
      </button>
      <button
        className={`${iconBtn} hover:text-rose-600 dark:hover:text-rose-400`}
        onClick={onDelete}
        aria-label={`Delete ${name}`}
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

// Horizontal bars, biggest first: "where did the money go?"
function RankedBars({ rows, color }) {
  const total = rows.reduce((sum, row) => sum + Math.max(row.amount, 0), 0);
  const biggest = Math.max(...rows.map((row) => row.amount), 0) || 1;
  return (
    <ul className="space-y-3">
      {rows.map((row) => (
        <li key={row.category}>
          <div className="flex items-baseline justify-between gap-2 text-sm">
            <span className="truncate text-slate-700">{row.category}</span>
            <span className="shrink-0 tabular-nums">
              <span className="font-medium text-slate-900">{formatMoney(row.amount)}</span>
              <span className="ml-2 inline-block w-9 text-right text-xs text-slate-400">
                {total > 0 ? Math.round((Math.max(row.amount, 0) / total) * 100) : 0}%
              </span>
            </span>
          </div>
          <div className="mt-1 h-2">
            <div
              className="h-2 rounded-r-[4px]"
              style={{
                width: `${(Math.max(row.amount, 0) / biggest) * 100}%`,
                backgroundColor: color,
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

// Income vs spending for each month of the year. Click a month to open it.
function YearChart({ months, selectedMonth, onPick }) {
  const [hovered, setHovered] = useState(null);
  const top = niceMax(Math.max(0, ...months.flatMap((m) => [m.income, m.spending])));
  const ticks = [top, top / 2, 0];
  const focus = months[(hovered ?? selectedMonth) - 1];

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 text-sm">
        <div className="flex items-center gap-4 text-slate-600">
          <span className="flex items-center gap-1.5">
            <Swatch color={INCOME_COLOR} /> Income
          </span>
          <span className="flex items-center gap-1.5">
            <Swatch color={SPENDING_COLOR} /> Spending
          </span>
        </div>
        {/* Readout for the hovered (or selected) month */}
        <p className="text-slate-500 tabular-nums">
          <span className="font-medium text-slate-900">{MONTHS[focus.month - 1]}</span>
          {" · "}in {formatMoney(focus.income)}
          {" · "}out {formatMoney(focus.spending)}
          {" · "}
          {focus.net >= 0 ? "saved" : "overspent"} {formatMoney(Math.abs(focus.net))}
        </p>
      </div>

      <div className="mt-4 flex gap-2">
        {/* y-axis labels */}
        <div className="relative w-12 shrink-0 text-right text-xs text-slate-400" style={{ height: CHART_HEIGHT }}>
          {ticks.map((tick) => (
            <span
              key={tick}
              className="absolute right-0 -translate-y-1/2 tabular-nums"
              style={{ top: `${(1 - tick / top) * 100}%` }}
            >
              {formatCompact(tick)}
            </span>
          ))}
        </div>

        {/* plot */}
        <div className="relative flex-1" style={{ height: CHART_HEIGHT }}>
          {ticks.map((tick) => (
            <div
              key={tick}
              className="absolute inset-x-0 border-t border-slate-100"
              style={{ top: `${(1 - tick / top) * 100}%` }}
            />
          ))}
          <div className="relative flex h-full">
            {months.map((m) => {
              const active = m.month === (hovered ?? selectedMonth);
              return (
                <button
                  key={m.month}
                  type="button"
                  className={`flex h-full flex-1 items-end justify-center gap-[2px] rounded-md transition-colors ${active ? "bg-slate-100/80" : ""}`}
                  onMouseEnter={() => setHovered(m.month)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(m.month)}
                  onBlur={() => setHovered(null)}
                  onClick={() => onPick(m.month)}
                  aria-label={`${MONTHS[m.month - 1]}: income ${formatMoney(m.income)}, spending ${formatMoney(m.spending)}. Open this month.`}
                >
                  <span
                    className="block w-2 rounded-t-[4px] sm:w-3.5"
                    style={{ height: `${(m.income / top) * 100}%`, backgroundColor: INCOME_COLOR }}
                  />
                  <span
                    className="block w-2 rounded-t-[4px] sm:w-3.5"
                    style={{ height: `${(Math.max(m.spending, 0) / top) * 100}%`, backgroundColor: SPENDING_COLOR }}
                  />
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* x-axis labels */}
      <div className="mt-1 flex gap-2">
        <div className="w-12 shrink-0" />
        <div className="flex flex-1">
          {months.map((m) => (
            <span key={m.month} className="flex-1 text-center text-xs text-slate-400">
              <span className="sm:hidden">{MONTHS_SHORT[m.month - 1][0]}</span>
              <span className="hidden sm:inline">{MONTHS_SHORT[m.month - 1]}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// Filters: [id, label, test]. The test decides if a row belongs under that pill.
const TRANSACTION_FILTERS = [
  ["all", "All", () => true],
  ["income", "Income", (tx) => tx.type === "income"],
  ["expense", "Expenses", (tx) => tx.type === "expense"],
  ["refund", "Refunds", (tx) => tx.type === "refund"],
  ["transfer", "Transfers", (tx) => tx.type === "transfer"],
  ["uncategorized", "Uncategorized", (tx) => tx.type !== "transfer" && tx.category_id === null],
];

const PREVIEW_FILTERS = [
  ["all", "All", () => true],
  ["needs", "Needs category", (row) => row.type !== "transfer" && row.category_id === null],
  ["categorized", "Categorized", (row) => row.type !== "transfer" && row.category_id !== null],
  ["review", "Check type", (row) => row.flag === "review"],
  ["income", "Income", (row) => row.type === "income"],
  ["expense", "Expenses", (row) => row.type === "expense"],
  ["transfer", "Transfers", (row) => row.type === "transfer"],
  ["already", "Already there", (row) => ["duplicate", "possible", "match"].includes(row.flag)],
];

// A row of clickable pills with counts. Pills with nothing in them are hidden
// (except "All" and the one you're on).
function FilterChips({ filters, rows, value, onChange }) {
  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter">
      {filters.map(([id, label, test]) => {
        const count = rows.filter(test).length;
        if (count === 0 && id !== "all" && id !== value) return null;
        const active = id === value;
        return (
          <button
            key={id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(id)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              active ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {label} <span className={active ? "text-slate-300" : "text-slate-400"}>{count}</span>
          </button>
        );
      })}
    </div>
  );
}

function SearchBox({ value, onChange, placeholder }) {
  return (
    <div className="relative min-w-0 flex-1">
      <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <input
        className={`${input} pr-8 pl-9`}
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={placeholder}
      />
      {value && (
        <button
          className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-0.5 text-slate-400 hover:text-slate-700"
          onClick={() => onChange("")}
          aria-label="Clear search"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

const FLAG_STYLES = {
  duplicate: { text: "Already imported", className: "bg-slate-100 text-slate-600" },
  possible: { text: "Probably imported", className: "bg-orange-50 text-orange-800 dark:bg-orange-950/60 dark:text-orange-300" },
  match: { text: "Already logged", className: "bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300" },
  transfer: { text: "Your transfer", className: "bg-violet-50 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300" },
  review: { text: "Check type", className: "bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300" },
};

function FlagBadge({ flag }) {
  const style = FLAG_STYLES[flag];
  if (!style) return null;
  return (
    <span className={`ml-2 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${style.className}`}>
      {style.text}
    </span>
  );
}

const THEMES = [
  ["system", Monitor, "System"],
  ["light", Sun, "Light"],
  ["dark", Moon, "Dark"],
];

function ThemeSwitch({ theme, onChange }) {
  return (
    <div
      className="flex items-center gap-0.5 rounded-xl border border-slate-200 bg-white p-1 shadow-sm"
      role="group"
      aria-label="Theme"
    >
      {THEMES.map(([value, Icon, text]) => (
        <button
          key={value}
          type="button"
          title={`${text} theme`}
          aria-label={`${text} theme`}
          aria-pressed={theme === value}
          onClick={() => onChange(value)}
          className={`rounded-md p-1 transition-colors sm:p-1.5 ${
            theme === value ? "bg-slate-100 text-slate-900" : "text-slate-400 hover:text-slate-700"
          }`}
        >
          <Icon className="h-4 w-4" />
        </button>
      ))}
    </div>
  );
}

function Logo() {
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-lg font-semibold text-white">
      $
    </div>
  );
}

// ================================================================ logging in
const EMPTY_LOGIN = { username: "", password: "", repeat: "", code: "" };

function AuthScreen({ theme, onThemeChange, onLoggedIn, notice }) {
  const [mode, setMode] = useState("login"); // "login" | "signup"
  // Start with the last username used in this browser, so you only type your password.
  const [form, setForm] = useState(() => ({
    ...EMPTY_LOGIN,
    username: readSaved("localStorage", "budget.lastUser") || "",
  }));
  const [needsCode, setNeedsCode] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  // Does creating an account need a sign-up code here? (Only once deployed, usually.)
  useEffect(() => {
    api("/auth/settings")
      .then((settings) => setNeedsCode(settings.signup_needs_code))
      .catch(() => {});
  }, []);

  function switchTo(next) {
    setMode(next);
    setError(null);
    setForm({ ...EMPTY_LOGIN, username: form.username });
  }

  async function handleSubmit(event) {
    event.preventDefault(); // stop the browser from reloading the page
    setError(null);
    if (mode === "signup" && form.password !== form.repeat) {
      setError("The two passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      const user =
        mode === "login"
          ? await api("/auth/login", {
              method: "POST",
              body: { username: form.username, password: form.password },
            })
          : await api("/auth/signup", {
              method: "POST",
              body: { username: form.username, password: form.password, signup_code: form.code || null },
            });
      onLoggedIn(user);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const signingUp = mode === "signup";
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto flex max-w-md flex-col px-4 py-8 sm:py-16">
        <div className="mb-8 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Logo />
            <h1 className="text-2xl font-semibold tracking-tight">Ledger</h1>
          </div>
          <ThemeSwitch theme={theme} onChange={onThemeChange} />
        </div>

        <div className={card}>
          <div className="mb-5 grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1" role="tablist">
            {[
              ["login", "Log in"],
              ["signup", "Create account"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={mode === value}
                onClick={() => switchTo(value)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  mode === value ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {notice && !error && (
            <p className="mb-4 rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-600">{notice}</p>
          )}

          <form className="space-y-4" onSubmit={handleSubmit}>
            <Field label="Username">
              <input
                className={input}
                value={form.username}
                onChange={(event) => setForm({ ...form, username: event.target.value })}
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                autoFocus={!form.username}
                required
              />
            </Field>
            <Field label={signingUp ? "Password (at least 8 characters)" : "Password"}>
              <input
                className={input}
                type="password"
                value={form.password}
                onChange={(event) => setForm({ ...form, password: event.target.value })}
                autoComplete={signingUp ? "new-password" : "current-password"}
                autoFocus={Boolean(form.username) && !signingUp}
                minLength={signingUp ? 8 : undefined}
                required
              />
            </Field>
            {signingUp && (
              <Field label="Password again">
                <input
                  className={input}
                  type="password"
                  value={form.repeat}
                  onChange={(event) => setForm({ ...form, repeat: event.target.value })}
                  autoComplete="new-password"
                  required
                />
              </Field>
            )}
            {signingUp && needsCode && (
              <Field label="Sign-up code">
                <input
                  className={input}
                  value={form.code}
                  onChange={(event) => setForm({ ...form, code: event.target.value })}
                  autoComplete="off"
                  required
                />
                <span className="mt-1 block text-xs text-slate-500">
                  Ask the person who runs this app for the code.
                </span>
              </Field>
            )}

            {error && (
              <p
                role="alert"
                className="flex items-start gap-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300"
              >
                <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                {error}
              </p>
            )}

            <button type="submit" className={`${primaryBtn} w-full`} disabled={busy}>
              {busy ? "One moment..." : signingUp ? "Create account" : "Log in"}
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-slate-400">
          Each account only ever sees its own money.
        </p>
      </div>
    </div>
  );
}

// ================================================================ the app
function BudgetApp({ user, theme, onThemeChange, onLogOut }) {
  // --- Which month you're looking at ---
  const [year, setYear] = useState(() => savedPeriod().year);
  const [month, setMonth] = useState(() => savedPeriod().month);

  // --- Data from the backend ---
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [transactions, setTransactions] = useState([]); // selected month only
  const [budgets, setBudgets] = useState([]); // selected month only
  const [monthly, setMonthly] = useState(null);
  const [yearly, setYearly] = useState(null);

  // --- Loading and messages ---
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [version, setVersion] = useState(0); // bump this to reload everything
  const [busy, setBusy] = useState(false); // a save/delete is in flight
  const [actionError, setActionError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [confirmBox, setConfirmBox] = useState(null); // { message, onConfirm, actionLabel, danger, title }

  // --- Add forms ---
  const [newAccount, setNewAccount] = useState(EMPTY_ACCOUNT);
  const [newCategory, setNewCategory] = useState(EMPTY_CATEGORY);
  const [newBudget, setNewBudget] = useState(EMPTY_BUDGET);
  const [newTx, setNewTx] = useState(emptyTransaction);

  // --- Edit modals (null = closed) ---
  const [editAccount, setEditAccount] = useState(null);
  const [editCategory, setEditCategory] = useState(null);
  const [editBudget, setEditBudget] = useState(null);
  const [editTx, setEditTx] = useState(null);
  // What the app could learn from a category change in the edit pop-up (null = nothing).
  const [learnHint, setLearnHint] = useState(null);

  // --- Transactions list filter ---
  const [accountFilter, setAccountFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [searchScope, setSearchScope] = useState("month"); // "month" | "all"
  const [allTimeResults, setAllTimeResults] = useState([]);
  const [previewFilter, setPreviewFilter] = useState("all");
  const [previewSearch, setPreviewSearch] = useState("");

  // --- Statement import ---
  const [importAccountId, setImportAccountId] = useState("");
  const [importFile, setImportFile] = useState(null);
  const [importPassword, setImportPassword] = useState("");
  const [fileInputKey, setFileInputKey] = useState(0); // changing a key resets the <input type="file">
  const [preview, setPreview] = useState(null); // { account_id, file_name, rows, problems }
  const [imports, setImports] = useState([]); // past statement imports, newest first
  const [rules, setRules] = useState([]); // keyword -> category rules
  const [newKeyword, setNewKeyword] = useState("");
  const [showAllImports, setShowAllImports] = useState(false);

  // --- Year report view ---
  const [yearView, setYearView] = useState("chart");

  // Load everything for the selected month. Runs on first render, when the month
  // changes, and after every save (reload() bumps `version`).
  useEffect(() => {
    let ignore = false; // if you switch months quickly, drop the older, slower answer
    const period = `year=${year}&month=${month}`;
    Promise.all([
      api("/account/"),
      api("/categories/"),
      api(`/transaction/?${period}`),
      api(`/budget/?${period}`),
      api(`/summary/${year}/${month}`),
      api(`/summary/${year}`),
      api("/statement/imports"),
      api("/rules/"),
    ])
      .then(([accountList, categoryList, txList, budgetList, monthSummary, yearSummary, importList, ruleList]) => {
        if (ignore) return;
        setAccounts(accountList);
        setCategories(categoryList);
        setTransactions(txList);
        setBudgets(budgetList);
        setMonthly(monthSummary);
        setYearly(yearSummary);
        setImports(importList);
        setRules(ruleList);
        setLoadError(null);
        // Keep the chosen import account if it still exists, else pick the first one.
        setImportAccountId((current) =>
          accountList.some((a) => String(a.id) === current)
            ? current
            : accountList[0]
              ? String(accountList[0].id)
              : ""
        );
      })
      .catch((err) => {
        if (!ignore) setLoadError(err.message);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [year, month, version]);

  // Success messages fade after a few seconds.
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 6000);
    return () => clearTimeout(timer);
  }, [notice]);

  // "All time" search asks the backend (the page only holds one month).
  // Waits 300ms after you stop typing so we don't send a request per key.
  useEffect(() => {
    const term = search.trim();
    if (searchScope !== "all" || term.length < 2) return;
    let ignore = false;
    const timer = setTimeout(() => {
      api(`/transaction/?q=${encodeURIComponent(term)}`)
        .then((rows) => {
          if (!ignore) setAllTimeResults(rows);
        })
        .catch((err) => {
          if (!ignore) setActionError(err.message);
        });
    }, 300);
    return () => {
      ignore = true;
      clearTimeout(timer);
    };
  }, [search, searchScope, version]);

  // Remember the month across refreshes (until the tab is closed).
  useEffect(() => {
    save("sessionStorage", "budget.period", JSON.stringify({ year, month }));
  }, [year, month]);

  function reload() {
    setVersion((v) => v + 1);
  }

  // Wraps every save/delete: clears old errors, blocks double clicks, shows failures.
  async function run(action) {
    setActionError(null);
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  // Opens the "are you sure?" pop-up. Options: button label, red (danger) or not, title.
  function askConfirm(message, onConfirm, { actionLabel = "Delete", danger = true, title = "Are you sure?" } = {}) {
    setConfirmBox({ message, onConfirm, actionLabel, danger, title });
  }

  function goToMonth(delta) {
    const next = shiftMonth(year, month, delta);
    setYear(next.year);
    setMonth(next.month);
  }

  // --- lookups ---
  function categoryName(id) {
    return categories.find((c) => c.id === id)?.name ?? "Uncategorized";
  }
  function accountName(id) {
    return accounts.find((a) => a.id === id)?.nickname ?? "No account";
  }
  function keywordCount(categoryId) {
    return rules.filter((r) => r.category_id === categoryId).length;
  }
  function categoriesFor(type) {
    return categories.filter((c) => categoryFits(c, type));
  }

  // ---------------------------------------------------------------- accounts
  function handleAddAccount() {
    run(async () => {
      await api("/account/", { method: "POST", body: newAccount });
      setNewAccount(EMPTY_ACCOUNT);
      reload();
    });
  }

  function handleSaveAccount() {
    run(async () => {
      const { id, nickname, bank_name, account_type, last_four } = editAccount;
      await api(`/account/${id}`, {
        method: "PATCH",
        body: { nickname, bank_name, account_type, last_four },
      });
      setEditAccount(null);
      reload();
    });
  }

  function handleDeleteAccount(account) {
    askConfirm(
      `Delete "${account.nickname}"? Its transactions stay in your history, just no longer linked to an account.`,
      async () => {
        await api(`/account/${account.id}`, { method: "DELETE" });
        reload();
      }
    );
  }

  // ---------------------------------------------------------------- categories
  function handleAddCategory() {
    run(async () => {
      await api("/categories/", { method: "POST", body: newCategory });
      setNewCategory(EMPTY_CATEGORY);
      reload();
    });
  }

  function handleSaveCategory() {
    run(async () => {
      await api(`/categories/${editCategory.id}`, {
        method: "PATCH",
        body: { name: editCategory.name, kind: editCategory.kind },
      });
      setEditCategory(null);
      reload();
    });
  }

  function handleDeleteCategory(category) {
    askConfirm(
      `Delete "${category.name}"? Its budgets and keywords are deleted too. Its transactions are kept and become Uncategorized.`,
      async () => {
        await api(`/categories/${category.id}`, { method: "DELETE" });
        reload();
      }
    );
  }

  // ---------------------------------------------------------------- keywords
  // Keyword changes save right away (unlike name/kind, which wait for Save).
  function handleAddKeyword() {
    run(async () => {
      await api("/rules/", { method: "POST", body: { keyword: newKeyword, category_id: editCategory.id } });
      setNewKeyword("");
      reload();
    });
  }

  function handleDeleteKeyword(rule) {
    run(async () => {
      await api(`/rules/${rule.id}`, { method: "DELETE" });
      reload();
    });
  }

  function handleAddSuggested() {
    run(async () => {
      const result = await api("/rules/suggested", { method: "POST" });
      setNotice(
        `Added ${plural(result.categories_added, "category", "categories")} and ` +
          `${plural(result.keywords_added, "keyword")}. Edit any category to see or change its keywords.`
      );
      reload();
    });
  }

  // ---------------------------------------------------------------- budgets
  function handleAddBudget() {
    run(async () => {
      if (!newBudget.category_id) throw new Error("Choose a category for the budget");
      await api("/budget/", {
        method: "POST",
        body: {
          category_id: Number(newBudget.category_id),
          year,
          month,
          amount: Number(newBudget.amount),
        },
      });
      setNewBudget(EMPTY_BUDGET);
      reload();
    });
  }

  function handleSaveBudget() {
    run(async () => {
      await api(`/budget/${editBudget.id}`, {
        method: "PATCH",
        body: { amount: Number(editBudget.amount) },
      });
      setEditBudget(null);
      reload();
    });
  }

  function handleDeleteBudget(budget) {
    askConfirm(
      `Delete the ${categoryName(budget.category_id)} budget for ${MONTHS[budget.month - 1]} ${budget.year}?`,
      async () => {
        await api(`/budget/${budget.id}`, { method: "DELETE" });
        reload();
      }
    );
  }

  // Start a new month quickly: copy last month's budgets you don't have yet.
  function handleCopyBudgets() {
    run(async () => {
      const prev = shiftMonth(year, month, -1);
      const last = await api(`/budget/?year=${prev.year}&month=${prev.month}`);
      const have = new Set(budgets.map((b) => b.category_id));
      const toCopy = last.filter((b) => !have.has(b.category_id));
      if (toCopy.length === 0) {
        throw new Error(`Nothing new to copy from ${MONTHS[prev.month - 1]} ${prev.year}`);
      }
      for (const b of toCopy) {
        await api("/budget/", {
          method: "POST",
          body: { category_id: b.category_id, year, month, amount: b.amount },
        });
      }
      setNotice(`Copied ${plural(toCopy.length, "budget")} from ${MONTHS[prev.month - 1]}`);
      reload();
    });
  }

  // ---------------------------------------------------------------- transactions
  function transactionBody(tx) {
    return {
      amount: Number(tx.amount),
      date: tx.date,
      description: tx.description,
      type: tx.type,
      account_id: toId(tx.account_id),
      category_id: tx.type === "transfer" ? null : toId(tx.category_id),
    };
  }

  // Changing the type can make the chosen category wrong (Food can't be income).
  function withType(tx, type) {
    const current = categories.find((c) => c.id === toId(tx.category_id));
    return { ...tx, type, category_id: categoryFits(current, type) ? tx.category_id : "" };
  }

  async function saveNewTransaction(body) {
    const created = await api("/transaction/", { method: "POST", body });
    // Keep type and account: you often log several of the same kind in a row.
    setNewTx({ ...emptyTransaction(), type: newTx.type, account_id: newTx.account_id });
    const [y, m] = created.date.split("-").map(Number);
    if (y !== year || m !== month) {
      setNotice(`Saved. It's dated ${formatDate(created.date, true)}, so it's under ${MONTHS[m - 1]} ${y}.`);
    }
    reload();
  }

  function handleAddTransaction() {
    run(async () => {
      const body = transactionBody(newTx);
      // Already in an imported statement? Ask before adding a double.
      if (body.amount > 0 && body.date) {
        const params = new URLSearchParams({ amount: body.amount, date: body.date, type: body.type });
        const similar = await api(`/transaction/similar?${params}`);
        if (similar.length > 0) {
          const found = similar[0];
          askConfirm(
            `Your ${accountName(found.account_id)} statement already has "${found.description}" for ` +
              `${formatMoney(found.amount)} on ${formatDate(found.date)}. If that's this purchase, adding it ` +
              "again would count it twice. Add it anyway?",
            () => saveNewTransaction(body),
            { actionLabel: "Add anyway", danger: false, title: "Already imported?" }
          );
          return;
        }
      }
      await saveNewTransaction(body);
    });
  }

  // You picked a new category in the edit pop-up: ask the backend what it could learn.
  function changeEditCategory(value) {
    setEditTx({ ...editTx, category_id: value });
    const categoryId = toId(value);
    if (categoryId === null || categoryId === editTx.original_category_id) {
      setLearnHint(null);
      return;
    }
    const params = new URLSearchParams({ description: editTx.description, category_id: categoryId, exclude_id: editTx.id });
    api(`/rules/suggest?${params}`)
      .then((s) => {
        const worthAsking = s.keyword && (s.rule_category_id !== categoryId || s.others > 0);
        setLearnHint(
          worthAsking ? { ...s, categoryId, remember: s.rule_category_id !== categoryId, applyOthers: false } : null
        );
      })
      .catch(() => setLearnHint(null)); // learning is optional: never block an edit
  }

  function handleSaveTransaction() {
    run(async () => {
      await api(`/transaction/${editTx.id}`, { method: "PATCH", body: transactionBody(editTx) });
      // Only use the hint if it's for the category you ended up saving.
      const hint =
        learnHint && learnHint.categoryId === toId(editTx.category_id) && editTx.type !== "transfer" ? learnHint : null;
      const learned = [];
      if (hint?.remember && hint.rule_category_id !== hint.categoryId) {
        await api("/rules/remember", { method: "POST", body: { keyword: hint.keyword, category_id: hint.categoryId } });
        learned.push(`${hint.keyword} → ${categoryName(hint.categoryId)} from now on`);
      }
      if (hint?.applyOthers && hint.others > 0) {
        const result = await api("/rules/apply", {
          method: "POST",
          body: { keyword: hint.keyword, category_id: hint.categoryId, exclude_id: editTx.id },
        });
        learned.push(`changed ${plural(result.updated, "other transaction")}`);
      }
      if (learned.length > 0) setNotice(`Saved. ${learned.join("; ")}.`);
      setEditTx(null);
      setLearnHint(null);
      reload();
    });
  }

  function handleDeleteTransaction(tx) {
    askConfirm(`Delete "${tx.description}" (${formatMoney(tx.amount)}) from ${formatDate(tx.date, true)}?`, async () => {
      await api(`/transaction/${tx.id}`, { method: "DELETE" });
      reload();
    });
  }

  function openEditTransaction(tx) {
    setLearnHint(null);
    setEditTx({
      ...tx,
      amount: String(tx.amount),
      account_id: tx.account_id ?? "",
      category_id: tx.category_id ?? "",
      original_category_id: tx.category_id, // to tell whether you changed it
    });
  }

  // ---------------------------------------------------------------- statement import
  function handlePreview() {
    run(async () => {
      if (!importAccountId) throw new Error("Add an account first, then choose it here");
      if (!importFile) throw new Error("Choose a .pdf or .csv statement first");
      const form = new FormData();
      form.append("account_id", importAccountId);
      form.append("file", importFile);
      if (importPassword) form.append("password", importPassword);
      const data = await api("/statement/preview", { method: "POST", form });
      setPreview(data);
      setPreviewFilter("all");
      setPreviewSearch("");
      setImportPassword(""); // don't keep the PDF password around longer than needed
      reload(); // the preview may have created the "Bank Fees" category
    });
  }

  function updatePreviewRow(key, changes) {
    setPreview((current) => ({
      ...current,
      rows: current.rows.map((row) => (row.key === key ? { ...row, ...changes } : row)),
    }));
  }

  // You picked a category for one row: rows from the same place (same keyword) that
  // you haven't set yourself get it too, if it fits their type.
  function setPreviewCategory(changed, categoryId) {
    const category = categories.find((c) => c.id === categoryId);
    setPreview((current) => ({
      ...current,
      rows: current.rows.map((row) => {
        if (row.key === changed.key) {
          return { ...row, category_id: categoryId, category_source: null, touched: true };
        }
        const samePlace = changed.keyword && row.keyword === changed.keyword;
        if (samePlace && !row.touched && categoryId !== null && categoryFits(category, row.type)) {
          return { ...row, category_id: categoryId, category_source: "same" };
        }
        return row;
      }),
    }));
  }

  // Select all / none: only the rows you can see with the current filter and search.
  function setAllIncluded(include, visibleKeys) {
    setPreview((current) => ({
      ...current,
      rows: current.rows.map((row) =>
        row.flag === "duplicate" || !visibleKeys.has(row.key) ? row : { ...row, include }
      ),
    }));
  }

  function handleConfirmImport() {
    const rows = preview.rows
      .filter((row) => row.include)
      .map(({ date, description, amount, type, category_id }) => ({
        date,
        description,
        amount,
        type,
        category_id: type === "transfer" ? null : toId(category_id),
      }));

    run(async () => {
      const result = await api("/statement/confirm", {
        method: "POST",
        body: {
          account_id: preview.account_id,
          file_name: preview.file_name,
          rows,
          // Rows left unticked because you logged them yourself: link your entries to this account.
          matched_ids: preview.rows.filter((r) => r.flag === "match" && !r.include).map((r) => r.match_id),
          // Transfers between your accounts: the other side becomes a transfer too.
          transfer_pair_ids: preview.rows
            .filter((r) => r.include && r.pair_id && r.type === "transfer")
            .map((r) => r.pair_id),
        },
      });

      // Jump to the month most of these transactions belong to.
      const perMonth = {};
      for (const row of rows) {
        const key = row.date.slice(0, 7); // "2026-09"
        perMonth[key] = (perMonth[key] || 0) + 1;
      }
      const busiest = Object.keys(perMonth).sort((a, b) => perMonth[b] - perMonth[a])[0];

      let message = `Imported ${plural(result.created.length, "transaction")}`;
      if (result.skipped) message += ` (${result.skipped} already there, skipped)`;
      if (result.keywords_learned.length > 0) {
        message += `. Learned ${plural(result.keywords_learned.length, "keyword")}: ${result.keywords_learned.join(", ")}`;
      }
      if (result.linked > 0) {
        message += `. Linked ${plural(result.linked, "entry", "entries")} you logged to ${accountName(preview.account_id)}`;
      }
      if (result.transfers_paired > 0) {
        message += `. Paired ${plural(result.transfers_paired, "transfer")} with your other account`;
      }
      if (busiest) {
        const [y, m] = busiest.split("-").map(Number);
        setYear(y);
        setMonth(m);
        message += `. Showing ${MONTHS[m - 1]} ${y}.`;
      }
      setNotice(message);
      setPreview(null);
      setImportFile(null);
      setFileInputKey((k) => k + 1);
      reload();
    });
  }

  // Wrong statement? Remove everything that import added, in one go.
  function handleUndoImport(batch) {
    const count = plural(batch.remaining, "transaction");
    askConfirm(
      `Remove the ${count} imported from "${batch.file_name}" (${formatDate(batch.first_date)} – ${formatDate(batch.last_date, true)})? ` +
        "Any changes you made to them go too. Transactions you logged yourself aren't touched.",
      async () => {
        const result = await api(`/statement/imports/${batch.id}`, { method: "DELETE" });
        setNotice(`Removed ${plural(result.deleted, "transaction")} from ${batch.file_name}`);
        reload();
      },
      { actionLabel: "Undo import" }
    );
  }

  // ---------------------------------------------------------------- numbers for the page
  const periodName = `${MONTHS[month - 1]} ${year}`;
  const previousMonthName = MONTHS[shiftMonth(year, month, -1).month - 1];
  const expenseCategories = categories.filter((c) => c.kind === "expense");
  const incomeCategories = categories.filter((c) => c.kind === "income");
  const budgetedIds = new Set(budgets.map((b) => b.category_id));
  const unbudgetedCategories = expenseCategories.filter((c) => !budgetedIds.has(c.id));
  const totalBudgeted = budgets.reduce((sum, b) => sum + b.amount, 0);

  // Transactions list: (month or all-time search) -> account -> search text -> pill.
  const searchTerm = search.trim().toLowerCase().replace(/,/g, "");
  const allTime = searchScope === "all" && searchTerm.length >= 2;
  const matchesSearch = (tx) =>
    !searchTerm ||
    [tx.description, categoryName(tx.category_id), accountName(tx.account_id), tx.amount.toFixed(2)].some((text) =>
      text.toLowerCase().replace(/,/g, "").includes(searchTerm)
    );
  const beforePills = (allTime ? allTimeResults : transactions)
    .filter((tx) => !accountFilter || String(tx.account_id) === accountFilter)
    .filter(matchesSearch);
  const pillTest = TRANSACTION_FILTERS.find(([id]) => id === typeFilter)[2];
  const shownTransactions = beforePills.filter(pillTest);

  const spendingRanked = monthly?.spending_by_category.filter((row) => row.amount > 0) ?? [];
  const budgetLines = monthly?.categories.filter((line) => line.budgeted > 0) ?? [];
  const notBudgeted = monthly?.categories.filter((line) => line.budgeted === 0 && line.actual > 0) ?? [];
  const overLines = budgetLines.filter((line) => line.actual > line.budgeted);
  const savedShare = monthly && monthly.income > 0 ? Math.round((monthly.net / monthly.income) * 100) : null;

  const activeMonths = yearly?.months.filter((m) => m.income > 0 || m.spending > 0) ?? [];
  const overspentMonths = activeMonths.filter((m) => m.net < 0);
  const yearTopCategory = yearly?.spending_by_category.find((row) => row.amount > 0);

  const previewRows = preview?.rows ?? [];
  const popupOpen = Boolean(preview || editTx || editAccount || editCategory || editBudget || confirmBox);
  const includedRows = previewRows.filter((row) => row.include);
  const previewIncome = includedRows.filter((r) => r.type === "income").reduce((s, r) => s + r.amount, 0);
  const previewSpending = includedRows.reduce(
    (s, r) => s + (r.type === "expense" ? r.amount : r.type === "refund" ? -r.amount : 0),
    0
  );
  const previewDates = previewRows.map((r) => r.date).sort();
  const previewTerm = previewSearch.trim().toLowerCase().replace(/,/g, "");
  const previewSearched = previewRows.filter(
    (row) =>
      !previewTerm ||
      [row.description, categoryName(row.category_id), row.amount.toFixed(2)].some((text) =>
        text.toLowerCase().replace(/,/g, "").includes(previewTerm)
      )
  );
  const previewTest = PREVIEW_FILTERS.find(([id]) => id === previewFilter)[2];
  const visiblePreviewRows = previewSearched.filter(previewTest);
  const visibleKeys = new Set(visiblePreviewRows.map((row) => row.key));

  // Why a row got its category, shown under the dropdown in the preview.
  function categoryHint(row) {
    if (row.type === "transfer" || row.category_id === null) return null;
    if (row.category_source === "rule") return `keyword: ${row.rule_keyword}`;
    if (row.category_source === "history") return "from your history";
    if (row.category_source === "fee") return "bank fee";
    if (row.category_source === "csv") return "from your CSV";
    if (row.category_source === "same") return `same as other ${row.keyword} rows`;
    if (row.category_source === "reversal") return `same as the purchase it refunds`;
    return null;
  }

  // ================================================================ render
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:py-10">
        {/* ---------------- HEADER + MONTH PICKER ---------------- */}
        <header className="mb-8 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-3">
            <Logo />
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Ledger</h1>
              <p className="text-sm text-slate-500">
                Signed in as <span className="font-medium text-slate-700">{user.username}</span>
                <span aria-hidden="true"> · </span>
                <button
                  type="button"
                  onClick={onLogOut}
                  className="inline-flex items-center gap-1 font-medium text-slate-700 underline-offset-2 hover:underline"
                >
                  <LogOut className="h-3.5 w-3.5" /> Log out
                </button>
              </p>
            </div>
          </div>

          {/* Month picker + theme switch, kept together on the right */}
          <div className="ml-auto flex items-center gap-2">
          <div className="flex items-center gap-0.5 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
            <button className={iconBtn} onClick={() => goToMonth(-1)} aria-label="Previous month">
              <ChevronLeft className="h-4 w-4" />
            </button>
            <select
              className="rounded-md bg-transparent px-1 py-1 text-sm font-medium focus:outline-none sm:px-2"
              value={month}
              onChange={(event) => setMonth(Number(event.target.value))}
              aria-label="Month"
            >
              {MONTHS.map((name, i) => (
                <option key={name} value={i + 1}>
                  {name}
                </option>
              ))}
            </select>
            <select
              className="rounded-md bg-transparent px-1 py-1 text-sm font-medium focus:outline-none sm:px-2"
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
              aria-label="Year"
            >
              {[...new Set([...YEARS, year])].sort().map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
            <button className={iconBtn} onClick={() => goToMonth(1)} aria-label="Next month">
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <ThemeSwitch theme={theme} onChange={onThemeChange} />
          </div>
        </header>

        {loading && <p className="text-slate-500">Loading...</p>}

        {loadError && (
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
            <span>Couldn't load your data: {loadError}</span>
            <button className={secondaryBtn} onClick={reload}>
              Try again
            </button>
          </div>
        )}

        {!loading && monthly && yearly && (
          <div className="space-y-6">
            {/* ---------------- GETTING STARTED ---------------- */}
            {accounts.length === 0 && (
              <section className="rounded-2xl border border-blue-200 bg-blue-50/60 p-5 text-sm text-slate-700 dark:border-blue-900/60 dark:bg-blue-950/30">
                <p className="font-medium text-slate-900">Start here</p>
                <ol className="mt-2 list-inside list-decimal space-y-1">
                  <li>Add your bank account under Accounts (only the last 4 digits).</li>
                  <li>Add categories under Categories, or one click for the suggested set.</li>
                  <li>Import that account's statement to bring in the month's income and spending.</li>
                  <li>Set this month's budgets, then log anything paid in cash as you go.</li>
                </ol>
              </section>
            )}

            {/* ---------------- THIS MONTH ---------------- */}
            <section className={card}>
              <p className={eyebrow}>This month</p>
              <h2 className={`${heading} mb-4`}>{periodName}</h2>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <StatTile label="Income" value={formatMoney(monthly.income)} />
                <StatTile label="Spent" value={formatMoney(monthly.spending)} />
                <StatTile
                  label={monthly.net >= 0 ? "Saved" : "Overspent"}
                  value={formatMoney(Math.abs(monthly.net))}
                  note={
                    monthly.net < 0 ? (
                      <span className="flex items-center gap-1 text-rose-700 dark:text-rose-400">
                        <TriangleAlert className="h-3.5 w-3.5" /> You spent more than came in
                      </span>
                    ) : savedShare !== null ? (
                      `${savedShare}% of income`
                    ) : null
                  }
                />
              </div>
              <p className="mt-2 text-xs text-slate-400">
                Transfers between your own accounts aren't counted as income or spending.
              </p>

              {/* One-line takeaways */}
              {(spendingRanked.length > 0 || budgetLines.length > 0) && (
                <ul className="mt-4 space-y-1 text-sm text-slate-600">
                  {spendingRanked.length > 1 && (
                    <li>
                      Most went to <span className="font-medium text-slate-900">{spendingRanked[0].category}</span> (
                      {formatMoney(spendingRanked[0].amount)}), least to{" "}
                      <span className="font-medium text-slate-900">
                        {spendingRanked[spendingRanked.length - 1].category}
                      </span>{" "}
                      ({formatMoney(spendingRanked[spendingRanked.length - 1].amount)}).
                    </li>
                  )}
                  {budgetLines.length > 0 && (
                    <li className="flex items-center gap-1.5">
                      {overLines.length === 0 ? (
                        <>
                          <CircleCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                          All {plural(budgetLines.length, "budget")} on track.
                        </>
                      ) : (
                        <>
                          <TriangleAlert className="h-4 w-4 text-rose-600 dark:text-rose-400" />
                          {budgetLines.length - overLines.length} of {plural(budgetLines.length, "budget")} on
                          track; over in {overLines.map((l) => l.category).join(", ")}.
                        </>
                      )}
                    </li>
                  )}
                </ul>
              )}

              <div className="mt-6 grid grid-cols-1 gap-8 md:grid-cols-2">
                {/* Budget vs actual */}
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-slate-900">Budget vs actual</h3>
                  {budgetLines.length === 0 ? (
                    <p className="text-sm text-slate-400">No budgets for {periodName} yet. Set some in Budgets below.</p>
                  ) : (
                    <ul className="space-y-4">
                      {budgetLines.map((line) => {
                        const over = line.actual > line.budgeted;
                        const fill = Math.min(Math.max(line.actual, 0) / line.budgeted, 1) * 100;
                        return (
                          <li key={line.category_id}>
                            <div className="flex items-baseline justify-between gap-2 text-sm">
                              <span className="truncate text-slate-700">{line.category}</span>
                              <span className="shrink-0 tabular-nums text-slate-500">
                                <span className="font-medium text-slate-900">{formatMoney(line.actual)}</span> of{" "}
                                {formatMoney(line.budgeted)}
                              </span>
                            </div>
                            <div
                              className="mt-1.5 h-2 rounded-full"
                              style={{ backgroundColor: over ? OVER_TRACK : SPENDING_TRACK }}
                            >
                              <div
                                className="h-2 rounded-full"
                                style={{ width: `${fill}%`, backgroundColor: over ? OVER_COLOR : SPENDING_COLOR }}
                              />
                            </div>
                            <p className={`mt-1 flex items-center gap-1 text-xs ${over ? "text-rose-700 dark:text-rose-400" : "text-slate-500"}`}>
                              {over ? (
                                <>
                                  <TriangleAlert className="h-3.5 w-3.5" /> Over by {formatMoney(-line.remaining)}
                                </>
                              ) : (
                                `${formatMoney(line.remaining)} left`
                              )}
                            </p>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                  {notBudgeted.length > 0 && (
                    <p className="mt-4 text-xs text-slate-500">
                      No budget set for:{" "}
                      {notBudgeted.map((line) => `${line.category} (${formatMoney(line.actual)})`).join(", ")}
                    </p>
                  )}
                </div>

                {/* Where the money went */}
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-slate-900">Where your money went</h3>
                  {spendingRanked.length === 0 ? (
                    <p className="text-sm text-slate-400">No spending in {periodName}.</p>
                  ) : (
                    <RankedBars rows={spendingRanked} color={SPENDING_COLOR} />
                  )}
                </div>
              </div>
            </section>

            {/* ---------------- TRANSACTIONS + IMPORT + BUDGETS ---------------- */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* Transactions */}
              <section className={`${card} lg:col-span-2`}>
                <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className={eyebrow}>Activity</p>
                    <h2 className={heading}>Transactions</h2>
                  </div>
                  <select
                    className={inputBox}
                    value={accountFilter}
                    onChange={(event) => setAccountFilter(event.target.value)}
                    aria-label="Filter by account"
                  >
                    <option value="">All accounts</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.nickname}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Add form */}
                <div className="grid grid-cols-1 gap-2 rounded-xl bg-slate-50 p-3 sm:grid-cols-6">
                  <select
                    className={`${input} sm:col-span-2`}
                    value={newTx.type}
                    onChange={(event) => setNewTx(withType(newTx, event.target.value))}
                    aria-label="Type"
                  >
                    {Object.entries(TYPE_LABELS).map(([value, text]) => (
                      <option key={value} value={value}>
                        {text}
                      </option>
                    ))}
                  </select>
                  <input
                    className={`${input} sm:col-span-2`}
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="Amount"
                    value={newTx.amount}
                    onChange={(event) => setNewTx({ ...newTx, amount: event.target.value })}
                  />
                  <input
                    className={`${input} sm:col-span-2`}
                    type="date"
                    value={newTx.date}
                    onChange={(event) => setNewTx({ ...newTx, date: event.target.value })}
                    aria-label="Date"
                  />
                  <input
                    className={`${input} sm:col-span-6`}
                    placeholder="Description (e.g. Lunch at Juici)"
                    value={newTx.description}
                    onChange={(event) => setNewTx({ ...newTx, description: event.target.value })}
                  />
                  <select
                    className={`${input} sm:col-span-2`}
                    value={newTx.account_id}
                    onChange={(event) => setNewTx({ ...newTx, account_id: event.target.value })}
                    aria-label="Account"
                  >
                    <option value="">Cash / no account</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.nickname}
                      </option>
                    ))}
                  </select>
                  <select
                    className={`${input} sm:col-span-2`}
                    value={newTx.type === "transfer" ? "" : newTx.category_id}
                    onChange={(event) => setNewTx({ ...newTx, category_id: event.target.value })}
                    disabled={newTx.type === "transfer"}
                    aria-label="Category"
                  >
                    <option value="">{newTx.type === "transfer" ? "No category for transfers" : "Uncategorized"}</option>
                    {categoriesFor(newTx.type).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                  <button className={`${primaryBtn} sm:col-span-2`} onClick={handleAddTransaction} disabled={busy}>
                    Add {TYPE_LABELS[newTx.type].toLowerCase()}
                  </button>
                </div>

                {/* Search + filters */}
                <div className="mt-5 flex flex-wrap items-center gap-2">
                  <SearchBox value={search} onChange={setSearch} placeholder="Search transactions" />
                  <div className="flex rounded-lg border border-slate-200 p-0.5 text-xs">
                    {[
                      ["month", MONTHS_SHORT[month - 1]],
                      ["all", "All time"],
                    ].map(([scope, label]) => (
                      <button
                        key={scope}
                        type="button"
                        aria-pressed={searchScope === scope}
                        className={`rounded-md px-2.5 py-1.5 font-medium ${searchScope === scope ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-50"}`}
                        onClick={() => setSearchScope(scope)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="mt-3">
                  <FilterChips filters={TRANSACTION_FILTERS} rows={beforePills} value={typeFilter} onChange={setTypeFilter} />
                </div>

                {/* List */}
                <p className="mt-3 text-xs text-slate-400">
                  {allTime
                    ? `${plural(shownTransactions.length, "match", "matches")} across all months`
                    : shownTransactions.length === transactions.length
                      ? `${plural(transactions.length, "transaction")} in ${periodName}`
                      : `${shownTransactions.length} of ${plural(transactions.length, "transaction")} in ${periodName}`}
                  {searchScope === "all" && searchTerm.length < 2 && " · type at least 2 letters to search all months"}
                </p>
                {shownTransactions.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-400">
                    {transactions.length === 0 && !allTime
                      ? "Nothing here yet. Add one above or import a statement."
                      : "Nothing matches. Try another pill or search."}
                  </p>
                ) : (
                  <ul className="mt-1 max-h-[34rem] divide-y divide-slate-100 overflow-y-auto pr-1">
                    {shownTransactions.map((tx) => {
                      const moneyIn = tx.type === "income" || tx.type === "refund";
                      return (
                        <li key={tx.id} className="flex items-center justify-between gap-3 py-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-slate-900">{tx.description}</p>
                            <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-slate-400">
                              <span>{formatDate(tx.date, allTime)}</span>
                              <span>·</span>
                              <span>{tx.type === "transfer" ? "Transfer" : categoryName(tx.category_id)}</span>
                              <span>·</span>
                              <span>{accountName(tx.account_id)}</span>
                              {tx.source === "statement" && (
                                <span className="flex items-center gap-0.5" title="Imported from a statement">
                                  <FileText className="h-3 w-3" /> statement
                                </span>
                              )}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            <span
                              className={`flex items-center gap-1 text-sm font-semibold tabular-nums ${
                                tx.type === "transfer"
                                  ? "text-slate-500"
                                  : moneyIn
                                    ? "text-emerald-700 dark:text-emerald-400"
                                    : "text-slate-900"
                              }`}
                            >
                              {tx.type === "transfer" && <ArrowLeftRight className="h-3.5 w-3.5" />}
                              {tx.type === "transfer" ? "" : moneyIn ? "+" : "−"}
                              {formatMoney(tx.amount)}
                              {tx.type === "refund" && (
                                <span className="text-xs font-normal text-slate-400">refund</span>
                              )}
                            </span>
                            <EditButtons
                              name={tx.description}
                              onEdit={() => openEditTransaction(tx)}
                              onDelete={() => handleDeleteTransaction(tx)}
                            />
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </section>

              {/* Right column: import + budgets */}
              <div className="space-y-6">
                <section className={card}>
                  <p className={eyebrow}>Bank</p>
                  <h2 className={`${heading} mb-4`}>Import a statement</h2>
                  {accounts.length === 0 ? (
                    <p className="text-sm text-slate-400">Add an account first (Accounts, below).</p>
                  ) : (
                    <div className="space-y-3">
                      <Field label="Account">
                        <select
                          className={input}
                          value={importAccountId}
                          onChange={(event) => setImportAccountId(event.target.value)}
                        >
                          {accounts.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.nickname} ·· {a.last_four}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Statement file (.pdf or .csv)">
                        <input
                          key={fileInputKey}
                          type="file"
                          accept=".pdf,.csv"
                          className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200"
                          onChange={(event) => setImportFile(event.target.files[0] ?? null)}
                        />
                      </Field>
                      <Field label="PDF password (only if it's locked)">
                        <input
                          className={input}
                          type="password"
                          autoComplete="off"
                          value={importPassword}
                          onChange={(event) => setImportPassword(event.target.value)}
                        />
                      </Field>
                      <button
                        className={`${primaryBtn} flex w-full items-center justify-center gap-2`}
                        onClick={handlePreview}
                        disabled={busy}
                      >
                        <Upload className="h-4 w-4" /> Preview
                      </button>
                      <p className="text-xs text-slate-400">
                        The file is read and thrown away. Nothing is saved until you review it and confirm.
                      </p>
                      <details className="text-xs text-slate-500">
                        <summary className="cursor-pointer select-none">CSV format</summary>
                        <p className="mt-1">
                          Columns <code>date,description,amount</code> (dates like 2026-09-14; negative amount =
                          money out). Optional columns: <code>type</code>, <code>category</code>.
                        </p>
                      </details>
                    </div>
                  )}

                  {imports.length > 0 && (
                    <div className="mt-5 border-t border-slate-100 pt-4">
                      <h3 className="mb-2 text-sm font-semibold text-slate-900">Recent imports</h3>
                      <ul className="divide-y divide-slate-100">
                        {(showAllImports ? imports : imports.slice(0, 3)).map((batch) => (
                          <li key={batch.id} className="flex items-center justify-between gap-2 py-2">
                            <div className="min-w-0">
                              <p className="truncate text-sm text-slate-700" title={batch.file_name}>
                                {batch.file_name}
                              </p>
                              <p className="text-xs text-slate-400">
                                {accountName(batch.account_id)} · {formatDate(batch.first_date)} –{" "}
                                {formatDate(batch.last_date)} ·{" "}
                                {batch.remaining === batch.row_count
                                  ? plural(batch.row_count, "row")
                                  : `${batch.remaining} of ${batch.row_count} rows left`}{" "}
                                · added {formatDay(batch.imported_at)}
                              </p>
                            </div>
                            <button
                              className={`${iconBtn} flex shrink-0 items-center gap-1 text-xs font-medium hover:text-rose-600 dark:hover:text-rose-400`}
                              onClick={() => handleUndoImport(batch)}
                              aria-label={`Undo import of ${batch.file_name}`}
                            >
                              <Undo2 className="h-4 w-4" /> Undo
                            </button>
                          </li>
                        ))}
                      </ul>
                      {imports.length > 3 && (
                        <button
                          className="mt-1 text-xs font-medium text-slate-500 hover:text-slate-800"
                          onClick={() => setShowAllImports(!showAllImports)}
                        >
                          {showAllImports ? "Show fewer" : `Show all ${imports.length}`}
                        </button>
                      )}
                    </div>
                  )}
                </section>

                <section className={card}>
                  <p className={eyebrow}>Plan</p>
                  <h2 className={`${heading} mb-4`}>Budgets for {MONTHS[month - 1]}</h2>
                  {budgets.length === 0 ? (
                    <p className="text-sm text-slate-400">No budgets for {periodName}.</p>
                  ) : (
                    <ul className="divide-y divide-slate-100">
                      {budgets.map((budget) => (
                        <li key={budget.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                          <span className="truncate text-slate-700">{categoryName(budget.category_id)}</span>
                          <div className="flex items-center gap-1">
                            <span className="font-medium tabular-nums text-slate-900">{formatMoney(budget.amount)}</span>
                            <EditButtons
                              name={`${categoryName(budget.category_id)} budget`}
                              onEdit={() => setEditBudget({ ...budget, amount: String(budget.amount) })}
                              onDelete={() => handleDeleteBudget(budget)}
                            />
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                  {budgets.length > 0 && (
                    <p className="mt-2 text-sm text-slate-500">
                      Total budgeted:{" "}
                      <span className="font-semibold tabular-nums text-slate-900">{formatMoney(totalBudgeted)}</span>
                    </p>
                  )}

                  {expenseCategories.length === 0 ? (
                    <p className="mt-4 text-xs text-slate-400">Add an expense category first (Categories, below).</p>
                  ) : (
                    <div className="mt-4 grid grid-cols-2 gap-2">
                      <select
                        className={`${input} col-span-2`}
                        value={newBudget.category_id}
                        onChange={(event) => setNewBudget({ ...newBudget, category_id: event.target.value })}
                        aria-label="Budget category"
                      >
                        <option value="">Choose category</option>
                        {unbudgetedCategories.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                      <input
                        className={input}
                        type="number"
                        min="0"
                        step="0.01"
                        placeholder="Amount"
                        value={newBudget.amount}
                        onChange={(event) => setNewBudget({ ...newBudget, amount: event.target.value })}
                      />
                      <button className={primaryBtn} onClick={handleAddBudget} disabled={busy}>
                        Add budget
                      </button>
                      <button className={`${secondaryBtn} col-span-2`} onClick={handleCopyBudgets} disabled={busy}>
                        Copy budgets from {previousMonthName}
                      </button>
                    </div>
                  )}
                </section>
              </div>
            </div>

            {/* ---------------- SETUP: ACCOUNTS + CATEGORIES ---------------- */}
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <section className={card}>
                <p className={eyebrow}>Setup</p>
                <h2 className={`${heading} mb-4`}>Accounts</h2>
                {accounts.length === 0 ? (
                  <p className="text-sm text-slate-400">No accounts yet.</p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {accounts.map((a) => (
                      <li key={a.id} className="flex items-center justify-between gap-2 py-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-900">{a.nickname}</p>
                          <p className="text-xs text-slate-400">
                            {a.bank_name} · {ACCOUNT_TYPE_LABELS[a.account_type]} · ·· {a.last_four} · {a.currency}
                          </p>
                        </div>
                        <EditButtons
                          name={a.nickname}
                          onEdit={() => setEditAccount({ ...a })}
                          onDelete={() => handleDeleteAccount(a)}
                        />
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <input
                    className={`${input} col-span-2`}
                    placeholder="Nickname (e.g. NCB Savings)"
                    value={newAccount.nickname}
                    onChange={(event) => setNewAccount({ ...newAccount, nickname: event.target.value })}
                  />
                  <input
                    className={input}
                    placeholder="Bank"
                    value={newAccount.bank_name}
                    onChange={(event) => setNewAccount({ ...newAccount, bank_name: event.target.value })}
                  />
                  <select
                    className={input}
                    value={newAccount.account_type}
                    onChange={(event) => setNewAccount({ ...newAccount, account_type: event.target.value })}
                    aria-label="Account type"
                  >
                    {Object.entries(ACCOUNT_TYPE_LABELS).map(([value, text]) => (
                      <option key={value} value={value}>
                        {text}
                      </option>
                    ))}
                  </select>
                  <input
                    className={input}
                    placeholder="Last 4 digits"
                    inputMode="numeric"
                    value={newAccount.last_four}
                    onChange={(event) =>
                      setNewAccount({ ...newAccount, last_four: event.target.value.replace(/\D/g, "").slice(0, 4) })
                    }
                  />
                  <button className={primaryBtn} onClick={handleAddAccount} disabled={busy}>
                    Add account
                  </button>
                </div>
                <p className="mt-2 text-xs text-slate-400">
                  Only the last 4 digits, to tell accounts apart. Never your full account number or bank login.
                </p>
              </section>

              <section className={card}>
                <p className={eyebrow}>Setup</p>
                <h2 className={`${heading} mb-4`}>Categories</h2>
                {expenseCategories.filter((c) => c.name !== "Bank Fees").length === 0 && (
                  <div className="mb-4 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-600">
                    <p>
                      Start with suggested categories (Food &amp; Dining, Groceries, Transport &amp; Gas and more), with
                      keywords for common places so imports are categorized for you.
                    </p>
                    <button className={`${secondaryBtn} mt-3`} onClick={handleAddSuggested} disabled={busy}>
                      Add suggested categories
                    </button>
                  </div>
                )}
                {categories.length === 0 ? (
                  <p className="text-sm text-slate-400">No categories yet.</p>
                ) : (
                  <div className="space-y-4">
                    {[
                      ["Spending", expenseCategories],
                      ["Income", incomeCategories],
                    ].map(([title, list]) =>
                      list.length === 0 ? null : (
                        <div key={title}>
                          <p className="text-xs font-medium text-slate-500">{title}</p>
                          <ul className="divide-y divide-slate-100">
                            {list.map((c) => (
                              <li key={c.id} className="flex items-center justify-between gap-2 py-1.5 text-sm">
                                <span className="truncate text-slate-700">
                                  {c.name}
                                  {keywordCount(c.id) > 0 && (
                                    <span className="text-xs text-slate-400"> · {plural(keywordCount(c.id), "keyword")}</span>
                                  )}
                                </span>
                                <EditButtons
                                  name={c.name}
                                  onEdit={() => {
                                    setNewKeyword("");
                                    setEditCategory({ ...c });
                                  }}
                                  onDelete={() => handleDeleteCategory(c)}
                                />
                              </li>
                            ))}
                          </ul>
                        </div>
                      )
                    )}
                  </div>
                )}
                <div className="mt-4 grid grid-cols-[minmax(0,1fr)_7.5rem_auto] gap-2">
                  <input
                    className={input}
                    placeholder="New category name"
                    value={newCategory.name}
                    onChange={(event) => setNewCategory({ ...newCategory, name: event.target.value })}
                  />
                  <select
                    className={input}
                    value={newCategory.kind}
                    onChange={(event) => setNewCategory({ ...newCategory, kind: event.target.value })}
                    aria-label="Category kind"
                  >
                    <option value="expense">Spending</option>
                    <option value="income">Income</option>
                  </select>
                  <button className={primaryBtn} onClick={handleAddCategory} disabled={busy}>
                    Add
                  </button>
                </div>
              </section>
            </div>

            {/* ---------------- THE YEAR ---------------- */}
            <section className={card}>
              <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className={eyebrow}>The year</p>
                  <h2 className={heading}>{year} report</h2>
                </div>
                <div className="flex rounded-lg border border-slate-200 p-0.5 text-sm">
                  {["chart", "table"].map((view) => (
                    <button
                      key={view}
                      className={`rounded-md px-3 py-1 capitalize ${yearView === view ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-50"}`}
                      onClick={() => setYearView(view)}
                    >
                      {view}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
                <StatTile label="Income" value={formatMoney(yearly.income)} />
                <StatTile label="Spent" value={formatMoney(yearly.spending)} />
                <StatTile label={yearly.net >= 0 ? "Saved" : "Overspent"} value={formatMoney(Math.abs(yearly.net))} />
                <StatTile
                  label="Savings rate"
                  value={yearly.savings_rate === null ? "—" : `${yearly.savings_rate}%`}
                  note={yearly.savings_rate === null ? "No income recorded yet" : "of income kept"}
                />
              </div>

              <div className="mt-6">
                {yearView === "chart" ? (
                  <YearChart months={yearly.months} selectedMonth={month} onPick={setMonth} />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                          <th className="py-2 font-medium">Month</th>
                          <th className="py-2 text-right font-medium">Income</th>
                          <th className="py-2 text-right font-medium">Spending</th>
                          <th className="py-2 text-right font-medium">Saved</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 tabular-nums">
                        {yearly.months.map((m) => (
                          <tr key={m.month}>
                            <td className="py-2 text-slate-700">{MONTHS[m.month - 1]}</td>
                            <td className="py-2 text-right">{formatMoney(m.income)}</td>
                            <td className="py-2 text-right">{formatMoney(m.spending)}</td>
                            <td className={`py-2 text-right ${m.net < 0 ? "text-rose-700 dark:text-rose-400" : ""}`}>{formatMoney(m.net)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="mt-8 grid grid-cols-1 gap-8 md:grid-cols-2">
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-slate-900">Top spending in {year}</h3>
                  {yearly.spending_by_category.filter((r) => r.amount > 0).length === 0 ? (
                    <p className="text-sm text-slate-400">No spending recorded in {year}.</p>
                  ) : (
                    <RankedBars
                      rows={yearly.spending_by_category.filter((r) => r.amount > 0).slice(0, 8)}
                      color={SPENDING_COLOR}
                    />
                  )}
                </div>

                <div>
                  <h3 className="mb-3 text-sm font-semibold text-slate-900">Habits to watch</h3>
                  {activeMonths.length === 0 ? (
                    <p className="text-sm text-slate-400">Nothing to report for {year} yet.</p>
                  ) : (
                    <ul className="space-y-3 text-sm text-slate-600">
                      {yearly.over_budget.map((row) => (
                        <li key={row.category} className="flex gap-2">
                          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400" />
                          <span>
                            <span className="font-medium text-slate-900">{row.category}</span> went over budget in{" "}
                            {row.months_over} of {plural(row.months_budgeted, "budgeted month")}.
                          </span>
                        </li>
                      ))}
                      {overspentMonths.length > 0 && (
                        <li className="flex gap-2">
                          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400" />
                          <span>
                            You spent more than came in during{" "}
                            {overspentMonths.map((m) => MONTHS_SHORT[m.month - 1]).join(", ")}.
                          </span>
                        </li>
                      )}
                      {yearTopCategory && yearly.spending > 0 && (
                        <li className="flex gap-2">
                          <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-slate-300" />
                          {yearTopCategory.category === "Uncategorized" ? (
                            <span>
                              {Math.round((yearTopCategory.amount / yearly.spending) * 100)}% of your spending is{" "}
                              <span className="font-medium text-slate-900">Uncategorized</span>. Give those
                              transactions a category to see where the money really goes.
                            </span>
                          ) : (
                            <span>
                              <span className="font-medium text-slate-900">{yearTopCategory.category}</span> is your
                              biggest cost: {Math.round((yearTopCategory.amount / yearly.spending) * 100)}% of
                              everything you spent.
                            </span>
                          )}
                        </li>
                      )}
                      {yearly.over_budget.length === 0 && overspentMonths.length === 0 && (
                        <li className="flex gap-2">
                          <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                          <span>No budget went over and no month spent more than came in.</span>
                        </li>
                      )}
                    </ul>
                  )}
                </div>
              </div>
            </section>
          </div>
        )}
      </div>

      {/* ================================================================ MODALS */}

      {/* Statement preview */}
      {preview && (
        <Modal
          wide
          title={`Review statement · ${accountName(preview.account_id)}`}
          subtitle={
            previewDates.length > 0
              ? `${plural(previewRows.length, "row")} from ${formatDate(previewDates[0], true)} to ${formatDate(previewDates[previewDates.length - 1], true)}`
              : "No rows"
          }
          onClose={() => setPreview(null)}
          footer={
            <>
              <p className="mr-auto text-sm text-slate-500 tabular-nums">
                In {formatMoney(previewIncome)} · out {formatMoney(previewSpending)}
              </p>
              <button className={secondaryBtn} onClick={() => setPreview(null)}>
                Cancel
              </button>
              <button className={primaryBtn} onClick={handleConfirmImport} disabled={busy || includedRows.length === 0}>
                Import {plural(includedRows.length, "transaction")}
              </button>
            </>
          }
        >
          {previewRows.length > 0 && previewRows.every((row) => row.flag === "duplicate") && (
            <div className="mb-4 rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-700">
              <p className="font-medium text-slate-900">
                Everything in this statement is already imported
                {[...new Set(previewRows.map((row) => row.imported_from).filter(Boolean))].length > 0 &&
                  ` (from ${[...new Set(previewRows.map((row) => row.imported_from).filter(Boolean))].join(", ")})`}
                .
              </p>
              <p className="mt-1">
                Nothing new to add, so the rows can't be ticked (that would count them twice). To import it again,
                close this, click <span className="font-medium">Undo</span> on it under Recent imports, then preview it
                again.
              </p>
            </div>
          )}

          {preview.problems.length > 0 && (
            <div className="mb-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
              <p className="flex items-center gap-1.5 font-medium">
                <TriangleAlert className="h-4 w-4" /> Check these before importing:
              </p>
              <ul className="mt-1 list-inside list-disc">
                {preview.problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="mb-3 space-y-3">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <SearchBox value={previewSearch} onChange={setPreviewSearch} placeholder="Search rows" />
              <span className="flex gap-3 text-xs">
                <button
                  className="font-medium text-slate-700 hover:underline"
                  onClick={() => setAllIncluded(true, visibleKeys)}
                >
                  Select all
                </button>
                <button
                  className="font-medium text-slate-700 hover:underline"
                  onClick={() => setAllIncluded(false, visibleKeys)}
                >
                  Select none
                </button>
              </span>
            </div>
            <FilterChips filters={PREVIEW_FILTERS} rows={previewSearched} value={previewFilter} onChange={setPreviewFilter} />
            {(previewFilter !== "all" || previewTerm) && (
              <p className="text-xs text-slate-500">
                Showing {visiblePreviewRows.length} of {previewRows.length}. Import still takes every ticked row, shown or
                not.
              </p>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                  <th className="w-8 py-2" />
                  <th className="w-20 py-2 font-medium">Date</th>
                  <th className="py-2 font-medium">Description</th>
                  <th className="w-28 py-2 font-medium">Type</th>
                  <th className="w-40 py-2 font-medium">Category</th>
                  <th className="w-28 py-2 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visiblePreviewRows.map((row) => {
                  const moneyIn = row.type === "income" || row.type === "refund";
                  return (
                    <tr key={row.key} className={row.include ? "" : "opacity-50"}>
                      <td className="py-2 align-top">
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4 accent-slate-900"
                          checked={row.include}
                          disabled={row.flag === "duplicate"}
                          onChange={(event) => updatePreviewRow(row.key, { include: event.target.checked })}
                          aria-label={`Import ${row.description}`}
                        />
                      </td>
                      <td className="py-2 align-top whitespace-nowrap text-slate-500">{formatDate(row.date)}</td>
                      <td className="py-2 pr-3 align-top">
                        <span className="text-slate-900">{row.description}</span>
                        <FlagBadge flag={row.flag} />
                        {row.note && <p className="mt-0.5 text-xs text-slate-500">{row.note}</p>}
                        {!row.note && row.reverses && (
                          <p className="mt-0.5 text-xs text-slate-500">Refund of {row.reverses}</p>
                        )}
                      </td>
                      <td className="py-2 pr-2 align-top">
                        <select
                          className={smallInput}
                          value={row.type}
                          onChange={(event) => {
                            const type = event.target.value;
                            const current = categories.find((c) => c.id === toId(row.category_id));
                            const keep = categoryFits(current, type);
                            updatePreviewRow(row.key, {
                              type,
                              category_id: keep ? row.category_id : null,
                              category_source: keep ? row.category_source : null,
                            });
                          }}
                          aria-label="Type"
                        >
                          {Object.entries(TYPE_LABELS).map(([value, text]) => (
                            <option key={value} value={value}>
                              {text}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2 pr-2 align-top">
                        <select
                          className={smallInput}
                          value={row.type === "transfer" ? "" : (row.category_id ?? "")}
                          disabled={row.type === "transfer"}
                          onChange={(event) => setPreviewCategory(row, toId(event.target.value))}
                          aria-label="Category"
                        >
                          <option value="">{row.type === "transfer" ? "—" : "Uncategorized"}</option>
                          {categoriesFor(row.type).map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                        {categoryHint(row) && (
                          <p className="mt-0.5 truncate text-[11px] text-slate-400" title={categoryHint(row)}>
                            {categoryHint(row)}
                          </p>
                        )}
                      </td>
                      <td
                        className={`py-2 text-right align-top font-medium whitespace-nowrap tabular-nums ${
                          row.type === "transfer" ? "text-slate-500" : moneyIn ? "text-emerald-700 dark:text-emerald-400" : "text-slate-900"
                        }`}
                      >
                        {row.type === "transfer" ? "" : moneyIn ? "+" : "−"}
                        {formatMoney(row.amount)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {visiblePreviewRows.length === 0 && (
            <p className="py-6 text-center text-sm text-slate-400">
              {previewFilter === "needs" && !previewTerm
                ? "Everything has a category."
                : "No rows match. Try another pill or search."}
            </p>
          )}

          {/* Missing a category while reviewing? Add it without leaving. */}
          <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 p-3">
            <span className="text-xs text-slate-500">Need a new category?</span>
            <input
              className={`${smallInputBox} w-44`}
              placeholder="Name"
              value={newCategory.name}
              onChange={(event) => setNewCategory({ ...newCategory, name: event.target.value })}
            />
            <select
              className={`${smallInputBox} w-28`}
              value={newCategory.kind}
              onChange={(event) => setNewCategory({ ...newCategory, kind: event.target.value })}
              aria-label="Category kind"
            >
              <option value="expense">Spending</option>
              <option value="income">Income</option>
            </select>
            <button className={`${secondaryBtn} px-3 py-1 text-xs`} onClick={handleAddCategory} disabled={busy}>
              Add category
            </button>
          </div>
        </Modal>
      )}

      {/* Edit transaction */}
      {editTx && (
        <Modal
          title="Edit transaction"
          subtitle={editTx.source === "statement" ? "Imported from a statement" : undefined}
          onClose={() => setEditTx(null)}
          footer={
            <>
              <button className={secondaryBtn} onClick={() => setEditTx(null)}>
                Cancel
              </button>
              <button className={primaryBtn} onClick={handleSaveTransaction} disabled={busy}>
                Save
              </button>
            </>
          }
        >
          <div className="grid grid-cols-2 gap-3">
            <Field label="Type">
              <select
                className={input}
                value={editTx.type}
                onChange={(event) => setEditTx(withType(editTx, event.target.value))}
              >
                {Object.entries(TYPE_LABELS).map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Amount">
              <input
                className={input}
                type="number"
                min="0"
                step="0.01"
                value={editTx.amount}
                onChange={(event) => setEditTx({ ...editTx, amount: event.target.value })}
              />
            </Field>
            <Field label="Description" className="col-span-2">
              <input
                className={input}
                value={editTx.description}
                onChange={(event) => setEditTx({ ...editTx, description: event.target.value })}
              />
            </Field>
            <Field label="Date">
              <input
                className={input}
                type="date"
                value={editTx.date}
                onChange={(event) => setEditTx({ ...editTx, date: event.target.value })}
              />
            </Field>
            <Field label="Account">
              <select
                className={input}
                value={editTx.account_id}
                onChange={(event) => setEditTx({ ...editTx, account_id: event.target.value })}
              >
                <option value="">Cash / no account</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.nickname}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Category" className="col-span-2">
              <select
                className={input}
                value={editTx.type === "transfer" ? "" : editTx.category_id}
                disabled={editTx.type === "transfer"}
                onChange={(event) => changeEditCategory(event.target.value)}
              >
                <option value="">{editTx.type === "transfer" ? "No category for transfers" : "Uncategorized"}</option>
                {categoriesFor(editTx.type).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
            {learnHint && learnHint.categoryId === toId(editTx.category_id) && editTx.type !== "transfer" && (
              <div className="col-span-2 space-y-2 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
                {learnHint.rule_category_id !== learnHint.categoryId && (
                  <label className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 shrink-0 accent-slate-900"
                      checked={learnHint.remember}
                      onChange={(event) => setLearnHint({ ...learnHint, remember: event.target.checked })}
                    />
                    <span>
                      Use <span className="font-medium">{categoryName(learnHint.categoryId)}</span> for{" "}
                      <span className="font-medium">{learnHint.keyword}</span> from now on
                      {learnHint.rule_category_id && (
                        <span className="text-slate-500"> (now {categoryName(learnHint.rule_category_id)})</span>
                      )}
                    </span>
                  </label>
                )}
                {learnHint.others > 0 && (
                  <label className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 shrink-0 accent-slate-900"
                      checked={learnHint.applyOthers}
                      onChange={(event) => setLearnHint({ ...learnHint, applyOthers: event.target.checked })}
                    />
                    <span>
                      Also change the other {plural(learnHint.others, "transaction")} from{" "}
                      <span className="font-medium">{learnHint.keyword}</span>
                    </span>
                  </label>
                )}
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* Edit account */}
      {editAccount && (
        <Modal
          title="Edit account"
          onClose={() => setEditAccount(null)}
          footer={
            <>
              <button className={secondaryBtn} onClick={() => setEditAccount(null)}>
                Cancel
              </button>
              <button className={primaryBtn} onClick={handleSaveAccount} disabled={busy}>
                Save
              </button>
            </>
          }
        >
          <div className="grid grid-cols-2 gap-3">
            <Field label="Nickname" className="col-span-2">
              <input
                className={input}
                value={editAccount.nickname}
                onChange={(event) => setEditAccount({ ...editAccount, nickname: event.target.value })}
              />
            </Field>
            <Field label="Bank">
              <input
                className={input}
                value={editAccount.bank_name}
                onChange={(event) => setEditAccount({ ...editAccount, bank_name: event.target.value })}
              />
            </Field>
            <Field label="Type">
              <select
                className={input}
                value={editAccount.account_type}
                onChange={(event) => setEditAccount({ ...editAccount, account_type: event.target.value })}
              >
                {Object.entries(ACCOUNT_TYPE_LABELS).map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Last 4 digits">
              <input
                className={input}
                inputMode="numeric"
                value={editAccount.last_four}
                onChange={(event) =>
                  setEditAccount({ ...editAccount, last_four: event.target.value.replace(/\D/g, "").slice(0, 4) })
                }
              />
            </Field>
          </div>
        </Modal>
      )}

      {/* Edit category */}
      {editCategory && (
        <Modal
          title="Edit category"
          onClose={() => setEditCategory(null)}
          footer={
            <>
              <button className={secondaryBtn} onClick={() => setEditCategory(null)}>
                Cancel
              </button>
              <button className={primaryBtn} onClick={handleSaveCategory} disabled={busy}>
                Save
              </button>
            </>
          }
        >
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name" className="col-span-2">
              <input
                className={input}
                value={editCategory.name}
                onChange={(event) => setEditCategory({ ...editCategory, name: event.target.value })}
              />
            </Field>
            <Field label="Kind" className="col-span-2">
              <select
                className={input}
                value={editCategory.kind}
                onChange={(event) => setEditCategory({ ...editCategory, kind: event.target.value })}
              >
                <option value="expense">Spending</option>
                <option value="income">Income</option>
              </select>
            </Field>
          </div>

          <div className="mt-5 border-t border-slate-100 pt-4">
            <p className="text-sm font-medium text-slate-900">Keywords</p>
            <p className="mt-0.5 text-xs text-slate-500">
              Imported rows whose description contains one of these get this category. Changes here save right away.
            </p>
            {rules.filter((r) => r.category_id === editCategory.id).length === 0 ? (
              <p className="mt-3 text-xs text-slate-400">No keywords yet.</p>
            ) : (
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {rules
                  .filter((r) => r.category_id === editCategory.id)
                  .map((rule) => (
                    <li
                      key={rule.id}
                      className="flex items-center gap-1 rounded-full bg-slate-100 py-0.5 pr-1 pl-2.5 text-xs font-medium text-slate-700"
                    >
                      {rule.keyword}
                      <button
                        className="rounded-full p-0.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700"
                        onClick={() => handleDeleteKeyword(rule)}
                        aria-label={`Remove keyword ${rule.keyword}`}
                        disabled={busy}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </li>
                  ))}
              </ul>
            )}
            <div className="mt-3 flex gap-2">
              <input
                className={input}
                placeholder="Add a keyword, e.g. JUICI"
                value={newKeyword}
                onChange={(event) => setNewKeyword(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && newKeyword.trim()) handleAddKeyword();
                }}
              />
              <button className={secondaryBtn} onClick={handleAddKeyword} disabled={busy || !newKeyword.trim()}>
                Add
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Edit budget */}
      {editBudget && (
        <Modal
          title={`${categoryName(editBudget.category_id)} budget`}
          subtitle={`${MONTHS[editBudget.month - 1]} ${editBudget.year}`}
          onClose={() => setEditBudget(null)}
          footer={
            <>
              <button className={secondaryBtn} onClick={() => setEditBudget(null)}>
                Cancel
              </button>
              <button className={primaryBtn} onClick={handleSaveBudget} disabled={busy}>
                Save
              </button>
            </>
          }
        >
          <Field label="Amount">
            <input
              className={input}
              type="number"
              min="0"
              step="0.01"
              value={editBudget.amount}
              onChange={(event) => setEditBudget({ ...editBudget, amount: event.target.value })}
            />
          </Field>
        </Modal>
      )}

      {/* Are you sure? */}
      {confirmBox && (
        <Modal
          title={confirmBox.title}
          onClose={() => setConfirmBox(null)}
          footer={
            <>
              <button className={secondaryBtn} onClick={() => setConfirmBox(null)}>
                Cancel
              </button>
              <button
                className={confirmBox.danger ? dangerBtn : primaryBtn}
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    await confirmBox.onConfirm();
                    setConfirmBox(null);
                  })
                }
              >
                {confirmBox.actionLabel}
              </button>
            </>
          }
        >
          <p className="text-sm text-slate-600">{confirmBox.message}</p>
        </Modal>
      )}

      {/* ================================================================ TOASTS */}
      {(actionError || notice) && (
        <div
          className={`pointer-events-none fixed inset-x-0 z-[60] flex flex-col items-center gap-2 px-4 ${
            popupOpen ? "top-4" : "bottom-4"
          }`}
        >
          {actionError && (
            <div
              role="alert"
              className="pointer-events-auto flex max-w-lg items-start gap-2 rounded-xl bg-rose-600 px-4 py-3 text-sm text-[#fff] shadow-lg"
            >
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{actionError}</span>
              <button className="ml-2 opacity-80 hover:opacity-100" onClick={() => setActionError(null)} aria-label="Dismiss">
                <X className="h-4 w-4" />
              </button>
            </div>
          )}
          {notice && (
            <div
              role="status"
              className="pointer-events-auto flex max-w-lg items-start gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm text-white shadow-lg"
            >
              <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400 dark:text-emerald-600" />
              <span>{notice}</span>
              <button className="ml-2 opacity-80 hover:opacity-100" onClick={() => setNotice(null)} aria-label="Dismiss">
                <X className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ================================================================ the top: logged in or not?
function App() {
  // undefined = still asking the backend, null = logged out, {id, username} = logged in
  const [user, setUser] = useState(undefined);
  const [loginNotice, setLoginNotice] = useState(null);
  const [startError, setStartError] = useState(null);
  const [attempt, setAttempt] = useState(0); // bump to ask again after "can't reach the server"
  const [theme, setTheme] = useState(() => readSaved("localStorage", "budget.theme") || "system");

  // Dark mode: put the "dark" class on <html> when chosen, or when "System" and
  // your computer is in dark mode (and follow it if that changes while open).
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const dark = theme === "dark" || (theme === "system" && media.matches);
      document.documentElement.classList.toggle("dark", dark);
    };
    apply();
    save("localStorage", "budget.theme", theme);
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);

  function loggedIn(me) {
    save("localStorage", "budget.lastUser", me.username);
    setLoginNotice(null);
    setUser(me);
  }

  // Who am I? The browser sends the login cookie by itself; a 401 means "not logged in".
  useEffect(() => {
    let ignore = false;
    api("/auth/me")
      .then((me) => !ignore && loggedIn(me))
      .catch((err) => {
        if (ignore) return;
        if (err.status === 401) setUser(null);
        else setStartError(err.message);
      });
    return () => {
      ignore = true;
    };
  }, [attempt]);

  // Any request that comes back 401 later (login expired, logged out in another tab)
  // brings you back here to log in again.
  useEffect(() => {
    onLoggedOut = () => {
      setLoginNotice("You've been logged out. Log in again to carry on.");
      setUser(null);
    };
    return () => {
      onLoggedOut = () => {};
    };
  }, []);

  async function logOut() {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      // Logging out should always work on screen, even if the server can't be reached.
    }
    setLoginNotice(null);
    setUser(null);
  }

  if (user === undefined) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 text-slate-500">
        {startError ? (
          <div className="text-center">
            <p className="mb-3">{startError}</p>
            <button
              className={secondaryBtn}
              onClick={() => {
                setStartError(null);
                setAttempt((a) => a + 1);
              }}
            >
              Try again
            </button>
          </div>
        ) : (
          "Loading..."
        )}
      </div>
    );
  }

  if (user === null) {
    return (
      <AuthScreen
        theme={theme}
        onThemeChange={setTheme}
        notice={loginNotice}
        onLoggedIn={loggedIn}
      />
    );
  }

  // key: a different person logging in gets a completely fresh app, nothing left over.
  return <BudgetApp key={user.id} user={user} theme={theme} onThemeChange={setTheme} onLogOut={logOut} />;
}

export default App;
