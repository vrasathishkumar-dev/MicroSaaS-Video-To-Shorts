import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AuthProvider } from '@/context/AuthContext';
import { AdminPage } from '@/pages/AdminPage';
import { AdminUsersPage } from '@/pages/AdminUsersPage';
import { ClipEditorPage } from '@/pages/ClipEditorPage';
import { ClipsPage } from '@/pages/ClipsPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage';
import { HomePage } from '@/pages/HomePage';
import { LoginPage } from '@/pages/LoginPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { RegisterPage } from '@/pages/RegisterPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { VideoDetailPage } from '@/pages/VideoDetailPage';
import { VideoSubmitPage } from '@/pages/VideoSubmitPage';
import { VideosPage } from '@/pages/VideosPage';

/**
 * Top-level route table. Every module's pages are wired in here rather
 * than by each module's own agent, so nobody edits this file concurrently.
 * Protected routes are gated by AuthContext-backed <ProtectedRoute>.
 */
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />

          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/videos"
            element={
              <ProtectedRoute>
                <VideosPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/videos/new"
            element={
              <ProtectedRoute>
                <VideoSubmitPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/videos/:id"
            element={
              <ProtectedRoute>
                <VideoDetailPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/clips"
            element={
              <ProtectedRoute>
                <ClipsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/clips/:id"
            element={
              <ProtectedRoute>
                <ClipEditorPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <AdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <ProtectedRoute>
                <AdminUsersPage />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
