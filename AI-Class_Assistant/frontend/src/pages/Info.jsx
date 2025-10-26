import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { API_URL } from "../config";
import "./Info.css";

export default function InfoPage() {
  const { classId } = useParams();
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  const [expandedSections, setExpandedSections] = useState({details:true,analytics:true,aiSlides:true});

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const res = await fetch(`${API_URL}/api/classes/${classId}/presentation-info`);
        if (!res.ok) throw new Error("Failed to fetch presentation info");
        const data = await res.json();
        // console.log("Presentation info:", data);
        setInfo(data);
      } catch (err) {
        console.error(err);
        setError(err.message);
      }
    };
    fetchInfo();
  }, [classId]);

  const formatDuration = (ms) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const calculateConcentrationScore = (analytics) => {
    if (!analytics || !analytics.slide_order) return [];
    
    const slideOrder = analytics.slide_order;
    const timePerSlide = analytics.time_per_slide;
    
    // avg time per slide
    const times = Object.values(timePerSlide);
    const avgTime = times.reduce((a, b) => a + b, 0) / times.length;
    
    const concentrationData = [];
    let cumulativeTime = 0;
    
    slideOrder.forEach((entry, index) => {
      const duration = entry.duration || 0;
      cumulativeTime += duration;
      
      //concentration score: ratio of actual time to average time (this is my additional analytic to the info tab)
      //score > 1 means more focused (spending more time than average)
      //score < 1 means less focused (spending less time than average)
      const score = Math.min((duration / avgTime) * 100, 200);
      
      concentrationData.push({
        time: cumulativeTime,
        score: score,
        slide: entry.slide
      });
    });
    
    return concentrationData;
  };

  const calculateSlideRevisits = (analytics) => {
    if (!analytics || !analytics.slide_order) return { revisits: {}, totalRevisits: 0 };
    
    const visitCount = {};
    analytics.slide_order.forEach(entry => {
      visitCount[entry.slide] = (visitCount[entry.slide] || 0) + 1;
    });
    
    const revisits = {};
    let totalRevisits = 0;
    
    Object.entries(visitCount).forEach(([slide, count]) => {
      if (count > 1) {
        revisits[slide] = count - 1;
        totalRevisits += count - 1;
      }
    });
    
    return { revisits, totalRevisits };
  };

  return (
    <div className="info-page">
      <div className="info-container">
        <h1>Presentation Info</h1>
        {error && <p className="error-text">{error}</p>}

        {!info && !error && <p>Loading presentation info...</p>}

        {info && (
          <>
            <div className="info-card">
              <div className="card-header" onClick={() => toggleSection('details')}>
                <h2>Presentation Details</h2>
                <span className="collapse-icon">{expandedSections.details ? '▼' : '▶'}</span>
              </div>
              {expandedSections.details && (
                <div className="card-content">
                  <p><strong>Presentation ID:</strong> {info.presentation_id}</p>
                  <p><strong>Class ID:</strong> {info.class_id}</p>
                  <p><strong>Total Slides:</strong> {info.slide_count}</p>
                  <p><strong>AI-Generated Slides:</strong> {info.ai_slides_count}</p>
                  <p><strong>Started At:</strong> {info.started_at ? formatTimestamp(info.started_at) : "Not started yet"}</p>
                  <p><strong>Ended At:</strong> {info.ended_at ? formatTimestamp(info.ended_at) : "Not ended yet"}</p>
                  <p><strong>Duration:</strong> {info.duration_seconds ? `${info.duration_seconds}s` : "N/A"}</p>
                </div>
              )}
            </div>

            {info.analytics && (
              <div className="info-card analytics-card">
                <div className="card-header" onClick={() => toggleSection('analytics')}>
                  <h2>Presentation Analytics</h2>
                  <span className="collapse-icon">{expandedSections.analytics ? '▼' : '▶'}</span>
                </div>
                {expandedSections.analytics && (
                  <div className="card-content">
                    <p><strong>Analysis Date:</strong> {formatTimestamp(info.analytics.created_at)}</p>
                    <p><strong>Total Time:</strong> {formatDuration(info.analytics.total_time_ms)}</p>
                    
                    <h3>Concentration Over Time</h3>
                    <div className="concentration-chart">
                      <div className="chart-description">
                        This chart shows attention levels throughout the presentation. 
                        Higher bars indicate more time spent on a slide (higher focus).
                      </div>
                      <div className="chart-container">
                        {calculateConcentrationScore(info.analytics).map((point, index) => {
                          const heightPercent = Math.min(point.score, 100);
                          const color = point.score > 100 ? '#28a745' : 
                                       point.score > 70 ? '#667eea' : 
                                       point.score > 40 ? '#ffc107' : '#dc3545';
                          
                          return (
                            <div key={index} className="chart-bar-wrapper">
                              <div 
                                className="chart-bar" 
                                style={{
                                  height: `${heightPercent}%`,
                                  backgroundColor: color
                                }}
                                title={`Slide ${point.slide}: ${point.score.toFixed(0)}% focus`}
                              >
                                <span className="bar-label">{point.slide}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      <div className="chart-legend">
                        <div className="legend-item">
                          <span className="legend-color" style={{backgroundColor: '#28a745'}}></span>
                          <span>High Focus (&gt;100%)</span>
                        </div>
                        <div className="legend-item">
                          <span className="legend-color" style={{backgroundColor: '#667eea'}}></span>
                          <span>Good Focus (70-100%)</span>
                        </div>
                        <div className="legend-item">
                          <span className="legend-color" style={{backgroundColor: '#ffc107'}}></span>
                          <span>Medium Focus (40-70%)</span>
                        </div>
                        <div className="legend-item">
                          <span className="legend-color" style={{backgroundColor: '#dc3545'}}></span>
                          <span>Low Focus (&lt;40%)</span>
                        </div>
                      </div>
                    </div>

                    <h3>Slide Revisits Analysis</h3>
                    <div className="revisits-section">
                      {(() => {
                        const { revisits, totalRevisits } = calculateSlideRevisits(info.analytics);
                        return (
                          <>
                            <p className="revisits-summary">
                              <strong>Total Revisits:</strong> {totalRevisits} 
                              {totalRevisits > 0 && 
                                ` (${((totalRevisits / info.analytics.slide_order.length) * 100).toFixed(1)}% of total navigation)`
                              }
                            </p>
                            {Object.keys(revisits).length > 0 ? (
                              <div className="revisits-grid">
                                {Object.entries(revisits)
                                  .sort((a, b) => b[1] - a[1])
                                  .map(([slide, count]) => (
                                    <div key={slide} className="revisit-item">
                                      <span className="revisit-slide">Slide {slide}</span>
                                      <span className="revisit-count">{count} revisit{count > 1 ? 's' : ''}</span>
                                    </div>
                                  ))}
                              </div>
                            ) : (
                              <p className="no-revisits">No slides were revisited during this presentation.</p>
                            )}
                          </>
                        );
                      })()}
                    </div>
                    
                    <h3>Time per Slide</h3>
                    <div className="time-per-slide-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Slide</th>
                            <th>Time Spent</th>
                            <th>Percentage</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(info.analytics.time_per_slide)
                            .sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
                            .map(([slide, duration]) => {
                              const percentage = ((duration / info.analytics.total_time_ms) * 100).toFixed(1);
                              return (
                                <tr key={slide}>
                                  <td>Slide {slide}</td>
                                  <td>{formatDuration(duration)}</td>
                                  <td>
                                    <div className="percentage-bar">
                                      <div 
                                        className="percentage-fill" 
                                        style={{width: `${percentage}%`}}
                                      />
                                      <span>{percentage}%</span>
                                    </div>
                                  </td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                    </div>

                    <h3>Navigation Pattern</h3>
                    <div className="navigation-pattern">
                      <p className="pattern-sequence">
                        {info.analytics.slide_order.map((entry, index) => (
                          <span key={index} className="slide-visit">
                            {entry.slide}
                            {index < info.analytics.slide_order.length - 1 && " → "}
                          </span>
                        ))}
                      </p>
                      <p className="pattern-stats">
                        <strong>Total Slide Visits:</strong> {info.analytics.slide_order.length}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {info.ai_slides && info.ai_slides.length > 0 && (
              <div className="info-card ai-slides-card">
                <div className="card-header" onClick={() => toggleSection('aiSlides')}>
                  <h2>AI-Generated Slides</h2>
                  <span className="collapse-icon">{expandedSections.aiSlides ? '▼' : '▶'}</span>
                </div>
                {expandedSections.aiSlides && (
                  <div className="card-content">
                    <p className="ai-slides-summary">
                      <strong>Total AI Slides:</strong> {info.ai_slides.length}
                    </p>
                    <div className="ai-slides-list">
                      {info.ai_slides.map((slide, index) => (
                        <div key={slide.id} className="ai-slide-item">
                          <div className="ai-slide-header">
                            <span className="ai-slide-number">AI Slide #{index + 1}</span>
                            <span className="ai-slide-position">Position: {slide.slide_index}</span>
                            <span className="ai-slide-date">{formatTimestamp(slide.created_at)}</span>
                          </div>
                          
                          {slide.user_input && (
                            <div className="ai-slide-section">
                              <h4>User Input:</h4>
                              <p>{slide.user_input}</p>
                            </div>
                          )}
                          
                          <div className="ai-slide-section">
                            <h4>Generated Content:</h4>
                            <div className="ai-slide-content">
                              {slide.slide_content}
                            </div>
                          </div>
                          
                          {slide.answer && (
                            <div className="ai-slide-section">
                              <h4>✅ Answer:</h4>
                              <p className="ai-slide-answer">{slide.answer}</p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {!info.analytics && info.ended_at && (
              <div className="info-card">
                <p>No analytics data available for this presentation.</p>
              </div>
            )}
          </>
        )}

        <button className="back-button" onClick={() => navigate(-1)}>
          ⬅ Back
        </button>
      </div>
    </div>
  );
}
