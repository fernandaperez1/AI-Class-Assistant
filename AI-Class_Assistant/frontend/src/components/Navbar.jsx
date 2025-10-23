import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { logout } from "../services/auth";
import "./Navbar.css";
import logo from "../assets/logo_blanco.png";

export default function Navbar({ user }) {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await logout();
      navigate("/login");
    } catch (error) {
      console.error("Error logging out:", error);
    }
  };

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <Link className="navbar-brand" to="/home">
          <img src={logo} alt="TutorFlow logo" className="navbar-logo" />
          <span className="navbar-title">TutorFlow</span>
        </Link>

        <div className="navbar-menu">
          <Link className="nav-link" to="/home">
            Home
          </Link>
          <Link className="nav-link" to="/chat">
            Chat
          </Link>
        </div>

        <div className="navbar-user">
          <span className="user-email">
            {user?.email || "User"}
          </span>
          <button className="logout-button" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}
