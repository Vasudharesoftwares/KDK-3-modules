import React, { useCallback, useEffect, useMemo, useState } from "react";
import Swal from "sweetalert2";
import {
  AlertCircle, ArrowLeft, CalendarDays, Check, CheckCircle2,
  ClipboardList, Eye, LoaderCircle, Pencil, Plus, RefreshCw, Save,
  Search, UserPlus, X, Trash2, Ban
} from "lucide-react";

const API = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8766/api/v1").replace(/\/$/, "");
const PAGE_SIZE = 10;

const UNITS = [
  ["MTR", "Metre (m)"], ["KG", "Kilogram (kg)"],
  ["PCS", "Piece (pcs)"], ["ROLL", "Roll"]
];

const SPEC_FIELDS = [
  ["material", "Material", 120],
  ["fibre_content", "Fabric Type", 200],
  ["colour", "Colour", 100],
  ["pattern", "Pattern", 120],
  ["size_specification", "Size", 120],
  ["brand", "Brand", 120],
  ["occasion", "Occasion", 120],
  ["pure", "Pure", 120],
  ["weight", "Weight", 80],
  ["washcare", "Washcare", 500]
];

async function request(path, options = {}) {
  let response;
  const headers = { ...(options.headers || {}) };

  if (options.body !== undefined && options.body !== null) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }

  try {
    response = await fetch(API + path, {
      ...options,
      headers
    });
  } catch (err) {
    console.error("KDK API request failed:", {
      url: API + path,
      origin: window.location.origin,
      error: err
    });
    throw new Error(
      `Browser request failed: ${err?.message || "Unknown network error"}. URL: ${API + path}. Page: ${window.location.origin}`
    );
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(Array.isArray(detail) ? detail.map(x => x.msg).join("; ") : detail || `HTTP ${response.status}`);
  }
  return data;
}

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
};
const isValidFourDigitDate = value => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === value;
};

const number = v => Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 3 });
const statusText = s => ({
  draft: "Draft", confirmed: "Confirmed", in_production: "In production",
  completed: "Production target met", cancelled: "Cancelled"
}[s] || s);
const statusClass = s => `order-status status-${s}`;
const ErrorBox = ({ children }) => children
  ? <div className="orders-error"><AlertCircle size={16}/><span>{children}</span></div>
  : null;

function CustomerForm({ onCreated, onCancel }) {
  const [data, setData] = useState({
    code: "", name: "", contact_person: "", mobile: "",
    email: "", state: "Punjab", notes: ""
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const change = key => e => setData(old => ({ ...old, [key]: e.target.value }));

  async function submit(e) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      onCreated(await request("/customers", {
        method: "POST", body: JSON.stringify(data)
      }));
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <form className="orders-form" onSubmit={submit}>
    <div className="orders-form-heading">
      <div><strong>Add customer</strong><span>Create a customer record.</span></div>
      <button type="button" className="plain-icon" onClick={onCancel}><X size={17}/></button>
    </div>
    <ErrorBox>{error}</ErrorBox>
    <div className="orders-form-grid">
      <label>Customer code *<input required value={data.code} onChange={change("code")} maxLength="40" placeholder="CUST-001"/></label>
      <label>Customer name *<input required value={data.name} onChange={change("name")} maxLength="200"/></label>
      <label>Contact person<input value={data.contact_person} onChange={change("contact_person")}/></label>
      <label>Mobile<input value={data.mobile} onChange={change("mobile")}/></label>
      <label>Email<input type="email" value={data.email} onChange={change("email")}/></label>
      <label>State<input value={data.state} onChange={change("state")}/></label>
    </div>
    <div className="orders-form-actions">
      <button type="button" className="secondary-button" onClick={onCancel}>Cancel</button>
      <button className="primary-button" disabled={busy}>{busy ? "Saving..." : "Save customer"}</button>
    </div>
  </form>;
}

function CustomAttributeEditor({ attributes, onChange }) {
  const rows = Array.isArray(attributes) ? attributes : [];

  const addAttribute = async () => {
    const result = await Swal.fire({
      title: "Add Attribute",
      input: "text",
      inputLabel: "Attribute name",
      inputPlaceholder: "e.g. Gender",
      showCancelButton: true,
      confirmButtonText: "Add Field",
      inputValidator: value => {
        const name = String(value || "").trim();
        if (!name) return "Please enter an attribute name.";
        if (rows.some(item => String(item.name || "").trim().toLowerCase() === name.toLowerCase())) {
          return "This attribute already exists.";
        }
        if (name.length > 80) return "Maximum 80 characters allowed.";
      }
    });

    if (result.isConfirmed) {
      onChange([...rows, { name: result.value.trim(), value: "" }]);
    }
  };

  return <div className="custom-attributes">
    <div className="custom-attributes-heading">
      <button
        type="button"
        className="secondary-button compact-button"
        onClick={addAttribute}
      ><Plus size={14}/> Add Attribute</button>
    </div>
    {rows.map((item, index) => <div className="custom-attribute-row" key={index}>
      <label>{item.name}
        <input
          maxLength="500"
          value={item.value || ""}
          onChange={e => onChange(
            rows.map((row, i) => i === index ? { ...row, value: e.target.value } : row)
          )}
          placeholder={`Enter ${item.name}`}
        />
      </label>
      <button
        type="button"
        className="remove-line custom-attribute-remove"
        aria-label={`Remove ${item.name}`}
        onClick={() => onChange(rows.filter((_, i) => i !== index))}
      ><X size={15}/></button>
    </div>)}
  </div>;
}

const emptyLine = () => ({
  description: "",
  ordered_qty: "",
  uom_code: "MTR",
  ...Object.fromEntries(SPEC_FIELDS.map(([key]) => [key, ""])),
  custom_attributes: [],
  notes: ""
});

function NewOrder({ customers, onCreated, onCancel, onCustomerCreated, initialOrder = null }) {
  const [customer, setCustomer] = useState(() =>
    initialOrder ? String(initialOrder.customer_id) : ""
  );
  const [form, setForm] = useState(() => ({
    order_date: initialOrder?.order_date || today(),
    delivery_date: initialOrder?.delivery_date || "",
    priority: initialOrder?.priority || "normal",
    notes: initialOrder?.notes || ""
  }));
  const [lines, setLines] = useState(() => initialOrder
    ? initialOrder.lines.map(line => ({
        ...emptyLine(),
        ...line,
        line_id: line.id,
        ordered_qty: String(line.ordered_qty),
        custom_attributes: Array.isArray(line.custom_attributes) ? line.custom_attributes : []
      }))
    : [emptyLine()]
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [addingCustomer, setAddingCustomer] = useState(false);
  const change = key => e => {
    setForm(old => ({ ...old, [key]: e.target.value }));
    setError("");
  };
  const lineChange = (i, key, value) =>
    setLines(old => old.map((line, n) => n === i ? { ...line, [key]: value } : line));

  async function submit(e) {
    e.preventDefault(); setError("");
    if (!customer) return setError("Select a customer.");
    if (!isValidFourDigitDate(form.order_date) || !isValidFourDigitDate(form.delivery_date))
      return setError("Enter valid dates using a four-digit year (YYYY).");
    if (form.delivery_date < form.order_date)
      return setError("Delivery deadline cannot be before the order date.");
    if (lines.some(l => !l.description.trim() || !(Number(l.ordered_qty) > 0)))
      return setError("Every item needs a Product Name and a positive Ordered Quantity.");
    for (const line of lines) {
      const attrs = (line.custom_attributes || []).filter(
        a => String(a.name || "").trim() || String(a.value || "").trim()
      );
      if (attrs.some(a => !String(a.name || "").trim() || !String(a.value || "").trim()))
        return setError("Each additional attribute needs both a name and a value.");
      const names = attrs.map(a => String(a.name).trim().toLowerCase());
      if (new Set(names).size !== names.length)
        return setError("Additional attribute names must be unique within each item.");
    }
    setBusy(true);
    const payload = {
      customer_id: Number(customer),
      order_date: form.order_date,
      delivery_date: form.delivery_date,
      priority: form.priority,
      notes: form.notes || null,
      lines: lines.map(l => ({
        ...(l.line_id ? { line_id: l.line_id } : {}),
        description: l.description.trim(),
        ...Object.fromEntries(SPEC_FIELDS.map(([key]) => [
          key, String(l[key] ?? "").trim() || null
        ])),
        ordered_qty: Number(l.ordered_qty),
        uom_code: l.uom_code,
        product_id: l.product_id ?? null,
        custom_attributes: (l.custom_attributes || [])
          .filter(a => String(a.name || "").trim() || String(a.value || "").trim())
          .map(a => ({ name: String(a.name || "").trim(), value: String(a.value || "").trim() })),
        notes: String(l.notes || "").trim() || null
      }))
    };
    try {
      const saved = await request(
        initialOrder ? `/orders/${initialOrder.id}` : "/orders",
        {
          method: initialOrder ? "PUT" : "POST",
          body: JSON.stringify(payload)
        }
      );
      onCreated(saved);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  if (addingCustomer) return <CustomerForm
    onCancel={() => setAddingCustomer(false)}
    onCreated={c => {
      onCustomerCreated(c);
      setCustomer(String(c.id));
      setAddingCustomer(false);
    }}
  />;

  return <form className="orders-form" onSubmit={submit}>
    <div className="orders-form-heading">
      <div><strong>{initialOrder ? `Edit order ${initialOrder.order_number}` : "New customer order"}</strong><span>{initialOrder ? "Update the customer commitment and order items. Recorded factory progress is preserved." : "Enter the customer commitment and delivery deadline."}</span></div>
      <button type="button" className="plain-icon" onClick={onCancel}><X size={17}/></button>
    </div>
    <ErrorBox>{error}</ErrorBox>
    <div className="orders-form-grid">
      <label className="field-wide">Customer *
        <div className="customer-select-row">
          <select required value={customer} onChange={e => { setCustomer(e.target.value); setError(""); }}>
            <option value="">Select customer</option>
            {customers.map(c => <option key={c.id} value={c.id}>{c.name} ({c.code})</option>)}
          </select>
          <button type="button" className="secondary-button compact-button" onClick={() => setAddingCustomer(true)}>
            <UserPlus size={14}/> Add customer
          </button>
        </div>
      </label>
      <label>Order date *<input type="date" required max="9999-12-31" value={form.order_date} onChange={change("order_date")}/></label>
      <label>Delivery deadline *<input type="date" required min={form.order_date} max="9999-12-31" value={form.delivery_date} onChange={change("delivery_date")}/></label>
      <label>Priority
        <select value={form.priority} onChange={change("priority")}>
          <option value="low">Low</option><option value="normal">Normal</option>
          <option value="high">High</option><option value="urgent">Urgent</option>
        </select>
      </label>
      <label className="field-wide">Order notes<textarea rows="2" value={form.notes} onChange={change("notes")}/></label>
    </div>
    <div className="order-lines-heading">
      <strong>Order items ({lines.length})</strong>
      <button type="button" className="secondary-button compact-button" onClick={() => setLines(old => [...old, emptyLine()])}>
        <Plus size={14}/> Add item
      </button>
    </div>
    {lines.map((line, i) => <div className="order-line-editor" key={i}>
      <span className="order-line-number">{String(i+1).padStart(2,"0")}</span>
      <div className="order-line-fields">
        <label className="line-description">Product Name *
          <input required maxLength="250" value={line.description}
            onChange={e => lineChange(i,"description",e.target.value)}
            placeholder="e.g. Woven wool shawl"/>
        </label>
        <label>Ordered Quantity *
          <input required type="number" min="0.001" step="0.001"
            value={line.ordered_qty}
            onChange={e => lineChange(i,"ordered_qty",e.target.value)}
            placeholder="0.000"/>
        </label>
        <label>Unit *
          <select value={line.uom_code}
            onChange={e => lineChange(i,"uom_code",e.target.value)}>
            {UNITS.map(([code,label]) => <option key={code} value={code}>{label}</option>)}
          </select>
        </label>
      </div>
      <div className="order-specifications">
        <div className="order-specifications-heading">
          <strong>Customer-required specifications</strong>
          <span>Optional details agreed with the customer.</span>
        </div>
        <div className="order-specifications-grid">
          {SPEC_FIELDS.map(([key,label,max]) => <label key={key}>
            {label}
            <input maxLength={max} value={line[key] || ""}
              onChange={e => lineChange(i,key,e.target.value)}
              placeholder={key === "weight" ? "e.g. 400 g or 220g" : ""}
            />
          </label>)}
          <label className="spec-notes">Special instructions for this item
            <textarea rows="2" value={line.notes || ""}
              onChange={e => lineChange(i,"notes",e.target.value)}
              placeholder="Optional customer-specific instructions"/>
          </label>
        </div>
        <CustomAttributeEditor
          attributes={line.custom_attributes}
          onChange={value => lineChange(i,"custom_attributes",value)}
        />
      </div>
      {lines.length > 1 && <button type="button" className="remove-line" onClick={() => setLines(old => old.filter((_,n) => n !== i))}><X size={15}/></button>}
    </div>)}
    <div className="orders-form-actions">
      <button type="button" className="secondary-button" onClick={onCancel}>Cancel</button>
      <button className="primary-button" disabled={busy}>{busy ? "Saving..." : <><Save size={15}/> {initialOrder ? "Save changes" : "Save order"}</>}</button>
    </div>
  </form>;
}

function Progress({ order, onRefresh }) {
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const next = {};
    order.lines.forEach(l => next[l.id] = {
      produced_qty: "",
      approved_qty: "",
      dispatched_qty: ""
    });
    setValues(next);
  }, [order]);

  const change = (id,key,value) => setValues(old => ({
    ...old, [id]: { ...old[id], [key]: value }
  }));

  async function save(line) {
    const v = values[line.id] || {};
    const entries = [v.produced_qty, v.approved_qty, v.dispatched_qty];
    if (!entries.some(value => String(value ?? "").trim() !== "")) {
      setError("Enter at least one quantity before saving.");
      return;
    }

    const cumulative = (value, current) =>
      String(value ?? "").trim() === "" ? Number(current) : Number(value);

    const p = cumulative(v.produced_qty, line.produced_qty);
    const a = cumulative(v.approved_qty, line.approved_qty);
    const d = cumulative(v.dispatched_qty, line.dispatched_qty);

    if (![p,a,d].every(Number.isFinite) ||
        p < Number(line.produced_qty) || a < Number(line.approved_qty) ||
        d < Number(line.dispatched_qty)) {
      setError("Recorded quantities are cumulative and cannot be reduced.");
      return;
    }
    if (a > p || d > a) {
      setError("Approved quantity cannot exceed produced quantity. Dispatched cannot exceed approved.");
      return;
    }

    setBusy(line.id);
    setError("");
    try {
      await request(`/orders/${order.id}/lines/${line.id}/progress`, {
        method: "PATCH",
        body: JSON.stringify({ produced_qty:p, approved_qty:a, dispatched_qty:d })
      });

      await onRefresh(order.id);

      await Swal.fire({
        icon: "success",
        title: "Saved successfully",
        text: "Production, quality and dispatch quantities have been updated.",
        confirmButtonText: "OK",
        confirmButtonColor: "#287a52"
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  return <section className="progress-section">
    <div className="detail-section-title"><div><strong>Production, quality & dispatch</strong><span>Enter cumulative quantities for each item.</span></div></div>
    <ErrorBox>{error}</ErrorBox>
    {order.lines.map(line => {
      const v = values[line.id] || {};
      const pending = Math.max(Number(line.ordered_qty)-Number(line.produced_qty),0);
      const extra = Math.max(Number(line.produced_qty)-Number(line.ordered_qty),0);
      const approval = Math.max(Number(line.produced_qty)-Number(line.approved_qty),0);
      const dispatch = Math.max(Number(line.approved_qty)-Number(line.dispatched_qty),0);
      return <div className="progress-line" key={line.id}>
        <div className="progress-line-title"><strong>{line.description}</strong><span>Ordered {number(line.ordered_qty)} {line.uom_code}{line.design_code ? ` · Design ${line.design_code}` : ""}</span></div>
        <div className="progress-inputs">
          <label>Produced<input type="number" min={line.produced_qty} step="0.001" value={v.produced_qty ?? ""} onChange={e => change(line.id,"produced_qty",e.target.value)}/></label>
          <label>Quality approved<input type="number" min={line.approved_qty} step="0.001" value={v.approved_qty ?? ""} onChange={e => change(line.id,"approved_qty",e.target.value)}/></label>
          <label>Dispatched<input type="number" min={line.dispatched_qty} step="0.001" value={v.dispatched_qty ?? ""} onChange={e => change(line.id,"dispatched_qty",e.target.value)}/></label>
          <button className="primary-button save-progress" disabled={busy === line.id || ["draft","cancelled"].includes(order.status)} onClick={() => save(line)}>
            {busy === line.id ? <LoaderCircle className="spin" size={14}/> : <Save size={14}/>} Save
          </button>
        </div>
        <div className="progress-facts">
          <span>Pending production: <b>{number(pending)} {line.uom_code}</b></span>
          {extra > 0 && <span className="fact-warning">Overproduced: <b>{number(extra)} {line.uom_code}</b></span>}
          <span>Pending approval: <b>{number(approval)} {line.uom_code}</b></span>
          <span>Pending dispatch: <b>{number(dispatch)} {line.uom_code}</b></span>
        </div>
      </div>;
    })}
    {order.status === "draft" && <p className="inline-hint">Confirm the order before recording production or dispatch.</p>}
    {order.status === "completed" && order.lines.some(l => Number(l.produced_qty)>Number(l.approved_qty)) &&
      <p className="inline-hint warning-hint">The ordered approved target is met, but additional production is still awaiting quality approval.</p>}
  </section>;
}

function Details({ order, onBack, onRefresh, onEdit }) {
  const [error,setError] = useState("");
  const [busy,setBusy] = useState(false);
  const [history,setHistory] = useState([]);
  const [editingLineId,setEditingLineId] = useState(null);
  const [editDraft,setEditDraft] = useState(null);
  const [savingLine,setSavingLine] = useState(false);
  const totals = order.lines.reduce((t,l) => ({
    ordered:t.ordered+Number(l.ordered_qty), produced:t.produced+Number(l.produced_qty),
    approved:t.approved+Number(l.approved_qty), dispatched:t.dispatched+Number(l.dispatched_qty)
  }),{ordered:0,produced:0,approved:0,dispatched:0});

  useEffect(() => {
    request(`/orders/${order.id}/history`)
      .then(setHistory)
      .catch(err => setError(err.message));
  }, [order.id, order.status]);

  async function status(s) {
    let reason = null;
    if (s === "cancelled") {
      const result = await Swal.fire({
        title: "Cancel this customer order?",
        text: "Production and dispatch history will be preserved. You can restore this order later.",
        input: "textarea",
        inputLabel: "Cancellation reason",
        inputPlaceholder: "Why is this order being cancelled?",
        inputAttributes: { "aria-label": "Cancellation reason" },
        showCancelButton: true,
        confirmButtonText: "Cancel order",
        cancelButtonText: "Keep order",
        confirmButtonColor: "#b42318",
        inputValidator: value => !value.trim() ? "A cancellation reason is required." : undefined
      });
      if (!result.isConfirmed) return;
      reason = result.value.trim();
    } else {
      const result = await Swal.fire({
        icon: "question",
        title: "Confirm this order?",
        showCancelButton: true,
        confirmButtonText: "Confirm order"
      });
      if (!result.isConfirmed) return;
    }

    setBusy(true); setError("");
    try {
      await request(`/orders/${order.id}/status`, {
        method:"PATCH",
        body:JSON.stringify({status:s, reason})
      });
      await onRefresh(order.id);
      await Swal.fire({
        icon:"success",
        title:s === "cancelled" ? "Order cancelled" : "Order confirmed",
        text:s === "cancelled"
          ? "The order and its production/dispatch history are safely preserved. You can restore it later."
          : "The order has been confirmed.",
        confirmButtonColor:"#287a52"
      });
    } catch(err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function archive() {
    const dispatched = totals.dispatched;
    const result = await Swal.fire({
      icon: "warning",
      title: "Delete / Archive this order?",
      html: `<p>This will close the order without permanently deleting it.</p>
        <p><strong>${number(dispatched)} dispatched units</strong> and all production, approval and audit records will remain preserved.</p>`,
      input: "textarea",
      inputLabel: "Reason for archiving",
      inputPlaceholder: "Enter why this order is being closed...",
      inputAttributes: { "aria-label": "Archive reason" },
      showCancelButton: true,
      confirmButtonText: "Archive order",
      cancelButtonText: "Keep order",
      confirmButtonColor: "#b42318",
      inputValidator: value => !value || !value.trim()
        ? "An archive reason is required."
        : undefined
    });
    if (!result.isConfirmed) return;

    setBusy(true);
    setError("");
    try {
      await request(`/orders/${order.id}/close`, {
        method: "POST",
        body: JSON.stringify({ reason: result.value.trim() })
      });
      await onRefresh(order.id);
      await Swal.fire({
        icon: "success",
        title: "Order archived",
        text: `${order.order_number} is closed. All recorded quantities and history remain preserved.`,
        confirmButtonColor: "#287a52"
      });
    } catch (err) {
      setError(err.message);
      await Swal.fire({
        icon: "error",
        title: "Could not archive order",
        text: err.message
      });
    } finally {
      setBusy(false);
    }
  }

  async function restore() {
    const result = await Swal.fire({
      icon:"question",
      title:"Restore this order?",
      text:"It will return to its previous status. Existing quantities and dispatch records will not be repeated.",
      showCancelButton:true,
      confirmButtonText:"Restore order",
      confirmButtonColor:"#287a52"
    });
    if (!result.isConfirmed) return;

    setBusy(true); setError("");
    try {
      await request(`/orders/${order.id}/restore`, {method:"POST"});
      await onRefresh(order.id);
      await Swal.fire({
        icon:"success",
        title:"Order restored",
        text:"The previous order status and all recorded quantities have been preserved.",
        confirmButtonColor:"#287a52"
      });
    } catch(err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <div className="order-detail-view">
    <button className="back-link" onClick={onBack}><ArrowLeft size={15}/> Back to order register</button>
    <div className="detail-header">
      <div><div className="eyebrow">CUSTOMER ORDER</div><h2>{order.order_number}</h2><p>{order.customer_name} · Order date {order.order_date}</p></div>
      <div className="detail-header-actions">
        {order.status !== "cancelled" && <>
          <button className="primary-button" disabled={busy} onClick={onEdit}>
            <Pencil size={15}/> Edit order
          </button>
          <button className="secondary-button danger-button" disabled={busy} onClick={archive}>
            <Trash2 size={15}/> Delete / Archive
          </button>
        </>}
        <span className={statusClass(order.status)}>{statusText(order.status)}</span>
      </div>
    </div>
    <ErrorBox>{error}</ErrorBox>
    <div className="detail-summary-grid">
      <div><span>Delivery deadline</span><strong>{order.delivery_date}</strong></div>
      <div><span>Priority</span><strong>{order.priority.toUpperCase()}</strong></div>
      <div><span>Ordered</span><strong>{number(totals.ordered)}</strong></div>
      <div><span>Produced</span><strong>{number(totals.produced)}</strong></div>
      <div><span>Quality approved</span><strong>{number(totals.approved)}</strong></div>
      <div><span>Dispatched</span><strong>{number(totals.dispatched)}</strong></div>
    </div>
    {order.notes && <div className="order-notes"><strong>Order notes</strong><p>{order.notes}</p></div>}
    <section className="customer-detail-card">
      <div className="detail-section-title">
        <div><strong>Customer information</strong><span>Details from the customer master record.</span></div>
      </div>
      {order.customer ? <>
        <div className="customer-detail-grid">
          {[
            ["Customer code", order.customer.code],
            ["Customer name", order.customer.name],
            ["Contact person", order.customer.contact_person],
            ["Mobile", order.customer.mobile],
            ["Email", order.customer.email],
            ["State", order.customer.state],
            ["GSTIN", order.customer.gstin],
            ["PAN", order.customer.pan],
          ].map(([label,value]) => <div key={label}>
            <span>{label}</span><b>{value || "Not provided"}</b>
          </div>)}
        </div>
        {order.customer.notes && <div className="customer-master-notes">
          <strong>Customer master notes</strong><p>{order.customer.notes}</p>
        </div>}
      </> : <p className="no-specifications">Customer master details are not available for this order.</p>}

      <div className="customer-address-heading">Saved customer addresses</div>
      {order.customer_addresses?.length ? order.customer_addresses.map(address =>
        <div className="customer-address-item" key={address.id}>
          <div>
            <strong>{address.address_type || "Address"} address</strong>
            {address.is_default && <span className="default-address-label">Default</span>}
          </div>
          <p>{address.address}</p>
          <span>{[address.city, address.district, address.state, address.pin_code, address.country].filter(Boolean).join(", ")}</span>
        </div>
      ) : <p className="no-specifications">No customer address has been saved.</p>}
    </section>

    <section className="order-specifications-view">
      <div className="detail-section-title">
        <div>
          <strong>Customer order items and specifications</strong>
          <span>Saved specifications and additional attributes for each item.</span>
        </div>
      </div>
      {order.lines.map(line => {
        const isEditing = editingLineId === line.id;
        const savedSpecs = SPEC_FIELDS
          .map(([key,label]) => ({ key, label, value: line[key] }))
          .filter(item => item.value !== null && item.value !== undefined && String(item.value).trim() !== "");
        const savedAttributes = Array.isArray(line.custom_attributes) ? line.custom_attributes : [];
        const beginEdit = () => {
          setEditingLineId(line.id);
          setEditDraft({
            description: line.description || "",
            ordered_qty: String(line.ordered_qty ?? ""),
            uom_code: line.uom_code || "MTR",
            ...Object.fromEntries(SPEC_FIELDS.map(([key]) => [key, line[key] ?? ""])),
            custom_attributes: savedAttributes.map(a => ({ name: a.name || "", value: a.value || "" })),
            notes: line.notes || ""
          });
          setError("");
        };
        const changeDraft = (key, value) =>
          setEditDraft(old => ({ ...old, [key]: value }));

        async function saveLine() {
          if (!editDraft.description.trim() || !(Number(editDraft.ordered_qty) > 0)) {
            setError("Product Name and a positive Ordered Quantity are required.");
            return;
          }
          const attrs = (editDraft.custom_attributes || []).filter(
            a => String(a.name || "").trim() || String(a.value || "").trim()
          );
          if (attrs.some(a => !String(a.name || "").trim() || !String(a.value || "").trim())) {
            setError("Each additional attribute needs both a name and a value.");
            return;
          }
          const names = attrs.map(a => String(a.name).trim().toLowerCase());
          if (new Set(names).size !== names.length) {
            setError("Additional attribute names must be unique within each item.");
            return;
          }

          const payload = {
            description: editDraft.description.trim(),
            ordered_qty: Number(editDraft.ordered_qty),
            uom_code: editDraft.uom_code,
            ...Object.fromEntries(SPEC_FIELDS.map(([key]) => [
              key, String(editDraft[key] ?? "").trim() || null
            ])),
            custom_attributes: attrs.map(a => ({
              name: String(a.name).trim(),
              value: String(a.value).trim()
            })),
            notes: String(editDraft.notes || "").trim() || null
          };
          setSavingLine(true);
          setError("");
          try {
            await request(`/orders/${order.id}/lines/${line.id}/details`, {
              method: "PATCH",
              body: JSON.stringify(payload)
            });
            await onRefresh(order.id);
            setEditingLineId(null);
            setEditDraft(null);
          } catch (err) {
            setError(err.message);
          } finally {
            setSavingLine(false);
          }
        }

        return <div className="specification-detail-line" key={line.id}>
          <div className="specification-line-heading">
            <div>
              <strong>{line.description || "Order item"}</strong>
              {line.design_code && <span className="legacy-design-code">Legacy design code: {line.design_code}</span>}
            </div>
            {order.status !== "cancelled" && !isEditing &&
              <button type="button" className="secondary-button compact-button"
                onClick={beginEdit}><Save size={14}/> Edit specifications</button>}
          </div>
          <div className="product-link-status">
            {line.product_id
              ? `Linked to product master · Product ID ${line.product_id}`
              : "Not linked to a product master record"}
          </div>

          {isEditing && editDraft ? <>
            <div className="order-line-fields specification-edit-fields">
              <label className="line-description">Product Name *
                <input maxLength="250" value={editDraft.description}
                  onChange={e => changeDraft("description",e.target.value)}/>
              </label>
              <label>Ordered Quantity *
                <input type="number" min="0.001" step="0.001"
                  value={editDraft.ordered_qty}
                  onChange={e => changeDraft("ordered_qty",e.target.value)}/>
              </label>
              <label>Unit *
                <select value={editDraft.uom_code}
                  onChange={e => changeDraft("uom_code",e.target.value)}>
                  {UNITS.map(([code,label]) => <option key={code} value={code}>{label}</option>)}
                </select>
              </label>
            </div>
            <div className="order-specifications-grid specification-edit-grid">
              {SPEC_FIELDS.map(([key,label,max]) => <label key={key}>
                {label}
                <input maxLength={max} value={editDraft[key] || ""}
                  onChange={e => changeDraft(key,e.target.value)}/>
              </label>)}
              <label className="spec-notes">Special instructions
                <textarea rows="2" value={editDraft.notes}
                  onChange={e => changeDraft("notes",e.target.value)}/>
              </label>
            </div>
            <CustomAttributeEditor
              attributes={editDraft.custom_attributes}
              onChange={value => changeDraft("custom_attributes",value)}
            />
            <div className="specification-edit-actions">
              <button type="button" className="secondary-button"
                disabled={savingLine}
                onClick={() => { setEditingLineId(null); setEditDraft(null); setError(""); }}>
                Cancel editing
              </button>
              <button type="button" className="primary-button"
                disabled={savingLine} onClick={saveLine}>
                <Save size={14}/> {savingLine ? "Saving..." : "Save specifications"}
              </button>
            </div>
          </> : <>
            <div className="specification-detail-grid">
              <div><span>Ordered Quantity</span><b>{number(line.ordered_qty)} {line.uom_code}</b></div>
              {savedSpecs.map(item => <div key={item.key}>
                <span>{item.label}</span><b>{String(item.value)}</b>
              </div>)}
              {line.notes && <div><span>Special instructions</span><b>{line.notes}</b></div>}
              {savedAttributes.map((item,index) => <div key={`${item.name}-${index}`}>
                <span>{item.name}</span><b>{item.value}</b>
              </div>)}
            </div>
            {!savedSpecs.length && !savedAttributes.length && !line.notes &&
              <p className="no-specifications">No optional specifications have been entered.</p>}
          </>}

          <div className="line-quantity-summary">
            <div><span>Ordered</span><b>{number(line.ordered_qty)} {line.uom_code}</b></div>
            <div><span>Produced</span><b>{number(line.produced_qty)} {line.uom_code}</b></div>
            <div><span>Quality approved</span><b>{number(line.approved_qty)} {line.uom_code}</b></div>
            <div><span>Dispatched</span><b>{number(line.dispatched_qty)} {line.uom_code}</b></div>
          </div>
        </div>;
      })}
    </section>
    <div className="detail-actions">
      {order.status === "draft" && <button className="primary-button" disabled={busy} onClick={() => status("confirmed")}><CheckCircle2 size={15}/> Confirm order</button>}
      {order.status !== "cancelled" && totals.dispatched === 0 && <button className="secondary-button danger-button" disabled={busy} onClick={() => status("cancelled")}>Cancel order</button>}
      {order.status === "cancelled" && <button className="primary-button" disabled={busy} onClick={restore}><CheckCircle2 size={15}/> Restore order</button>}
      <button className="secondary-button" onClick={() => onRefresh(order.id)}><RefreshCw size={14}/> Refresh</button>
    </div>
    <section className="order-status-history">
      <div className="detail-section-title">
        <div><strong>Cancellation and restoration history</strong><span>Recorded status changes and preserved quantity snapshots.</span></div>
      </div>
      {history.length === 0
        ? <p className="no-specifications">No cancellation or restoration actions recorded.</p>
        : history.map(event => <div className="order-history-event" key={event.id}>
            <strong>{event.action === "cancelled" ? "Order cancelled" : "Order restored"}</strong>
            <span>{statusText(event.from_status)} → {statusText(event.to_status)}</span>
            <time>{new Date(event.occurred_at).toLocaleString("en-IN")}</time>
            {event.reason && <p>{event.reason}</p>}
            <small>Quantities at this action: {event.quantity_snapshot.map(q => `Line ${q.line_id}: dispatched ${q.dispatched_qty}`).join(" · ")}</small>
          </div>)}
    </section>
    <Progress order={order} onRefresh={onRefresh}/>
  </div>;
}

export default function OrdersPage() {
  const [orders,setOrders] = useState([]);
  const [customers,setCustomers] = useState([]);
  const [selected,setSelected] = useState(null);
  const [showNew,setShowNew] = useState(false);
  const [editingOrder,setEditingOrder] = useState(null);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState("");
  const [search,setSearch] = useState("");
  const [filter,setFilter] = useState("all");
  const [currentPage,setCurrentPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [o,c] = await Promise.all([
        request("/orders"), request("/lookups/customers")
      ]);
      setOrders(o); setCustomers(c);
    } catch(err) { setError(err.message); }
    finally { setLoading(false); }
  },[]);

  useEffect(() => { load(); },[load]);

  async function refreshSelected(id) {
    const fresh = await request(`/orders/${id}`);
    setSelected(fresh);
    setOrders(old => old.map(o => o.id === id ? fresh : o));
  }

  const fifoOrders = useMemo(() => [...orders].sort((a, b) => Number(a.id) - Number(b.id)), [orders]);

  const filtered = useMemo(() => fifoOrders.filter(o => {
    const term = search.trim().toLowerCase();
    const matches = !term || [
      o.order_number, o.customer_name,
      ...o.lines.flatMap(l => [
        l.description, l.design_code || "",
        ...SPEC_FIELDS.map(([key]) => l[key] || "")
      ])
    ].join(" ").toLowerCase().includes(term);
    return matches && (filter === "all" || o.status === filter);
  }),[fifoOrders,search,filter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);
  const pageOrders = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  function created(order) {
    setOrders(old => [...old, order]);
    setSearch("");
    setFilter("all");
    setCurrentPage(Math.floor(orders.length / PAGE_SIZE) + 1);
    setSelected(order);
    setShowNew(false);
  }

  function updated(order) {
    setOrders(old => old.map(item => item.id === order.id ? order : item));
    setSelected(order);
    setEditingOrder(null);
    Swal.fire({
      icon: "success",
      title: "Order updated",
      text: `${order.order_number} has been saved. Existing factory progress was preserved.`,
      confirmButtonColor: "#287a52"
    });
  }

  async function deleteDraftOrder(order) {
    const result = await Swal.fire({
      icon: "warning",
      title: "Permanently delete this draft?",
      text: `${order.order_number} and its order items will be deleted. This cannot be undone.`,
      showCancelButton: true,
      confirmButtonText: "Delete draft",
      cancelButtonText: "Keep order",
      confirmButtonColor: "#b42318"
    });
    if (!result.isConfirmed) return;

    try {
      await request(`/orders/${order.id}`, { method: "DELETE" });
      setOrders(old => old.filter(item => item.id !== order.id));
      await Swal.fire({ icon: "success", title: "Draft deleted", text: order.order_number });
    } catch (err) {
      await Swal.fire({ icon: "error", title: "Could not delete order", text: err.message });
    }
  }

  async function cancelFromRegister(order) {
    const result = await Swal.fire({
      icon: "warning",
      title: "Cancel this customer order?",
      input: "textarea",
      inputLabel: "Cancellation reason",
      inputPlaceholder: "Why is this order being cancelled?",
      inputAttributes: { "aria-label": "Cancellation reason" },
      showCancelButton: true,
      confirmButtonText: "Cancel order",
      cancelButtonText: "Keep order",
      confirmButtonColor: "#b42318",
      inputValidator: value => !value || !value.trim()
        ? "A cancellation reason is required."
        : undefined
    });
    if (!result.isConfirmed) return;

    try {
      await request(`/orders/${order.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "cancelled", reason: result.value.trim() })
      });
      await load();
      await Swal.fire({ icon: "success", title: "Order cancelled", text: order.order_number });
    } catch (err) {
      await Swal.fire({ icon: "error", title: "Could not cancel order", text: err.message });
    }
  }

  if (editingOrder) return <NewOrder
    key={`edit-${editingOrder.id}`}
    customers={customers}
    initialOrder={editingOrder}
    onCreated={updated}
    onCancel={() => setEditingOrder(null)}
    onCustomerCreated={c => setCustomers(old => [...old,c].sort((a,b)=>a.name.localeCompare(b.name)))}
  />;

  if (selected) return <Details
    order={selected}
    onBack={() => setSelected(null)}
    onRefresh={refreshSelected}
    onEdit={() => setEditingOrder(selected)}
  />;

  return <>
    <div className="page-heading orders-page-heading">
      <div><div className="eyebrow">FACTORY OPERATIONS</div><h1>Order Management</h1><p>Manage customer commitments, production, quality approval and dispatch.</p></div>
      <div className="orders-heading-actions">
        <button className="secondary-button" onClick={load} disabled={loading}><RefreshCw size={15}/> Refresh</button>
        <button className="primary-button" onClick={() => setShowNew(v => !v)}><Plus size={16}/> New customer order</button>
      </div>
    </div>
    <ErrorBox>{error}</ErrorBox>
    {showNew && <NewOrder customers={customers} onCreated={created} onCancel={() => setShowNew(false)} onCustomerCreated={c => setCustomers(old => [...old,c].sort((a,b)=>a.name.localeCompare(b.name)))}/>}
    <div className="orders-metrics">
      <div><span>Total orders</span><strong>{orders.length}</strong></div>
      <div><span>Active orders</span><strong>{orders.filter(o=>!["completed","cancelled"].includes(o.status)).length}</strong></div>
      <div><span>In production</span><strong>{orders.filter(o=>o.status==="in_production").length}</strong></div>
      <div><span>Production target met</span><strong>{orders.filter(o=>o.status==="completed").length}</strong></div>
    </div>
    <div className="section-heading orders-register-heading"><div><h2>Customer order register</h2><p>{filtered.length} of {orders.length} orders</p></div></div>
    <div className="orders-toolbar">
      <div className="orders-search"><Search size={16}/><input value={search} onChange={e=>{setSearch(e.target.value);setCurrentPage(1);}} placeholder="Search order, customer, design..."/></div>
      <select value={filter} onChange={e=>{setFilter(e.target.value);setCurrentPage(1);}} aria-label="Filter orders">
        <option value="all">All statuses</option><option value="draft">Draft</option>
        <option value="confirmed">Confirmed</option><option value="in_production">In production</option>
        <option value="completed">Production target met</option><option value="cancelled">Cancelled</option>
      </select>
    </div>
    <div className="panel orders-register-panel">
      {loading ? <div className="orders-empty"><LoaderCircle className="spin"/> Loading orders...</div> :
       filtered.length === 0 ? <div className="orders-empty">
        <div className="empty-icon"><ClipboardList size={23}/></div>
        <strong>{orders.length ? "No matching orders" : "No customer orders recorded"}</strong>
        <p>{orders.length ? "Try another search or status filter." : "Create the first order to start tracking factory commitments."}</p>
        {orders.length===0 && <button className="primary-button" onClick={()=>setShowNew(true)}><Plus size={15}/> Create first order</button>}
       </div> :
       <div className="table-wrap"><table className="orders-table">
        <thead><tr><th>ORDER NO.</th><th>CUSTOMER</th><th>DESIGN / FABRIC</th><th>ORDER QTY.</th><th>PRODUCED</th><th>APPROVED</th><th>DISPATCHED</th><th>DEADLINE</th><th>STATUS</th><th>ACTIONS</th></tr></thead>
        <tbody>{pageOrders.map(o => {
          const sum = key => o.lines.reduce((n,l)=>n+Number(l[key]),0);
          return <tr key={o.id} className="order-table-row" onClick={()=>setSelected(o)}>
            <td><strong className="order-number">{o.order_number}</strong></td>
            <td>{o.customer_name}</td>
            <td><span className="design-cell">{o.lines.map(l=>l.description).join(", ")}</span><small>{o.lines.length} item(s)</small></td>
            <td>{number(sum("ordered_qty"))}</td><td>{number(sum("produced_qty"))}</td>
            <td>{number(sum("approved_qty"))}</td><td>{number(sum("dispatched_qty"))}</td>
            <td>{o.delivery_date}</td><td><span className={statusClass(o.status)}>{statusText(o.status)}</span></td>
            <td>
              <div className="order-row-actions" onClick={e => e.stopPropagation()}>
                <button type="button" className="order-action-view"
                  onClick={() => setSelected(o)}><Eye size={14}/> View</button>
                {o.status !== "cancelled" && sum("dispatched_qty") === 0 &&
                  <button type="button" className="order-action-edit"
                    onClick={() => setEditingOrder(o)}><Pencil size={14}/> Edit</button>}
                {o.status !== "cancelled" && sum("dispatched_qty") === 0 &&
                  <button type="button" className="order-action-cancel"
                    onClick={() => cancelFromRegister(o)}><Ban size={14}/> Cancel</button>}
                <button type="button" className="order-action-delete"
                  onClick={() => deleteDraftOrder(o)}><Trash2 size={14}/> Delete</button>
              </div>
            </td>
          </tr>;
        })}</tbody>
       </table></div>}
    </div>
    {filtered.length > 0 && <div className="orders-pagination">
      <span>Showing {(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, filtered.length)} of {filtered.length} orders · FIFO sequence</span>
      <div className="orders-pagination-controls">
        <button type="button" className="secondary-button" disabled={safePage === 1} onClick={() => setCurrentPage(1)}>First</button>
        <button type="button" className="secondary-button" disabled={safePage === 1} onClick={() => setCurrentPage(safePage - 1)}>Previous</button>
        <strong>Page {safePage} of {totalPages}</strong>
        <button type="button" className="secondary-button" disabled={safePage === totalPages} onClick={() => setCurrentPage(safePage + 1)}>Next</button>
        <button type="button" className="secondary-button" disabled={safePage === totalPages} onClick={() => setCurrentPage(totalPages)}>Last</button>
      </div>
    </div>}
    <div className="orders-footnote"><CheckCircle2 size={15}/><span>Ordered, produced, quality-approved and dispatched quantities are tracked independently. Quantities are cumulative.</span></div>
  </>;
}
