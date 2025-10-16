import React, { useState } from "react";
import "./CreateClassModal.css";
import { API_URL } from "../config";

export default function CreateClassModal({ userId, onClose, onClassCreated }) {
  const [formData, setFormData] = useState({
    class_name: "",
    subject: "",
    difficulty_level: "",
    pptx_file: null,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value, files } = e.target;
    setFormData({
      ...formData,
      [name]: files ? files[0] : value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const formDataToSend = new FormData();
    formDataToSend.append("class_name", formData.class_name);
    formDataToSend.append("subject", formData.subject);
    formDataToSend.append("difficulty_level", formData.difficulty_level);
    formDataToSend.append("user_id", userId);
    formDataToSend.append("pptx_file", formData.pptx_file);

    try {
      const response = await fetch(`${API_URL}/api/classes`, {
        method: "POST",
        body: formDataToSend,
      });

      if (!response.ok) throw new Error("Failed to create class");

      const newClass = await response.json();
      onClassCreated(newClass);
      onClose();
    } catch (err) {
      console.error(err);
      setError("Error creating class. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2>Create New Class</h2>

        <form onSubmit={handleSubmit}>
          <label>
            Class Name (optional)
            <input
              type="text"
              name="class_name"
              value={formData.class_name}
              onChange={handleChange}
              placeholder="e.g., Algebra Basics"
            />
          </label>

          <label>
            Subject *
            <input
              type="text"
              name="subject"
              value={formData.subject}
              onChange={handleChange}
              required
              placeholder="e.g., Math"
            />
          </label>

          <label>
            Difficulty Level *
            <select
              name="difficulty_level"
              value={formData.difficulty_level}
              onChange={handleChange}
              required
            >
              <option value="">Select...</option>
              <option value="Beginner">Beginner</option>
              <option value="Intermediate">Intermediate</option>
              <option value="Advanced">Advanced</option>
            </select>
          </label>

          <label>
            Upload PowerPoint (.pptx) *
            <input
              type="file"
              name="pptx_file"
              accept=".pptx"
              onChange={handleChange}
              required
            />
          </label>

          {error && <div className="error">{error}</div>}

          <div className="modal-buttons">
            <button type="button" onClick={onClose} className="cancel-btn">
              Cancel
            </button>
            <button type="submit" disabled={loading} className="submit-btn">
              {loading ? "Creating..." : "Create Class"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
