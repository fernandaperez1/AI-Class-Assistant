import React, { useState } from "react";
import { signInWithGoogle } from "../firebase";
import { API_URL } from "../config";
import "./Login.css";
import { useNavigate } from "react-router-dom";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError(null);

    try {
      const fbUser = await signInWithGoogle();
      console.log("Firebase user logged in:", fbUser.uid);

      // Check if user exists in backend
      let backendUser;
      try {
        const getRes = await fetch(`${API_URL}/api/users/${fbUser.uid}`);
        
        if (getRes.ok) {
          backendUser = await getRes.json();
          console.log("User found in backend:", backendUser);
        } else if (getRes.status === 404) {
          // User doesn't exist, create new user
          console.log("User not found, creating new user...");
          const createRes = await fetch(`${API_URL}/api/users`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              firebase_uid: fbUser.uid,
              email: fbUser.email,
            }),
          });

          if (!createRes.ok) {
            throw new Error("Failed to create user in backend");
          }

          backendUser = await createRes.json();
          console.log("User created in backend:", backendUser);
        } else {
          throw new Error("Failed to fetch user from backend");
        }
      } catch (err) {
        console.error("Backend error:", err);
        throw new Error("Could not connect to backend");
      }

      navigate('/home', { replace: true });

      // User is now authenticated and stored in backend
      // The App.jsx will handle the navigation through auth state change
      
    } catch (err) {
      console.error("Login failed:", err);
      setError(err.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1 className="login-title">Welcome to Class Assistant</h1>
        <p className="login-subtitle">
          Your AI-powered educational assistant for interactive learning
        </p>
        
        {error && <div className="login-error">{error}</div>}
        
        <button 
          className="login-button" 
          onClick={handleGoogleLogin}
          disabled={loading}
        >
          {loading ? "Logging in..." : "Log in with Google"}
        </button>
        
        <p className="login-info">
          Sign in to create classes, interact with AI-generated content, and link your Telegram account
        </p>
      </div>
    </div>
  );
}
