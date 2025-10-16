import React, { useState, useEffect } from "react";
import { API_URL } from "../config";
import "./Home.css";

export default function HomePage({ user }) {
  const [linkCode, setLinkCode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [codeExpiry, setCodeExpiry] = useState(null);

  // Check if user already has Telegram linked
  const isTelegramLinked = user?.telegram_chat_id !== null;

  const generateLinkCode = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/users/${user.id}/link-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) {
        throw new Error("Failed to generate link code");
      }

      const data = await response.json();
      setLinkCode(data.telegram_link_code);
      
      // Set expiry time (15 minutes from now)
      const expiryTime = new Date();
      expiryTime.setMinutes(expiryTime.getMinutes() + 15);
      setCodeExpiry(expiryTime);
    } catch (err) {
      console.error("Error generating link code:", err);
      setError("Failed to generate link code. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Countdown timer for code expiry (it isnt working but shit looks good, check if you can fix it fer)
  useEffect(() => {
    if (!codeExpiry) return;

    const interval = setInterval(() => {
      const now = new Date();
      const timeLeft = codeExpiry - now;

      if (timeLeft <= 0) {
        setLinkCode(null);
        setCodeExpiry(null);
        clearInterval(interval);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [codeExpiry]);

  const getTimeRemaining = () => {
    if (!codeExpiry) return "";
    
    const now = new Date();
    const timeLeft = Math.max(0, codeExpiry - now);
    const minutes = Math.floor(timeLeft / 60000);
    const seconds = Math.floor((timeLeft % 60000) / 1000);
    
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="home-page">
      <div className="home-container">
        <div className="welcome-section">
          <h1>Welcome to Class Assistant! 🎓</h1>
          <p className="subtitle">
            Your AI-powered educational platform for interactive learning
          </p>
          <div className="user-info">
            <p>Logged in as: <strong>{user?.email}</strong></p>
          </div>
        </div>

        <div className="telegram-section">
          <div className="section-card">
            <div className="card-header">
              <h2>📱 Link Your Telegram Account</h2>
            </div>
            <div className="card-body">
              {isTelegramLinked ? (
                <div className="success-message">
                  <div className="success-icon">✓</div>
                  <h3>Telegram Linked Successfully!</h3>
                  <p>Your Telegram account is connected and ready to use.</p>
                  <p className="info-text">
                    You can now interact with the Class Assistant bot on Telegram
                    to ask questions during presentations.
                  </p>
                </div>
              ) : (
                <>
                  <p className="instruction-text">
                    Link your Telegram account to interact with the Class Assistant bot
                    during presentations. You'll be able to ask questions and receive
                    AI-generated answers in real-time!
                  </p>

                  {!linkCode ? (
                    <button
                      className="generate-button"
                      onClick={generateLinkCode}
                      disabled={loading}
                    >
                      {loading ? "Generating..." : "Generate Link Code"}
                    </button>
                  ) : (
                    <div className="link-code-section">
                      <div className="code-display">
                        <div className="code-label">Your Link Code:</div>
                        <div className="code-value">{linkCode}</div>
                        <div className="code-timer">
                          Expires in: {getTimeRemaining()}
                        </div>
                      </div>

                      <div className="instructions">
                        <h4>How to link:</h4>
                        <ol>
                          <li>Open Telegram and search for <strong>@ClassAssistantBot</strong></li>
                          <li>Start a chat with the bot</li>
                          <li>Send the command: <code>/link {linkCode}</code></li>
                          <li>Wait for confirmation</li>
                        </ol>
                      </div>

                      <button
                        className="regenerate-button"
                        onClick={generateLinkCode}
                        disabled={loading}
                      >
                        Generate New Code
                      </button>
                    </div>
                  )}

                  {error && <div className="error-message">{error}</div>}
                </>
              )}
            </div>
          </div>
        </div>

        <div className="features-section">
          <h2>Coming Soon:</h2>
          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon">📚</div>
              <h3>Create Classes</h3>
              <p>Organize your learning materials by subject and difficulty level</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">🎤</div>
              <h3>Start Presentations</h3>
              <p>Upload PowerPoint files and begin interactive sessions</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">🤖</div>
              <h3>AI Q&A</h3>
              <p>Ask questions via Telegram and get instant AI-generated answers</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">📊</div>
              <h3>Track Progress</h3>
              <p>View your presentation history and question analytics</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
