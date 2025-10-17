import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from db import database as db
from pptx_utils import extract_text_from_pptx, convert_pptx_to_pdf, get_slide_count

load_dotenv()

app = Flask(__name__)

# Enable CORS for all routes (just doing for debug, will delete ltr)
CORS(app, resources={r"/api/*": {"origins": "*"}})

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
PORT = int(os.getenv("PORT", 5000))
HOST = os.getenv("HOST", "0.0.0.0")

socketio = SocketIO(app, cors_allowed_origins=CORS_ORIGINS)


@app.route("/")
def index():
    return jsonify({
        "message": "Class Assistant API is running",
        "endpoints": {
            "users": "/api/users",
            "classes": "/api/classes",
            "presentations": "/api/presentations"
        }
    })


@app.route("/api/users/<firebase_uid>", methods=["GET"])
def get_user(firebase_uid):
    """Get user by Firebase UID"""
    try:
        user = db.get_user_by_firebase_uid(firebase_uid)
        if user:
            return jsonify(user), 200
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users", methods=["POST"])
def create_user():
    """Create a new user"""
    try:
        data = request.json
        
        # Check if user already exists
        existing_user = db.get_user_by_firebase_uid(data["firebase_uid"])
        if existing_user:
            print(f"User already exists: {existing_user['id']}")
            return jsonify(existing_user), 200
        
        # Create new user
        user = db.create_user(
            firebase_uid=data["firebase_uid"],
            email=data["email"]
        )
        print(f"New user created: {user['id']}")
        return jsonify(user), 201
    except Exception as e:
        print(f"Error creating user: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<int:user_id>/link-code", methods=["POST"])
def generate_link_code(user_id):
    """Generate a one-time code for Telegram linking"""
    try:
        import random
        import string
        from datetime import datetime, timedelta
        
        # Generate a 6-character code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        expires_at = datetime.now() + timedelta(minutes=15)  # Valid for 15 minutes
        
        result = db.generate_telegram_link_code(user_id, code, expires_at)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/telegram/link", methods=["POST"])
def link_telegram():
    """Link Telegram account using one-time code"""
    try:
        data = request.json
        user = db.link_telegram_account(
            link_code=data["code"],
            telegram_chat_id=data["telegram_chat_id"]
        )
        if user:
            return jsonify(user), 200
        return jsonify({"error": "Invalid or expired code"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/telegram/check/<int:chat_id>", methods=["GET"])
def check_telegram_link(chat_id):
    """Check if a Telegram chat_id is linked to a user"""
    try:
        user = db.get_user_by_telegram_chat_id(chat_id)
        if not user:
            return jsonify({"error": "Not linked"}), 404

        active_presentation = db.get_active_presentation_for_user(user["id"])
        user["active_presentation_id"] = active_presentation

        return jsonify(user), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<int:user_id>/classes", methods=["GET"])
def get_user_classes(user_id):
    """Get all classes for a user"""
    try:
        classes = db.get_user_classes(user_id)
        return jsonify(classes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/classes", methods=["POST"])
def create_class():
    """Create a new class"""
    try:
        data = request.json
        new_class = db.create_class(
            user_id=data["user_id"],
            subject=data["subject"],
            difficulty_level=data["difficulty_level"],
            class_name=data.get("class_name")
        )
        return jsonify(new_class), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500  
    
@app.route("/api/classes/<int:class_id>/delete", methods=["DELETE"])
def delete_class_endpoint(class_id):
    """Delete a class"""
    try:
        data = request.json
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        class_return = db.delete_class(class_id, user_id)
        print("DEBUG")
        print(class_return)
        if class_return:
            return jsonify(class_return), 200
        else:
            return jsonify({"error": "Class not found or not authorized"}), 404

    except Exception as e:
        print("the exception is")
        print(e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/classes/<int:class_id>", methods=["GET"])
def get_class(class_id):
    """Get class by ID"""
    try:
        class_data = db.get_class_by_id(class_id)
        if class_data:
            return jsonify(class_data), 200
        return jsonify({"error": "Class not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# @app.route("/api/classes/<int:class_id>/presentation", methods=["POST"])
# def create_presentation(class_id):
#     """Create a presentation for a class"""
#     try:
#         data = request.json
#         presentation = db.create_presentation(
#             class_id=class_id,
#             original_pptx_path=data.get("pptx_path")
#         )
#         return jsonify(presentation), 201
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# file upload pptx
@app.route("/api/classes/<int:class_id>/presentation", methods=["POST"])
def create_presentation(class_id):
    """Create a presentation for a class from uploaded PPTX"""
    try:
        pptx_file = request.files.get("pptx_file")
        if not pptx_file:
            return jsonify({"error": "No file uploaded"}), 400

        save_path = f"./uploads/class_{class_id}_{pptx_file.filename}"
        pptx_file.save(save_path)

        presentation = db.create_presentation(
            class_id=class_id,
            original_pptx_path=save_path
        )

        return jsonify(presentation), 201
    except Exception as e:
        print("Error uploading PPTX:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/presentations/<int:presentation_id>/start", methods=["POST"])
def start_presentation(presentation_id):
    """Start a presentation"""
    try:
        result = db.start_presentation(presentation_id)
        if result:
            return jsonify(result), 200
        return jsonify({"error": "Presentation not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/presentations/<int:presentation_id>/end", methods=["POST"])
def end_presentation(presentation_id):
    """End a presentation"""
    try:
        result = db.end_presentation(presentation_id)
        if result:
            return jsonify(result), 200
        return jsonify({"error": "Presentation not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route("/api/presentations/<int:presentation_id>/control", methods=["POST"])
def control_presentation(presentation_id):
    """
    Body esperado:
    {
      "action": "next" | "prev" | "goto",
      "target_slide": int (solo para goto),
      "telegram_chat_id": int
    }
    """
    data = request.json or {}
    action = data.get("action")
    telegram_chat_id = data.get("telegram_chat_id")

    if action not in {"next", "prev", "goto"} or telegram_chat_id is None:
        return jsonify({"error": "Bad request"}), 400

    presentation = db.get_presentation_by_id(presentation_id)
    if not presentation:
        return jsonify({"error": "Presentation not found"}), 404

    owner_chat = presentation.get("presenter_chat_id")
    if owner_chat is None or owner_chat != telegram_chat_id:
        return jsonify({"error": "Presentation not accessible"}), 403

    current_slide = presentation.get("current_slide", 1)
    total_slides = presentation.get("slide_count", 1)

    if action == "next":
        new_slide = min(current_slide + 1, total_slides)
    elif action == "prev":
        new_slide = max(current_slide - 1, 1)
    else:  # action == "goto"
        target = data.get("target_slide")
        if not isinstance(target, int) or not (1 <= target <= total_slides):
            return jsonify({"error": "Invalid target slide"}), 400
        new_slide = target

    updated = db.update_current_slide(presentation_id, new_slide)

    socketio.emit(
        "presentation:update",
        {"presentation_id": presentation_id, "current_slide": updated["current_slide"]},
    )
    return jsonify(updated), 200



@app.route("/api/presentations/<int:presentation_id>/questions", methods=["POST"])
def add_question(presentation_id):
    """Add a question and answer to a presentation"""
    try:
        data = request.json
        question = db.add_question(
            presentation_id=presentation_id,
            question=data["question"],
            answer=data["answer"],
            slide_index=data.get("slide_index")
        )
        return jsonify(question), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/presentations/<int:presentation_id>/questions", methods=["GET"])
def get_questions(presentation_id):
    """Get all questions for a presentation"""
    try:
        questions = db.get_presentation_questions(presentation_id)
        return jsonify(questions), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/presentations/<int:presentation_id>/text", methods=["GET"])
def get_presentation_text(presentation_id):
    """Get text content from all slides in the presentation"""
    try:
        presentation = db.get_presentation_by_id(presentation_id)
        if not presentation:
            return jsonify({"error": "Presentation not found"}), 404
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        slides_text = extract_text_from_pptx(pptx_path)
        return jsonify({
            "presentation_id": presentation_id,
            "slide_count": len(slides_text),
            "slides": slides_text
        }), 200
    except Exception as e:
        print(f"Error extracting text: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/presentations/<int:presentation_id>/convert", methods=["POST"])
def convert_presentation_to_pdf(presentation_id):
    """Convert PPTX to PDF and return the PDF path"""
    try:
        presentation = db.get_presentation_by_id(presentation_id)
        if not presentation:
            return jsonify({"error": "Presentation not found"}), 404
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        output_dir = "./slides"
        pdf_path = convert_pptx_to_pdf(pptx_path, output_dir)
        
        slide_count = get_slide_count(pptx_path)
        db.update_slide_metadata(presentation_id, slide_count=slide_count)

        pdf_filename = os.path.basename(pdf_path)
        pdf_url = f"/api/presentations/{presentation_id}/pdf/{pdf_filename}"
        
        return jsonify({
            "presentation_id": presentation_id,
            "slide_count": slide_count,
            "pdf_url": pdf_url
        }), 200
    except Exception as e:
        print(f"Error converting presentation: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/presentations/<int:presentation_id>/pdf/<path:filename>", methods=["GET"])
def serve_pdf(presentation_id, filename):
    try:
        file_path = os.path.join("./slides", filename)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "PDF not found"}), 404
        
        return send_file(file_path, mimetype='application/pdf')
    except Exception as e:
        print(f"Error serving PDF: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/classes/<int:class_id>/presentation-info", methods=["GET"])
def get_presentation_info(class_id):
    """Get presentation information including slide count and availability, gotta complete this for the last deliverable, cz its unfinished"""
    try:
        presentation = db.get_presentation_by_class_id(class_id)
        if not presentation:
            return jsonify({"error": "No presentation found for this class"}), 404
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        slide_count = get_slide_count(pptx_path)
        
        return jsonify({
            "presentation_id": presentation["id"],
            "class_id": class_id,
            "slide_count": slide_count,
            "pptx_path": pptx_path,
            "started_at": presentation.get("started_at"),
            "ended_at": presentation.get("ended_at"),
            "duration_seconds": presentation.get("duration_seconds")
        }), 200
    except Exception as e:
        print(f"Error getting presentation info: {e}")
        return jsonify({"error": str(e)}), 500


# WebSocket events

@socketio.on("connect")
def handle_connect():
    print("Client connected")
    emit("message", {"msg": "Connected to Class Assistant backend"})


@socketio.on("send_message")
def handle_send_message(data):
    print("Received from frontend:", data)
    emit("response", {"msg": f"Backend received: {data['msg']}"}, broadcast=True)


@socketio.on("bot_message")
def handle_bot_message(data):
    """
    Handle messages from the Telegram bot (need to complete it, it will be a pretty big func)
    Expected data:
    {
        "telegram_chat_id": int,
        "question": str,
        "presentation_id": int,
        "slide_index": int (optional)
    }
    """
    print("Received from bot:", data)
    
    try:
        # Get user from telegram chat ID
        user = db.get_user_by_telegram_chat_id(data["telegram_chat_id"])
        if not user:
            emit("bot_response", {"error": "User not found"})
            return
        
        # simulated the ai ans, will add it ltr
        answer = f"AI response to: {data['question']}"
        
        # Save the question and answer
        if "presentation_id" in data:
            db.add_question(
                presentation_id=data["presentation_id"],
                question=data["question"],
                answer=answer,
                slide_index=data.get("slide_index")
            )
        
        emit("bot_response", {
            "answer": answer,
            "user_id": user["id"]
        })
        
    except Exception as e:
        print(f"Error handling bot message: {e}")
        emit("bot_response", {"error": str(e)})


@socketio.on("add_ai_slide")
def handle_add_ai_slide(data):
    """
    Handle adding an AI-generated slide
    Expected data:
    {
        "presentation_id": int,
        "slide_index": int
    }
    """
    try:
        result = db.add_ai_generated_slide(
            presentation_id=data["presentation_id"],
            slide_index=data["slide_index"]
        )
        emit("slide_added", result, broadcast=True)
    except Exception as e:
        print(f"Error adding AI slide: {e}")
        emit("error", {"error": str(e)})


if __name__ == "__main__":
    print(f"Starting Class Assistant backend on {HOST}:{PORT}")
    socketio.run(app, host=HOST, port=PORT, debug=True)
