import React, { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import "./Presentations.css";
import socket from "../sockets/socket";
import { 
  getPresentationInfo, 
  convertPresentationToImages,
  getSlideImageUrl,
  startPresentation,
  endPresentation 
} from "../services/presentations";
import { API_URL } from "../config";

function Presentations({ user }) {
  const { classId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [converting, setConverting] = useState(false);
  const [error, setError] = useState(null);
  const [presentationId, setPresentationId] = useState(null);
  const [presentationStarted, setPresentationStarted] = useState(false);
  
  const [currentSlide, setCurrentSlide] = useState(1);
  const [totalSlides, setTotalSlides] = useState(0);
  const [imageVersion, setImageVersion] = useState(0); // forcing the pres to reload in place
  const [presentationOrder, setPresentationOrder] = useState([]) //array of {slide: number, timestamp: number, duration: number}, the duration is only set after changing or ending
  
  const containerRef = useRef(null);
  const imageRef = useRef(null);
  const slideStartTimeRef = useRef(null); //track when current slide started

  //update backend with current slide (so bot stays in sync)
  const updateBackendSlide = async (slideNumber) => {
    if (!presentationId || !presentationStarted) return;
    
    try {
      const telegramChatId = user?.telegram_chat_id;
      if (!telegramChatId) return; //only sync if Telegram is connected
      
      await fetch(`${API_URL}/api/presentations/${presentationId}/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'goto',
          target_slide: slideNumber,
          telegram_chat_id: telegramChatId
        })
      });
    } catch (err) {
      console.error('Error syncing slide to backend:', err);
    }
  };

  // calculate time spent per slide (I calc it sepparately, then we add it up in the next func)
  // syncToBackend param prevents race condition when slide change comes from WebSocket
  const recordSlideVisit = (slideNumber, syncToBackend = true) => {
    if (!presentationStarted) return; //this is the fix I did to the slide recording when not in fullscreen, need to test more
    const now=Date.now();
    const duration = slideStartTimeRef.current ? now - slideStartTimeRef.current : 0;
    
    setPresentationOrder(prevOrder => {
      const newEntry = {
        slide: slideNumber,
        timestamp: now,
        duration: duration
      };
      // console.log(`Recording slide visit: slide ${slideNumber}, duration: ${duration}ms`);
      return [...prevOrder, newEntry];
    });
    
    slideStartTimeRef.current = now;
    
    //only sync to backend if this is a local change (not from WebSocket, the bot does it auto in this case)
    if (syncToBackend) {
      updateBackendSlide(slideNumber);
    }
  };

  //calc the time stats
  const calculateTimeStatistics = (slideOrder) => {
    const timePerSlide = {};
    slideOrder.forEach(entry => {
      if (!timePerSlide[entry.slide]) {
        timePerSlide[entry.slide] = 0;
      }
      timePerSlide[entry.slide] += entry.duration;
    });
    
    return {
      timePerSlide,
      totalTime: Object.values(timePerSlide).reduce((sum, time) => sum + time, 0),
      slideOrder
    };
  };

  //save analythics to the db
  const saveAnalytics = async (finalOrder) => {
    if (!presentationId || finalOrder.length === 0) return;
    
    const stats = calculateTimeStatistics(finalOrder);
    
    try {
      const response = await fetch(`${API_URL}/api/presentations/${presentationId}/analytics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          slide_order: stats.slideOrder,
          time_per_slide: stats.timePerSlide,
          total_time_ms: stats.totalTime
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to save analytics');
      }
      
      console.log('[ANALYTICS] Successfully saved presentation analytics');
    } catch (err) {
      console.error('[ANALYTICS] Error saving analytics:', err);
    }
  };

  useEffect(() => {
    const fetchAndConvertPresentation = async () => {
      try {
        setLoading(true);
        setError(null);

        console.log(`Fetching presentation info for class ${classId}...`);
        const infoData = await getPresentationInfo(classId);
        setPresentationId(infoData.presentation_id);

        console.log(`Converting presentation ${infoData.presentation_id} to images...`);
        setConverting(true);
        const convertData = await convertPresentationToImages(infoData.presentation_id);
        setConverting(false);
        
        setTotalSlides(convertData.slide_count);
        console.log(`Successfully converted to ${convertData.slide_count} slide images`);
      } catch (err) {
        console.error("Error loading presentation:", err);
        setError(err.message || "Could not load presentation."); 
        setConverting(false);
      } finally {
        setLoading(false);
      }   
    }; 

    if (classId) {
      fetchAndConvertPresentation();
    }
  }, [classId]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyPress = (e) => {
      if (!totalSlides) return; //fixing here, if the pres is not in full screen, I dont want to update the timer or slide order

      switch (e.key) {
        case 'ArrowRight':
        case 'ArrowDown':
        case ' ':
          e.preventDefault();
          if (currentSlide < totalSlides) {
            const nextSlide = currentSlide + 1;
            recordSlideVisit(nextSlide);
            setCurrentSlide(nextSlide);
          }
          break;
        case 'ArrowLeft':
        case 'ArrowUp':
          e.preventDefault();
          if (currentSlide > 1) {
            const prevSlide = currentSlide - 1;
            recordSlideVisit(prevSlide);
            setCurrentSlide(prevSlide);
          }
          break;
        case 'Home':
          e.preventDefault();
          recordSlideVisit(1);
          setCurrentSlide(1);
          break;
        case 'End':
          e.preventDefault();
          recordSlideVisit(totalSlides);
          setCurrentSlide(totalSlides);
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [currentSlide, totalSlides, presentationStarted]);

  // WebSocket slide updates
  useEffect(() => {
    if (!presentationId) return;

    const handleUpdate = ({ presentation_id, current_slide }) => {
      if (presentation_id === presentationId) {
        console.log(`WebSocket update: moving to slide ${current_slide}`);
        //pass false to prevent syncing back to backend (avoid race condition)
        recordSlideVisit(current_slide, false);
        setCurrentSlide(current_slide);
      }
    };

    const handleSlideAdded = ({ presentation_id, new_slide_count, inserted_at, cache_bust }) => {
      if (presentation_id === presentationId) {
        console.log(`Slides added! New count: ${new_slide_count}, inserted at: ${inserted_at}, cache_bust: ${cache_bust}`);
        
        setTotalSlides(new_slide_count);
        setImageVersion(cache_bust || Date.now());
        
        //iIf a slide was inserted before or at the current position, adjust current slide (so tha tthe order makes sense then)
        if (inserted_at && inserted_at <= currentSlide) {
          const newCurrentSlide = currentSlide + 1;
          console.log(`Adjusting current slide from ${currentSlide} to ${newCurrentSlide} due to insertion at ${inserted_at}`);
          setCurrentSlide(newCurrentSlide);
          
          if (presentationStarted) {
            //don't sync to backend x3, the insertion already updated backend
            recordSlideVisit(newCurrentSlide, false);
          }
        }

        setPresentationOrder(prevOrder => {
          return prevOrder.map(entry => {
            if (entry.slide >= inserted_at) {
              return {
                ...entry,
                slide: entry.slide + 1
              };
            }
            return entry;
          });
        });
      }
    };

    socket.on("presentation:update", handleUpdate);
    socket.on("presentation:slides_updated", handleSlideAdded);

    return () => {
      socket.off("presentation:update", handleUpdate);
      socket.off("presentation:slides_updated", handleSlideAdded);
    };
  }, [presentationId, presentationStarted, currentSlide]);

  const handleStartPresentation = async () => {
    if (!presentationId) return;
    
    try {
      const telegramChatId = user?.telegram_chat_id || null;
      
      // log Telegram
      if (telegramChatId) {
        console.log("Starting presentation with Telegram bot integration:", { presentationId, telegramChatId });
      } else {
        console.log("Starting presentation without Telegram bot (no account linked):", { presentationId });
      }
      
      await startPresentation(presentationId, telegramChatId, currentSlide);
      setPresentationStarted(true);
      
      //initialize tracking for first slide
      const now = Date.now();
      slideStartTimeRef.current = now;
      setPresentationOrder([{
        slide: currentSlide,
        timestamp: now,
        duration: 0
      }]);
      console.log(`Started tracking at slide ${currentSlide}`);
      
      console.log("Presentation started successfully");
      
      //enter fullscreen mode
      const container = containerRef.current;
      if (container) {
        if (container.requestFullscreen) {
          container.requestFullscreen();
        } else if (container.webkitRequestFullscreen) {
          container.webkitRequestFullscreen();
        } else if (container.msRequestFullscreen) {
          container.msRequestFullscreen();
        }
      }
    } catch (err) {
      console.error("Error starting presentation:", err);
      alert("Failed to start presentation: " + err.message);
    }
  };

  const handleEndPresentation = async () => {
    if (!presentationId) return;
    
    try {
      //record the final slide duration before ending
      const now = Date.now();
      const finalDuration = slideStartTimeRef.current ? now - slideStartTimeRef.current : 0;
      
      //calculate final order taking into consideration the race condition before state update (fk use state)
      const finalOrder = presentationOrder.map((entry, index) => {
        //update the last entry with its final duration
        if (index === presentationOrder.length - 1) {
          return {
            ...entry,
            duration: finalDuration
          };
        }
        return entry;
      });
      
      console.log("Final order to save:", finalOrder);
      
      //save analytics to backend
      await saveAnalytics(finalOrder);
      
      const telegramChatId = user?.telegram_chat_id || null;
      const result = await endPresentation(presentationId, telegramChatId);
      setPresentationStarted(false);
      console.log("Presentation ended. Duration:", result.duration_seconds, "seconds");
      
      //reset tracking
      slideStartTimeRef.current = null;
      setPresentationOrder([]);
      
      //exit fullscreen mode
      if (document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement) {
        if (document.exitFullscreen) {
          document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
          document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) {
          document.msExitFullscreen();
        }
      }
    } catch (err) {
      console.error("Error ending presentation:", err);
    }
  };

  // Handle fullscreen exit
  useEffect(() => {
    const handleFullscreenChange = async () => {
      if (!document.fullscreenElement && !document.webkitFullscreenElement && !document.msFullscreenElement) {
        console.log("Exited fullscreen mode");
        
        if (presentationStarted && presentationId) {
          try {
            const now = Date.now();
            const finalDuration = slideStartTimeRef.current ? now - slideStartTimeRef.current : 0;
            
            // same shit
            const finalOrder = presentationOrder.map((entry, index) => {
              if (index === presentationOrder.length - 1) {
                return {
                  ...entry,
                  duration: finalDuration
                };
              }
              return entry;
            });
            
            console.log("Final order to save (auto-end):", finalOrder);

            await saveAnalytics(finalOrder);
            
            const telegramChatId = user?.telegram_chat_id || null;
            const result = await endPresentation(presentationId, telegramChatId);
            setPresentationStarted(false);
            slideStartTimeRef.current = null;
            setPresentationOrder([]);
            console.log("Presentation auto-ended. Duration:", result.duration_seconds, "seconds");
          } catch (err) {
            console.error("Error auto-ending presentation:", err);
          }
        }
      }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('msfullscreenchange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('msfullscreenchange', handleFullscreenChange);
    };
  }, [presentationStarted, presentationId, user, presentationOrder]);

  const goToNextSlide = () => {
    if (currentSlide < totalSlides) {
      const nextSlide = currentSlide + 1;
      recordSlideVisit(nextSlide);
      setCurrentSlide(nextSlide);
    }
  };

  const goToPrevSlide = () => {
    if (currentSlide > 1) {
      const prevSlide = currentSlide - 1;
      recordSlideVisit(prevSlide);
      setCurrentSlide(prevSlide);
    }
  };

  // Preload adjacent slides for smooth navigation
  useEffect(() => {
    if (!presentationId || !totalSlides) return;

    const preloadSlides = [];
    
    // Preload next slide (CHECK THIS LATER, IT MIGHT NOT ALLOW ADDING NEW SLIDES)
    if (currentSlide < totalSlides) {
      preloadSlides.push(currentSlide + 1);
    }
    
    // Preload previous slide
    if (currentSlide > 1) {
      preloadSlides.push(currentSlide - 1);
    }

    preloadSlides.forEach(slideNum => {
      const img = new Image();
      img.src = getSlideImageUrl(presentationId, slideNum) + `?v=${imageVersion}`;
    });
  }, [currentSlide, presentationId, totalSlides, imageVersion]);

  if (loading || converting) {
    return (
      <div className="presentation-placeholder">
        {converting 
          ? "Converting presentation to images... This may take a moment."
          : "Loading presentation..."
        }
      </div>
    );
  }

  if (error)
    return <div className="presentation-placeholder error">{error}</div>;

  if (!presentationId || totalSlides === 0)
    return (
      <div className="presentation-placeholder">
        <h2>No presentation available</h2>
        <p>Upload a PowerPoint file to start your presentation.</p>
      </div>
    );

  return (
    <div className="presentation-wrapper">
      <div className="presentation-top-bar">
        <button onClick={() => navigate('/home')} className="control-btn back-btn">
          ← Back to Home
        </button>
        {!user?.telegram_chat_id && (
          <div className="telegram-notice">
            ℹ️ <strong>Tip:</strong> Link your Telegram account on the Home page to control presentations from your phone and use AI features!
          </div>
        )}
        <div className="presentation-controls">
          {!presentationStarted ? (
            <button onClick={handleStartPresentation} className="control-btn start-btn">
              Start Presentation
            </button>
          ) : (
            <>
              <button onClick={handleEndPresentation} className="control-btn end-btn">
                End Presentation
              </button>
              <div className="slide-counter">
                Slide {currentSlide} / {totalSlides}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="presentation-container">
        <div className="pdf-viewer" ref={containerRef}>
          <img 
            ref={imageRef}
            src={getSlideImageUrl(presentationId, currentSlide) + `?v=${imageVersion}`}
            alt={`Slide ${currentSlide}`}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'contain',
              backgroundColor: '#000'
            }}
            onError={(e) => {
              console.error(`Failed to load slide ${currentSlide}`);
              e.target.src = ''; // Prevent infinite reload loops
            }}
          />
        </div>
      </div>

      <div className="slide-navigation">
        <button 
          onClick={goToPrevSlide} 
          disabled={currentSlide === 1}
          className="nav-btn prev-btn"
        >
          ← Previous
        </button>
        <span className="slide-info">
          {currentSlide} / {totalSlides}
        </span>
        <button 
          onClick={goToNextSlide} 
          disabled={currentSlide === totalSlides}
          className="nav-btn next-btn"
        >
          Next →
        </button>
      </div>
      
    </div>
  );
}

export default Presentations;
