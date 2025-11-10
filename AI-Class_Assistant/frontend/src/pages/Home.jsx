import React, { useState, useEffect } from "react";
import CreateClassModal from "../components/CreateClassModal";
import { useNavigate } from "react-router-dom";
import { API_URL } from "../config";
import socket from "../sockets/socket";
import "./Home.css";
import qrcode from "../assets/qr_code_no_bg.png";

export default function HomePage({ user }) {
  const [linkCode, setLinkCode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [codeExpiry, setCodeExpiry] = useState(null);
  const [isTelegramOpen, setIsTelegramOpen] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [classes, setClasses] = useState([]);
  const [isUnlinking, setIsUnlinking] = useState(false);

  const navigate = useNavigate();

  const isTelegramLinked = user?.telegram_chat_id !== null;

  const fetchClasses = async () => {
    try {
      const res = await fetch(`${API_URL}/api/users/${user.id}/classes`);
      if (!res.ok) throw new Error("Failed to fetch classes");
      const data = await res.json();
      setClasses(data);
    } catch (err) {
      console.error(err);
      setError("Failed to load classes");
    }
  };

  useEffect(() => {
    if (user?.id) fetchClasses();
  }, [user]);

  //listen for telegram:linked event to update UI
  useEffect(() => {
    if (!user?.firebase_uid) return;

    const handleTelegramLinked = (data) => {
      //only update if the event is for the current user
      if (data.firebase_uid === user.firebase_uid) {
        console.log("[TELEGRAM] Account linked via WebSocket, reloading page...");
        // Reload the page to fetch updated user data
        window.location.reload();
      }
    };

    socket.on("telegram:linked", handleTelegramLinked);

    return () => {
      socket.off("telegram:linked", handleTelegramLinked);
    };
  }, [user?.firebase_uid]);

  const handleDeleteClass = async (classId) => {
    if (!window.confirm("Are you sure you want to delete this class?")) return;

    try {
      const response = await fetch(`${API_URL}/api/classes/${classId}/delete`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: user.id }),
      });

      if (!response.ok) throw new Error("Failed to delete class");

      setClasses(classes.filter((c) => c.id !== classId));
    } catch (err) {
      console.error(err);
      alert("Error deleting class. Please try again.");
    }
  };

  const handleDownloadPresentation = async (classId) => {
    try {
      const response = await fetch(`${API_URL}/api/classes/${classId}/presentation/download`);
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to download presentation");
      }

      //this should be able to get the filename from the Content-Disposition header, otherwise I use a default
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = 'presentation.pptx';
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      
      //cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert(`Error downloading presentation: ${err.message}`);
    }
  };

  const handleResetPresentation = async (classId) => {
    if (!window.confirm("Are you sure you want to reset this presentation to its original state? All AI-generated slides will be removed.")) return;

    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/api/classes/${classId}/presentation/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to reset presentation");
      }
      const data = await response.json();
      //update the class in the list with new slide count (need to also update the presentation info, resetting the AI responses)
      setClasses(classes.map(c => 
        c.id === classId 
          ? { ...c, slide_count: data.slide_count }
          : c
      ));
      alert("Presentation reset successfully!");
    } catch (err) {
      console.error(err);
      alert(`Error resetting presentation: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

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
    setClasses([...classes, newClass]);
    setShowModal(false);
  };

  const handleUnlinkTelegram = async () => {
    if (!user?.telegram_chat_id) return;

    if (!window.confirm("Are you sure you want to unlink your Telegram account?")) return;

    setIsUnlinking(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/telegram/unlink`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_chat_id: user.telegram_chat_id }), 
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to unlink Telegram");
      }

      alert("Telegram account unlinked successfully! Reloading page...");
      window.location.reload();
      
    } catch (err) {
      console.error("Error unlinking Telegram:", err);
      setError(`Failed to unlink Telegram: ${err.message}`);
    } finally {
      setIsUnlinking(false);
    }
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
                    <button
                        className="generate-button"
                        onClick={handleUnlinkTelegram}
                        disabled={isUnlinking}
                    >
                        {isUnlinking ? "Unlinking..." : "Unlink Telegram"}
                    </button>
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

                        <div className="link-section-container">
                            <div className="instructions">
                                <h4>How to link:</h4>
                                <ol>
                                    <li>
                                        Scan the QR code or open Telegram and search for{" "}
                                        <strong>@TutorsFlow_Bot</strong>
                                    </li>
                                    <li>Start a chat with the bot</li>
                                    <li>
                                        Send: <code>/link {linkCode}</code>
                                    </li>
                                </ol>
                            </div>

                            <div className="qr-container">
                                <img
                                    src={qrcode}
                                    alt="Telegram Bot QR"
                                    className="qr-image"
                                />
                            </div>
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

  {/* Create Class Button */}
  <div className="create-class-button-wrapper">
    <button
      className="generate-button"
      onClick={() => setShowModal(true)}
    >
      + Create New Class
    </button>
  </div>

  {/* Classes Grid */}
  <div className="features-grid">
    {classes.map((cls) => (
      <div key={cls.id} className="feature-card">
        <h3>{cls.class_name || "Untitled Class"}</h3>
        <p>Subject: {cls.subject}</p>
        <p>Difficulty: {cls.difficulty_level}</p>
        {cls.class_language && (
          <p>Language: {cls.class_language}</p>
        )}
        {cls.presentation_id && cls.slide_count && (
          <p className="slide-info">Slides: {cls.slide_count}</p>
        )}
        <div className="class-buttons">
          <button
            className="info-button"
            onClick={() => navigate(`/class/${cls.id}/info`)}
          >
            Info
          </button>
          {cls.presentation_id && (
            <>
              <button
                className="download-button"
                onClick={() => handleDownloadPresentation(cls.id)}
                title="Download PPTX file"
              >
                Download
              </button>
              <button
                className="reset-button"
                onClick={() => handleResetPresentation(cls.id)}
                title="Reset presentation to original"
              >
                Reset
              </button>
            </>
          )}
          <button
            className="delete-button"
            onClick={() => handleDeleteClass(cls.id)}
          >
            Delete
          </button>
          <button
            className="start-button"
            onClick={() => navigate(`/class/${cls.id}/presentation`)}
          >
            Start
          </button>
        </div>
      </div>
    ))}
  </div>
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