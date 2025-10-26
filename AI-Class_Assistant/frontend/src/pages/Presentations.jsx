import React, { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import "./Presentations.css";
import socket from "../sockets/socket";
import { 
  getPresentationInfo, 
  convertPresentationToImages,
  getSlideImageUrl,
  startPresentation,
  endPresentation 
} from "../services/presentations";

function Presentations({ user }) {
  const { classId } = useParams();
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

  // calculate time spent per slide (I calc it sepparately, then we add it up in the next func)
  const recordSlideVisit = (slideNumber) => {
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
  };

  // leaving this here to send the full data to the backend ltr
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
        recordSlideVisit(current_slide);
        setCurrentSlide(current_slide);
      }
    };

    const handleSlideAdded = ({ presentation_id, new_slide_count, cache_bust }) => {
      if (presentation_id === presentationId) {
        console.log(`Slides added! New count: ${new_slide_count}, cache_bust: ${cache_bust}`);
        setTotalSlides(new_slide_count);
        // changed the cache I had cz the images would not refresh, the cache bust is the time it will stay
        setImageVersion(cache_bust || Date.now());
      }
    };

    socket.on("presentation:update", handleUpdate);
    socket.on("presentation:slides_updated", handleSlideAdded);

    return () => {
      socket.off("presentation:update", handleUpdate);
      socket.off("presentation:slides_updated", handleSlideAdded);
    };
  }, [presentationId]);

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
      
      setPresentationOrder(prevOrder => {
        const finalOrder = [...prevOrder];
        if (finalOrder.length > 0) {
          //update the last entry with its final duration
          finalOrder[finalOrder.length - 1] = {
            ...finalOrder[finalOrder.length - 1],
            duration: finalDuration
          };
        }
        
        // calculate statistics (debugging, will comment)
        // console.log("=== PRESENTATION STATISTICS ===");
        // console.log("Full slide order:", finalOrder);
        
        // Calculate total time per slide
        const timePerSlide = {};
        finalOrder.forEach(entry => {
          if (!timePerSlide[entry.slide]) {
            timePerSlide[entry.slide] = 0;
          }
          timePerSlide[entry.slide] += entry.duration;
        });
        
        // console.log("\nTime spent per slide (in seconds):");
        // Object.entries(timePerSlide)
        //   .sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
        //   .forEach(([slide, duration]) => {
        //     console.log(`  Slide ${slide}: ${(duration / 1000).toFixed(2)}s`);
        //   });
        
        const totalTime = Object.values(timePerSlide).reduce((sum, time) => sum + time, 0);
        // console.log(`\nTotal presentation time: ${(totalTime / 1000).toFixed(2)}s`);
        // console.log("==============================\n");
        
        return finalOrder;
      });
      
      const telegramChatId = user?.telegram_chat_id || null;
      const result = await endPresentation(presentationId, telegramChatId);
      setPresentationStarted(false);
      console.log("Presentation ended. Duration:", result.duration_seconds, "seconds");
      
      //reset tracking
      slideStartTimeRef.current = null;
      
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
            //same as before
            const now = Date.now();
            const finalDuration = slideStartTimeRef.current ? now - slideStartTimeRef.current : 0;
            
            setPresentationOrder(prevOrder => {
              const finalOrder = [...prevOrder];
              if (finalOrder.length > 0) {
                finalOrder[finalOrder.length - 1] = {
                  ...finalOrder[finalOrder.length - 1],
                  duration: finalDuration
                };
              }
              
              console.log("=== PRESENTATION STATISTICS (Auto-ended) ===");
              console.log("Full slide order:", finalOrder);
              
              // Calculate total time per slide
              const timePerSlide = {};
              finalOrder.forEach(entry => {
                if (!timePerSlide[entry.slide]) {
                  timePerSlide[entry.slide] = 0;
                }
                timePerSlide[entry.slide] += entry.duration;
              });
              
              console.log("\nTime spent per slide (in seconds):");
              Object.entries(timePerSlide)
                .sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
                .forEach(([slide, duration]) => {
                  console.log(`  Slide ${slide}: ${(duration / 1000).toFixed(2)}s`);
                });
              
              const totalTime = Object.values(timePerSlide).reduce((sum, time) => sum + time, 0);
              console.log(`\nTotal presentation time: ${(totalTime / 1000).toFixed(2)}s`);
              console.log("==============================\n");
              
              return finalOrder;
            });
            
            const telegramChatId = user?.telegram_chat_id || null;
            const result = await endPresentation(presentationId, telegramChatId);
            setPresentationStarted(false);
            slideStartTimeRef.current = null;
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
  }, [presentationStarted, presentationId, user]);

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
