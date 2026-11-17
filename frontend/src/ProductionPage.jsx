import React, { useCallback, useEffect, useState } from "react";
import Swal from "sweetalert2";
import {
  Activity, RefreshCw, Save, Factory, Gauge, Ruler, Hash,
  Clock3, UserRound, CalendarClock, ChevronRight, Package,
  Plus, Trash2, ClipboardList
} from "lucide-react";

const API = (
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8778/api/v1"
).replace(/\/$/, "");

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const fmt = value => Number(value || 0).toLocaleString("en-IN", {
  maximumFractionDigits: 3
});

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(API + path, { ...options, headers });
  } catch (error) {
    throw new Error(`Cannot connect to Production API at ${API}.`);
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

function Metric({ title, total, target, achievement, unit, icon: Icon }) {
  return (
    <div className="production-metric">
      <div className="production-metric-top">
        <span>{title}</span><Icon size={19} />
      </div>
      <strong>{fmt(total)} <small>{unit}</small></strong>
      <div className="production-metric-bottom">
        <span>Target: {fmt(target)} {unit}</span>
        <b>{fmt(achievement)}% achieved</b>
      </div>
    </div>
  );
}

function displayDateTime(value) {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: true
  });
}

function JobDetails({ job, title }) {
  if (!job) {
    return <div className="production-machine-no-job">{title}: No allocation</div>;
  }
  return (
    <div className="production-job-block">
      <div className="production-job-heading">{title}</div>
      <div className="production-job-order">
        <small>Customer Order Number</small>
        <strong>{job.order_number || "Order number unavailable"}</strong>
        <span>Customer: {job.customer_name || "Customer not assigned"}</span>
      </div>
      <div className="production-job-product">
        <small>Product Name</small><br />
        {job.product_description || "Product description unavailable"}
        {job.design_code ? ` · Design ${job.design_code}` : ""}
      </div>
      <div className="production-job-grid">
        <div><small>Delivery date</small><strong>{job.delivery_date || "Not set"}</strong></div>
        <div><small>Labour Name</small><strong>{job.worker_name || "Not assigned"}</strong></div>
        <div><small>Shift</small><strong>{job.shift_name || "Not assigned"}</strong></div>
        <div><small>Shift starts</small><strong>{displayDateTime(job.starts_at)}</strong></div>
        <div><small>Shift ends</small><strong>{displayDateTime(job.ends_at)}</strong></div>
      </div>
      <div className="production-quantity-track">
        <div>
          <span>Produced Quantity / Order Quantity</span>
          <strong>{fmt(job.order_produced_qty)} / {fmt(job.ordered_qty)} {job.uom_code || ""}</strong>
        </div>
        <div className="production-progress-bar">
          <span style={{
            width: `${Math.min(100, job.ordered_qty > 0
              ? (Number(job.order_produced_qty || 0) / Number(job.ordered_qty)) * 100
              : 0)}%`
          }} />
        </div>
        <div className="production-quantity-foot">
          <span>Pending Order Quantity: {fmt(job.order_pending_qty)} {job.uom_code || ""}</span>
          <span>Pending Plan Quantity: {fmt(job.plan_pending_qty)} {job.uom_code || ""}</span>
        </div>
      </div>
      <div className="production-spec-line">
        <Package size={15} />
        <span>
          {[job.material, job.colour, job.shade_code,
            job.width_mm ? `${job.width_mm} mm` : null,
            job.gsm ? `${job.gsm} GSM` : null]
            .filter(Boolean).join(" · ") || "Product specifications not entered"}
        </span>
      </div>
    </div>
  );
}


function localDateTimeValue() {
  const date = new Date();
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function MachineRPMPanel() {
  const [machines, setMachines] = useState([]);
  const [machineFilter, setMachineFilter] = useState("");
  const [range, setRange] = useState("6");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [standardMachine, setStandardMachine] = useState("");
  const [standardValue, setStandardValue] = useState("");
  const [newMachineName, setNewMachineName] = useState("");
  const [newMachineStandardRPM, setNewMachineStandardRPM] = useState("");
  const [readingMachine, setReadingMachine] = useState("");
  const [actualRPM, setActualRPM] = useState("");
  const [recordedAt, setRecordedAt] = useState(localDateTimeValue());
  const [readings, setReadings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const machineLabel = id => {
    const index = machines.findIndex(item => item.id === Number(id));
    if (index < 0) return "Machine";
    const machine = machines[index];
    // Keep QA fixture names generic; show names entered for real factory machines.
    if (String(machine.code || "").startsWith("QA-LOOM")) {
      return `Machine ${index + 1}`;
    }
    return machine.name || `Machine ${index + 1}`;
  };

  async function loadMachines() {
    const data = await request("/production/rpm/lookups");
    setMachines(data.machines || []);
  }

  async function loadReadings() {
    setLoading(true);
    setError("");

    if (!machineFilter) {
      setReadings([]);
      setLoading(false);
      return;
    }

    try {
      const params = new URLSearchParams();
      if (machineFilter) params.set("machine_id", machineFilter);

      if (range === "custom") {
        if (customFrom) params.set("from_at", new Date(customFrom).toISOString());
        if (customTo) params.set("to_at", new Date(customTo).toISOString());
      } else {
        const hours = Number(range || 6);
        params.set("from_at", new Date(Date.now() - hours * 3600000).toISOString());
        params.set("to_at", new Date().toISOString());
      }

      const data = await request(`/production/rpm/readings?${params.toString()}`);
      setReadings(data);
    } catch (err) {
      setError(err.message || "Could not load RPM readings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMachines().catch(err => setError(err.message || "Could not load machines."));
  }, []);

  useEffect(() => {
    loadReadings();
  }, [machineFilter, range, customFrom, customTo]);

  async function refreshReport() {
    await loadMachines();
    await loadReadings();
  }

  useEffect(() => {
    const selected = machines.find(item => String(item.id) === standardMachine);
    setStandardValue(selected?.standard_rpm == null ? "" : String(selected.standard_rpm));
  }, [standardMachine, machines]);

  const selectedReadingMachine = machines.find(
    item => String(item.id) === readingMachine
  );
  const standardForReading = Number(selectedReadingMachine?.standard_rpm || 0);
  const preview = standardForReading > 0 && Number(actualRPM) > 0
    ? (Number(actualRPM) / standardForReading * 100).toFixed(2)
    : "";

  const machineReports = machines
    .filter(machine => machineFilter && String(machine.id) === machineFilter)
    .map(machine => {
      const machineReadings = readings.filter(
        reading => Number(reading.machine_id) === Number(machine.id)
      );
      const performances = machineReadings.map(
        reading => Number(reading.performance_percent)
      );
      const average = performances.length
        ? performances.reduce((sum, value) => sum + value, 0) / performances.length
        : null;

      return {
        machine,
        readings: machineReadings,
        count: machineReadings.length,
        latest: machineReadings[0] || null,
        average,
        highest: performances.length ? Math.max(...performances) : null,
        lowest: performances.length ? Math.min(...performances) : null,
      };
    });

  async function saveNewMachine(event) {
    event.preventDefault();
    setError("");
    setNotice("");

    if (!newMachineName.trim()) {
      await Swal.fire({
        icon: "warning",
        title: "Machine name required",
        text: "Enter a machine name before adding the machine.",
        confirmButtonColor: "#287a52"
      });
      return;
    }
    if (!newMachineStandardRPM || Number(newMachineStandardRPM) <= 0) {
      await Swal.fire({
        icon: "warning",
        title: "Standard RPM required",
        text: "Enter a Standard RPM greater than zero.",
        confirmButtonColor: "#287a52"
      });
      return;
    }

    const addedName = newMachineName.trim();
    setSaving(true);
    try {
      const created = await request("/production/rpm/machines", {
        method: "POST",
        body: JSON.stringify({
          machine_name: addedName,
          standard_rpm: String(newMachineStandardRPM)
        })
      });

      await loadMachines();
      setNewMachineName("");
      setNewMachineStandardRPM("");

      await Swal.fire({
        icon: "success",
        title: "Machine added successfully",
        text: `${addedName} has been registered. You can now enter its Actual RPM to view speed performance against its Standard RPM.`,
        confirmButtonText: "OK",
        confirmButtonColor: "#287a52"
      });
    } catch (err) {
      setError("");
      await Swal.fire({
        icon: "error",
        title: "Could not add machine",
        text: err.message || "Machine registration failed.",
        confirmButtonColor: "#287a52"
      });
    } finally {
      setSaving(false);
    }
  }

  async function saveStandard(event) {
    event.preventDefault();
    setError("");
    setNotice("");

    if (!standardMachine || !standardValue || Number(standardValue) <= 0) {
      await Swal.fire({
        icon: "warning",
        title: "Invalid Standard RPM",
        text: "Select a machine and enter a Standard RPM greater than zero.",
        confirmButtonColor: "#287a52"
      });
      return;
    }

    const selectedMachineName = machineLabel(standardMachine);
    const savedRPM = String(standardValue);
    setSaving(true);
    try {
      await request(`/production/rpm/machines/${standardMachine}/standard`, {
        method: "PUT",
        body: JSON.stringify({ standard_rpm: savedRPM })
      });
      await loadMachines();

      await Swal.fire({
        icon: "success",
        title: "Machine Standard RPM updated",
        text: `${selectedMachineName} Standard RPM has been updated to ${savedRPM} RPM.`,
        confirmButtonText: "OK",
        confirmButtonColor: "#287a52"
      });
    } catch (err) {
      setError("");
      await Swal.fire({
        icon: "error",
        title: "Could not update Standard RPM",
        text: err.message || "The machine Standard RPM could not be updated.",
        confirmButtonColor: "#287a52"
      });
    } finally {
      setSaving(false);
    }
  }

  async function saveReading(event) {
    event.preventDefault();
    setError("");
    setNotice("");

    if (!readingMachine || !actualRPM || Number(actualRPM) <= 0) {
      await Swal.fire({
        icon: "warning",
        title: "Actual RPM required",
        text: "Select a machine and enter an Actual RPM greater than zero.",
        confirmButtonColor: "#287a52"
      });
      return;
    }
    if (!standardForReading) {
      await Swal.fire({
        icon: "warning",
        title: "Standard RPM not set",
        text: "Set the machine's Standard RPM before recording a reading.",
        confirmButtonColor: "#287a52"
      });
      return;
    }

    const selectedMachineName = machineLabel(readingMachine);
    const savedActualRPM = String(actualRPM);
    setSaving(true);
    try {
      await request("/production/rpm/readings", {
        method: "POST",
        body: JSON.stringify({
          machine_id: Number(readingMachine),
          recorded_at: new Date(recordedAt).toISOString(),
          actual_rpm: savedActualRPM
        })
      });
      setActualRPM("");
      setRecordedAt(localDateTimeValue());
      await loadReadings();

      await Swal.fire({
        icon: "success",
        title: "RPM reading saved",
        text: `${selectedMachineName} Actual RPM of ${savedActualRPM} has been recorded successfully.`,
        confirmButtonText: "OK",
        confirmButtonColor: "#287a52"
      });
    } catch (err) {
      setError("");
      await Swal.fire({
        icon: "error",
        title: "Could not save RPM reading",
        text: err.message || "The RPM reading could not be saved.",
        confirmButtonColor: "#287a52"
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel production-rpm-panel">
      <div className="production-section-title">
        <div>
          <h2><Gauge size={19} /> Machine RPM & Speed Performance</h2>
          <p>Set each machine's standard speed, enter actual readings and review performance.</p>
        </div>
      </div>

      {error && <div className="production-rpm-message is-error">{error}</div>}
      {notice && <div className="production-rpm-message is-success">{notice}</div>}

      {machines.length === 0 ? (
        <div className="production-empty">No active machines are configured.</div>
      ) : (
        <>
          <div className="production-rpm-grid">
            <form className="production-rpm-card" onSubmit={saveNewMachine}>
              <h3>1. Machine Setup</h3>
              <p>Register each factory machine once with its name and standard speed.</p>
              <label>
                Machine Name
                <input type="text" maxLength="100"
                  value={newMachineName}
                  onChange={event => setNewMachineName(event.target.value)}
                  placeholder="Enter machine name or number" required />
              </label>
              <label>
                Standard RPM
                <input type="number" min="0.01" step="0.01"
                  value={newMachineStandardRPM}
                  onChange={event => setNewMachineStandardRPM(event.target.value)}
                  placeholder="Enter standard RPM" required />
              </label>
              <div className="production-rpm-hint">
                Factory branch and internal machine code are assigned automatically.
              </div>
              <button className="primary-button" type="submit" disabled={saving}>
                <Plus size={15} /> Add Machine
              </button>
            </form>
            <form className="production-rpm-card" onSubmit={saveStandard}>
              <h3>2. Edit Machine Standard RPM</h3>
              <p>Enter the normal RPM specified for each machine.</p>
              <label>
                Machine
                <select value={standardMachine}
                  onChange={event => setStandardMachine(event.target.value)} required>
                  <option value="">Select Machine</option>
                  {machines.map(machine => (
                    <option key={machine.id} value={machine.id}>{machineLabel(machine.id)}</option>
                  ))}
                </select>
              </label>
              <label>
                Standard RPM
                <input type="number" min="0.01" step="0.01"
                  value={standardValue}
                  onChange={event => setStandardValue(event.target.value)}
                  placeholder="Enter standard RPM" required />
              </label>
              <button className="primary-button" type="submit" disabled={saving}>
                <Save size={15} /> Save Standard RPM
              </button>
              <div className="production-rpm-hint">
                {machines.find(item => String(item.id) === standardMachine)?.standard_rpm
                  ? `Current setting: ${fmt(machines.find(item => String(item.id) === standardMachine).standard_rpm)} RPM`
                  : "Standard RPM has not been entered for this machine."}
              </div>
            </form>

            <form className="production-rpm-card" onSubmit={saveReading}>
              <h3>3. Record Actual RPM</h3>
              <p>Enter the reading shown on the machine.</p>
              <label>
                Machine
                <select value={readingMachine}
                  onChange={event => setReadingMachine(event.target.value)} required>
                  <option value="">Select Machine</option>
                  {machines.map(machine => (
                    <option key={machine.id} value={machine.id}>{machineLabel(machine.id)}</option>
                  ))}
                </select>
              </label>
              <label>
                Reading Date & Time
                <input type="datetime-local" value={recordedAt}
                  onChange={event => setRecordedAt(event.target.value)} required />
              </label>
              <label>
                Actual RPM
                <input type="number" min="0.01" step="0.01"
                  value={actualRPM}
                  onChange={event => setActualRPM(event.target.value)}
                  placeholder="Enter actual RPM" required />
              </label>
              <div className="production-rpm-preview">
                <span>Standard: {standardForReading ? `${fmt(standardForReading)} RPM` : "Not set"}</span>
                <strong>{preview ? `${preview}% speed performance` : "Performance will calculate automatically"}</strong>
              </div>
              <button className="primary-button" type="submit" disabled={saving}>
                <Save size={15} /> Save RPM Reading
              </button>
            </form>
          </div>

          <div className="production-rpm-history">
            <div className="production-rpm-history-heading">
              <div>
                <h3>RPM Report Filters</h3>
                <p>Choose a machine and time period to view its report below.</p>
              </div>
              <button type="button" className="secondary-button"
                onClick={refreshReport} disabled={loading}>
                <RefreshCw size={14} /> Refresh
              </button>
            </div>
            <div className="production-rpm-filters">
              <label>
                Machine
                <select value={machineFilter}
                  onChange={event => setMachineFilter(event.target.value)}>
                  <option value="">Select Machine</option>
                  {machines.map(machine => (
                    <option key={machine.id} value={machine.id}>{machineLabel(machine.id)}</option>
                  ))}
                </select>
              </label>
              <label>
                Time range
                <select value={range} onChange={event => setRange(event.target.value)}>
                  <option value="6">Last 6 hours</option>
                  <option value="24">Last 24 hours</option>
                  <option value="168">Last 7 days</option>
                  <option value="custom">Custom date & time</option>
                </select>
              </label>
              {range === "custom" && (
                <>
                  <label>From<input type="datetime-local" value={customFrom}
                    onChange={event => setCustomFrom(event.target.value)} /></label>
                  <label>To<input type="datetime-local" value={customTo}
                    onChange={event => setCustomTo(event.target.value)} /></label>
                </>
              )}
            </div>

            {loading && (
              <div className="production-empty">Loading RPM report...</div>
            )}

            <section className="production-machine-reports">
              <div className="production-machine-reports-heading">
                <div>
                  <h3>Machine-wise RPM Report</h3>
                  <p>Individual machine statistics for the selected time period.</p>
                </div>
              </div>

              {!machineFilter ? (
                <div className="production-empty">Select a machine to view its RPM report.</div>
              ) : machineReports.length === 0 ? (
                <div className="production-empty">The selected machine is not available. Refresh the machine list.</div>
              ) : (
                <div className="production-machine-report-list">
                  {machineReports.map(report => (
                    <details className="production-machine-report" key={report.machine.id}>
                      <summary>
                        <span className="production-machine-report-name">
                          {machineLabel(report.machine.id)}
                        </span>
                        <span className="production-machine-report-summary">
                          {report.count} {report.count === 1 ? "reading" : "readings"}
                          {report.latest
                            ? ` · Latest ${fmt(report.latest.performance_percent)}%`
                            : " · No readings"}
                        </span>
                      </summary>

                      {report.count === 0 ? (
                        <div className="production-empty">
                          No RPM readings found for this machine in the selected period.
                        </div>
                      ) : (
                        <>
                          <div className="production-machine-report-stats">
                            <div>
                              <span>Standard RPM</span>
                              <strong>{fmt(report.latest.standard_rpm)} RPM</strong>
                            </div>
                            <div>
                              <span>Latest Actual RPM</span>
                              <strong>{fmt(report.latest.actual_rpm)} RPM</strong>
                            </div>
                            <div>
                              <span>Latest Performance</span>
                              <strong>{fmt(report.latest.performance_percent)}%</strong>
                            </div>
                            <div>
                              <span>Average Performance</span>
                              <strong>{fmt(report.average)}%</strong>
                            </div>
                            <div>
                              <span>Highest Performance</span>
                              <strong>{fmt(report.highest)}%</strong>
                            </div>
                            <div>
                              <span>Lowest Performance</span>
                              <strong>{fmt(report.lowest)}%</strong>
                            </div>
                            <div>
                              <span>Total Readings</span>
                              <strong>{report.count}</strong>
                            </div>
                          </div>

                          <div className="table-wrap production-machine-report-table">
                            <table>
                              <thead>
                                <tr>
                                  <th>DATE & TIME</th>
                                  <th>STANDARD RPM</th>
                                  <th>ACTUAL RPM</th>
                                  <th>PERFORMANCE</th>
                                </tr>
                              </thead>
                              <tbody>
                                {report.readings.map(reading => (
                                  <tr key={reading.id}>
                                    <td>{displayDateTime(reading.recorded_at)}</td>
                                    <td>{fmt(reading.standard_rpm)}</td>
                                    <td>{fmt(reading.actual_rpm)}</td>
                                    <td>
                                      <span className={`production-achievement ${
                                        Number(reading.performance_percent) >= 100 ? "is-good" : ""
                                      }`}>{fmt(reading.performance_percent)}%</span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}
                    </details>
                  ))}
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </section>
  );
}

export default function ProductionPage() {
  const [lookups, setLookups] = useState({ machines: [], shifts: [] });
  const [entries, setEntries] = useState([]);
  const [machineOverview, setMachineOverview] = useState({
    machines: [], machine_count: 0, running_count: 0,
    scheduled_count: 0, idle_count: 0
  });
  const [selectedMachineId, setSelectedMachineId] = useState(null);
  const [recipeLookups, setRecipeLookups] = useState({
    finished_products: [], materials: [], stock_stages: []
  });
  const [recipes, setRecipes] = useState([]);
  const [recipeSaving, setRecipeSaving] = useState(false);
  const [recipeEditing, setRecipeEditing] = useState(null);
  const [recipeForm, setRecipeForm] = useState({
    product_id: "",
    recipe_code: "",
    design_code: "",
    basis_quantity: "1",
    basis_uom_code: "metres",
    notes: "",
    lines: [{
      material_product_id: "",
      stock_stage_id: "",
      quantity_per_basis: "",
      quantity_uom_code: "kg",
      wastage_percent: "0",
      notes: ""
    }]
  });
  const [summary, setSummary] = useState({
    totals: {
      metres: { target: 0, actual: 0, achievement_percent: 0 },
      pieces: { target: 0, actual: 0, achievement_percent: 0 }
    },
    by_machine: [],
    entry_count: 0
  });
  const [workDate, setWorkDate] = useState(today());
  const [form, setForm] = useState({
    machine_id: "",
    shift_id: "",
    work_date: today(),
    unit_code: "metres",
    target_output: "",
    actual_output: "",
    notes: ""
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = `?date_from=${workDate}&date_to=${workDate}`;
      const [
        lookupData, entryData, summaryData, machineData,
        recipeLookupData, recipeData
      ] = await Promise.all([
        request("/production/lookups"),
        request(`/production/entries${query}`),
        request(`/production/summary${query}`),
        request("/production/machine-overview"),
        request("/production/recipes/lookups"),
        request("/production/recipes")
      ]);
      setLookups(lookupData);
      setEntries(entryData);
      setSummary(summaryData);
      setMachineOverview(machineData);
      setRecipeLookups(recipeLookupData);
      setRecipes(recipeData);
      setSelectedMachineId(previous => {
        if (previous && machineData.machines.some(item => item.machine_id === previous)) {
          return previous;
        }
        return machineData.machines[0]?.machine_id ?? null;
      });

      setForm(previous => ({
        ...previous,
        machine_id: previous.machine_id || String(lookupData.machines[0]?.id || ""),
        shift_id: previous.shift_id || String(lookupData.shifts[0]?.id || ""),
        work_date: workDate
      }));
    } catch (err) {
      setError(err.message || "Could not load production data.");
    } finally {
      setLoading(false);
    }
  }, [workDate]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  function update(key, value) {
    setForm(previous => ({ ...previous, [key]: value }));
  }

  async function saveEntry(event) {
    event.preventDefault();
    setError("");
    setNotice("");

    if (!form.machine_id || !form.shift_id) {
      setError("Please configure at least one active machine and shift first.");
      return;
    }
    if (!form.target_output || Number(form.target_output) <= 0) {
      setError("Enter a target greater than zero.");
      return;
    }
    if (form.actual_output === "" || Number(form.actual_output) < 0) {
      setError("Enter actual output. Zero is allowed.");
      return;
    }

    setSaving(true);
    try {
      await request("/production/entries", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          machine_id: Number(form.machine_id),
          shift_id: Number(form.shift_id),
          target_output: String(form.target_output),
          actual_output: String(form.actual_output),
          notes: form.notes.trim() || null
        })
      });
      setNotice("Shift production saved successfully.");
      setForm(previous => ({
        ...previous,
        target_output: "",
        actual_output: "",
        notes: ""
      }));
      await loadData();
    } catch (err) {
      setError(err.message || "Could not save production entry.");
    } finally {
      setSaving(false);
    }
  }

  function updateRecipe(key, value) {
    setRecipeForm(previous => ({ ...previous, [key]: value }));
  }

  function updateRecipeLine(index, key, value) {
    setRecipeForm(previous => ({
      ...previous,
      lines: previous.lines.map((line, i) =>
        i === index ? { ...line, [key]: value } : line
      )
    }));
  }

  function addRecipeLine() {
    setRecipeForm(previous => ({
      ...previous,
      lines: [...previous.lines, {
        material_product_id: "",
        stock_stage_id: "",
        quantity_per_basis: "",
        quantity_uom_code: "kg",
        wastage_percent: "0",
        notes: ""
      }]
    }));
  }

  function removeRecipeLine(index) {
    setRecipeForm(previous => ({
      ...previous,
      lines: previous.lines.filter((_, i) => i !== index)
    }));
  }

  function resetRecipeForm() {
    setRecipeEditing(null);
    setRecipeForm({
      product_id: "",
      recipe_code: "",
      design_code: "",
      basis_quantity: "1",
      basis_uom_code: "metres",
      notes: "",
      lines: [{
        material_product_id: "",
        stock_stage_id: "",
        quantity_per_basis: "",
        quantity_uom_code: "kg",
        wastage_percent: "0",
        notes: ""
      }]
    });
  }

  function startRecipeVersion(recipe) {
    setRecipeEditing(recipe.id);
    setRecipeForm({
      product_id: String(recipe.product_id),
      recipe_code: recipe.recipe_code,
      design_code: recipe.design_code || "",
      basis_quantity: String(recipe.basis_quantity),
      basis_uom_code: recipe.basis_uom_code,
      notes: recipe.notes || "",
      lines: recipe.lines.map(line => ({
        material_product_id: String(line.material_product_id),
        stock_stage_id: String(line.stock_stage_id),
        quantity_per_basis: String(line.quantity_per_basis),
        quantity_uom_code: line.quantity_uom_code,
        wastage_percent: String(line.wastage_percent ?? 0),
        notes: line.notes || ""
      }))
    });
    setNotice(`Creating a new version of ${recipe.recipe_code}. Previous version will be preserved.`);
    setError("");
    document.getElementById("production-recipe-editor")?.scrollIntoView({
      behavior: "smooth", block: "start"
    });
  }

  async function saveRecipe(event) {
    event.preventDefault();
    setError("");
    setNotice("");

    if (!recipeForm.product_id || !recipeForm.recipe_code.trim()) {
      setError("Select a finished product and enter a recipe code.");
      return;
    }
    if (!recipeForm.lines.length || recipeForm.lines.some(line =>
      !line.material_product_id || !line.stock_stage_id ||
      !line.quantity_per_basis || Number(line.quantity_per_basis) <= 0
    )) {
      setError("Complete the material, stock stage and positive quantity on every recipe line.");
      return;
    }

    const payload = {
      product_id: Number(recipeForm.product_id),
      recipe_code: recipeForm.recipe_code.trim(),
      design_code: recipeForm.design_code.trim() || null,
      basis_quantity: String(recipeForm.basis_quantity),
      basis_uom_code: recipeForm.basis_uom_code,
      notes: recipeForm.notes.trim() || null,
      lines: recipeForm.lines.map((line, index) => ({
        line_number: index + 1,
        material_product_id: Number(line.material_product_id),
        stock_stage_id: Number(line.stock_stage_id),
        quantity_per_basis: String(line.quantity_per_basis),
        quantity_uom_code: line.quantity_uom_code,
        wastage_percent: String(line.wastage_percent || "0"),
        notes: line.notes.trim() || null
      }))
    };

    setRecipeSaving(true);
    try {
      if (recipeEditing) {
        await request(`/production/recipes/${recipeEditing}/new-version`, {
          method: "POST",
          body: JSON.stringify(payload)
        });
        setNotice("New recipe version saved. The previous version remains preserved.");
      } else {
        await request("/production/recipes", {
          method: "POST",
          body: JSON.stringify(payload)
        });
        setNotice("Material recipe created successfully.");
      }
      const [recipeData, lookupData] = await Promise.all([
        request("/production/recipes"),
        request("/production/recipes/lookups")
      ]);
      setRecipes(recipeData);
      setRecipeLookups(lookupData);
      resetRecipeForm();
    } catch (err) {
      setError(err.message || "Could not save material recipe.");
    } finally {
      setRecipeSaving(false);
    }
  }

  const metres = summary.totals?.metres || {};
  const pieces = summary.totals?.pieces || {};

  return (
    <div className="production-page">
      <div className="production-heading">
        <div>
          <span className="production-eyebrow">FACTORY OUTPUT</span>
          <h1>Production Management</h1>
          <p>Monitor machine RPM and speed performance.</p>
        </div>
        <button className="secondary-button" onClick={loadData} disabled={loading}>
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      {error && <div className="production-alert production-alert-error">{error}</div>}
      {notice && <div className="production-alert production-alert-success">{notice}</div>}

      <MachineRPMPanel />

    </div>
  );
}
