import { useEffect, useState } from "react";
import {
  ArrowLeftRight,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  FileText,
  Pencil,
  Trash2,
  TriangleAlert,
  Upload,
  X,
} from "lucide-react";

const BASE_URL = "http://127.0.0.1:8000";

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
  "rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-500 disabled:cursor-not-allowed disabled:bg-rose-300";
const iconBtn =
  "rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700";

// Chart colors. Each color always means the same thing everywhere on the page.
// (Blue + orange is a pair colorblind readers can still tell apart.)
const INCOME_COLOR = "#2a78d6";
const SPENDING_COLOR = "#eb6834";
const SPENDING_TRACK = "#fbe2d7"; // light step of the spending orange, for meter backgrounds
const OVER_COLOR = "#d03b3b"; // only for "over budget", always shown with an icon + words
const OVER_TRACK = "#f6d8d8";
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

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
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
  if (!response.ok) throw new Error(readError(data, response.status));
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
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
        className={`${iconBtn} hover:text-rose-600`}
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

const FLAG_STYLES = {
  duplicate: { text: "Already imported", className: "bg-slate-100 text-slate-600" },
  match: { text: "Already logged", className: "bg-blue-50 text-blue-700" },
  review: { text: "Check type", className: "bg-amber-50 text-amber-800" },
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

function App() {
  // --- Which month you're looking at ---
  const [year, setYear] = useState(CURRENT_YEAR);
  const [month, setMonth] = useState(CURRENT_MONTH);

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
  const [confirmBox, setConfirmBox] = useState(null); // { message, onConfirm }

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

  // --- Transactions list filter ---
  const [accountFilter, setAccountFilter] = useState("");

  // --- Statement import ---
  const [importAccountId, setImportAccountId] = useState("");
  const [importFile, setImportFile] = useState(null);
  const [importPassword, setImportPassword] = useState("");
  const [fileInputKey, setFileInputKey] = useState(0); // changing a key resets the <input type="file">
  const [preview, setPreview] = useState(null); // { account_id, rows, problems }

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
    ])
      .then(([accountList, categoryList, txList, budgetList, monthSummary, yearSummary]) => {
        if (ignore) return;
        setAccounts(accountList);
        setCategories(categoryList);
        setTransactions(txList);
        setBudgets(budgetList);
        setMonthly(monthSummary);
        setYearly(yearSummary);
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

  function askConfirm(message, onConfirm) {
    setConfirmBox({ message, onConfirm });
  }

  function goToMonth(delta) {
    const next = shiftMonth(year, month, delta);
    setYear(next.year);
    setMonth(next.month);
  }

  // --- Lookups ---
  function categoryName(id) {
    return categories.find((c) => c.id === id)?.name ?? "Uncategorized";
  }
  function accountName(id) {
    return accounts.find((a) => a.id === id)?.nickname ?? "No account";
  }
  function categoriesFor(type) {
    return categories.filter((c) => categoryFits(c, type));
  }

  // --- Accounts ---
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
      `Delete "${category.name}"? Its budgets are deleted too. Its transactions are kept and become Uncategorized.`,
      async () => {
        await api(`/categories/${category.id}`, { method: "DELETE" });
        reload();
      }
    );
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

  function handleAddTransaction() {
    run(async () => {
      const created = await api("/transaction/", { method: "POST", body: transactionBody(newTx) });
      // Keep type and account: you often log several of the same kind in a row.
      setNewTx({ ...emptyTransaction(), type: newTx.type, account_id: newTx.account_id });
      const [y, m] = created.date.split("-").map(Number);
      if (y !== year || m !== month) {
        setNotice(`Saved. It's dated ${formatDate(created.date, true)}, so it's under ${MONTHS[m - 1]} ${y}.`);
      }
      reload();
    });
  }

  function handleSaveTransaction() {
    run(async () => {
      await api(`/transaction/${editTx.id}`, { method: "PATCH", body: transactionBody(editTx) });
      setEditTx(null);
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
    setEditTx({
      ...tx,
      amount: String(tx.amount),
      account_id: tx.account_id ?? "",
      category_id: tx.category_id ?? "",
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

  function setAllIncluded(include) {
    setPreview((current) => ({
      ...current,
      rows: current.rows.map((row) => (row.flag === "duplicate" ? row : { ...row, include })),
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
        body: { account_id: preview.account_id, rows },
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

  // ---------------------------------------------------------------- numbers for the page
  const periodName = `${MONTHS[month - 1]} ${year}`;
  const previousMonthName = MONTHS[shiftMonth(year, month, -1).month - 1];
  const expenseCategories = categories.filter((c) => c.kind === "expense");
  const incomeCategories = categories.filter((c) => c.kind === "income");
  const budgetedIds = new Set(budgets.map((b) => b.category_id));
  const unbudgetedCategories = expenseCategories.filter((c) => !budgetedIds.has(c.id));
  const totalBudgeted = budgets.reduce((sum, b) => sum + b.amount, 0);

  const shownTransactions = accountFilter
    ? transactions.filter((tx) => String(tx.account_id) === accountFilter)
    : transactions;

  const spendingRanked = monthly?.spending_by_category.filter((row) => row.amount > 0) ?? [];
  const budgetLines = monthly?.categories.filter((line) => line.budgeted > 0) ?? [];
  const notBudgeted = monthly?.categories.filter((line) => line.budgeted === 0 && line.actual > 0) ?? [];
  const overLines = budgetLines.filter((line) => line.actual > line.budgeted);
  const savedShare = monthly && monthly.income > 0 ? Math.round((monthly.net / monthly.income) * 100) : null;

  const activeMonths = yearly?.months.filter((m) => m.income > 0 || m.spending > 0) ?? [];
  const overspentMonths = activeMonths.filter((m) => m.net < 0);
  const yearTopCategory = yearly?.spending_by_category.find((row) => row.amount > 0);

  const previewRows = preview?.rows ?? [];
  const includedRows = previewRows.filter((row) => row.include);
  const previewIncome = includedRows.filter((r) => r.type === "income").reduce((s, r) => s + r.amount, 0);
  const previewSpending = includedRows.reduce(
    (s, r) => s + (r.type === "expense" ? r.amount : r.type === "refund" ? -r.amount : 0),
    0
  );
  const previewDates = previewRows.map((r) => r.date).sort();
  const flagCount = (flag) => previewRows.filter((r) => r.flag === flag).length;

  // ================================================================ render
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:py-10">
        {/* ---------------- HEADER + MONTH PICKER ---------------- */}
        <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-lg font-semibold text-white">
              $
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">My Budget</h1>
              <p className="text-sm text-slate-500">Income, spending and budgets, month by month</p>
            </div>
          </div>

          <div className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
            <button className={iconBtn} onClick={() => goToMonth(-1)} aria-label="Previous month">
              <ChevronLeft className="h-4 w-4" />
            </button>
            <select
              className="rounded-md bg-transparent px-2 py-1 text-sm font-medium focus:outline-none"
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
              className="rounded-md bg-transparent px-2 py-1 text-sm font-medium focus:outline-none"
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
        </header>

        {loading && <p className="text-slate-500">Loading...</p>}

        {loadError && (
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">
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
              <section className="rounded-2xl border border-blue-200 bg-blue-50/60 p-5 text-sm text-slate-700">
                <p className="font-medium text-slate-900">Start here</p>
                <ol className="mt-2 list-inside list-decimal space-y-1">
                  <li>Add your bank account under Accounts (only the last 4 digits).</li>
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
                      <span className="flex items-center gap-1 text-rose-700">
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
                          <CircleCheck className="h-4 w-4 text-emerald-600" />
                          All {plural(budgetLines.length, "budget")} on track.
                        </>
                      ) : (
                        <>
                          <TriangleAlert className="h-4 w-4 text-rose-600" />
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
                            <p className={`mt-1 flex items-center gap-1 text-xs ${over ? "text-rose-700" : "text-slate-500"}`}>
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

                {/* List */}
                <p className="mt-5 text-xs text-slate-400">
                  {plural(shownTransactions.length, "transaction")} in {periodName}
                </p>
                {shownTransactions.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-400">
                    Nothing here yet. Add one above or import a statement.
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
                              <span>{formatDate(tx.date)}</span>
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
                                    ? "text-emerald-700"
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
                                <span className="truncate text-slate-700">{c.name}</span>
                                <EditButtons
                                  name={c.name}
                                  onEdit={() => setEditCategory({ ...c })}
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
                            <td className={`py-2 text-right ${m.net < 0 ? "text-rose-700" : ""}`}>{formatMoney(m.net)}</td>
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
                          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
                          <span>
                            <span className="font-medium text-slate-900">{row.category}</span> went over budget in{" "}
                            {row.months_over} of {plural(row.months_budgeted, "budgeted month")}.
                          </span>
                        </li>
                      ))}
                      {overspentMonths.length > 0 && (
                        <li className="flex gap-2">
                          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
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
                          <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
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
          {preview.problems.length > 0 && (
            <div className="mb-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
              <p className="flex items-center gap-1.5 font-medium">
                <TriangleAlert className="h-4 w-4" /> Some numbers didn't add up. Check these against the PDF:
              </p>
              <ul className="mt-1 list-inside list-disc">
                {preview.problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-500">
            {["duplicate", "match", "review"].map((flag) =>
              flagCount(flag) > 0 ? (
                <span key={flag}>
                  <FlagBadge flag={flag} /> {flagCount(flag)}
                </span>
              ) : null
            )}
            <span className="ml-auto flex gap-3">
              <button className="font-medium text-slate-700 hover:underline" onClick={() => setAllIncluded(true)}>
                Select all
              </button>
              <button className="font-medium text-slate-700 hover:underline" onClick={() => setAllIncluded(false)}>
                Select none
              </button>
            </span>
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
                {previewRows.map((row) => {
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
                      </td>
                      <td className="py-2 pr-2 align-top">
                        <select
                          className={smallInput}
                          value={row.type}
                          onChange={(event) => {
                            const type = event.target.value;
                            const current = categories.find((c) => c.id === toId(row.category_id));
                            updatePreviewRow(row.key, {
                              type,
                              category_id: categoryFits(current, type) ? row.category_id : null,
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
                          onChange={(event) => updatePreviewRow(row.key, { category_id: toId(event.target.value) })}
                          aria-label="Category"
                        >
                          <option value="">{row.type === "transfer" ? "—" : "Uncategorized"}</option>
                          {categoriesFor(row.type).map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td
                        className={`py-2 text-right align-top font-medium whitespace-nowrap tabular-nums ${
                          row.type === "transfer" ? "text-slate-500" : moneyIn ? "text-emerald-700" : "text-slate-900"
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
                onChange={(event) => setEditTx({ ...editTx, category_id: event.target.value })}
              >
                <option value="">{editTx.type === "transfer" ? "No category for transfers" : "Uncategorized"}</option>
                {categoriesFor(editTx.type).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
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
          title="Are you sure?"
          onClose={() => setConfirmBox(null)}
          footer={
            <>
              <button className={secondaryBtn} onClick={() => setConfirmBox(null)}>
                Cancel
              </button>
              <button
                className={dangerBtn}
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    await confirmBox.onConfirm();
                    setConfirmBox(null);
                  })
                }
              >
                Delete
              </button>
            </>
          }
        >
          <p className="text-sm text-slate-600">{confirmBox.message}</p>
        </Modal>
      )}

      {/* ================================================================ TOASTS */}
      {(actionError || notice) && (
        <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4">
          {actionError && (
            <div
              role="alert"
              className="pointer-events-auto flex max-w-lg items-start gap-2 rounded-xl bg-rose-600 px-4 py-3 text-sm text-white shadow-lg"
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
              <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
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

export default App;
