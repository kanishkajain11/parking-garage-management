import { useEffect, useState } from "react";
import "./App.css";

/* =========================================================
   API URL
   Works locally and in GitHub Codespaces
   ========================================================= */

const API = window.location.hostname.includes("app.github.dev")
  ? `${window.location.protocol}//${window.location.hostname.replace(
      /-\d+\.app\.github\.dev$/,
      "-8000.app.github.dev"
    )}`
  : "http://localhost:8000";


/* =========================================================
   API HELPER
   ========================================================= */

async function apiRequest(endpoint, options = {}) {
  const response = await fetch(`${API}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  let data;

  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    throw new Error(
      data.detail || data.message || "Something went wrong"
    );
  }

  return data;
}


/* =========================================================
   APP
   ========================================================= */

export default function App() {
  const [token, setToken] = useState(
    localStorage.getItem("parkease_token")
  );

  const [userName, setUserName] = useState(
    localStorage.getItem("parkease_name") || ""
  );

  const [authMode, setAuthMode] = useState("login");

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const [garage, setGarage] = useState(null);
  const [availability, setAvailability] = useState(null);
  const [spots, setSpots] = useState([]);
  const [activeSessions, setActiveSessions] = useState([]);
  const [history, setHistory] = useState(null);

  const [plate, setPlate] = useState("");
  const [vehicleType, setVehicleType] = useState("STANDARD");

  const [searchPlate, setSearchPlate] = useState("");
  const [searchResults, setSearchResults] = useState([]);

  const [page, setPage] = useState(1);

  const [selectedSpot, setSelectedSpot] = useState("");

  const [pricing, setPricing] = useState(null);

  const [oldPlate, setOldPlate] = useState("");
  const [newPlate, setNewPlate] = useState("");

  const [rateCardText, setRateCardText] = useState(
    `COMPACT 50 30 300
STANDARD 60 35 350
EV 40 25 250

junk text
invalid row`
  );

  const [clockTime, setClockTime] = useState("");


  /* =======================================================
     AUTH
     ======================================================= */

  async function handleAuth(e) {
    e.preventDefault();

    setError("");
    setMessage("");
    setLoading(true);

    try {
      const endpoint =
        authMode === "login"
          ? "/auth/login"
          : "/auth/register";

      const body =
        authMode === "login"
          ? {
              email,
              password,
            }
          : {
              name,
              email,
              password,
            };

      const data = await apiRequest(endpoint, {
        method: "POST",
        body: JSON.stringify(body),
      });

      localStorage.setItem(
        "parkease_token",
        data.access_token
      );

      localStorage.setItem(
        "parkease_name",
        data.name
      );

      setToken(data.access_token);
      setUserName(data.name);

      setMessage(
        authMode === "login"
          ? "Login successful!"
          : "Account created successfully!"
      );

      setPassword("");

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }


  function logout() {
    localStorage.removeItem("parkease_token");
    localStorage.removeItem("parkease_name");

    setToken(null);
    setUserName("");
  }


  /* =======================================================
     DASHBOARD DATA
     ======================================================= */

  async function loadDashboard() {
    try {
      const [
        garageData,
        availabilityData,
        spotsData,
        activeData,
        historyData,
        pricingData,
      ] = await Promise.all([
        apiRequest("/garage"),
        apiRequest("/parking/availability"),
        apiRequest("/parking/spots"),
        apiRequest("/parking/active"),
        apiRequest(
          `/parking/history?page=${page}&limit=10&sort_by=check_in_time&order=desc`
        ),
        apiRequest("/pricing"),
      ]);

      setGarage(garageData);
      setAvailability(availabilityData);
      setSpots(spotsData);
      setActiveSessions(activeData);
      setHistory(historyData);
      setPricing(pricingData);

    } catch (err) {
      setError(err.message);
    }
  }


  useEffect(() => {
    if (token) {
      loadDashboard();
    }
  }, [token, page]);


  /* =======================================================
     CHECK-IN
     ======================================================= */

  async function handleCheckIn(e) {
    e.preventDefault();

    setError("");
    setMessage("");

    try {
      const body = {
        vehicle_plate: plate,
        vehicle_type: vehicleType,
      };

      if (selectedSpot) {
        body.spot_id = Number(selectedSpot);
      }

      const data = await apiRequest(
        "/parking/check-in",
        {
          method: "POST",
          body: JSON.stringify(body),
        }
      );

      setMessage(
        `Vehicle ${data.vehicle_plate} checked in successfully. Spot ${data.spot_id} assigned.`
      );

      setPlate("");
      setSelectedSpot("");

      await loadDashboard();

    } catch (err) {
      setError(err.message);
    }
  }


  /* =======================================================
     CHECK-OUT
     ======================================================= */

  async function handleCheckout(identifier) {
    setError("");
    setMessage("");

    try {
      const data = await apiRequest(
        `/parking/check-out/${encodeURIComponent(identifier)}`,
        {
          method: "POST",
        }
      );

      setMessage(
        `Checkout successful. Fee: ₹${data.fee}`
      );

      await loadDashboard();

    } catch (err) {
      setError(err.message);
    }
  }


  /* =======================================================
     SEARCH
     ======================================================= */

  async function handleSearch(e) {
    e.preventDefault();

    setError("");

    if (!searchPlate.trim()) {
      setSearchResults([]);
      return;
    }

    try {
      const data = await apiRequest(
        `/parking/search/${encodeURIComponent(
          searchPlate.trim()
        )}`
      );

      setSearchResults(data);

    } catch (err) {
      setError(err.message);
    }
  }


  /* =======================================================
     TRANSFER - T6
     ======================================================= */

  async function handleTransfer(e) {
    e.preventDefault();

    setError("");
    setMessage("");

    try {
      const data = await apiRequest(
        "/parking/transfer",
        {
          method: "POST",
          body: JSON.stringify({
            old_plate: oldPlate,
            new_plate: newPlate,
          }),
        }
      );

      setMessage(
        `Transfer successful: ${data.old_plate} → ${data.new_plate}. Spot ${data.spot_id} retained.`
      );

      setOldPlate("");
      setNewPlate("");

      await loadDashboard();

    } catch (err) {
      setError(err.message);
    }
  }


  /* =======================================================
     RATE CARD IMPORT - T4
     ======================================================= */

  async function handleRateCardImport(e) {
    e.preventDefault();

    setError("");
    setMessage("");

    try {
      const data = await apiRequest(
        "/pricing/import",
        {
          method: "POST",
          body: JSON.stringify({
            raw_text: rateCardText,
          }),
        }
      );

      setMessage(
        `Rate card imported. ${data.imported.length} rate types cleaned successfully.`
      );

      await loadDashboard();

    } catch (err) {
      setError(err.message);
    }
  }


  /* =======================================================
     CLOCK - T2
     ======================================================= */

  async function handleClock(e) {
    e.preventDefault();

    setError("");
    setMessage("");

    try {
      const data = await apiRequest(
        "/clock",
        {
          method: "POST",
          body: JSON.stringify({
            now: clockTime || null,
          }),
        }
      );

      setMessage(
        `Nightly job completed. ${data.closed_sessions} session(s) automatically closed and billed.`
      );

      await loadDashboard();

    } catch (err) {
      setError(err.message);
    }
  }


  /* =======================================================
     LOGIN / REGISTER SCREEN
     ======================================================= */

  if (!token) {
    return (
      <div className="app">

        <div className="auth-card">

          <div className="brand">
            <h1>ParkEase</h1>
            <p>
              Smart Parking Garage Management
            </p>
          </div>

          <div className="auth-tabs">

            <button
              className={
                authMode === "login"
                  ? "active-tab"
                  : ""
              }
              onClick={() => {
                setAuthMode("login");
                setError("");
                setMessage("");
              }}
            >
              Login
            </button>

            <button
              className={
                authMode === "register"
                  ? "active-tab"
                  : ""
              }
              onClick={() => {
                setAuthMode("register");
                setError("");
                setMessage("");
              }}
            >
              Register
            </button>

          </div>

          <form onSubmit={handleAuth}>

            {authMode === "register" && (
              <input
                type="text"
                placeholder="Full name"
                value={name}
                onChange={(e) =>
                  setName(e.target.value)
                }
                required
              />
            )}

            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) =>
                setEmail(e.target.value)
              }
              required
            />

            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) =>
                setPassword(e.target.value)
              }
              required
            />

            <button
              className="primary-btn"
              disabled={loading}
              type="submit"
            >
              {loading
                ? "Please wait..."
                : authMode === "login"
                ? "Login"
                : "Create Account"}
            </button>

          </form>

          {error && (
            <div className="error">
              {error}
            </div>
          )}

          {message && (
            <div className="success">
              {message}
            </div>
          )}

        </div>

        <LandingSection />

      </div>
    );
  }


  /* =======================================================
     DASHBOARD
     ======================================================= */

  return (
    <div className="dashboard">

      <header className="topbar">

        <div>
          <h1>ParkEase</h1>
          <span>
            Smart Parking Garage Management
          </span>
        </div>

        <div className="user-area">
          <span>Welcome, {userName}</span>

          <button
            className="logout-btn"
            onClick={logout}
          >
            Logout
          </button>
        </div>

      </header>


      <main className="container">

        {error && (
          <div className="error banner">
            {error}
          </div>
        )}

        {message && (
          <div className="success banner">
            {message}
          </div>
        )}


        {/* =================================================
            GARAGE INFO
            ================================================= */}

        {garage && (
          <section className="hero-card">

            <div>
              <h2>{garage.name}</h2>

              <p>
                {garage.address}
              </p>
            </div>

            <div>
              <strong>
                Multi-level parking
              </strong>
              <p>
                EV-ready • Automated billing
              </p>
            </div>

          </section>
        )}


        {/* =================================================
            STATS
            ================================================= */}

        {availability && (
          <section className="stats-grid">

            <StatCard
              title="Total Spots"
              value={availability.total_spots}
            />

            <StatCard
              title="Available"
              value={availability.available_spots}
            />

            <StatCard
              title="Occupied"
              value={availability.occupied_spots}
            />

            <StatCard
              title="EV Available"
              value={availability.ev_available}
            />

          </section>
        )}


        {/* =================================================
            CHECK-IN
            ================================================= */}

        <section className="card">

          <h2>🚗 Vehicle Check-In</h2>

          <form
            className="form-grid"
            onSubmit={handleCheckIn}
          >

            <input
              placeholder="Vehicle plate e.g. RJ14AB1234"
              value={plate}
              onChange={(e) =>
                setPlate(e.target.value)
              }
              required
            />

            <select
              value={vehicleType}
              onChange={(e) =>
                setVehicleType(e.target.value)
              }
            >
              <option value="STANDARD">
                STANDARD
              </option>

              <option value="COMPACT">
                COMPACT
              </option>

              <option value="EV">
                EV
              </option>
            </select>

            <select
              value={selectedSpot}
              onChange={(e) =>
                setSelectedSpot(e.target.value)
              }
            >

              <option value="">
                Auto Assign Spot
              </option>

              {spots
                .filter(
                  (spot) =>
                    !spot.is_occupied &&
                    spot.spot_type ===
                      vehicleType
                )
                .map((spot) => (
                  <option
                    key={spot.id}
                    value={spot.id}
                  >
                    Floor {spot.floor} • Spot{" "}
                    {spot.spot_number} •{" "}
                    {spot.spot_type}
                  </option>
                ))}

            </select>

            <button
              className="primary-btn"
              type="submit"
            >
              Check In
            </button>

          </form>

        </section>


        {/* =================================================
            ACTIVE VEHICLES
            ================================================= */}

        <section className="card">

          <div className="section-header">

            <div>
              <h2>🅿️ Active Vehicles</h2>
              <p>
                Currently parked vehicles
              </p>
            </div>

            <button
              className="secondary-btn"
              onClick={loadDashboard}
            >
              Refresh
            </button>

          </div>

          {activeSessions.length === 0 ? (
            <div className="empty">
              No active vehicles.
            </div>
          ) : (
            <div className="table-wrapper">

              <table>

                <thead>
                  <tr>
                    <th>Plate</th>
                    <th>Type</th>
                    <th>Spot</th>
                    <th>Check-In</th>
                    <th>Action</th>
                  </tr>
                </thead>

                <tbody>

                  {activeSessions.map(
                    (session) => (
                      <tr key={session.id}>

                        <td>
                          <strong>
                            {session.vehicle_plate}
                          </strong>
                        </td>

                        <td>
                          {session.vehicle_type}
                        </td>

                        <td>
                          #{session.spot_id}
                        </td>

                        <td>
                          {formatDate(
                            session.check_in_time
                          )}
                        </td>

                        <td>

                          <button
                            className="danger-btn"
                            onClick={() =>
                              handleCheckout(
                                session.vehicle_plate
                              )
                            }
                          >
                            Check Out
                          </button>

                        </td>

                      </tr>
                    )
                  )}

                </tbody>

              </table>

            </div>
          )}

        </section>


        {/* =================================================
            SEARCH
            ================================================= */}

        <section className="card">

          <h2>🔎 Search Vehicle</h2>

          <form
            className="search-form"
            onSubmit={handleSearch}
          >

            <input
              placeholder="Search by vehicle plate"
              value={searchPlate}
              onChange={(e) =>
                setSearchPlate(e.target.value)
              }
            />

            <button
              className="primary-btn"
              type="submit"
            >
              Search
            </button>

          </form>

          {searchResults.length > 0 && (
            <div className="table-wrapper">

              <table>

                <thead>
                  <tr>
                    <th>Plate</th>
                    <th>Type</th>
                    <th>Spot</th>
                    <th>Status</th>
                    <th>Fee</th>
                  </tr>
                </thead>

                <tbody>

                  {searchResults.map(
                    (item) => (
                      <tr key={item.id}>

                        <td>
                          {item.vehicle_plate}
                        </td>

                        <td>
                          {item.vehicle_type}
                        </td>

                        <td>
                          #{item.spot_id}
                        </td>

                        <td>
                          {item.status}
                        </td>

                        <td>
                          ₹{item.fee ?? "-"}
                        </td>

                      </tr>
                    )
                  )}

                </tbody>

              </table>

            </div>
          )}

        </section>


        {/* =================================================
            PARKING HISTORY
            ================================================= */}

        <section className="card">

          <div className="section-header">

            <div>
              <h2>📋 Parking History</h2>
              <p>
                Persistent parking records
              </p>
            </div>

            {history && (
              <span>
                Total: {history.total}
              </span>
            )}

          </div>

          {history?.results?.length > 0 ? (

            <div className="table-wrapper">

              <table>

                <thead>
                  <tr>
                    <th>Plate</th>
                    <th>Type</th>
                    <th>Check-In</th>
                    <th>Check-Out</th>
                    <th>Duration</th>
                    <th>Fee</th>
                    <th>Status</th>
                  </tr>
                </thead>

                <tbody>

                  {history.results.map(
                    (item) => (
                      <tr key={item.id}>

                        <td>
                          {item.vehicle_plate}
                        </td>

                        <td>
                          {item.vehicle_type}
                        </td>

                        <td>
                          {formatDate(
                            item.check_in_time
                          )}
                        </td>

                        <td>
                          {item.check_out_time
                            ? formatDate(
                                item.check_out_time
                              )
                            : "-"}
                        </td>

                        <td>
                          {item.duration_minutes
                            ? `${item.duration_minutes} min`
                            : "-"}
                        </td>

                        <td>
                          {item.fee != null
                            ? `₹${item.fee}`
                            : "-"}
                        </td>

                        <td>
                          <span
                            className={
                              item.status ===
                              "ACTIVE"
                                ? "status-active"
                                : "status-complete"
                            }
                          >
                            {item.status}
                          </span>
                        </td>

                      </tr>
                    )
                  )}

                </tbody>

              </table>

            </div>

          ) : (
            <div className="empty">
              No parking history yet.
            </div>
          )}

          {history &&
            history.total_pages > 0 && (
              <div className="pagination">

                <button
                  disabled={page <= 1}
                  onClick={() =>
                    setPage((p) =>
                      Math.max(1, p - 1)
                    )
                  }
                >
                  ← Previous
                </button>

                <span>
                  Page {page} of{" "}
                  {history.total_pages}
                </span>

                <button
                  disabled={
                    page >= history.total_pages
                  }
                  onClick={() =>
                    setPage((p) =>
                      Math.min(
                        history.total_pages,
                        p + 1
                      )
                    )
                  }
                >
                  Next →
                </button>

              </div>
            )}

        </section>


        {/* =================================================
            T6 TRANSFER
            ================================================= */}

        <section className="card">

          <h2>🔄 Valet Hand-Off</h2>

          <p className="muted">
            Transfer an active session to a
            different vehicle plate. Spot and
            original entry time remain unchanged.
          </p>

          <form
            className="form-grid"
            onSubmit={handleTransfer}
          >

            <input
              placeholder="Old plate"
              value={oldPlate}
              onChange={(e) =>
                setOldPlate(e.target.value)
              }
              required
            />

            <input
              placeholder="New plate"
              value={newPlate}
              onChange={(e) =>
                setNewPlate(e.target.value)
              }
              required
            />

            <button
              className="primary-btn"
              type="submit"
            >
              Transfer Session
            </button>

          </form>

        </section>


        {/* =================================================
            T4 RATE CARD
            ================================================= */}

        <section className="card">

          <h2>💰 Messy Rate Card Import</h2>

          <p className="muted">
            Paste a rate card. Valid COMPACT,
            STANDARD and EV rows are extracted
            while unrelated junk is ignored.
          </p>

          <form onSubmit={handleRateCardImport}>

            <textarea
              rows="7"
              value={rateCardText}
              onChange={(e) =>
                setRateCardText(
                  e.target.value
                )
              }
            />

            <button
              className="primary-btn"
              type="submit"
            >
              Import Clean Rates
            </button>

          </form>

          {pricing?.rate_cards?.length > 0 && (
            <div className="rate-grid">

              {pricing.rate_cards.map(
                (rate) => (
                  <div
                    className="rate-card"
                    key={rate.spot_type}
                  >
                    <h3>
                      {rate.spot_type}
                    </h3>

                    <p>
                      First hour: ₹
                      {rate.first_hour_rate}
                    </p>

                    <p>
                      Additional hour: ₹
                      {rate.additional_hour_rate}
                    </p>

                    <p>
                      Daily cap: ₹
                      {rate.daily_cap}
                    </p>

                  </div>
                )
              )}

            </div>
          )}

        </section>


        {/* =================================================
            T2 CLOCK
            ================================================= */}

        <section className="card">

          <h2>⏰ Nightly Automation</h2>

          <p className="muted">
            Automatically closes and bills
            sessions parked for more than
            24 hours.
          </p>

          <form
            className="form-grid"
            onSubmit={handleClock}
          >

            <input
              type="datetime-local"
              value={clockTime}
              onChange={(e) =>
                setClockTime(
                  e.target.value
                    ? `${e.target.value}:00`
                    : ""
                )
              }
            />

            <button
              className="primary-btn"
              type="submit"
            >
              Run Clock Job
            </button>

          </form>

        </section>


        {/* =================================================
            API DOCS
            ================================================= */}

        <section className="card api-card">

          <h2>🧩 API Documentation</h2>

          <p>
            Explore and test all REST APIs using
            FastAPI Swagger.
          </p>

          <a
            href={`${API}/docs`}
            target="_blank"
            rel="noreferrer"
          >
            Open API Docs →
          </a>

        </section>

      </main>

    </div>
  );
}


/* =========================================================
   STAT CARD
   ========================================================= */

function StatCard({ title, value }) {
  return (
    <div className="stat-card">
      <span>{title}</span>
      <strong>{value}</strong>
    </div>
  );
}


/* =========================================================
   LANDING SECTION
   ========================================================= */

function LandingSection() {
  return (
    <section className="landing">

      <div className="landing-inner">

        <h2>
          Built for modern parking operations
        </h2>

        <p>
          ParkEase helps parking attendants and
          garage operators manage multi-level
          garages, EV spots, vehicle check-in/out,
          pricing, search and parking history from
          one dashboard.
        </p>


        <div className="feature-grid">

          <div>
            🚗
            <strong>Smart Check-In</strong>
            <span>
              Automatic spot assignment
            </span>
          </div>

          <div>
            ⚡
            <strong>EV Management</strong>
            <span>
              Dedicated EV availability
            </span>
          </div>

          <div>
            💰
            <strong>Automatic Billing</strong>
            <span>
              Tiered rates and daily caps
            </span>
          </div>

          <div>
            🔎
            <strong>Plate Search</strong>
            <span>
              Quickly find parking records
            </span>
          </div>

          <div>
            📋
            <strong>Parking History</strong>
            <span>
              Persistent database records
            </span>
          </div>

          <div>
            🏢
            <strong>Multi-Level Garage</strong>
            <span>
              Designed for scalable garages
            </span>
          </div>

        </div>


        <h3>Target Audience</h3>

        <p>
          Parking garage attendants, operators
          and city-centre parking businesses.
        </p>


        <h3>How ParkEase Helps</h3>

        <p>
          It reduces manual parking tracking,
          prevents double parking, enforces EV
          spot rules, calculates fees consistently
          and keeps searchable parking history.
        </p>


        <h3>Future Features</h3>

        <ul>
          <li>Online reservations</li>
          <li>Payment gateway integration</li>
          <li>Real-time analytics and notifications</li>
        </ul>

      </div>

    </section>
  );
}


/* =========================================================
   DATE FORMATTER
   ========================================================= */

function formatDate(value) {
  if (!value) return "-";

  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}