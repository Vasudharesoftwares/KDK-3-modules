import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertCircle, CalendarDays, CheckCircle2, Clock3,
  Factory, History, LoaderCircle, Pencil, Plus, RefreshCw, Save,
  UserRound, X
} from "lucide-react";

const API = (
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8777/api/v1"
).replace(/\/$/, "");

const toIndiaDateTimeLocal = value => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("sv-SE", {
    timeZone: "Asia/Kolkata",
    hour12: false
  }).replace(" ", "T").slice(0, 16);
};

const indiaDateTimeISO = value => {
  if (!value) return "";
  return `${value}:00+05:30`;
};

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const number = value =>
  Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 3 });

const statusLabel = value => ({
  draft: "Draft",
  scheduled: "Scheduled",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled"
}[value] || value);

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };

  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response;

  try {
    response = await fetch(API + path, {
      ...options,
      headers
    });
  } catch (error) {
    throw new Error(
      `Cannot connect to Planning API at ${API}. ${error?.message || ""}`
    );
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(
      Array.isArray(detail)
        ? detail.map(item => item.msg).join("; ")
        : detail || `Request failed (HTTP ${response.status})`
    );
  }

  return data;
}

function StatusPill({ status }) {
  return (
    <span className={`planning-status planning-status-${status}`}>
      {statusLabel(status)}
    </span>
  );
}

function Field({ label, children }) {
  return (
    <label className="planning-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export default function PlanningPage() {
  const [dashboard, setDashboard] = useState(null);
  const [lookups, setLookups] = useState({
    eligible_orders: [],
    saved_machines: [],
    saved_workers: [],
    machines: [],
    shifts: [],
    workers: [],
    timezone: "Asia/Kolkata"
  });
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [expandedHistory, setExpandedHistory] = useState({});
  const [histories, setHistories] = useState({});
  const [actualInputs, setActualInputs] = useState({});
  const [statusInputs, setStatusInputs] = useState({});
  const [showCompletedArchive, setShowCompletedArchive] = useState(false);
  const [collapsedPlans, setCollapsedPlans] = useState({});
  const [editingPlanId, setEditingPlanId] = useState(null);
  const [editForm, setEditForm] = useState({});

  const [createForm, setCreateForm] = useState({
    sales_order_line_id: "",
    planned_qty: "",
    planned_start_date: today(),
    target_end_date: "",
    notes: ""
  });

  const [allocationInputs, setAllocationInputs] = useState({});

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [dash, lookupData, planData] = await Promise.all([
        request("/planning/dashboard"),
        request("/planning/lookups"),
        request("/planning/plans")
      ]);

      setDashboard(dash);
      setLookups(lookupData);
      setPlans(Array.isArray(planData) ? planData : []);

      // Always synchronize editable forms with the latest saved API values.
      // A page refresh or successful save must never leave stale form values.
      setActualInputs(
        Object.fromEntries(
          (Array.isArray(planData) ? planData : [])
            .map(plan => [plan.id, String(plan.actual_qty ?? 0)])
        )
      );

      setStatusInputs(
        Object.fromEntries(
          (Array.isArray(planData) ? planData : [])
            .map(plan => [plan.id, plan.status])
        )
      );

      setAllocationInputs(
        Object.fromEntries(
          (Array.isArray(planData) ? planData : []).map(plan => {
            const existingAllocations = Array.isArray(plan.allocations)
              ? plan.allocations
              : [];
            const latestAllocation = existingAllocations.length
              ? existingAllocations[existingAllocations.length - 1]
              : null;

            return [plan.id, {
              machine_name: latestAllocation?.machine_name || "",
              worker_name: latestAllocation?.worker_name || "",
              starts_at: toIndiaDateTimeLocal(latestAllocation?.starts_at),
              ends_at: toIndiaDateTimeLocal(latestAllocation?.ends_at)
            }];
          })
        )
      );
    } catch (err) {
      setError(err.message || "Could not load planning data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const orderLines = useMemo(() => {
    const rows = [];

    for (const order of lookups.eligible_orders || []) {
      for (const line of order.lines || []) {
        rows.push({
          ...line,
          order_number: order.order_number,
          customer_name: order.customer_name,
          order_status: order.status
        });
      }
    }

    return rows;
  }, [lookups]);

  const selectedLine = orderLines.find(
    line => String(line.id) === String(createForm.sales_order_line_id)
  );

  const updateCreate = (key, value) => {
    setCreateForm(previous => ({ ...previous, [key]: value }));
  };

  const updateAllocation = (planId, key, value) => {
    setAllocationInputs(previous => ({
      ...previous,
      [planId]: {
        ...(previous[planId] || {}),
        [key]: value
      }
    }));
  };

  function startEditingPlan(plan) {
    setError("");
    setNotice("");
    setCollapsedPlans(previous => ({ ...previous, [plan.id]: false }));
    setEditingPlanId(plan.id);
    setEditForm({
      sales_order_line_id: String(plan.sales_order_line_id),
      planned_qty: String(plan.planned_qty ?? ""),
      planned_start_date: String(plan.planned_start_date || ""),
      target_end_date: String(plan.target_end_date || ""),
      notes: plan.notes || ""
    });
  }

  function updateEdit(key, value) {
    setEditForm(previous => ({ ...previous, [key]: value }));
  }

  async function savePlanEdits(event, plan) {
    event.preventDefault();

    if (!editForm.sales_order_line_id || !editForm.planned_qty ||
        !editForm.planned_start_date) {
      setError("Select an order line and enter planned quantity and start date.");
      return;
    }

    if (!Number.isFinite(Number(editForm.planned_qty)) ||
        Number(editForm.planned_qty) <= 0) {
      setError("Planned quantity must be greater than zero.");
      return;
    }

    if (editForm.target_end_date &&
        editForm.target_end_date < editForm.planned_start_date) {
      setError("Target end date cannot be before the start date.");
      return;
    }

    setSaving(true);
    setError("");
    setNotice("");

    try {
      await request(`/planning/plans/${plan.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          sales_order_line_id: Number(editForm.sales_order_line_id),
          planned_qty: String(editForm.planned_qty),
          planned_start_date: editForm.planned_start_date,
          target_end_date: editForm.target_end_date || null,
          notes: editForm.notes.trim() || null
        })
      });

      setEditingPlanId(null);
      setEditForm({});
      setNotice(`Plan ${plan.plan_number} updated successfully.`);
      await loadData();
    } catch (err) {
      setError(err.message || "Could not update the production plan.");
    } finally {
      setSaving(false);
    }
  }

  async function createPlan(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");

    try {
      const payload = {
        sales_order_line_id: Number(createForm.sales_order_line_id),
        planned_qty: createForm.planned_qty,
        planned_start_date: createForm.planned_start_date,
        target_end_date: createForm.target_end_date || null,
        notes: createForm.notes.trim() || null
      };

      await request("/planning/plans", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      setShowCreate(false);
      setCreateForm({
        sales_order_line_id: "",
        planned_qty: "",
        planned_start_date: today(),
        target_end_date: "",
        notes: ""
      });
      setNotice("Production plan created successfully.");
      await loadData();
    } catch (err) {
      setError(err.message || "Could not create the plan.");
    } finally {
      setSaving(false);
    }
  }

  async function addAllocation(event, plan) {
    event.preventDefault();
    const form = allocationInputs[plan.id] || {};

    if (
      !form.machine_name?.trim() ||
      !form.worker_name?.trim() ||
      !form.starts_at ||
      !form.ends_at
    ) {
      setError("Enter machine name, worker name, start date/time and end date/time.");
      return;
    }

    if (new Date(form.ends_at) <= new Date(form.starts_at)) {
      setError("End date and time must be after the start date and time.");
      return;
    }

    setSaving(true);
    setError("");
    setNotice("");

    try {
      const payload = {
        machine_name: form.machine_name.trim(),
        worker_name: form.worker_name.trim(),
        starts_at: indiaDateTimeISO(form.starts_at),
        ends_at: indiaDateTimeISO(form.ends_at)
      };

      await request(`/planning/plans/${plan.id}/allocations`, {
        method: "POST",
        body: JSON.stringify(payload)
      });

      setNotice(`Assignment saved for ${plan.plan_number}.`);
      await loadData();
    } catch (err) {
      setError(err.message || "Could not save the assignment.");
    } finally {
      setSaving(false);
    }
  }

  async function updateActual(plan) {
    const value = actualInputs[plan.id];

    if (value === undefined || value === "" || !Number.isFinite(Number(value)) || Number(value) < 0) {
      setError("Enter a valid actual production quantity (zero or greater).");
      return;
    }

    setSaving(true);
    setError("");
    setNotice("");

    try {
      await request(`/planning/plans/${plan.id}/actual`, {
        method: "PATCH",
        body: JSON.stringify({
          actual_qty: String(value),
          reason: "Updated from Planning & Scheduling screen"
        })
      });

      setNotice(`Actual output updated for ${plan.plan_number}.`);
      await loadData();
    } catch (err) {
      setError(err.message || "Could not update actual output.");
    } finally {
      setSaving(false);
    }
  }

  async function updateStatus(plan) {
    const status = statusInputs[plan.id];

    if (!status || status === plan.status) return;

    setSaving(true);
    setError("");
    setNotice("");

    try {
      await request(`/planning/plans/${plan.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({
          status,
          reason: "Status updated from Planning & Scheduling screen"
        })
      });

      setNotice(`Status updated for ${plan.plan_number}.`);
      await loadData();
    } catch (err) {
      setError(err.message || "Could not update plan status.");
      setStatusInputs(previous => ({
        ...previous,
        [plan.id]: plan.status
      }));
    } finally {
      setSaving(false);
    }
  }

  async function toggleHistory(plan) {
    const isOpen = Boolean(expandedHistory[plan.id]);

    setExpandedHistory(previous => ({
      ...previous,
      [plan.id]: !isOpen
    }));

    if (isOpen || histories[plan.id]) return;

    try {
      const result = await request(`/planning/plans/${plan.id}/history`);
      const events = Array.isArray(result)
        ? result
        : result?.events || result?.history || [];

      setHistories(previous => ({
        ...previous,
        [plan.id]: events
      }));
    } catch (err) {
      setError(`Could not load plan history: ${err.message}`);
    }
  }

  const counts = dashboard?.counts || {};
  const activePlanCount =
    Number(counts.draft || 0) +
    Number(counts.scheduled || 0) +
    Number(counts.in_progress || 0);
  const completedPlanCount = plans.filter(plan => plan.status === "completed").length;
  const visiblePlans = plans.filter(plan => showCompletedArchive ? plan.status === "completed" : plan.status !== "completed");

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">FACTORY OPERATIONS</div>
          <h1>Planning &amp; Scheduling</h1>
          <p>Plan order-wise production and assign machines and workers with exact timings.</p>
        </div>
        <div className="planning-heading-actions">
          <button className="secondary-button" onClick={loadData} disabled={loading || saving}>
            <RefreshCw size={15} /> Refresh
          </button>
          <button className="primary-button" onClick={() => setShowCreate(value => !value)}>
            {showCreate ? <X size={16} /> : <Plus size={16} />}
            {showCreate ? "Close form" : "Create plan"}
          </button>
        </div>
      </div>

      {error && (
        <div className="planning-message planning-error">
          <AlertCircle size={17} />
          <span>{error}</span>
          <button onClick={() => setError("")} aria-label="Dismiss error"><X size={15} /></button>
        </div>
      )}

      {notice && (
        <div className="planning-message planning-success">
          <CheckCircle2 size={17} />
          <span>{notice}</span>
          <button onClick={() => setNotice("")} aria-label="Dismiss message"><X size={15} /></button>
        </div>
      )}

      <div className="planning-metrics">
        <div><span>Active plans</span><strong>{dashboard ? activePlanCount : "—"}</strong><small>Draft, scheduled and in progress</small></div>
        <div><span>Planned quantity</span><strong>{dashboard ? number(dashboard.planned_qty) : "—"}</strong><small>Across all plans</small></div>
        <div><span>Actual quantity</span><strong>{dashboard ? number(dashboard.actual_qty) : "—"}</strong><small>Recorded against plans</small></div>
        <div><span>Available resources</span><strong>{dashboard ? `${dashboard.active_machines} / ${dashboard.active_shifts} / ${dashboard.active_workers}` : "—"}</strong><small>Machines / shifts / workers</small></div>
      </div>

      {showCreate && (
        <section className="panel planning-create-panel">
          <div className="planning-panel-heading">
            <div>
              <h2><Plus size={17} /> Create production plan</h2>
              <p>Select an eligible customer order line and enter the planned quantity.</p>
            </div>
          </div>

          <form className="planning-form" onSubmit={createPlan}>
            <Field label="Customer order / order line">
              <select
                required
                value={createForm.sales_order_line_id}
                onChange={event => updateCreate("sales_order_line_id", event.target.value)}
              >
                <option value="">Select eligible order line</option>
                {orderLines.map(line => (
                  <option key={line.id} value={line.id}>
                    {line.order_number} · {line.customer_name} · {line.description} · Available {number(line.available_to_plan_qty)} {line.uom_code}
                  </option>
                ))}
              </select>
            </Field>

            <Field label={`Planned quantity${selectedLine ? ` (${selectedLine.uom_code})` : ""}`}>
              <input
                type="number"
                min="0.001"
                step="0.001"
                required
                value={createForm.planned_qty}
                onChange={event => updateCreate("planned_qty", event.target.value)}
                placeholder="Enter quantity"
              />
            </Field>

            <Field label="Planned start date">
              <input
                type="date"
                required
                value={createForm.planned_start_date}
                onChange={event => updateCreate("planned_start_date", event.target.value)}
              />
            </Field>

            <Field label="Target end date">
              <input
                type="date"
                min={createForm.planned_start_date}
                value={createForm.target_end_date}
                onChange={event => updateCreate("target_end_date", event.target.value)}
              />
            </Field>

            <Field label="Notes">
              <input
                type="text"
                maxLength="4000"
                value={createForm.notes}
                onChange={event => updateCreate("notes", event.target.value)}
                placeholder="Optional planning notes"
              />
            </Field>

            {selectedLine && (
              <div className="planning-availability">
                <strong>Order quantity:</strong> {number(selectedLine.ordered_qty)} {selectedLine.uom_code}
                <span><strong>Already planned:</strong> {number(selectedLine.already_planned_qty)} {selectedLine.uom_code}</span>
                <span><strong>Available to plan:</strong> {number(selectedLine.available_to_plan_qty)} {selectedLine.uom_code}</span>
              </div>
            )}

            <div className="planning-form-actions">
              <button className="primary-button" type="submit" disabled={saving || loading}>
                {saving ? <LoaderCircle size={16} className="planning-spin" /> : <Save size={16} />}
                Save production plan
              </button>
              <button className="secondary-button" type="button" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
            </div>
          </form>

          {orderLines.length === 0 && (
            <p className="planning-inline-note">
              No eligible order lines are currently available. Confirm an order before creating its production plan.
            </p>
          )}
        </section>
      )}

      <div className="section-heading planning-register-heading">
        <div>
          <h2>Production plan register</h2>
          <p>Review production plans, machine and worker assignments, and production progress.</p>
        </div>
        <span className="planning-timezone"><Clock3 size={14} /> {lookups.timezone || "Asia/Kolkata"}</span>
      </div>

      <div className="planning-archive-toolbar">
        <div><strong>{showCompletedArchive ? "Completed production plans" : "Active production plans"}</strong><span>{plans.filter(plan => plan.status !== "completed").length} active · {completedPlanCount} completed</span></div>
        <button className="secondary-button" type="button" onClick={() => setShowCompletedArchive(value => !value)} disabled={completedPlanCount === 0}>
          {showCompletedArchive ? "Hide completed archive" : `Show completed archive (${completedPlanCount})`}
        </button>
      </div>

      {loading ? (
        <div className="panel planning-loading">
          <LoaderCircle size={24} className="planning-spin" />
          <span>Loading planning records...</span>
        </div>
      ) : plans.length === 0 ? (
        <div className="panel">
          <div className="empty-state">
            <div className="empty-icon"><CalendarDays size={23} /></div>
            <strong>No production plans yet</strong>
            <p>Create a plan from a confirmed or in-production customer order.</p>
          </div>
        </div>
      ) : (
        <div className="planning-plan-list">
          {visiblePlans.length === 0 ? (
            <div className="panel planning-archive-empty">
              <strong>{plans.length ? "No active plans" : "No production plans yet"}</strong>
              <p>{plans.length ? "All plans are completed. Open the completed archive to review them." : "Create a plan from a confirmed or in-production customer order."}</p>
            </div>
          ) : visiblePlans.map(plan => {
            const allocation = allocationInputs[plan.id] || {};
            const history = histories[plan.id] || [];
            const canAllocate = !["completed", "cancelled"].includes(plan.status);
            const canUpdateActual = !["completed", "cancelled"].includes(plan.status);
            const canUpdateStatus = !["completed", "cancelled"].includes(plan.status);

            return (
              <article className="panel planning-plan-card" key={plan.id}>
                <div className="planning-plan-top">
                  <div>
                    <div className="planning-plan-number">{plan.plan_number}</div>
                    <h3>{plan.item_description || "Production item"}</h3>
                    <p>{plan.order_number} · {plan.order_status} · Line #{plan.sales_order_line_id}</p>
                  </div>
                  <div className="planning-card-header-actions">
                    <StatusPill status={plan.status} />
                    {!["completed", "cancelled"].includes(plan.status) && (
                      <button
                        className="secondary-button planning-edit-button"
                        type="button"
                        onClick={() => editingPlanId === plan.id
                          ? setEditingPlanId(null)
                          : startEditingPlan(plan)}
                      >
                        <Pencil size={14} />
                        {editingPlanId === plan.id ? "Close edit" : "Edit plan"}
                      </button>
                    )}
                    <button className="secondary-button planning-collapse-button" type="button" onClick={() => setCollapsedPlans(previous => ({ ...previous, [plan.id]: !previous[plan.id] }))}>
                      {collapsedPlans[plan.id] ? "Expand details" : "Collapse details"}
                    </button>
                  </div>
                </div>

                <div className="planning-quantity-grid">
                  <div><span>Planned</span><strong>{number(plan.planned_qty)} {plan.uom_code}</strong></div>
                  <div><span>Actual</span><strong>{number(plan.actual_qty)} {plan.uom_code}</strong></div>
                  <div><span>Order produced</span><strong>{number(plan.order_produced_qty)} {plan.uom_code}</strong></div>
                  <div><span>Planned dates</span><strong>{plan.planned_start_date}{plan.target_end_date && plan.target_end_date !== plan.planned_start_date ? ` – ${plan.target_end_date}` : ""}</strong></div>
                </div>

                <div className="planning-progress">
                  <div className="planning-progress-label">
                    <span>Plan output progress</span>
                    <strong>{plan.planned_qty > 0 ? Math.min(100, Number(plan.actual_qty || 0) / Number(plan.planned_qty) * 100).toFixed(1) : "0.0"}%</strong>
                  </div>
                  <div className="planning-progress-track">
                    <span style={{ width: `${plan.planned_qty > 0 ? Math.min(100, Number(plan.actual_qty || 0) / Number(plan.planned_qty) * 100) : 0}%` }} />
                  </div>
                </div>

                {!collapsedPlans[plan.id] && <>
                {editingPlanId === plan.id && (
                  <form
                    className="planning-edit-form"
                    onSubmit={event => savePlanEdits(event, plan)}
                  >
                    <div className="planning-subheading">
                      <Pencil size={16} /> Edit production plan details
                    </div>

                    <Field label="Sales order and order line">
                      <select
                        value={editForm.sales_order_line_id || ""}
                        disabled={Number(plan.actual_qty || 0) > 0}
                        onChange={event => updateEdit("sales_order_line_id", event.target.value)}
                        required
                      >
                        {(() => {
                          const currentLineExists = orderLines.some(
                            line => String(line.id) === String(plan.sales_order_line_id)
                          );
                          const options = currentLineExists
                            ? orderLines
                            : [{
                                id: plan.sales_order_line_id,
                                description: plan.item_description,
                                order_number: plan.order_number,
                                customer_name: "",
                                order_status: plan.order_status
                              }, ...orderLines];

                          return options.map(line => (
                            <option key={line.id} value={String(line.id)}>
                              {line.order_number} · {line.description || `Line #${line.id}`}
                              {line.id === plan.sales_order_line_id ? " (Current)" : ""}
                            </option>
                          ));
                        })()}
                      </select>
                    </Field>

                    {Number(plan.actual_qty || 0) > 0 && (
                      <p className="planning-edit-note">
                        The order line is locked because actual production has already been recorded.
                      </p>
                    )}

                    <Field label={`Planned quantity (${plan.uom_code})`}>
                      <input
                        type="number"
                        min="0.001"
                        step="0.001"
                        required
                        value={editForm.planned_qty || ""}
                        onChange={event => updateEdit("planned_qty", event.target.value)}
                      />
                    </Field>

                    <Field label="Planned start date">
                      <input
                        type="date"
                        required
                        value={editForm.planned_start_date || ""}
                        onChange={event => updateEdit("planned_start_date", event.target.value)}
                      />
                    </Field>

                    <Field label="Target end date">
                      <input
                        type="date"
                        min={editForm.planned_start_date || undefined}
                        value={editForm.target_end_date || ""}
                        onChange={event => updateEdit("target_end_date", event.target.value)}
                      />
                    </Field>

                    <Field label="Notes">
                      <textarea
                        rows="3"
                        maxLength="2000"
                        value={editForm.notes || ""}
                        onChange={event => updateEdit("notes", event.target.value)}
                        placeholder="Add production planning notes"
                      />
                    </Field>

                    <div className="planning-edit-actions">
                      <button className="primary-button" type="submit" disabled={saving}>
                        <Save size={15} /> {saving ? "Saving..." : "Save plan changes"}
                      </button>
                      <button
                        className="secondary-button"
                        type="button"
                        disabled={saving}
                        onClick={() => setEditingPlanId(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}

                <div className="planning-allocations">
                  <div className="planning-subheading"><Factory size={16} /> Machine and worker assignments</div>

                  {plan.allocations?.length ? (
                    <div className="planning-allocation-list">
                      {plan.allocations.map(item => (
                        <div className="planning-allocation-row" key={item.id}>
                          <div><Factory size={15} /><strong>{item.machine_code ? `${item.machine_code} · ` : ""}{item.machine_name || "Machine not recorded"}</strong></div>
                          {item.shift_name && (
                            <div><Clock3 size={15} /><span>{item.shift_name}</span></div>
                          )}
                          <div><UserRound size={15} /><span>{item.worker_name || "Worker not assigned"}</span></div>
                          <div><CalendarDays size={15} /><span>{item.work_date}</span></div>
                          <small>
                            {new Date(item.starts_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}
                            {" – "}
                            {new Date(item.ends_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}
                          </small>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="planning-no-allocation">No machine or worker assignment yet.</p>
                  )}

                  {canAllocate && (
                    <form className="planning-allocation-form" onSubmit={event => addAllocation(event, plan)}>
                      <Field label="Machine name">
                        <>
                          <input
                            type="text"
                            list={`planning-machines-${plan.id}`}
                            required
                            maxLength={120}
                            placeholder="Enter or select machine"
                            value={allocation.machine_name || ""}
                            onChange={event => updateAllocation(plan.id, "machine_name", event.target.value)}
                          />
                          <datalist id={`planning-machines-${plan.id}`}>
                            {(lookups.saved_machines || [])
                              .filter(item => item.branch_id === plan.branch_id)
                              .map(item => <option key={item.id} value={item.name} />)}
                          </datalist>
                        </>
                      </Field>

                      <Field label="Worker name">
                        <>
                          <input
                            type="text"
                            list={`planning-workers-${plan.id}`}
                            required
                            maxLength={120}
                            placeholder="Enter or select worker"
                            value={allocation.worker_name || ""}
                            onChange={event => updateAllocation(plan.id, "worker_name", event.target.value)}
                          />
                          <datalist id={`planning-workers-${plan.id}`}>
                            {(lookups.saved_workers || [])
                              .filter(item => item.branch_id === plan.branch_id)
                              .map(item => <option key={item.id} value={item.name} />)}
                          </datalist>
                        </>
                      </Field>

                      <Field label="Start date & time (IST)">
                        <input
                          type="datetime-local"
                          required
                          value={allocation.starts_at || ""}
                          onChange={event => updateAllocation(plan.id, "starts_at", event.target.value)}
                        />
                      </Field>

                      <Field label="End date & time (IST)">
                        <input
                          type="datetime-local"
                          required
                          value={allocation.ends_at || ""}
                          onChange={event => updateAllocation(plan.id, "ends_at", event.target.value)}
                        />
                      </Field>

                      <button className="primary-button" type="submit" disabled={saving}>
                        <Plus size={15} /> Save assignment
                      </button>
                    </form>
                  )}
                </div>

                <div className="planning-action-grid">
                  {canUpdateActual && (
                    <div className="planning-action-box">
                      <div className="planning-subheading"><Activity size={16} /> Record actual output</div>
                      <div className="planning-inline-controls">
                        <input
                          aria-label="Actual production quantity"
                          type="number"
                          min="0"
                          step="0.001"
                          value={actualInputs[plan.id] ?? String(plan.actual_qty || 0)}
                          onChange={event => setActualInputs(previous => ({
                            ...previous,
                            [plan.id]: event.target.value
                          }))}
                        />
                        <button className="secondary-button" onClick={() => updateActual(plan)} disabled={saving}>
                          <Save size={14} /> Update
                        </button>
                      </div>
                    </div>
                  )}

                  {canUpdateStatus && (
                    <div className="planning-action-box">
                      <div className="planning-subheading"><CheckCircle2 size={16} /> Plan status</div>
                      <div className="planning-inline-controls">
                        <select
                          value={statusInputs[plan.id] ?? plan.status}
                          onChange={event => setStatusInputs(previous => ({
                            ...previous,
                            [plan.id]: event.target.value
                          }))}
                        >
                          <option value="draft">Draft</option>
                          <option value="scheduled">Scheduled</option>
                          <option value="in_progress">In progress</option>
                          <option value="completed">Completed</option>
                          <option value="cancelled">Cancelled</option>
                        </select>
                        <button
                          className="secondary-button"
                          onClick={() => updateStatus(plan)}
                          disabled={saving || (statusInputs[plan.id] ?? plan.status) === plan.status}
                        >
                          Save status
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                <div className="planning-history">
                  <button className="planning-history-toggle" onClick={() => toggleHistory(plan)}>
                    <History size={16} />
                    {expandedHistory[plan.id] ? "Hide audit history" : "View audit history"}
                  </button>

                  {expandedHistory[plan.id] && (
                    <div className="planning-history-list">
                      {history.length ? history.map((item, index) => (
                        <div className="planning-history-event" key={item.id || index}>
                          <strong>{String(item.event_type || "event").replaceAll("_", " ")}</strong>
                          <span>{item.reason || "System event"}</span>
                          <small>{item.occurred_at ? new Date(item.occurred_at).toLocaleString("en-IN") : ""}</small>
                        </div>
                      )) : (
                        <p className="planning-no-allocation">No audit events found for this plan.</p>
                      )}
                    </div>
                  )}
                </div>
                </>}
              </article>
            );
          })}
        </div>
      )}

      <div className="planning-safety-note">
        <CheckCircle2 size={16} />
        <span>Planning records are separate from production posting. Recording planned or actual quantities here does not update order-line production quantities or inventory stock.</span>
      </div>
    </>
  );
}
