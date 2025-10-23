import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { API_URL } from "../config";
import "./Info.css";

export default function InfoPage() {
  const { classId } = useParams();
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const res = await fetch(`${API_URL}/api/classes/${classId}/presentation-info`);
        if (!res.ok) throw new Error("Failed to fetch presentation info");
        const data = await res.json();
        setInfo(data);
      } catch (err) {
        console.error(err);
        setError(err.message);
      }
    };
    fetchInfo();
  }, [classId]);

  return (
    <div className="info-page">
      <div className="info-container">
        <h1>Presentation Info</h1>
        {error && <p className="error-text">{error}</p>}

        {!info && !error && <p>Loading presentation info...</p>}

        {info && (
          <div className="info-card">
            <p><strong>Presentation ID:</strong> {info.presentation_id}</p>
            <p><strong>Class ID:</strong> {info.class_id}</p>
            <p><strong>Slide Count:</strong> {info.slide_count}</p>
            <p><strong>Started At:</strong> {info.started_at || "Not started yet"}</p>
            <p><strong>Ended At:</strong> {info.ended_at || "Not ended yet"}</p>
            <p><strong>Duration (seconds):</strong> {info.duration_seconds || "N/A"}</p>
            <p><strong>File Path:</strong> {info.pptx_path}</p>
          </div>
        )}

        <button className="back-button" onClick={() => navigate(-1)}>
          ⬅ Back
        </button>
      </div>
    </div>
  );
}
