import React, { useEffect, useMemo, useState } from "react";
import Swal from "sweetalert2";
import {
  Plus, Trash2, Save, RefreshCw, Search, ShoppingCart,
  FileText, X, Package, Pencil
} from "lucide-react";

const API = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8778/api/v1").replace(/\/$/, "");
const blankLine = () => ({
  category: "Yarn", material_name: "", description: "",
  quantity: "", unit: "Kg", rate: "", product_id: ""
});
const blankForm = () => ({
  purchase_number: "", purchase_date: new Date().toISOString().slice(0, 10),
  supplier_id: "", supplier_name: "", mobile: "", gstin: "",
  supplier_bill_number: "", warehouse_id: "", freight: "0",
  other_charges: "0", payment_status: "unpaid", payment_method: "",
  remarks: "", lines: [blankLine()]
});
const money = n => Number(n || 0).toLocaleString("en-IN", {
  minimumFractionDigits: 2, maximumFractionDigits: 2
});
const getList = data => Array.isArray(data) ? data : data?.items || data?.results || [];

export default function PurchasesPage() {
  const [form, setForm] = useState(blankForm);
  const [suppliers, setSuppliers] = useState([]);
  const [products, setProducts] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [records, setRecords] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [activeTab, setActiveTab] = useState(() => {
    try {
      const saved = window.localStorage.getItem("kdk_purchase_active_tab");
      return saved === "register" ? "register" : "entry";
    } catch {
      return "entry";
    }
  });
  const [editReturnTab, setEditReturnTab] = useState("register");
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    try {
      window.localStorage.setItem("kdk_purchase_active_tab", activeTab);
    } catch {}
  }, [activeTab]);

  const request = async (path, options = {}) => {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.message || `Request failed (${response.status})`);
    return data;
  };

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [s, p, w, r] = await Promise.all([
        request("/lookups/suppliers"),
        request("/lookups/purchase-products"),
        request("/lookups/purchase-warehouses"),
        request("/purchase-entries")
      ]);
      setSuppliers(getList(s));
      setProducts(getList(p));
      setWarehouses(getList(w));
      setRecords(getList(r));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const lineTotal = line => Number(line.quantity || 0) * Number(line.rate || 0);
  const itemsTotal = useMemo(
    () => form.lines.reduce((sum, line) => sum + lineTotal(line), 0),
    [form.lines]
  );
  const grandTotal = itemsTotal + Number(form.freight || 0) + Number(form.other_charges || 0);

  const update = (key, value) => setForm(old => ({ ...old, [key]: value }));
  const updateLine = (index, key, value) => setForm(old => ({
    ...old,
    lines: old.lines.map((line, i) => i === index ? { ...line, [key]: value } : line)
  }));
  const addLine = () => update("lines", [...form.lines, blankLine()]);
  const removeLine = index => update("lines", form.lines.filter((_, i) => i !== index));

  const chooseSupplier = id => {
    const supplier = suppliers.find(x => String(x.id) === String(id));
    setForm(old => ({
      ...old,
      supplier_id: id,
      supplier_name: supplier?.name || "",
      mobile: supplier?.mobile || "",
      gstin: supplier?.gstin || ""
    }));
  };

  const chooseProduct = (index, id) => {
    const product = products.find(x => String(x.id) === String(id));
    setForm(old => ({
      ...old,
      lines: old.lines.map((line, i) => i === index
        ? { ...line, product_id: id, material_name: product?.name || line.material_name }
        : line)
    }));
  };

  const reset = () => {
    const destination = editingId ? editReturnTab : "entry";
    setForm(blankForm());
    setEditingId(null);
    setError("");
    setActiveTab(destination);
  };

  const save = async event => {
    event.preventDefault();
    setError("");
    if (!form.purchase_number.trim()) return setError("Enter the Purchase Number.");
    if (!form.supplier_name.trim()) return setError("Enter the Supplier / Business Name.");
    if (!form.lines.length || form.lines.some(x => !x.material_name.trim() || Number(x.quantity) <= 0 || Number(x.rate) < 0))
      return setError("Enter a material name, valid quantity and rate for every item.");

    const payload = {
      ...form,
      supplier_id: form.supplier_id ? Number(form.supplier_id) : null,
      warehouse_id: form.warehouse_id ? Number(form.warehouse_id) : null,
      freight: Number(form.freight || 0),
      other_charges: Number(form.other_charges || 0),
      lines: form.lines.map(line => ({
        ...line,
        product_id: line.product_id ? Number(line.product_id) : null,
        quantity: Number(line.quantity),
        rate: Number(line.rate),
        amount: lineTotal(line)
      }))
    };

    const confirmation = await Swal.fire({
      title: editingId ? "Update Purchase?" : "Save Purchase?",
      text: editingId
        ? "Do you want to update this purchase entry?"
        : "Do you want to save this purchase entry?",
      icon: "question",
      showCancelButton: true,
      confirmButtonText: editingId ? "Yes, Update" : "Yes, Save",
      cancelButtonText: "Cancel",
      reverseButtons: true
    });

    if (!confirmation.isConfirmed) return;

    setSaving(true);
    try {
      await request(editingId ? `/purchase-entries/${editingId}` : "/purchase-entries", {
        method: editingId ? "PUT" : "POST",
        body: JSON.stringify(payload)
      });
      reset();
      await load();
      await Swal.fire({
        title: editingId ? "Purchase Updated!" : "Purchase Saved!",
        text: "The purchase entry has been saved successfully.",
        icon: "success",
        confirmButtonText: "OK"
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const editRecord = record => {
    setEditReturnTab(activeTab);
    setEditingId(record.id);
    setActiveTab("entry");
    setForm({
      ...blankForm(),
      ...record,
      supplier_id: record.supplier_id ? String(record.supplier_id) : "",
      warehouse_id: record.warehouse_id ? String(record.warehouse_id) : "",
      lines: (record.lines || []).map(line => ({
        ...blankLine(), ...line,
        product_id: line.product_id ? String(line.product_id) : ""
      }))
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const deleteRecord = async record => {
    const confirmation = await Swal.fire({
      title: "Delete Purchase?",
      text: `Delete purchase ${record.purchase_number}? This removes the purchase entry and its item rows. Inventory will not be changed.`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Yes, Delete",
      cancelButtonText: "Cancel",
      confirmButtonColor: "#d33",
      reverseButtons: true
    });
    if (!confirmation.isConfirmed) return;

    setDeletingId(record.id);
    setError("");
    try {
      await request(`/purchase-entries/${record.id}`, { method: "DELETE" });
      if (editingId === record.id) {
        setForm(blankForm());
        setEditingId(null);
      }
      await load();
      await Swal.fire({
        title: "Purchase Deleted",
        text: `${record.purchase_number} was deleted successfully.`,
        icon: "success",
        confirmButtonText: "OK"
      });
    } catch (e) {
      setError(e.message);
      await Swal.fire({
        title: "Could Not Delete Purchase",
        text: e.message || "An unexpected error occurred.",
        icon: "error",
        confirmButtonText: "OK"
      });
    } finally {
      setDeletingId(null);
    }
  };

  const filtered = records.filter(record => {
    const q = search.toLowerCase();
    return !q || [
      record.purchase_number, record.supplier_name,
      record.supplier_bill_number, record.purchase_date
    ].some(value => String(value || "").toLowerCase().includes(q));
  });

  const field = (label, name, type = "text", optional = false) => (
    <label>{label}{optional && <small>Optional</small>}
      <input type={type} value={form[name] ?? ""} onChange={e => update(name, e.target.value)} />
    </label>
  );

  return (
    <div className="purchases-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">FACTORY OPERATIONS</div>
          <h1>Purchase Management</h1>
          <p>Record materials and items purchased for the factory.</p>
        </div>
        <button className="secondary-button" onClick={load} disabled={loading}>
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      <div className="purchase-tabs">
        <button type="button" className={`purchase-tab ${activeTab === "entry" ? "active" : ""}`}
          onClick={() => setActiveTab("entry")}>
          <ShoppingCart size={15}/> Purchase Entry
        </button>
        <button type="button" className={`purchase-tab ${activeTab === "register" ? "active" : ""}`}
          onClick={() => setActiveTab("register")}>
          <FileText size={15}/> Purchase Register
        </button>
      </div>

      {activeTab === "entry" && (
      <form className="panel purchase-form" onSubmit={save}>
        <div className="panel-heading">
          <div><h3>{editingId ? "Edit Purchase Entry" : "New Factory Purchase"}</h3>
            <p>Enter supplier details and the materials purchased.</p></div>
          <Package size={19} className="panel-heading-icon"/>
        </div>

        {error && <div className="orders-error"><span>{error}</span><button type="button" onClick={() => setError("")}><X size={15}/></button></div>}

        <section className="purchase-section">
          <h3>Purchase Information</h3>
          <div className="purchase-fields">
            {field("Purchase No. *", "purchase_number")}
            {field("Purchase Date *", "purchase_date", "date")}
            <label>Supplier / Business Name *
              <input list="purchase-suppliers" value={form.supplier_name}
                onChange={e => {
                  const match = suppliers.find(x => x.name === e.target.value);
                  setForm(old => ({ ...old, supplier_name: e.target.value,
                    supplier_id: match ? String(match.id) : "",
                    mobile: match?.mobile || old.mobile,
                    gstin: match?.gstin || old.gstin }));
                }} placeholder="Select or enter supplier"/>
              <datalist id="purchase-suppliers">{suppliers.map(x => <option key={x.id} value={x.name}/>)}</datalist>
            </label>
            {field("Mobile Number", "mobile", "tel", true)}
            {field("GSTIN", "gstin", "text", true)}
            {field("Supplier Bill Number", "supplier_bill_number")}
          </div>
        </section>

        <section className="purchase-section">
          <div className="purchase-section-title">
            <div><h3>Material / Items Purchased</h3><p>Add all materials included in this purchase bill.</p></div>
            <button type="button" className="secondary-button" onClick={addLine}><Plus size={15}/> Add Item</button>
          </div>
          {form.lines.map((line, index) => (
            <div className="purchase-line" key={index}>
              <div className="purchase-line-top">
                <strong>Item {index + 1}</strong>
                {form.lines.length > 1 && <button type="button" className="remove-line" onClick={() => removeLine(index)}><Trash2 size={15}/></button>}
              </div>
              <div className="purchase-fields purchase-item-fields">
                <label>Material Category
                  <select value={line.category} onChange={e => updateLine(index, "category", e.target.value)}>
                    {["Yarn","Fabric","Chemicals","Packing","Accessories","Other"].map(x => <option key={x}>{x}</option>)}
                  </select>
                </label>
                <label>Material Name
                  <input list={`purchase-products-${index}`} value={line.material_name}
                    onChange={e => updateLine(index, "material_name", e.target.value)}
                    placeholder="Select existing or enter new material"/>
                  <datalist id={`purchase-products-${index}`}>{products.map(x => <option key={x.id} value={x.name}/>)}</datalist>
                </label>
                <label>Description / Specification
                  <input value={line.description} onChange={e => updateLine(index, "description", e.target.value)} placeholder="Count, quality, colour, etc."/>
                </label>
                <label>Quantity
                  <input type="number" min="0.001" step="0.001" value={line.quantity} onChange={e => updateLine(index, "quantity", e.target.value)}/>
                </label>
                <label>Unit
                  <select value={line.unit} onChange={e => updateLine(index, "unit", e.target.value)}>
                    {["Kg","Cone","Meter","Metre","Pieces","Roll","Packet","Litre","Dozen","Other"].map(x => <option key={x}>{x}</option>)}
                  </select>
                </label>
                <label>Rate
                  <input type="number" min="0" step="0.0001" value={line.rate} onChange={e => updateLine(index, "rate", e.target.value)}/>
                </label>
                <label>Amount
                  <input readOnly value={money(lineTotal(line))}/>
                </label>
              </div>
            </div>
          ))}
        </section>

        <section className="purchase-section">
          <h3>Purchase Details</h3>
          <div className="purchase-fields">
            <label>Delivery Location / Warehouse
              <select value={form.warehouse_id} onChange={e => update("warehouse_id", e.target.value)}>
                <option value="">Select warehouse</option>
                {warehouses.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
            </label>
            {field("Transport Charges (Freight)", "freight", "number")}
            {field("Other Charges", "other_charges", "number")}
            <label>Payment Status
              <select value={form.payment_status} onChange={e => update("payment_status", e.target.value)}>
                <option value="unpaid">Unpaid</option><option value="paid">Paid</option><option value="partially_paid">Partially Paid</option>
              </select>
            </label>
            <label>Payment Method
              <select value={form.payment_method} onChange={e => update("payment_method", e.target.value)}>
                <option value="">Select method</option><option>Cash</option><option>Bank Transfer</option><option>UPI</option><option>Cheque</option><option>Other</option>
              </select>
            </label>
            <label className="purchase-wide">Remarks / Attachment
              <textarea value={form.remarks} onChange={e => update("remarks", e.target.value)} rows="3" placeholder="Optional remarks or attachment details"/>
            </label>
          </div>
        </section>

        <div className="purchase-total">
          <div><span>Items Total</span><strong>₹ {money(itemsTotal)}</strong></div>
          <div><span>Transport Charges + Other Charges</span><strong>₹ {money(Number(form.freight || 0) + Number(form.other_charges || 0))}</strong></div>
          <div className="purchase-grand"><span>Grand Total</span><strong>₹ {money(grandTotal)}</strong></div>
        </div>

        <div className="purchase-actions">
          {editingId && <button type="button" className="secondary-button" onClick={reset}>Cancel Edit</button>}
          <button type="submit" className="primary-button" disabled={saving}><Save size={16}/>{saving ? "Saving..." : "Save Purchase"}</button>
        </div>
      </form>
      )}

      {activeTab === "register" && (
      <section className="panel purchase-register">
        <div className="panel-heading">
          <div><h3>Purchase Register</h3><p>Saved factory purchase entries.</p></div>
          <span className="purchase-count">{filtered.length} records</span>
        </div>
        <div className="purchase-toolbar">
          <div className="purchase-search"><Search size={15}/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search purchase no., supplier or bill no."/></div>
        </div>
        <div className="table-wrap">
          <table className="purchase-table">
            <thead><tr><th>PURCHASE NO.</th><th>DATE</th><th>SUPPLIER</th><th>BILL NO.</th><th>ITEMS</th><th>GRAND TOTAL</th><th>PAYMENT</th><th>ACTION</th></tr></thead>
            <tbody>
              {filtered.map(record => <tr key={record.id}>
                <td><strong>{record.purchase_number}</strong></td>
                <td>{record.purchase_date}</td>
                <td>{record.supplier_name}</td>
                <td>{record.supplier_bill_number || "—"}</td>
                <td>{record.lines?.length || 0}</td>
                <td>₹ {money(record.grand_total)}</td>
                <td><span className={`order-status status-${record.payment_status || "unpaid"}`}>{(record.payment_status || "unpaid").replace("_"," ").toUpperCase()}</span></td>
                <td>
                  <div className="purchase-row-actions">
                    <button type="button" className="purchase-edit-btn"
                      onClick={() => editRecord(record)} title="Edit purchase">
                      <Pencil size={14}/> Edit
                    </button>
                    <button type="button" className="purchase-delete-btn"
                      onClick={() => deleteRecord(record)}
                      disabled={deletingId === record.id} title="Delete purchase">
                      <Trash2 size={14}/> {deletingId === record.id ? "Deleting..." : "Delete"}
                    </button>
                  </div>
                </td>
              </tr>)}
            </tbody>
          </table>
          {!filtered.length && <div className="empty-state"><div className="empty-icon"><FileText size={22}/></div><strong>{loading ? "Loading purchases..." : "No purchase entries found"}</strong><p>Saved factory purchases will appear here.</p></div>}
        </div>
      </section>
      )}
    </div>
  );
}
