import { useState } from "react";
import { useAppSelector, useAppDispatch } from "../hooks";
import { logout } from "../slices/authSlice";
import { useGetMenuItemsQuery, useGetOrdersQuery, useGetReservationsQuery } from "../services/api";
import "./Sidebar.css";

type Tab = "menu" | "orders" | "reservations";

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.auth.user);
  const [tab, setTab] = useState<Tab>("menu");

  const { data: menuItems, isLoading: menuLoading } = useGetMenuItemsQuery(undefined);
  const { data: ordersData, isLoading: ordersLoading } = useGetOrdersQuery(undefined);
  const { data: reservationsData, isLoading: reservationsLoading } = useGetReservationsQuery(undefined);

  const orders = ordersData?.results ?? [];
  const reservations = reservationsData?.results ?? [];

  return (
    <>
      {open && <div className="sidebar-backdrop" onClick={onClose} />}
      <aside className={`sidebar ${open ? "sidebar--open" : ""}`}>
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

        <nav className="sidebar__tabs">
          <button
            className={`sidebar__tab ${tab === "menu" ? "sidebar__tab--active" : ""}`}
            onClick={() => setTab("menu")}
          >
            Menu
          </button>
          <button
            className={`sidebar__tab ${tab === "orders" ? "sidebar__tab--active" : ""}`}
            onClick={() => setTab("orders")}
          >
            Orders
          </button>
          <button
            className={`sidebar__tab ${tab === "reservations" ? "sidebar__tab--active" : ""}`}
            onClick={() => setTab("reservations")}
          >
            Reservations
          </button>
        </nav>

        <div className="sidebar__body">
          {tab === "menu" && (
            <MenuPanel items={menuItems} loading={menuLoading} />
          )}
          {tab === "orders" && (
            <OrdersPanel orders={orders} loading={ordersLoading} />
          )}
          {tab === "reservations" && (
            <ReservationsPanel reservations={reservations} loading={reservationsLoading} />
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
}: {
  reservations: Array<{ id: number; status: string; party_size: number; reservation_time: string }>;
  loading: boolean;
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
          </div>
        </div>
      ))}
    </div>
  );
}
