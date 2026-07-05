import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";

// The app shell for the top-level phase pages (Build list, Actuate, Execute).
// The editor and wizard render full-screen without this shell.
export function MainLayout() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="min-w-0 flex-1 overflow-y-auto">
        <Outlet />
      </div>
    </div>
  );
}
