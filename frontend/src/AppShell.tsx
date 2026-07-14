import { Navigate, useLocation } from "react-router-dom";
import { useAppSelector } from "./hooks";
import { Chat } from "./components/Chat";

export function AppShell() {
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Chat />;
}
