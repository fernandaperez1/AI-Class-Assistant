## Project Name
TutorFlow

## Purpose
A real-time educational assistant that helps teachers interact with their course material via a Telegram chatbot and a web frontend.

---

## Architecture Overview

### Frontend: React (TypeScript preferred)
- Uses **Firebase Authentication** for secure login.  
- Connects to the backend via **WebSockets** for real-time communication.  
- Displays PowerPoint content as **images** converted from `.pptx` files.  (changed this, its pdfs now)

### Backend: Flask (Python)
- Handles WebSocket connections with both the **frontend** and **Telegram bot**.  
- Integrates **PostgreSQL** as the database.  
- Manages `.pptx` files using `python-pptx`:
  - Reads and edits slides based on user queries.
  - Adds new slides dynamically using **OpenAI or Gemini API**, which takes context from the class PowerPoint.  
- Shows the pptx as an html in the frontend using Reveal.js, images included (extracted using python-pptx).  (changed this aswell to pdf)
- Serves the pptx view to the frontend and only updates the new slides inserted.

### Chatbot: Telegram Bot (Python using `python-telegram-bot`)
- Acts as a **class assistant** for students.  
- Sends user queries to the backend via WebSocket.  
- Receives generated slide images or summaries back from the backend and sends them to the user.  

### Containerization: Docker
- Each service (frontend, backend, database, LibreOffice, bot) runs in its own container.  
- Docker Compose orchestrates the full environment.

---

## Workflow

1. A student interacts with the **Telegram bot**, asking a question related to a class topic.  
2. The backend receives the request via WebSocket and retrieves relevant context from the class PowerPoint.  
3. The backend queries **OpenAI** to generate new content or explanations based on that context.  
4. `python-pptx` edits or adds new slides with the generated information.  
5. LibreOffice converts the updated `.pptx` to image files (one per slide).  
6. The backend sends the new image data via WebSocket to the **React frontend**, where the user can view the updated slides in real time with Reveal.js.  
7. All relevant data (queries, responses, slides) are stored in **PostgreSQL** for persistence.

---

## Core Technologies

- **Frontend:** React, Firebase Auth, WebSocket  
- **Backend:** Flask, WebSocket, Python-pptx, OpenAI API, LibreOffice (headless), PostgreSQL  
- **Bot:** Telegram (python-telegram-bot)  
- **Deployment:** Docker + Docker Compose  

---

## Key Features

- Real-time updates between bot, backend, and frontend.  
- Contextual AI slide generation.  
- Secure user authentication with Firebase.  
- Automatic PowerPoint to image conversion for browser visualization.  (changed this x3)
- Persistent PostgreSQL storage for logs, users, and generated slides.  