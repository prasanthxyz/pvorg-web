import { lazy, Suspense, useEffect, useRef } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { CleanupDialog } from "../components/CleanupDialog";
import { Button } from "../components/controls";
import { AlertHost } from "../components/Dialog";
import { EmptyState, ToastRegion } from "../components/feedback";
import { MenuHost } from "../components/Menu";
import { PreviewHost } from "../components/Preview";
import { hasAnyPending } from "../state/mapping";
import { connectionError, pollStatus, status } from "../state/status";
import { useStore } from "../state/store";
import { installShortcuts } from "./shortcuts";
import { Shell } from "./Shell";
import { StartupError, StartupProgress } from "./Startup";

const ViewerPage = lazy(() => import("../pages/ViewerPage"));
const FiltersPage = lazy(() => import("../pages/FiltersPage"));
const LibraryPage = lazy(() => import("../pages/LibraryPage"));
const MappingPage = lazy(() => import("../pages/MappingPage"));
const SettingsPage = lazy(() => import("../pages/SettingsPage"));

function NotFound() {
  const navigate = useNavigate();
  return (
    <EmptyState icon="viewer" title="Page Not Found" actions={<Button onClick={() => navigate("/")}>Open Viewer</Button>}>
      This address isn’t part of pvorg.
    </EmptyState>
  );
}

/** Moves focus to the page heading after in-app navigation, for screen readers and keyboard users. */
function useFocusOnNavigate() {
  const location = useLocation();
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const heading = document.getElementById("page-title");
    if (heading) {
      heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
    }
  }, [location.pathname]);
}

export default function App() {
  const current = useStore(status);
  const offline = useStore(connectionError);
  const navigate = useNavigate();
  const ready = current?.phase === "ready";
  const readyRef = useRef(ready);
  readyRef.current = ready;

  useEffect(() => {
    void pollStatus();
  }, []);

  useEffect(() => installShortcuts(navigate, () => readyRef.current), [navigate]);

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (hasAnyPending()) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  useFocusOnNavigate();

  let content;
  if (current?.phase === "error") content = <StartupError status={current} />;
  else if (!ready) content = <StartupProgress status={current} offline={offline && !current} />;
  else
    content = (
      <Shell>
        <Suspense fallback={null}>
          <Routes>
            <Route path="/" element={<ViewerPage />} />
            <Route path="/filters" element={<FiltersPage />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/mapping/galleries" element={<MappingPage key="galleries" kind="galleries" />} />
            <Route path="/mapping/tags" element={<MappingPage key="tags" kind="tags" />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/config" element={<Navigate to="/filters" replace />} />
            <Route path="/deleter" element={<Navigate to="/library" replace />} />
            <Route path="/mapper" element={<Navigate to="/mapping/galleries" replace />} />
            <Route path="/tag-mapper" element={<Navigate to="/mapping/tags" replace />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </Shell>
    );

  return (
    <>
      {content}
      <ToastRegion />
      <AlertHost />
      <MenuHost />
      <PreviewHost />
      {ready && <CleanupDialog />}
    </>
  );
}
