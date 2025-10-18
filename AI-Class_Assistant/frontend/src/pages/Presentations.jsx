import React, { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import * as pdfjsLib from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.js?url";
import "./Presentations.css";
import socket from "../sockets/socket";
import { 
  getPresentationInfo, 
  convertPresentationToPDF,
  startPresentation,
  endPresentation 
} from "../services/presentations";
import { API_URL } from "../config";

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

function Presentations({ user }) {
  const { classId } = useParams();
  const [pdfUrl, setPdfUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [converting, setConverting] = useState(false);
  const [error, setError] = useState(null);
  const [presentationId, setPresentationId] = useState(null);
  const [presentationStarted, setPresentationStarted] = useState(false);
  
  const [pdfDoc, setPdfDoc] = useState(null);
  const [currentSlide, setCurrentSlide] = useState(1); //var to use to manage slide pos, we need to use it with the telegram bot
  const [totalSlides, setTotalSlides] = useState(0);
  const [pageRendering, setPageRendering] = useState(false);
  
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    const fetchAndConvertPresentation = async () => {
      try {
        setLoading(true);
        setError(null);

        console.log(`Fetching presentation info for class ${classId}...`);
        console.log("test")
        const infoData = await getPresentationInfo(classId);
        setPresentationId(infoData.presentation_id);

        console.log(`Converting presentation ${infoData.presentation_id} to PDF...`);
        setConverting(true);
        const convertData = await convertPresentationToPDF(infoData.presentation_id);
        setConverting(false);
        console.log(`current slide`)
        console.log(currentSlide)        
        const fullPdfUrl = `${API_URL}${convertData.pdf_url}`;   
    
        console.log(`Successfully converted to PDF: ${fullPdfUrl}`);
        setPdfUrl(fullPdfUrl); 
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

  useEffect(() => {
    if (!pdfUrl) return;

    const loadPdf = async () => {
      try {
        console.log("Loading PDF from:", pdfUrl);
        const loadingTask = pdfjsLib.getDocument({
          url: pdfUrl,
        });
        const pdf = await loadingTask.promise;
        setPdfDoc(pdf);
        setTotalSlides(pdf.numPages);
        console.log(`PDF loaded successfully: ${pdf.numPages} pages`);
      } catch (err) {
        console.error("Error loading PDF:", err);
        setError(`Failed to load PDF: ${err.message}`);
      }
    };

    loadPdf();
  }, [pdfUrl]);

  useEffect(() => {
    if (!pdfDoc || !canvasRef.current || !containerRef.current) return;

    const renderPage = async () => {
      setPageRendering(true);
      
      try {
        const page = await pdfDoc.getPage(currentSlide);
        const canvas = canvasRef.current;
        const context = canvas.getContext('2d');
        
        const container = containerRef.current;
        const containerWidth = container.clientWidth;
        const containerHeight = container.clientHeight;
        
        // Calculate scale to fit slide to screen (need to test in dif screens, caused issues in w10)
        const viewport = page.getViewport({ scale: 1 });
        const scaleX = containerWidth / viewport.width;
        const scaleY = containerHeight / viewport.height;
        const scale = Math.min(scaleX, scaleY) * 0.95; 
        
        const scaledViewport = page.getViewport({ scale });
        
        // Set canvas dimensions
        canvas.width = scaledViewport.width;
        canvas.height = scaledViewport.height;
        
        // Render PDF page into canvas context
        const renderContext = {
          canvasContext: context,
          viewport: scaledViewport
        };
        
        await page.render(renderContext).promise;
        setPageRendering(false);
        console.log(`Rendered slide ${currentSlide}/${totalSlides}`);
      } catch (err) {
        console.error("Error rendering page:", err);
        setPageRendering(false);
      }
    };

    renderPage();
  }, [pdfDoc, currentSlide, totalSlides]);

  // works as an ex for the thing we gotta add with the telegram bot
  useEffect(() => {
    const handleKeyPress = (e) => {
      if (!pdfDoc) return;

      switch (e.key) {
        case 'ArrowRight':
        case 'ArrowDown':
        case ' ':
          e.preventDefault();
          if (currentSlide < totalSlides) {
            setCurrentSlide(prev => prev + 1);
          }
          break;
        case 'ArrowLeft':
        case 'ArrowUp':
          e.preventDefault();
          if (currentSlide > 1) {
            setCurrentSlide(prev => prev - 1);
          }
          break;
        case 'Home':
          e.preventDefault();
          setCurrentSlide(1);
          break;
        case 'End':
          e.preventDefault();
          setCurrentSlide(totalSlides);
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [pdfDoc, currentSlide, totalSlides]);

    useEffect(() => {
    if (!presentationId) return;

    const handleUpdate = ({ presentation_id, current_slide }) => {
      if (presentation_id === presentationId) {
        setCurrentSlide(current_slide);
      }
    };

    socket.on("presentation:update", handleUpdate);

    return () => {
      socket.off("presentation:update", handleUpdate);
    };
  }, [presentationId]);


  const handleStartPresentation = async () => {
    if (!presentationId) return;
    
    try {
      // Pass telegram_chat_id if user has it linked (made this optional just in case so that the app wouldnt fall)
      const telegramChatId = user?.telegram_chat_id || null;
      console.log("Starting presentation with:", { presentationId, telegramChatId, user });
      
      await startPresentation(presentationId, telegramChatId, currentSlide);
      setPresentationStarted(true);
      console.log("Presentation started successfully");
      
      // fullscreen mode on the container
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
      const telegramChatId = user?.telegram_chat_id || null;
      const result = await endPresentation(presentationId, telegramChatId);
      setPresentationStarted(false);
      console.log("Presentation ended. Duration:", result.duration_seconds, "seconds");
      
      // Exit fullscreen mode auto (sometimes it breaks?)
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
            const telegramChatId = user?.telegram_chat_id || null;
            const result = await endPresentation(presentationId, telegramChatId);
            setPresentationStarted(false);
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
  }, [presentationStarted, presentationId]);

  const goToNextSlide = () => {
    if (currentSlide < totalSlides) {
      setCurrentSlide(prev => prev + 1);
    }
  };

  const goToPrevSlide = () => {
    if (currentSlide > 1) {
      setCurrentSlide(prev => prev - 1);
    }
  };

  if (loading || converting) {
    return (
      <div className="presentation-placeholder">
        {converting 
          ? "Converting presentation to PDF... This may take a moment."
          : "Loading presentation..."
        }
      </div>
    );
  }

  if (error)
    return <div className="presentation-placeholder error">{error}</div>;

  if (!pdfUrl)
    return (
      <div className="presentation-placeholder">
        <h2>No presentation available</h2>
        <p>Upload a PowerPoint file to start your presentation.</p>
      </div>
    );

  return (
    <div className="presentation-wrapper">
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
      
      <div className="pdf-viewer" ref={containerRef}>
        <canvas ref={canvasRef} />
        
        {pdfDoc && (
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
        )}
      </div>
    </div>
  );
}

export default Presentations;
