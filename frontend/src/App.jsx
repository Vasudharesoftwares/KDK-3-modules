import React, { useEffect, useState } from "react";
import OrdersPage from "./OrdersPage.jsx";
import PlanningPage from "./PlanningPage.jsx";
import ProductionPage from "./ProductionPage.jsx";
import PurchasesPage from "./PurchasesPage.jsx";
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight,
  Bell, Boxes, CalendarDays, CheckCircle2, ChevronDown, ClipboardList,
  Clock3, Factory, Gauge, LayoutDashboard, Menu, Package, Plus,
  Search, Settings, ShoppingCart, Truck, Users, Waves, X, Cog,
  Layers3, ChartNoAxesCombined, CircleHelp, RefreshCw
} from "lucide-react";

const navigation = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { section: "OPERATIONS" },
  { id: "orders", label: "Order Management", icon: ClipboardList },
  { id: "purchases", label: "Purchase Management", icon: ShoppingCart },
  { id: "production", label: "Production Management", icon: Activity },
];

const moduleInfo = {
  orders: {
    title: "Order Management",
    subtitle: "Manage customer orders, designs, quantities and delivery commitments.",
    icon: ClipboardList,
    features: ["Customer and order details", "Design and fabric specifications", "Ordered quantity and unit", "Delivery deadline and priority", "Produced, approved and dispatched quantities"],
    columns: ["Order No.", "Customer", "Design / Fabric", "Order Qty.", "Deadline", "Priority", "Status"]
  },
  purchases: {
    title: "Purchase Management",
    subtitle: "Manage yarn procurement, suppliers, purchase orders and goods receipts.",
    icon: ShoppingCart,
    features: ["Supplier directory", "Yarn purchase requests", "Purchase orders", "Goods receipt notes (GRN)", "Ordered versus received quantities"],
    columns: ["PO No.", "Supplier", "Material", "Order Date", "Expected Date", "Status"]
  },
  production: {
    title: "Production Management",
    subtitle: "Record actual production by machine, shift, order and production stage.",
    icon: Activity,
    features: ["Shift-wise production entries", "Machine-wise output", "Order-wise production progress", "Wastage and rejected quantity", "Quality-approved output"],
    columns: ["Date", "Order No.", "Machine", "Shift", "Produced Qty.", "Wastage", "Approved Qty."]
  },
  machines: {
    title: "Machine Management",
    subtitle: "Monitor machine availability, capacity, downtime and operating efficiency.",
    icon: Cog,
    features: ["Machine register and type", "Machine operating status", "Production capacity", "Downtime records and reasons", "Machine-wise efficiency"],
    columns: ["Machine", "Machine Type", "Capacity", "Current Status", "Current Shift", "Downtime"]
  }
};

const metrics = [
  { label: "Active Orders", value: "—", note: "Awaiting order records", icon: ClipboardList },
  { label: "Pending Dispatch", value: "—", note: "Awaiting dispatch records", icon: Truck },
  { label: "Today's Production", value: "—", note: "Awaiting shift entries", icon: Activity },
  { label: "Running Machines", value: "—", note: "Awaiting machine status", icon: Factory }
];

function Sidebar({ active, onNavigate, mobileOpen, closeMobile }) {
  return (
    <>
      {mobileOpen && <div className="mobile-overlay" onClick={closeMobile} />}
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Waves size={25} /></div>
          <div>
            <div className="brand-name">KAY DEE KAY</div>
            <div className="brand-caption">MANUFACTURING ERP</div>
          </div>
          <button className="mobile-close" onClick={closeMobile}><X size={19} /></button>
        </div>

        <div className="factory-chip">
          <div className="factory-chip-icon"><Factory size={17} /></div>
          <div className="factory-chip-text">
            <strong>Factory Operations</strong>
            <span>Manufacturing workspace</span>
          </div>
          <ChevronDown size={15} />
        </div>

        <div className="nav-label">WORKSPACE</div>
        <nav className="navigation">
          {navigation.map((item, index) => {
            if (item.section) return <div className="nav-section" key={index}>{item.section}</div>;
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`nav-item ${active === item.id ? "active" : ""}`}
                onClick={() => { onNavigate(item.id); closeMobile(); }}
              >
                <Icon size={18} strokeWidth={1.8} />
                <span>{item.label}</span>
                {active === item.id && <span className="active-indicator" />}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-icon"><CircleHelp size={18} /></div>
            <strong>Factory workspace</strong>
            <span>Track orders from planning through production and dispatch.</span>
          </div>
          <button className="nav-item settings-link" onClick={() => onNavigate("settings")}>
            <Settings size={18} /><span>Settings</span>
          </button>
          <div className="user-profile">
            <div className="avatar">KD</div>
            <div className="user-details"><strong>KAY DEE KAY</strong><span>Factory workspace</span></div>
            <ChevronDown size={15} />
          </div>
        </div>
      </aside>
    </>
  );
}

function Header({ title, onMenu }) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="menu-button" onClick={onMenu}><Menu size={21} /></button>
        <div className="breadcrumb">Workspace <span>/</span> <strong>{title}</strong></div>
      </div>
      <div className="topbar-actions">
        <div className="system-status"><span className="status-dot" /> System workspace</div>
        <button className="icon-button" aria-label="Search"><Search size={19} /></button>
        <button className="icon-button notification-button" aria-label="Notifications">
          <Bell size={19} /><span />
        </button>
        <div className="top-avatar">KD</div>
      </div>
    </header>
  );
}

function PageHeading({ eyebrow, title, subtitle, action }) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {action}
    </div>
  );
}

function MetricCard({ item }) {
  const Icon = item.icon;
  return (
    <div className="metric-card">
      <div className="metric-top">
        <span>{item.label}</span>
        <div className="metric-icon"><Icon size={19} /></div>
      </div>
      <div className="metric-value">{item.value}</div>
      <div className="metric-note">{item.note}</div>
    </div>
  );
}

function EmptyState({ title, description }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Layers3 size={23} /></div>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

function Dashboard({ onNavigate }) {
  return (
    <>
      <PageHeading
        eyebrow="FACTORY OVERVIEW"
        title="Dashboard"
        subtitle="Your factory at a glance. Monitor orders, production, machines and inventory."
        action={<div className="date-pill"><CalendarDays size={16} /> Factory overview</div>}
      />

      <div className="metric-grid">
        {metrics.map((item) => <MetricCard key={item.label} item={item} />)}
      </div>

      <div className="section-heading">
        <div><h2>Production overview</h2><p>Actual machine and shift output will appear here.</p></div>
        <span className="live-label"><span /> Awaiting production entries</span>
      </div>

      <div className="production-grid">
        <div className="panel machine-panel">
          <div className="panel-heading">
            <div><h3>Machine production</h3><p>Output recorded by machine and shift</p></div>
            <Factory size={19} className="panel-heading-icon" />
          </div>
          <div className="machine-placeholder">
            <div className="machine-placeholder-icon"><Gauge size={25} /></div>
            <strong>No production entries yet</strong>
            <span>Once shift-wise output is recorded, machine performance will be shown here.</span>
            <button className="text-action" onClick={() => onNavigate("production")}>Open Production Management <ArrowRight size={15} /></button>
          </div>
        </div>

        <div className="panel alerts-panel">
          <div className="panel-heading">
            <div><h3>Factory alerts</h3><p>Items requiring attention</p></div>
            <Bell size={18} className="panel-heading-icon" />
          </div>
          <div className="alert-empty">
            <CheckCircle2 size={23} />
            <strong>No alerts to display</strong>
            <span>Order delays, material shortages and machine downtime alerts will appear here when records are available.</span>
          </div>
        </div>
      </div>

      <div className="section-heading recent-heading">
        <div><h2>Recent customer orders</h2><p>Follow order progress from booking to dispatch.</p></div>
        <button className="text-action" onClick={() => onNavigate("orders")}>View orders <ArrowRight size={15} /></button>
      </div>
      <div className="panel orders-panel">
        <div className="table-wrap">
          <table>
            <thead><tr>
              <th>ORDER NO.</th><th>CUSTOMER</th><th>DESIGN / FABRIC</th>
              <th>ORDER QTY.</th><th>DEADLINE</th><th>STATUS</th>
            </tr></thead>
          </table>
        </div>
        <EmptyState title="No customer orders recorded" description="Customer orders will appear here after they are entered into Order Management." />
      </div>

      <div className="quick-access">
        <div className="quick-title"><h2>Quick access</h2><p>Go directly to a factory operation.</p></div>
        <div className="quick-grid">
          {[
            ["orders", "Create and track orders", ClipboardList],
            ["planning", "Plan machine schedules", CalendarDays],
            ["inventory", "Check material stock", Boxes],
            ["production", "Record shift output", Activity]
          ].map(([id, label, Icon]) => (
            <button className="quick-card" key={id} onClick={() => onNavigate(id)}>
              <span className="quick-icon"><Icon size={19} /></span><span>{label}</span><ArrowUpRight size={16} className="quick-arrow" />
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

function ModulePage({ id }) {
  const info = moduleInfo[id];
  const Icon = info.icon;
  return (
    <>
      <PageHeading
        eyebrow="FACTORY OPERATIONS"
        title={info.title}
        subtitle={info.subtitle}
        action={<button className="primary-button" disabled title="Data entry will be enabled when this module is connected to the backend"><Plus size={17} /> Add New</button>}
      />
      <div className="module-banner">
        <div className="module-banner-icon"><Icon size={24} /></div>
        <div><strong>{info.title}</strong><span>Module interface created · Backend integration pending</span></div>
        <span className="setup-status">SETUP IN PROGRESS</span>
      </div>

      <div className="section-heading module-section-heading">
        <div><h2>Module capabilities</h2><p>Functions included in this manufacturing workflow.</p></div>
      </div>
      <div className="feature-grid">
        {info.features.map((feature, i) => (
          <div className="feature-card" key={feature}>
            <div className="feature-number">{String(i + 1).padStart(2, "0")}</div>
            <span>{feature}</span>
            <CheckCircle2 size={17} className="feature-check" />
          </div>
        ))}
      </div>

      <div className="section-heading register-heading">
        <div><h2>{id === "orders" ? "Customer order register" : `${info.title} register`}</h2><p>Records will be displayed here once backend integration is completed.</p></div>
        <div className="register-tools"><button className="secondary-button" disabled><RefreshCw size={15} /> Refresh</button></div>
      </div>
      <div className="panel register-panel">
        <div className="table-wrap">
          <table><thead><tr>{info.columns.map((col) => <th key={col}>{col.toUpperCase()}</th>)}</tr></thead></table>
        </div>
        <EmptyState title="No records available" description="This register is empty. Real business records will appear here after the module is connected to the backend." />
      </div>
    </>
  );
}

function SettingsPage() {
  return (
    <>
      <PageHeading eyebrow="WORKSPACE" title="Settings" subtitle="Factory workspace configuration." />
      <div className="panel settings-panel">
        <div className="settings-row"><div><strong>Business</strong><span>KAY DEE KAY</span></div><span className="settings-value">Manufacturing</span></div>
        <div className="settings-row"><div><strong>Location</strong><span>Factory location configuration</span></div><span className="settings-value">Not configured</span></div>
        <div className="settings-row"><div><strong>Production units</strong><span>Metres, pieces, rolls and kilograms as applicable</span></div><span className="settings-value">To be configured</span></div>
        <div className="settings-row"><div><strong>Machine and shift masters</strong><span>Use existing backend master data</span></div><span className="settings-value">Integration pending</span></div>
      </div>
    </>
  );
}

export default function App() {
  const [active, setActive] = useState(() => {
    try {
      const saved = localStorage.getItem("kdk_active_module");
      if (saved === "settings" || navigation.some(item => item.id === saved)) {
        return saved;
      }
    } catch (error) {
      console.warn("Could not restore last active module.", error);
    }
    return "dashboard";
  });
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem("kdk_active_module", active);
    } catch (error) {
      console.warn("Could not save active module.", error);
    }
  }, [active]);
  const title = active === "dashboard" ? "Dashboard" : active === "settings" ? "Settings" : moduleInfo[active]?.title;

  return (
    <div className="app-shell">
      <Sidebar active={active} onNavigate={setActive} mobileOpen={mobileOpen} closeMobile={() => setMobileOpen(false)} />
      <main className="main-area">
        <Header title={title} onMenu={() => setMobileOpen(true)} />
        <div className="page-content">
          {active === "dashboard" ? <Dashboard onNavigate={setActive} /> :
            active === "settings" ? <SettingsPage /> : active === "orders" ? <OrdersPage /> : active === "planning" ? <PlanningPage /> : active === "production" ? <ProductionPage /> : active === "purchases" ? <PurchasesPage /> : <ModulePage id={active} />}
          <footer className="footer">
            <span>KAY DEE KAY Manufacturing ERP</span>
            <span>Factory operations workspace</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
