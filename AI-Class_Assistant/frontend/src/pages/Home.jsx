import React, { useState, useEffect } from "react";
import CreateClassModal from "../components/CreateClassModal";
import { API_URL } from "../config";
import "./Home.css";

export default function HomePage({ user }) {
  const [linkCode, setLinkCode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [codeExpiry, setCodeExpiry] = useState(null);
  const [isTelegramOpen, setIsTelegramOpen] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const isTelegramLinked = user?.telegram_chat_id !== null;

  const generateLinkCode = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_URL}/api/users/${user.id}/link-code`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      );

      if (!response.ok) throw new Error("Failed to generate link code");

      const data = await response.json();
      setLinkCode(data.telegram_link_code);

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

  // Countdown timer (shit aint working xd, need to add a use effect)
  useEffect(() => {
    if (!codeExpiry) return;
    const interval = setInterval(() => {
      const now = new Date();
      if (now >= codeExpiry) {
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
    const diff = Math.max(0, codeExpiry - now);
    const min = Math.floor(diff / 60000);
    const sec = Math.floor((diff % 60000) / 1000);
    return `${min}:${sec.toString().padStart(2, "0")}`;
  };

  const toggleTelegram = () => setIsTelegramOpen(!isTelegramOpen);

  const handleClassCreated = (newClass) => {
    console.log("Class created:", newClass);
  };

  return (
    <div className="home-page">
      <div className="home-container">
        {/* Welcome */}
        <div className="welcome-section">
          <h1>Welcome to TutorFlow! 🎓</h1>
          <p className="subtitle">
            Your AI-powered educational platform to assist you with your classes
          </p>
        </div>

        {/* Telegram Section(I wanna make it smalled in the future) */}
        <div className="telegram-section">
          <div className="section-card">
            <div
              className="card-header collapsible-header"
              onClick={toggleTelegram}
            >
              <h2>📱 Link Your Telegram Account</h2>
              <span className="collapse-arrow">
                {isTelegramOpen ? "▲" : "▼"}
              </span>
            </div>

            {isTelegramOpen && (
              <div className="card-body">
                {isTelegramLinked ? (
                  <div className="success-message">
                    <div className="success-icon">✓</div>
                    <h3>Telegram Linked Successfully!</h3>
                    <p>Your Telegram account is connected and ready to use.</p>
                    <p className="info-text">
                      You can now interact with the Class Assistant bot on
                      Telegram to ask questions during presentations.
                    </p>
                  </div>
                ) : (
                  <>
                    <p className="instruction-text">
                      Link your Telegram account to interact with the bot during
                      presentations.
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
                            <li>
                              Open Telegram and search for{" "}
                              <strong>@ClassAssistantBot</strong>
                            </li>
                            <li>Start a chat with the bot</li>
                            <li>
                              Send: <code>/link {linkCode}</code>
                            </li>
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
            )}
          </div>
        </div>
        <div className="features-section">
          <h2>Your Classes</h2>
          <button
            className="generate-button"
            onClick={() => setShowModal(true)}
          >
            ➕ Create New Class
          </button>
        </div>

        {showModal && (
          <CreateClassModal
            userId={user.id}
            onClose={() => setShowModal(false)}
            onClassCreated={handleClassCreated}
          />
        )}
      </div>
    </div>
  );
}
