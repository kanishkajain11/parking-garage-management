import { useEffect, useState } from "react";
import "./App.css";

const API = `${window.location.protocol}//${window.location.hostname.replace(
  "5173",
  "8000"
)}`;

function App() {
  const [loggedIn, setLoggedIn] = useState(
    !!localStorage.getItem("token")
  );

  const [authMode, setAuthMode] = useState("login");

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [availability, setAvailability] =
    useState(null);

  const [history, setHistory] = useState([]);
  const [active, setActive] = useState([]);

  const [plate, setPlate] = useState("");
  const [vehicleType, setVehicleType] =
    useState("STANDARD");

  const [spotId, setSpotId] = useState("");

  const [search, setSearch] = useState("");
  const [message, setMessage] = useState("");

  const handleAuth = async () => {
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

      const response = await fetch(
        `${API}${endpoint}`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify(body),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        setMessage(
          data.detail ||
            "Authentication failed."
        );
        return;
      }

      localStorage.setItem(
        "token",
        data.access_token
      );

      setLoggedIn(true);

      setMessage(
        authMode === "login"
          ? "Login successful!"
          : "Registration successful!"
      );
    } catch {
      setMessage(
        "Unable to connect to backend."
      );
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    setLoggedIn(false);
    setMessage("");
  };

  const loadDashboard = async () => {
    try {
      const [
        availabilityRes,
        historyRes,
        activeRes,
      ] = await Promise.all([
        fetch(
          `${API}/parking/availability`
        ),
        fetch(
          `${API}/parking/history?page=1&limit=10&sort_by=check_in_time&order=desc`
        ),
        fetch(`${API}/parking/active`),
      ]);

      if (
        !availabilityRes.ok ||
        !historyRes.ok ||
        !activeRes.ok
      ) {
        throw new Error();
      }

      const availabilityData =
        await availabilityRes.json();

      const historyData =
        await historyRes.json();

      const activeData =
        await activeRes.json();

      setAvailability(
        availabilityData
      );

      setHistory(
        historyData.results || []
      );

      setActive(
        activeData.results || []
      );

      setMessage("");
    } catch {
      setMessage(
        "Backend connection failed."
      );
    }
  };

  useEffect(() => {
    if (loggedIn) {
      loadDashboard();
    }
  }, [loggedIn]);

  const checkIn = async () => {
    if (!plate) {
      setMessage(
        "Please enter vehicle plate."
      );
      return;
    }

    try {
      const body = {
        vehicle_plate: plate,
        vehicle_type: vehicleType,
      };

      if (spotId) {
        body.spot_id = Number(spotId);
      }

      const response = await fetch(
        `${API}/parking/check-in`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify(body),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        setMessage(
          data.detail ||
            "Check-in failed."
        );
        return;
      }

      setMessage(
        `Vehicle ${data.vehicle_plate} checked in at Spot ${data.spot_id}.`
      );

      setPlate("");
      setSpotId("");

      loadDashboard();
    } catch {
      setMessage("Check-in failed.");
    }
  };

  const checkOut = async (
    vehiclePlate
  ) => {
    try {
      const response = await fetch(
        `${API}/parking/check-out/${encodeURIComponent(
          vehiclePlate
        )}`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        setMessage(
          data.detail ||
            "Checkout failed."
        );
        return;
      }

      setMessage(
        `Checkout successful. Fee: ₹${data.fee}`
      );

      loadDashboard();
    } catch {
      setMessage(
        "Checkout failed."
      );
    }
  };

  const searchVehicle = async () => {
    if (!search.trim()) {
      loadDashboard();
      return;
    }

    try {
      const response = await fetch(
        `${API}/parking/search?plate=${encodeURIComponent(
          search.trim()
        )}`
      );

      const data = await response.json();

      if (!response.ok) {
        setMessage(
          data.detail ||
            "Search failed."
        );
        return;
      }

      setHistory(
        data.results || []
      );

      setMessage(
        `${data.total || 0} record(s) found.`
      );
    } catch {
      setMessage("Search failed.");
    }
  };

  if (!loggedIn) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1>ParkEase</h1>

          <p className="auth-subtitle">
            Smart Parking Garage Management
          </p>

          <div className="auth-tabs">
            <button
              className={
                authMode === "login"
                  ? "active-tab"
                  : ""
              }
              onClick={() => {
                setAuthMode("login");
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
                setMessage("");
              }}
            >
              Register
            </button>
          </div>

          {authMode === "register" && (
            <input
              placeholder="Full Name"
              value={name}
              onChange={(e) =>
                setName(e.target.value)
              }
            />
          )}

          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) =>
              setEmail(e.target.value)
            }
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) =>
              setPassword(e.target.value)
            }
          />

          <button
            className="primary-button"
            onClick={handleAuth}
          >
            {authMode === "login"
              ? "Login"
              : "Create Account"}
          </button>

          {message && (
            <div className="message">
              {message}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header>
        <div>
          <h1>ParkEase</h1>
          <p>
            Smart Parking Garage Management
          </p>
        </div>

        <div className="header-actions">
          <button onClick={loadDashboard}>
            Refresh
          </button>

          <button onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      <section className="hero">
        <h2>
          Manage your parking garage with ease.
        </h2>

        <p>
          Track availability, check vehicles
          in and out, calculate parking fees,
          and search parking history.
        </p>
      </section>

      {message && (
        <div className="message">
          {message}
        </div>
      )}

      <section className="stats">
        <div className="card">
          <h3>Total Spots</h3>
          <strong>
            {availability?.total_spots ?? "-"}
          </strong>
        </div>

        <div className="card">
          <h3>Available</h3>
          <strong>
            {availability?.available_spots ?? "-"}
          </strong>
        </div>

        <div className="card">
          <h3>Occupied</h3>
          <strong>
            {availability?.occupied_spots ?? "-"}
          </strong>
        </div>

        <div className="card">
          <h3>EV Available</h3>
          <strong>
            {availability?.ev_available ?? "-"}
          </strong>
        </div>
      </section>

      <section className="panel">
        <h2>Spot Availability</h2>

        <div className="availability-grid">
          {[
            "COMPACT",
            "STANDARD",
            "EV",
          ].map((type) => (
            <div
              className="availability-card"
              key={type}
            >
              <h3>{type}</h3>

              <p>
                Available:{" "}
                <strong>
                  {availability
                    ?.by_type?.[type]
                    ?.available ?? "-"}
                </strong>
              </p>

              <p>
                Occupied:{" "}
                {availability
                  ?.by_type?.[type]
                  ?.occupied ?? "-"}
              </p>

              <p>
                Total:{" "}
                {availability
                  ?.by_type?.[type]
                  ?.total ?? "-"}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Vehicle Check-In</h2>

        <div className="form">
          <input
            placeholder="Vehicle Plate"
            value={plate}
            onChange={(e) =>
              setPlate(e.target.value)
            }
          />

          <select
            value={vehicleType}
            onChange={(e) =>
              setVehicleType(e.target.value)
            }
          >
            <option value="STANDARD">
              Standard
            </option>

            <option value="EV">
              EV
            </option>
          </select>

          <input
            type="number"
            placeholder="Spot ID (optional)"
            value={spotId}
            onChange={(e) =>
              setSpotId(e.target.value)
            }
          />

          <button onClick={checkIn}>
            Check In
          </button>
        </div>

        <p className="hint">
          Leave Spot ID empty for automatic
          suitable spot assignment.
        </p>
      </section>

      <section className="panel">
        <h2>Currently Parked</h2>

        {active.length === 0 ? (
          <p>
            No vehicles currently parked.
          </p>
        ) : (
          <div className="table-wrap">
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
                {active.map((item) => (
                  <tr key={item.id}>
                    <td>
                      {item.vehicle_plate}
                    </td>

                    <td>
                      {item.vehicle_type}
                    </td>

                    <td>
                      {item.spot_id}
                    </td>

                    <td>
                      {new Date(
                        item.check_in_time
                      ).toLocaleString()}
                    </td>

                    <td>
                      <button
                        onClick={() =>
                          checkOut(
                            item.vehicle_plate
                          )
                        }
                      >
                        Check Out
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <div className="search-row">
          <h2>Parking History</h2>

          <div className="search-box">
            <input
              placeholder="Search plate"
              value={search}
              onChange={(e) =>
                setSearch(e.target.value)
              }
            />

            <button
              onClick={searchVehicle}
            >
              Search
            </button>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Plate</th>
                <th>Type</th>
                <th>Spot</th>
                <th>Check-In</th>
                <th>Check-Out</th>
                <th>Duration</th>
                <th>Fee</th>
                <th>Status</th>
              </tr>
            </thead>

            <tbody>
              {history.length === 0 ? (
                <tr>
                  <td colSpan="8">
                    No parking history found.
                  </td>
                </tr>
              ) : (
                history.map((item) => (
                  <tr key={item.id}>
                    <td>
                      {item.vehicle_plate}
                    </td>

                    <td>
                      {item.vehicle_type}
                    </td>

                    <td>
                      {item.spot_id}
                    </td>

                    <td>
                      {new Date(
                        item.check_in_time
                      ).toLocaleString()}
                    </td>

                    <td>
                      {item.check_out_time
                        ? new Date(
                            item.check_out_time
                          ).toLocaleString()
                        : "-"}
                    </td>

                    <td>
                      {item.duration_minutes ??
                        "-"}{" "}
                      min
                    </td>

                    <td>
                      {item.fee !== null &&
                      item.fee !== undefined
                        ? `₹${item.fee}`
                        : "-"}
                    </td>

                    <td>
                      {item.status}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <footer>
        <p>
          ParkEase — Parking Garage Management
          System
        </p>

        <p>
          React • FastAPI • SQLAlchemy • SQLite
        </p>
      </footer>
    </div>
  );
}

export default App;