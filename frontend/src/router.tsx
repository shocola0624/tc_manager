import { Navigate, Route, Routes } from "react-router-dom";
import { ActivitiesPage } from "./activities/ActivitiesPage";
import { ActivityDetailPage } from "./activities/ActivityDetailPage";
import { ItemSelectionPage } from "./activities/ItemSelectionPage";
import { useAuth } from "./auth/AuthProvider";
import { CalendarPage } from "./calendar/CalendarPage";
import { AppLayout } from "./components/AppLayout";
import { useI18n } from "./i18n/useI18n";
import { ItemsPage } from "./items/ItemsPage";
import { ErrorPage } from "./pages/ErrorPage";
import { HomePage } from "./pages/HomePage";
import { InactivePage } from "./pages/InactivePage";
import { LoginPage } from "./pages/LoginPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RegisterPage } from "./pages/RegisterPage";
import { TasksPage } from "./tasks/TasksPage";

/**
 * 認証状態に応じたルーティング。状態は AuthProvider が GET /auth/me の結果
 * (または ApiError.code)から正規化したものを使う。
 */
export function AppRouter() {
  const { status, errorCode } = useAuth();
  const { t } = useI18n();

  if (status === "loading") {
    return <p>{t("common.loading")}</p>;
  }

  if (status === "error") {
    return <ErrorPage code={errorCode} />;
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={status === "authenticated" ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/register"
        element={
          status === "pending" ? (
            <RegisterPage />
          ) : status === "authenticated" ? (
            <Navigate to="/" replace />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route
        path="/inactive"
        element={status === "inactive" ? <InactivePage /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/*"
        element={
          status === "authenticated" ? (
            <AppLayout />
          ) : status === "pending" ? (
            <Navigate to="/register" replace />
          ) : status === "inactive" ? (
            <Navigate to="/inactive" replace />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      >
        <Route index element={<HomePage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="items" element={<ItemsPage />} />
        <Route path="activities" element={<ActivitiesPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="activities/:activityId" element={<ActivityDetailPage />} />
        <Route path="activities/:activityId/select-item" element={<ItemSelectionPage />} />
      </Route>
    </Routes>
  );
}
