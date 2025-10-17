import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { subscribeToAuthChanges } from "./firebase";
import { API_URL } from "./config";
import ProtectedRoute from "./components/ProtectedRoute";
import Navbar from "./components/Navbar.jsx";
import Presentations from "./pages/Presentations.jsx";

import LoginPage from "./pages/Login";
import HomePage from "./pages/Home";
import ChatPage from "./pages/Chat";
import "./App.css";

export default function App() {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = subscribeToAuthChanges(async (firebaseUser) => {
      if (firebaseUser) {
        try {
          // Fetch user from backend
          const res = await fetch(`${API_URL}/api/users/${firebaseUser.uid}`);
          
          if (res.ok) {
            const backendUser = await res.json();
            console.log("Backend user loaded:", backendUser);
            setUser(backendUser);
          } else {
            console.error("Failed to fetch backend user, status:", res.status);
            setUser(null);
          }
        } catch (err) {
          console.error("Failed to fetch backend user:", err);
          setUser(null);
        }
      } else {
        setUser(null);
      }
      setAuthLoading(false);
    });

    return () => unsubscribe();
  }, []);

  if (authLoading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <BrowserRouter>
      {user && <Navbar user={user} />}
      <Routes>
        <Route
          path="/login"
          element={user ? <Navigate to="/home" replace /> : <LoginPage />}
        />

        <Route
          path="/home"
          element={
            <ProtectedRoute user={user}>
              <HomePage user={user} />
            </ProtectedRoute>
          }
        />

        <Route
          path="/class/:classId/presentation"
          element={
            <ProtectedRoute user={user}>
              <Presentations user={user} />
            </ProtectedRoute>
          }
        />

        <Route
          path="/chat"
          element={
            <ProtectedRoute user={user}>
              <ChatPage user={user} />
            </ProtectedRoute>
          }
        />

        {/* Default redirect */}
        <Route path="*" element={<Navigate to={user ? "/home" : "/login"} replace />} />
      </Routes>
    </BrowserRouter>
  );
}
