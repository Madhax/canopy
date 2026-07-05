import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ToastProvider } from "./components/common";
import { MainLayout } from "./components/MainLayout";
import { OrganizationListPage } from "./pages/OrganizationListPage";
import { NewOrganizationWizard } from "./pages/NewOrganizationWizard";
import { EditorPage } from "./pages/EditorPage";
import { ActuatePage, ExecutePage } from "./pages/PhasePlaceholderPage";

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
              <Route path="/" element={<OrganizationListPage />} />
              <Route path="/actuate" element={<ActuatePage />} />
              <Route path="/execute" element={<ExecutePage />} />
            </Route>
            <Route path="/organizations/new" element={<NewOrganizationWizard />} />
            <Route path="/organizations/:id" element={<EditorPage />} />
            <Route path="/organizations/:id/org/*" element={<EditorPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
