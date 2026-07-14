import { Routes, Route, Navigate } from "react-router-dom";
import { AuthScreen } from "./components/AuthScreen";
import { AppShell } from "./AppShell";

function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthScreen />} />
      <Route path="/" element={<AppShell />} />
      <Route path="/history" element={<AppShell />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
