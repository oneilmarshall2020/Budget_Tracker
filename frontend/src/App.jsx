import { useState, useEffect } from "react";

const BASE_URL = "http://127.0.0.1:8000";

// Reused class strings, pulled out so the markup below stays readable.
const card = "rounded-2xl border border-slate-200 bg-white p-6 shadow-sm";
const heading = "text-lg font-semibold text-slate-900";
const eyebrow = "text-xs font-medium uppercase tracking-wide text-slate-400";
const input =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/10";
const primaryBtn =
  "rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";

function formatMoney(n) {
  if (n === null || n === undefined) return "$0.00";
  return `$${Number(n).toFixed(2)}`;
}

function App() {
  // --- Data loaded from the backend ---
  const [categories, setCategories] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [budgets, setBudgets] = useState([]);

  // --- Loading / error state for the initial load ---
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // --- Category form ---
  const [newCategoryName, setNewCategoryName] = useState("");

  // --- Expense form ---
  const [expAmount, setExpAmount] = useState("");
  const [expDate, setExpDate] = useState("");
  const [expDescription, setExpDescription] = useState("");
  const [expCategoryId, setExpCategoryId] = useState("");

  // --- Budget form ---
  const [budCategoryId, setBudCategoryId] = useState("");
  const [budYear, setBudYear] = useState("2026");
  const [budMonth, setBudMonth] = useState("1");
  const [budAmount, setBudAmount] = useState("");

  // --- Monthly summary ---
  const [sumYear, setSumYear] = useState("2026");
  const [sumMonth, setSumMonth] = useState("1");
  const [monthlyResult, setMonthlyResult] = useState(null);

  // --- Yearly summary ---
  const [yearlyYear, setYearlyYear] = useState("2026");
  const [yearlyResult, setYearlyResult] = useState(null);

  // --- Load everything once, when the app first renders ---
  useEffect(() => {
    fetch(`${BASE_URL}/categories/`)
      .then((response) => {
        if (!response.ok) throw new Error("Failed to load categories");
        return response.json();
      })
      .then((data) => setCategories(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));

    fetch(`${BASE_URL}/expense/`)
      .then((response) => response.json())
      .then((data) => setExpenses(data))
      .catch((err) => console.error(err));

    fetch(`${BASE_URL}/budget/`)
      .then((response) => response.json())
      .then((data) => setBudgets(data))
      .catch((err) => console.error(err));
  }, []);

  function getCategoryName(categoryId) {
    const match = categories.find((category) => category.id === categoryId);
    return match ? match.name : "Uncategorized";
  }

function handleAddCategory() {
  if (newCategoryName.trim() === "") {
    return;
  }

  fetch(`${BASE_URL}/categories/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: newCategoryName }),
  })
    .then((response) => response.json())
    .then((created) => {
      setCategories([...categories, created]);
      setNewCategoryName("");
    })
    .catch((err) => console.error(err));
}

function handleAddExpense() {
  if (
    expAmount === "" ||
    expDate === "" ||
    expDescription.trim() === ""
  ) {
    return;
  }

  fetch(`${BASE_URL}/expense/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      amount: Number(expAmount),
      date: expDate,
      description: expDescription,
      category_id: expCategoryId ? Number(expCategoryId) : null,
    }),
  })
    .then((response) => response.json())
    .then((created) => {
      setExpenses([...expenses, created]);
      setExpAmount("");
      setExpDate("");
      setExpDescription("");
      setExpCategoryId("");
    })
    .catch((err) => console.error(err));
}

function handleAddBudget() {
  if (
    budCategoryId === "" ||
    budAmount === "" ||
    budYear === "" ||
    budMonth === ""
  ) {
    return;
  }

  fetch(`${BASE_URL}/budget/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      category_id: Number(budCategoryId),
      year: Number(budYear),
      month: Number(budMonth),
      amount: Number(budAmount),
    }),
  })
    .then((response) => response.json())
    .then((created) => {
      setBudgets([...budgets, created]);
      setBudAmount("");
    })
    .catch((err) => console.error(err));
}
  function handleGetMonthly() {
    fetch(`${BASE_URL}/summary/${sumYear}/${sumMonth}`)
      .then((response) => response.json())
      .then((data) => setMonthlyResult(data))
      .catch((err) => console.error(err));
  }

  function handleGetYearly() {
    fetch(`${BASE_URL}/summary/${yearlyYear}`)
      .then((response) => response.json())
      .then((data) => setYearlyResult(data))
      .catch((err) => console.error(err));
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-5xl px-4 py-10">
        {/* ---------------- HEADER ---------------- */}
        <header className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-lg font-semibold text-white">
            $
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">My Budget</h1>
            <p className="text-sm text-slate-500">
              Track spending against your monthly plan
            </p>
          </div>
        </header>

        {loading && <p className="text-slate-500">Loading...</p>}
        {error && (
          <p className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">
            Something went wrong: {error}
          </p>
        )}

        {!loading && !error && (
          <div className="space-y-6">
            {/* ---------------- SETUP ROW: CATEGORIES + BUDGETS ---------------- */}
            <div className="grid gap-6 md:grid-cols-2">
              {/* Categories */}
              <section className={card}>
                <p className={eyebrow}>Setup</p>
                <h2 className={`${heading} mb-4`}>Categories</h2>

                {categories.length === 0 ? (
                  <p className="text-sm text-slate-400">No categories yet.</p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {categories.map((category) => (
                      <li
                        key={category.id}
                        className="py-2 text-sm text-slate-700"
                      >
                        {category.name}
                      </li>
                    ))}
                  </ul>
                )}

                <div className="mt-4 flex gap-2">
                  <input
                    className={input}
                    value={newCategoryName}
                    onChange={(event) => setNewCategoryName(event.target.value)}
                    placeholder="New category name"
                  />
                  <button className={primaryBtn} onClick={handleAddCategory}>
                    Add
                  </button>
                </div>
              </section>

              {/* Budgets */}
              <section className={card}>
                <p className={eyebrow}>Setup</p>
                <h2 className={`${heading} mb-4`}>Budgets</h2>

                {budgets.length === 0 ? (
                  <p className="text-sm text-slate-400">No budgets set.</p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {budgets.map((budget) => (
                      <li
                        key={budget.id}
                        className="flex items-center justify-between py-2 text-sm"
                      >
                        <span className="text-slate-700">
                          {getCategoryName(budget.category_id)}
                          <span className="text-slate-400">
                            {" "}
                            · {budget.month}/{budget.year}
                          </span>
                        </span>
                        <span className="font-medium text-slate-900">
                          {formatMoney(budget.amount)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}

                <div className="mt-4 grid gap-2 sm:grid-cols-2">
                  <select
                    className={input}
                    value={budCategoryId}
                    onChange={(event) => setBudCategoryId(event.target.value)}
                  >
                    <option value="">Choose category</option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                  <input
                    className={input}
                    value={budAmount}
                    onChange={(event) => setBudAmount(event.target.value)}
                    placeholder="Amount"
                    type="number"
                  />
                  <input
                    className={input}
                    value={budYear}
                    onChange={(event) => setBudYear(event.target.value)}
                    placeholder="Year"
                    type="number"
                  />
                  <input
                    className={input}
                    value={budMonth}
                    onChange={(event) => setBudMonth(event.target.value)}
                    placeholder="Month"
                    type="number"
                  />
                </div>
                <button
                  className={`${primaryBtn} mt-2 w-full`}
                  onClick={handleAddBudget}
                >
                  Add budget
                </button>
              </section>
            </div>

            {/* ---------------- EXPENSES ---------------- */}
            <section className={card}>
              <p className={eyebrow}>Activity</p>
              <h2 className={`${heading} mb-4`}>Expenses</h2>

              {expenses.length === 0 ? (
                <p className="text-sm text-slate-400">No expenses logged.</p>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {expenses.map((expense) => (
                    <li
                      key={expense.id}
                      className="flex items-center justify-between py-3"
                    >
                      <div>
                        <p className="text-sm font-medium text-slate-900">
                          {expense.description}
                        </p>
                        <p className="text-xs text-slate-400">
                          {expense.date} · {getCategoryName(expense.category_id)}
                        </p>
                      </div>
                      <span className="text-sm font-semibold text-slate-900">
                        {formatMoney(expense.amount)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <input
                  className={input}
                  value={expAmount}
                  onChange={(event) => setExpAmount(event.target.value)}
                  placeholder="Amount"
                  type="number"
                />
                <input
                  className={input}
                  value={expDate}
                  onChange={(event) => setExpDate(event.target.value)}
                  type="date"
                />
                <input
                  className={input}
                  value={expDescription}
                  onChange={(event) => setExpDescription(event.target.value)}
                  placeholder="Description"
                />
                <select
                  className={input}
                  value={expCategoryId}
                  onChange={(event) => setExpCategoryId(event.target.value)}
                >
                  <option value="">No category</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </div>
              <button
                className={`${primaryBtn} mt-2`}
                onClick={handleAddExpense}
              >
                Add expense
              </button>
            </section>

            {/* ---------------- INSIGHTS ROW: MONTHLY + YEARLY ---------------- */}
            <div className="grid gap-6 md:grid-cols-2">
              {/* Monthly summary */}
              <section className={card}>
                <p className={eyebrow}>Insights</p>
                <h2 className={`${heading} mb-4`}>Monthly summary</h2>

                <div className="flex gap-2">
                  <input
                    className={input}
                    value={sumYear}
                    onChange={(event) => setSumYear(event.target.value)}
                    placeholder="Year"
                    type="number"
                  />
                  <input
                    className={input}
                    value={sumMonth}
                    onChange={(event) => setSumMonth(event.target.value)}
                    placeholder="Month"
                    type="number"
                  />
                  <button className={primaryBtn} onClick={handleGetMonthly}>
                    Go
                  </button>
                </div>

                {monthlyResult && (
                  <div className="mt-5">
                    <p className={eyebrow}>
                      {monthlyResult.month}/{monthlyResult.year}
                    </p>
                    <ul className="mt-2 divide-y divide-slate-100">
                      {monthlyResult.categories.map((line) => (
                        <li
                          key={line.category}
                          className="flex items-center justify-between py-2 text-sm"
                        >
                          <span className="text-slate-700">{line.category}</span>
                          <span className="text-slate-500">
                            {formatMoney(line.actual)} /{" "}
                            {formatMoney(line.budgeted)}
                            <span
                              className={`ml-2 font-medium ${
                                line.remaining >= 0
                                  ? "text-emerald-600"
                                  : "text-rose-600"
                              }`}
                            >
                              {formatMoney(line.remaining)}
                            </span>
                          </span>
                        </li>
                      ))}
                    </ul>
                    <div className="mt-4 rounded-xl bg-slate-50 p-4">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-500">Total spent</span>
                        <span className="font-semibold">
                          {formatMoney(monthlyResult.total_actual)} /{" "}
                          {formatMoney(monthlyResult.total_budgeted)}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center justify-between text-sm">
                        <span className="text-slate-500">Remaining</span>
                        <span
                          className={`font-semibold ${
                            monthlyResult.total_remaining >= 0
                              ? "text-emerald-600"
                              : "text-rose-600"
                          }`}
                        >
                          {formatMoney(monthlyResult.total_remaining)}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </section>

              {/* Yearly summary */}
              <section className={card}>
                <p className={eyebrow}>Insights</p>
                <h2 className={`${heading} mb-4`}>Yearly summary</h2>

                <div className="flex gap-2">
                  <input
                    className={input}
                    value={yearlyYear}
                    onChange={(event) => setYearlyYear(event.target.value)}
                    placeholder="Year"
                    type="number"
                  />
                  <button className={primaryBtn} onClick={handleGetYearly}>
                    Go
                  </button>
                </div>

                {yearlyResult && (
                  <div className="mt-5 rounded-xl bg-slate-50 p-4">
                    <p className={eyebrow}>{yearlyResult.year}</p>
                    <div className="mt-2 flex items-center justify-between text-sm">
                      <span className="text-slate-500">Total spent</span>
                      <span className="font-semibold">
                        {formatMoney(yearlyResult.total_actual)} /{" "}
                        {formatMoney(yearlyResult.total_budgeted)}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-sm">
                      <span className="text-slate-500">Remaining</span>
                      <span
                        className={`font-semibold ${
                          yearlyResult.total_remaining >= 0
                            ? "text-emerald-600"
                            : "text-rose-600"
                        }`}
                      >
                        {formatMoney(yearlyResult.total_remaining)}
                      </span>
                    </div>
                  </div>
                )}
              </section>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
