import { useState } from "react";
import { useAppSelector, useAppDispatch } from "../hooks";
import { logout } from "../slices/authSlice";
import {
  useGetMenuItemsQuery,
  useGetOrdersQuery,
  useGetReservationsQuery,
  useGetStaffNotificationsQuery,
  useUpdateStaffNotificationMutation,
  useGetToolLogsQuery,
  useGetSessionsQuery,
  useDeleteSessionMutation,
} from "../services/api";
import { CountdownTimer } from "./CountdownTimer";
import "./Sidebar.css";

type Tab = "menu" | "orders" | "reservations" | "alerts" | "activity" | "sessions";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  onSelectSession?: (sessionId: string) => void;
  activeSessionId?: string;
}

export function Sidebar({ open, onClose, onSelectSession, activeSessionId }: SidebarProps) {
  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.auth.user);
  const [tab, setTab] = useState<Tab>("menu");

  const { data: menuItems, isLoading: menuLoading } = useGetMenuItemsQuery(undefined);
  const { data: ordersData, isLoading: ordersLoading } = useGetOrdersQuery(undefined, { pollingInterval: 10000 });
  const { data: reservationsData, isLoading: reservationsLoading, refetch: refetchReservations } = useGetReservationsQuery(undefined, { pollingInterval: 15000 });
  const { data: notificationsData } = useGetStaffNotificationsQuery({ status: "pending" });

  const orders = ordersData?.results ?? [];
  const reservations = reservationsData?.results ?? [];
  const pendingCount = notificationsData?.count ?? 0;

  return (
    <>
      {open && <div className="sidebar-backdrop" onClick={onClose} aria-hidden="true" />}
      <aside className={`sidebar ${open ? "sidebar--open" : ""}`} role="dialog" aria-modal="true" aria-label="Sidebar navigation">
        <div className="sidebar__header">
          <div className="sidebar__user">
            <span className="sidebar__user-icon">{user?.username?.[0]?.toUpperCase() ?? "?"}</span>
            <div className="sidebar__user-info">
              <span className="sidebar__user-name">{user?.username ?? "Guest"}</span>
              <span className="sidebar__user-email">{user?.email ?? ""}</span>
            </div>
          </div>
          <button className="sidebar__close" onClick={onClose} aria-label="Close sidebar">
            ✕
          </button>
        </div>

        <nav className="sidebar__tabs" role="tablist" aria-label="Sidebar tabs">
          <button
            role="tab"
            aria-selected={tab === "menu"}
            aria-controls="sidebar-panel-menu"
            className={`sidebar__tab ${tab === "menu" ? "sidebar__tab--active" : ""}`}
            onClick={() => setTab("menu")}
          >
            Menu
          </button>
          <button
            role="tab"
            aria-selected={tab === "orders"}
            aria-controls="sidebar-panel-orders"
            className={`sidebar__tab ${tab === "orders" ? "sidebar__tab--active" : ""}`}
            onClick={() => setTab("orders")}
          >
            Orders
          </button>
          <button
            role="tab"
            aria-selected={tab === "reservations"}
            aria-controls="sidebar-panel-reservations"
            className={`sidebar__tab ${tab === "reservations" ? "sidebar__tab--active" : ""}`}
            onClick={() => setTab("reservations")}
          >
            Reservations
          </button>
          <button
            role="tab"
            aria-selected={tab === "alerts"}
            aria-controls="sidebar-panel-alerts"
            className={`sidebar__tab sidebar__tab--alerts ${tab === "alerts" ? "sidebar__tab--active" : ""}`}
            onClick={() => setTab("alerts")}
          >
            Alerts
            {pendingCount > 0 && (
              <span className="sidebar__badge" aria-label={`${pendingCount} pending alerts`}>{pendingCount}</span>
            )}
          </button>
          <button
            role="tab"
            aria-selected={tab === "activity"}
            aria-controls="sidebar-panel-activity"
            className={`sidebar__tab ${tab === "activity" ? "sidebar__tab--active" : ""}`}
            onClick={() => setTab("activity")}
          >
            Activity
          </button>
          <button
            role="tab"
            aria-selected={tab === "sessions"}
            aria-controls="sidebar-panel-sessions"
            className={`sidebar__tab ${tab === "sessions" ? "sidebar__tab--active" : ""}`}
            onClick={() => setTab("sessions")}
          >
            Sessions
          </button>
        </nav>

        <div className="sidebar__body">
          {tab === "menu" && (
            <div id="sidebar-panel-menu" role="tabpanel" aria-label="Menu">
              <MenuPanel items={menuItems} loading={menuLoading} />
            </div>
          )}
          {tab === "orders" && (
            <div id="sidebar-panel-orders" role="tabpanel" aria-label="Orders">
              <OrdersPanel orders={orders} loading={ordersLoading} />
            </div>
          )}
          {tab === "reservations" && (
            <div id="sidebar-panel-reservations" role="tabpanel" aria-label="Reservations">
              <ReservationsPanel reservations={reservations} loading={reservationsLoading} onRefetch={refetchReservations} />
            </div>
          )}
          {tab === "alerts" && (
            <div id="sidebar-panel-alerts" role="tabpanel" aria-label="Staff alerts">
              <AlertsPanel />
            </div>
          )}
          {tab === "activity" && (
            <div id="sidebar-panel-activity" role="tabpanel" aria-label="Activity">
              <ActivityPanel />
            </div>
          )}
          {tab === "sessions" && (
            <div id="sidebar-panel-sessions" role="tabpanel" aria-label="Sessions">
              <SessionsPanel onSelectSession={onSelectSession} activeSessionId={activeSessionId} />
            </div>
          )}
        </div>

        <div className="sidebar__footer">
          <button className="sidebar__logout" onClick={() => dispatch(logout())}>
            Sign out
          </button>
        </div>
      </aside>
    </>
  );
}

function AlertsPanel() {
  const { data, isLoading } = useGetStaffNotificationsQuery({ status: "pending" });
  const [updateNotification] = useUpdateStaffNotificationMutation();
  const notifications = data?.results ?? [];

  if (isLoading) return <div className="sidebar__loading">Loading alerts...</div>;
  if (!notifications.length) return <div className="sidebar__empty">No pending staff alerts.</div>;

  return (
    <div className="alerts-panel">
      {notifications.map((n: { id: number; priority: string; reason: string; customer_name: string; customer_id: string; created_at: string }) => (
        <div key={n.id} className={`alerts-panel__item alerts-panel__item--${n.priority}`}>
          <div className="alerts-panel__item-header">
            <span className="alerts-panel__item-id">#{n.id}</span>
            <span className={`orders-panel__badge orders-panel__badge--${n.priority === "high" ? "cancelled" : n.priority === "medium" ? "placed" : "draft"}`}>
              {n.priority}
            </span>
          </div>
          <p className="alerts-panel__item-reason">{n.reason}</p>
          <div className="alerts-panel__item-meta">
            <span>{n.customer_name || n.customer_id || "Unknown guest"}</span>
            <span>{new Date(n.created_at).toLocaleString()}</span>
          </div>
          <div className="alerts-panel__actions">
            <button
              className="alerts-panel__btn alerts-panel__btn--ack"
              onClick={() => updateNotification({ id: n.id, status: "acknowledged" })}
            >
              Acknowledge
            </button>
            <button
              className="alerts-panel__btn alerts-panel__btn--resolve"
              onClick={() => updateNotification({ id: n.id, status: "resolved" })}
            >
              Resolve
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function MenuPanel({
  items,
  loading,
}: {
  items: Array<{ id: number; name: string; description: string; price: string; category: string; is_available: boolean }> | undefined;
  loading: boolean;
}) {
  if (loading) return <div className="sidebar__loading">Loading menu...</div>;
  if (!items?.length) return <div className="sidebar__empty">No menu items found.</div>;

  const grouped = items.reduce<Record<string, typeof items>>((acc, item) => {
    const cat = item.category || "Other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(item);
    return acc;
  }, {});

  return (
    <div className="menu-panel">
      {Object.entries(grouped).map(([category, catItems]) => (
        <div key={category} className="menu-panel__group">
          <h4 className="menu-panel__category">{category}</h4>
          {catItems.map((item) => (
            <div
              key={item.id}
              className={`menu-panel__item ${!item.is_available ? "menu-panel__item--unavailable" : ""}`}
            >
              <div className="menu-panel__item-header">
                <span className="menu-panel__item-name">{item.name}</span>
                <span className="menu-panel__item-price">${item.price}</span>
              </div>
              <p className="menu-panel__item-desc">{item.description}</p>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function OrdersPanel({
  orders,
  loading,
}: {
  orders: Array<{ id: number; status: string; created_at: string; total_amount: string }>;
  loading: boolean;
}) {
  if (loading) return <div className="sidebar__loading">Loading orders...</div>;
  if (!orders.length) return <div className="sidebar__empty">No orders yet. Start chatting to place one!</div>;

  return (
    <div className="orders-panel">
      {orders.map((order) => (
        <div key={order.id} className="orders-panel__item">
          <div className="orders-panel__item-header">
            <span className="orders-panel__item-id">Order #{order.id}</span>
            <span className={`orders-panel__badge orders-panel__badge--${order.status}`}>
              {order.status}
            </span>
          </div>
          <div className="orders-panel__item-meta">
            <span>${order.total_amount}</span>
            <span>{new Date(order.created_at).toLocaleDateString()}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ReservationsPanel({
  reservations,
  loading,
  onRefetch,
}: {
  reservations: Array<{ id: number; status: string; party_size: number; reservation_time: string; held_until: string | null }>;
  loading: boolean;
  onRefetch?: () => void;
}) {
  if (loading) return <div className="sidebar__loading">Loading reservations...</div>;
  if (!reservations.length) return <div className="sidebar__empty">No reservations yet.</div>;

  return (
    <div className="reservations-panel">
      {reservations.map((res) => (
        <div key={res.id} className="reservations-panel__item">
          <div className="reservations-panel__item-header">
            <span className="reservations-panel__item-id">Table for {res.party_size}</span>
            <span className={`orders-panel__badge orders-panel__badge--${res.status}`}>
              {res.status}
            </span>
          </div>
          <div className="reservations-panel__item-meta">
            <span>{new Date(res.reservation_time).toLocaleString()}</span>
            {res.status === "held" && res.held_until && (
              <CountdownTimer expiresAt={res.held_until} onExpired={onRefetch} />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

interface ToolLog {
  id: number;
  tool_name: string;
  success: boolean;
  duration_ms: number | null;
  outcome: string;
  created_at: string;
}

function ActivityPanel() {
  const { data, isLoading } = useGetToolLogsQuery({ limit: 30 });
  const logs = (data?.results ?? []) as ToolLog[];

  if (isLoading) return <div className="sidebar__loading">Loading activity...</div>;
  if (!logs.length) return <div className="sidebar__empty">No tool activity yet.</div>;

  const successCount = logs.filter((l) => l.success).length;
  const failCount = logs.length - successCount;
  const avgDuration = logs.reduce((sum, l) => sum + (l.duration_ms ?? 0), 0) / (logs.length || 1);

  return (
    <div className="activity-panel">
      <div className="activity-panel__stats">
        <div className="activity-panel__stat">
          <span className="activity-panel__stat-value">{logs.length}</span>
          <span className="activity-panel__stat-label">Total calls</span>
        </div>
        <div className="activity-panel__stat activity-panel__stat--success">
          <span className="activity-panel__stat-value">{successCount}</span>
          <span className="activity-panel__stat-label">Succeeded</span>
        </div>
        <div className="activity-panel__stat activity-panel__stat--fail">
          <span className="activity-panel__stat-value">{failCount}</span>
          <span className="activity-panel__stat-label">Failed</span>
        </div>
        <div className="activity-panel__stat">
          <span className="activity-panel__stat-value">{Math.round(avgDuration)}ms</span>
          <span className="activity-panel__stat-label">Avg duration</span>
        </div>
      </div>
      <div className="activity-panel__list">
        {logs.map((log) => (
          <div key={log.id} className={`activity-panel__item ${!log.success ? "activity-panel__item--fail" : ""}`}>
            <div className="activity-panel__item-header">
              <span className="activity-panel__item-name">{log.tool_name}</span>
              <span className={`orders-panel__badge orders-panel__badge--${log.success ? "paid" : "cancelled"}`}>
                {log.outcome}
              </span>
            </div>
            <div className="activity-panel__item-meta">
              <span>{log.duration_ms !== null ? `${log.duration_ms}ms` : "—"}</span>
              <span>{new Date(log.created_at).toLocaleTimeString()}</span>
            </div>
          </div>
         ))}
      </div>
    </div>
  );
}

function SessionsPanel({
  onSelectSession,
  activeSessionId,
}: {
  onSelectSession?: (sessionId: string) => void;
  activeSessionId?: string;
}) {
  const { data, isLoading } = useGetSessionsQuery(undefined);
  const [deleteSession] = useDeleteSessionMutation();
  const sessions = data?.results ?? [];

  if (isLoading) return <div className="sidebar__loading">Loading sessions...</div>;
  if (!sessions.length) return <div className="sidebar__empty">No conversations yet. Start chatting!</div>;

  return (
    <div className="sessions-panel">
      {sessions.map((session: { id: string; title: string; message_count: number; updated_at: string }) => (
        <div
          key={session.id}
          className={`sessions-panel__item ${activeSessionId === session.id ? "sessions-panel__item--active" : ""}`}
          onClick={() => onSelectSession?.(session.id)}
        >
          <div className="sessions-panel__item-header">
            <span className="sessions-panel__item-title">{session.title}</span>
            <button
              className="sessions-panel__delete"
              onClick={(e) => {
                e.stopPropagation();
                deleteSession(session.id);
              }}
              aria-label="Delete session"
            >
              ✕
            </button>
          </div>
          <div className="sessions-panel__item-meta">
            <span>{session.message_count} messages</span>
            <span>{new Date(session.updated_at).toLocaleDateString()}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
