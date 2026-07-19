import { Navigate, useLocation } from "react-router-dom";
import { useAppSelector } from "./hooks";
import { Chat } from "./components/Chat";

export function AppShell() {
  const isAuthenticated = useAppSelector((s) => s.auth.isAuthenticated);
  const user = useAppSelector((s) => s.auth.user);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Wait for user data to be loaded before rendering Chat
  if (!user) {
    return <div>Loading...</div>;
  }

  return <Chat userId={user.id.toString()} />;
}
