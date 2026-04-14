import { useState } from "react";

const API_BASE = "http://localhost:8000";

// --- Shared helpers ---
const fmt = (n) => `$${Number(n).toLocaleString("en-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtInt = (n) => `$${Number(n).toLocaleString("en-CA")}`;

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// --- Program cards ---

function CCBForm({ onResult }) {
  const [income, setIncome] = useState(55000);
  const [children, setChildren] = useState([{ age: 3 }, { age: 8 }]);
  const [loading, setLoading] = useState(false);

  const addChild = () => setChildren([...children, { age: 0 }]);
  const removeChild = (i) => setChildren(children.filter((_, idx) => idx !== i));
  const setAge = (i, age) => {
    const c = [...children];
    c[i] = { age: parseInt(age) || 0 };
    setChildren(c);
  };

  const calculate = async () => {
    setLoading(true);
    try {
      const result = await apiPost("/programs/canada-child-benefit/calculate", {
        num_children: children.length,
        children,
        family_net_income: income,
      });
      onResult(result);
    } catch (e) {
      onResult({ error: e.message });
    }
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Family net income</label>
        <input
          type="number"
          value={income}
          onChange={(e) => setIncome(Number(e.target.value))}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Children</label>
        {children.map((child, i) => (
          <div key={i} className="flex items-center gap-2 mb-2">
            <span className="text-sm text-gray-500 w-16">Child {i + 1}</span>
            <input
              type="number"
              min="0"
              max="17"
              value={child.age}
              onChange={(e) => setAge(i, e.target.value)}
              className="w-20 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Age"
            />
            <span className="text-xs text-gray-400">years old</span>
            {children.length > 1 && (
              <button onClick={() => removeChild(i)} className="text-red-400 hover:text-red-600 text-sm ml-2">remove</button>
            )}
          </div>
        ))}
        <button onClick={addChild} className="text-sm text-blue-600 hover:text-blue-800 mt-1">+ Add child</button>
      </div>
      <button
        onClick={calculate}
        disabled={loading}
        className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
      >
        {loading ? "Calculating..." : "Calculate CCB"}
      </button>
    </div>
  );
}

function EIForm({ onResult }) {
  const [earnings, setEarnings] = useState(900);
  const [loading, setLoading] = useState(false);

  const calculate = async () => {
    setLoading(true);
    try {
      const result = await apiPost("/programs/employment-insurance/calculate", {
        average_insurable_weekly_earnings: earnings,
      });
      onResult(result);
    } catch (e) {
      onResult({ error: e.message });
    }
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Average insurable weekly earnings</label>
        <input
          type="number"
          value={earnings}
          onChange={(e) => setEarnings(Number(e.target.value))}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <button
        onClick={calculate}
        disabled={loading}
        className="w-full bg-green-600 text-white py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
      >
        {loading ? "Calculating..." : "Calculate EI benefits"}
      </button>
    </div>
  );
}

function OASForm({ onResult }) {
  const [age, setAge] = useState(68);
  const [years, setYears] = useState(30);
  const [income, setIncome] = useState(45000);
  const [loading, setLoading] = useState(false);

  const calculate = async () => {
    setLoading(true);
    try {
      const result = await apiPost("/programs/old-age-security/calculate", {
        applicant_age: age,
        years_residence_after_18: years,
        individual_net_income: income,
      });
      onResult(result);
    } catch (e) {
      onResult({ error: e.message });
    }
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Your age</label>
        <input
          type="number"
          min="65"
          max="100"
          value={age}
          onChange={(e) => setAge(Number(e.target.value))}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Years of residence in Canada (after age 18)</label>
        <input
          type="number"
          min="0"
          max="60"
          value={years}
          onChange={(e) => setYears(Number(e.target.value))}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Individual net income</label>
        <input
          type="number"
          value={income}
          onChange={(e) => setIncome(Number(e.target.value))}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <button
        onClick={calculate}
        disabled={loading}
        className="w-full bg-purple-600 text-white py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 text-sm font-medium"
      >
        {loading ? "Calculating..." : "Calculate OAS pension"}
      </button>
    </div>
  );
}

// --- Results display ---

function CCBResult({ data }) {
  if (data.error) return <ErrorBox msg={data.error} />;
  const p = data.parameters_used;
  const inp = data.inputs_received;
  const underCount = (inp.children || []).filter(c => c.age < 6).length;
  const overCount = (inp.children || []).filter(c => c.age >= 6).length;

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
      <div className="text-center">
        <div className="text-3xl font-bold text-blue-700">{fmt(data.monthly)}<span className="text-base font-normal text-blue-500"> /month</span></div>
        <div className="text-sm text-blue-500 mt-1">{fmt(data.annual)} per year</div>
      </div>
      <div className="border-t border-blue-200 pt-3 text-sm text-gray-600 space-y-1">
        {underCount > 0 && <div>{underCount} child(ren) under 6 — max {fmtInt(p.max_annual_under_6)}/yr each</div>}
        {overCount > 0 && <div>{overCount} child(ren) aged 6-17 — max {fmtInt(p.max_annual_6_to_17)}/yr each</div>}
        {inp.family_net_income > p.income_threshold_1 && (
          <div className="text-orange-600">Income of {fmtInt(inp.family_net_income)} exceeds {fmtInt(p.income_threshold_1)} threshold — benefit reduced</div>
        )}
        {inp.family_net_income <= p.income_threshold_1 && (
          <div className="text-green-600">Income is at or below {fmtInt(p.income_threshold_1)} — you receive the maximum</div>
        )}
      </div>
    </div>
  );
}

function EIResult({ data }) {
  if (data.error) return <ErrorBox msg={data.error} />;
  const p = data.parameters_used;
  return (
    <div className="bg-green-50 border border-green-200 rounded-lg p-4 space-y-3">
      <div className="text-center">
        <div className="text-3xl font-bold text-green-700">{fmt(data.weekly)}<span className="text-base font-normal text-green-500"> /week</span></div>
        <div className="text-sm text-green-500 mt-1">{fmt(data.bi_weekly)} bi-weekly</div>
      </div>
      <div className="border-t border-green-200 pt-3 text-sm text-gray-600 space-y-1">
        <div>Benefit rate: {p.benefit_rate}% of insurable earnings</div>
        <div>Maximum weekly: {fmtInt(p.max_weekly_benefit)}</div>
        {data.weekly >= p.max_weekly_benefit && (
          <div className="text-orange-600">You've hit the weekly maximum</div>
        )}
      </div>
    </div>
  );
}

function OASResult({ data }) {
  if (data.error) return <ErrorBox msg={data.error} />;
  const p = data.parameters_used;
  const inp = data.inputs_received;
  return (
    <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 space-y-3">
      <div className="text-center">
        <div className="text-3xl font-bold text-purple-700">{fmt(data.monthly)}<span className="text-base font-normal text-purple-500"> /month</span></div>
        <div className="text-sm text-purple-500 mt-1">{fmt(data.annual)} per year — {data.full_or_partial} pension</div>
      </div>
      <div className="border-t border-purple-200 pt-3 text-sm text-gray-600 space-y-1">
        <div>{inp.years_residence_after_18} of {p.full_pension_years} years for full pension</div>
        {inp.individual_net_income > p.clawback_threshold && (
          <div className="text-orange-600">Income above {fmtInt(p.clawback_threshold)} — recovery tax of {p.clawback_rate}% applied</div>
        )}
        {inp.individual_net_income <= p.clawback_threshold && (
          <div className="text-green-600">No recovery tax — income below {fmtInt(p.clawback_threshold)} threshold</div>
        )}
      </div>
    </div>
  );
}

function ErrorBox({ msg }) {
  const isConnectionError = msg.includes("Failed to fetch") || msg.includes("NetworkError");
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
      {isConnectionError ? (
        <div>
          <div className="font-medium mb-1">Can't reach the API</div>
          <div className="text-red-500">Start it with: <code className="bg-red-100 px-1 py-0.5 rounded text-xs">uvicorn api.main:app --reload --port 8000</code></div>
        </div>
      ) : (
        <div>{msg}</div>
      )}
    </div>
  );
}

// --- API status indicator ---

function useApiStatus() {
  const [status, setStatus] = useState("checking");
  const [programs, setPrograms] = useState([]);

  useState(() => {
    apiGet("/programs?lang=en")
      .then((data) => {
        setPrograms(data);
        setStatus("connected");
      })
      .catch(() => setStatus("disconnected"));
  });

  return { status, programs };
}

// --- Main app ---

const TABS = [
  { id: "ccb", label: "Canada Child Benefit", color: "blue", icon: "👶" },
  { id: "ei", label: "Employment Insurance", color: "green", icon: "💼" },
  { id: "oas", label: "Old Age Security", color: "purple", icon: "🏡" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("ccb");
  const [results, setResults] = useState({});
  const { status } = useApiStatus();

  const setResult = (programId, data) => {
    setResults((prev) => ({ ...prev, [programId]: data }));
  };

  const tabColors = {
    ccb: { active: "bg-blue-600 text-white", inactive: "bg-white text-blue-600 hover:bg-blue-50 border border-blue-200" },
    ei: { active: "bg-green-600 text-white", inactive: "bg-white text-green-600 hover:bg-green-50 border border-green-200" },
    oas: { active: "bg-purple-600 text-white", inactive: "bg-white text-purple-600 hover:bg-purple-50 border border-purple-200" },
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-xl mx-auto">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gray-900">GC Benefits Estimator</h1>
          <p className="text-sm text-gray-500 mt-1">
            Proof of concept — powered by the GC Rules API
          </p>
          <div className="mt-2 flex items-center justify-center gap-2 text-xs">
            <span className={`inline-block w-2 h-2 rounded-full ${status === "connected" ? "bg-green-500" : status === "checking" ? "bg-yellow-400" : "bg-red-500"}`} />
            <span className="text-gray-400">
              {status === "connected" ? "API connected" : status === "checking" ? "Connecting..." : "API offline — start uvicorn"}
            </span>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.id ? tabColors[tab.id].active : tabColors[tab.id].inactive
              }`}
            >
              <span className="mr-1">{tab.icon}</span>
              <span className="hidden sm:inline">{tab.label}</span>
              <span className="sm:hidden">{tab.label.split(" ")[0]}</span>
            </button>
          ))}
        </div>

        {/* Form + Result */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            {TABS.find((t) => t.id === activeTab)?.icon}{" "}
            {TABS.find((t) => t.id === activeTab)?.label}
          </h2>

          {activeTab === "ccb" && <CCBForm onResult={(r) => setResult("ccb", r)} />}
          {activeTab === "ei" && <EIForm onResult={(r) => setResult("ei", r)} />}
          {activeTab === "oas" && <OASForm onResult={(r) => setResult("oas", r)} />}

          {results[activeTab] && (
            <div className="mt-6">
              {activeTab === "ccb" && <CCBResult data={results.ccb} />}
              {activeTab === "ei" && <EIResult data={results.ei} />}
              {activeTab === "oas" && <OASResult data={results.oas} />}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-6 text-center text-xs text-gray-400 space-y-1">
          <p>All amounts come from structured JSON via the GC Rules API — zero hardcoded values in this app.</p>
          <p>Not an official Government of Canada product. For demonstration purposes only.</p>
        </div>
      </div>
    </div>
  );
}
