import { useEffect, useState } from "react";
import {
  useGetOrdersQuery,
  useGetReservationsQuery,
  useGetStaffNotificationsQuery,
  useUpdateStaffNotificationMutation,
} from "../services/api";
import "./StaffDashboard.css";

export function StaffDashboard() {
  const [activeTab, setActiveTab] = useState<"orders" | "reservations" | "alerts">("orders");

  const { data: ordersData, isLoading: ordersLoading } = useGetOrdersQuery({ status: "active" });
  const { data: reservationsData, isLoading: reservationsLoading } = useGetReservationsQuery({ status: "held" });
  const { data: alertsData, isLoading: alertsLoading } = useGetStaffNotificationsQuery({ status: "pending" });
  const [updateNotification] = useUpdateStaffNotificationMutation();

  const orders = ordersData?.results ?? [];
  const reservations = reservationsData?.results ?? [];
  const alerts = alertsData?.results ?? [];

  const handleAcknowledge = async (id: number) => {
    await updateNotification({ id, status: "acknowledged" });
  };

  const handleResolve = async (id: number) => {
    await updateNotification({ id, status: "resolved" });
  };

  return (
    <div className="staff-dashboard">
      <header className="staff-dashboard__header">
        <h1>Staff Dashboard</h1>
        <div className="staff-dashboard__tabs" role="tablist" aria-label="Dashboard sections">
          <button
            role="tab"
            aria-selected={activeTab === "orders"}
            aria-controls="staff-panel-orders"
            className={`staff-dashboard__tab ${activeTab === "orders" ? "staff-dashboard__tab--active" : ""}`}
            onClick={() => setActiveTab("orders")}
          >
            Orders ({orders.length})
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "reservations"}
            aria-controls="staff-panel-reservations"
            className={`staff-dashboard__tab ${activeTab === "reservations" ? "staff-dashboard__tab--active" : ""}`}
            onClick={() => setActiveTab("reservations")}
          >
            Reservations ({reservations.length})
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "alerts"}
            aria-controls="staff-panel-alerts"
            className={`staff-dashboard__tab ${activeTab === "alerts" ? "staff-dashboard__tab--active" : ""}`}
            onClick={() => setActiveTab("alerts")}
          >
            Alerts ({alerts.length})
          </button>
        </div>
      </header>

      <main className="staff-dashboard__content">
        {activeTab === "orders" && (
          <div id="staff-panel-orders" role="tabpanel" className="staff-dashboard__list">
            {ordersLoading && <p className="staff-dashboard__muted">Loading...</p>}
            {!ordersLoading && orders.length === 0 && (
              <p className="staff-dashboard__muted">No active orders</p>
            )}
            {orders.map((order: any) => (
              <div key={order.id} className="staff-dashboard__card">
                <div className="staff-dashboard__card-header">
                  <span className="staff-dashboard__badge">#{order.id}</span>
                  <span className={`staff-dashboard__status staff-dashboard__status--${order.status}`}>
                    {order.status}
                  </span>
                </div>
                <p>Customer: {order.customer_name || order.customer_id || "Walk-in"}</p>
                <p>Items: {order.items?.length ?? 0} | Total: ${parseFloat(order.total ?? "0").toFixed(2)}</p>
                <p className="staff-dashboard__muted">
                  {new Date(order.created_at).toLocaleTimeString()}
                </p>
              </div>
            ))}
          </div>
        )}

        {activeTab === "reservations" && (
          <div id="staff-panel-reservations" role="tabpanel" className="staff-dashboard__list">
            {reservationsLoading && <p className="staff-dashboard__muted">Loading...</p>}
            {!reservationsLoading && reservations.length === 0 && (
              <p className="staff-dashboard__muted">No held reservations</p>
            )}
            {reservations.map((res: any) => (
              <div key={res.id} className="staff-dashboard__card">
                <div className="staff-dashboard__card-header">
                  <span className="staff-dashboard__badge">Table {res.table_id}</span>
                  <span className={`staff-dashboard__status staff-dashboard__status--${res.status}`}>
                    {res.status}
                  </span>
                </div>
                <p>Party: {res.party_size} | {res.reservation_date} at {res.reservation_time}</p>
                {res.held_until && (
                  <p className="staff-dashboard__muted">
                    Hold expires: {new Date(res.held_until).toLocaleTimeString()}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {activeTab === "alerts" && (
          <div id="staff-panel-alerts" role="tabpanel" className="staff-dashboard__list">
            {alertsLoading && <p className="staff-dashboard__muted">Loading...</p>}
            {!alertsLoading && alerts.length === 0 && (
              <p className="staff-dashboard__muted">No pending alerts</p>
            )}
            {alerts.map((alert: any) => (
              <div key={alert.id} className="staff-dashboard__card staff-dashboard__card--alert">
                <div className="staff-dashboard__card-header">
                  <span className={`staff-dashboard__priority staff-dashboard__priority--${alert.priority}`}>
                    {alert.priority}
                  </span>
                  <span className="staff-dashboard__muted">
                    {new Date(alert.created_at).toLocaleTimeString()}
                  </span>
                </div>
                <p>{alert.reason}</p>
                <p className="staff-dashboard__muted">
                  Customer: {alert.customer_name || alert.customer_id}
                </p>
                <div className="staff-dashboard__actions">
                  <button
                    className="staff-dashboard__action-btn"
                    aria-label={`Acknowledge alert: ${alert.reason}`}
                    onClick={() => handleAcknowledge(alert.id)}
                  >
                    Acknowledge
                  </button>
                  <button
                    className="staff-dashboard__action-btn staff-dashboard__action-btn--resolve"
                    aria-label={`Resolve alert: ${alert.reason}`}
                    onClick={() => handleResolve(alert.id)}
                  >
                    Resolve
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
