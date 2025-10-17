import React, { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import Reveal from "reveal.js";
import "reveal.js/dist/reveal.css";
import "reveal.js/dist/theme/black.css";
import "./Presentations.css";

function Presentations({ user }) {
  const { classId } = useParams();
  const [slides, setSlides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const revealRef = useRef(null);

  useEffect(() => {
    const fetchSlides = async () => {
      try {
        //dont have the fetch yet, need to add libreoffice
        setSlides(data.slides || []);
      } catch (err) {
        console.error("Error loading slides:", err);
        setError("Could not load presentation.");
      } finally {
        setLoading(false);
      }
    };
    fetchSlides();
  }, [classId]);


  useEffect(() => {
    if (slides.length > 0 && revealRef.current) {
      const deck = new Reveal(revealRef.current, {
        hash: true,
        center: true,
        width: "100%",
        height: "100%",
        slideNumber: true,
        transition: "slide",
      });
      deck.initialize();
    }
  }, [slides]);

  if (loading)
    return <div className="presentation-placeholder">Loading presentation...</div>;

  if (error)
    return <div className="presentation-placeholder error">{error}</div>;

  if (slides.length === 0)
    return (
      <div className="presentation-placeholder">
        <h2>No slides available</h2>
        <p>Upload a PowerPoint file to start your presentation.</p>
      </div>
    );

  return (
    <div className="presentation-wrapper">
      <div className="reveal" ref={revealRef}>
        <div className="slides">
          {slides.map((src, index) => (
            <section key={index}>
              <img
                src={src}
                alt={`Slide ${index + 1}`}
                className="slide-image"
              />
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}

export default Presentations;
