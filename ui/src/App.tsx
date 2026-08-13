import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ToastProvider } from "./components/common";
import { MainLayout } from "./components/MainLayout";
import { PortfolioPage } from "./pages/PortfolioPage";
import { OrgPage } from "./pages/OrgPage";
import { CapacityPage } from "./pages/CapacityPage";
import { NewTeamWizard } from "./pages/NewTeamWizard";
import { EditorPage } from "./pages/EditorPage";
import { ActuatePage } from "./pages/ActuatePage";
import { ExecutePage } from "./pages/ExecutePage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<MainLayout />}>
              <Route path="/" element={<PortfolioPage />} />
              <Route path="/orgs/:id" element={<OrgPage />} />
              <Route path="/capacity" element={<CapacityPage />} />
              <Route path="/actuate" element={<ActuatePage />} />
              <Route path="/execute" element={<ExecutePage />} />
            </Route>
            <Route path="/teams/new" element={<NewTeamWizard />} />
            <Route path="/teams/:id" element={<EditorPage />} />
            <Route path="/teams/:id/team/*" element={<EditorPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
