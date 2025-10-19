import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from db import database as db
from pptx_utils import extract_text_from_pptx, convert_pptx_to_pdf, get_slide_count, convert_pptx_to_images
from ai_utils import generate_question_slide, generate_example_slide, read_presentation, add_slide

load_dotenv()

app = Flask(__name__)

# Enable CORS for all routes (just doing for debug, will delete ltr)
CORS(app, resources={r"/api/*": {"origins": "*"}})

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
PORT = int(os.getenv("PORT", 5000))
HOST = os.getenv("HOST", "0.0.0")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("⚠️  WARNING: GOOGLE_API_KEY not set in .env file. AI features will not work.")

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


@app.route("/api/presentations/<int:presentation_id>", methods=["GET"])
def get_presentation(presentation_id):
    """Get presentation details by ID"""
    try:
        presentation = db.get_presentation_by_id(presentation_id)
        if presentation:
            return jsonify(presentation), 200
        return jsonify({"error": "Presentation not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/presentations/<int:presentation_id>/start", methods=["POST"])
def start_presentation(presentation_id):
    """Start a presentation"""
    try:
        data = request.json or {}
        telegram_chat_id = data.get("telegram_chat_id")
        
        print(f"Starting presentation {presentation_id}")
        print(f"Request data: {data}")
        # print(f"Telegram chat ID: {telegram_chat_id}")
        
        result = db.start_presentation(presentation_id)
        if result:
            db.update_current_slide(presentation_id, data.get("current_slide"))
            presentation = db.get_presentation_by_id(presentation_id)
            slide_count = presentation.get("slide_count", 0)
            current_slide = presentation.get("current_slide")
            print("all the presentation info")
            print(presentation)
            
            # Emit WebSocket event to notify bot (need to test with concurrent users)
            if telegram_chat_id:
                print(f"Emitting presentation:started event to bot for chat {telegram_chat_id}")
                socketio.emit("presentation:started", {
                    "presentation_id": presentation_id,
                    "telegram_chat_id": telegram_chat_id,
                    "slide_count": slide_count,
                    "current_slide": current_slide
                })
            else:
                print("No telegram_chat_id provided, skipping bot notification")
            
            return jsonify(result), 200
        return jsonify({"error": "Presentation not found"}), 404
    except Exception as e:
        print(f"Error starting presentation: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/presentations/<int:presentation_id>/end", methods=["POST"])
def end_presentation(presentation_id):
    """End a presentation"""
    try:
        data = request.json or {}
        telegram_chat_id = data.get("telegram_chat_id")
        
        print(f"Ending presentation {presentation_id}")
        print(f"Request body: {data}")
        print(f"Telegram chat ID: {telegram_chat_id}")
        
        result = db.end_presentation(presentation_id)
        if result:
            # socket event to notify bot it ended
            if telegram_chat_id:
                print(f"Emitting presentation:ended event to bot for chat {telegram_chat_id}")
                socketio.emit("presentation:ended", {
                    "presentation_id": presentation_id,
                    "telegram_chat_id": telegram_chat_id,
                    "duration_seconds": result.get("duration_seconds", 0)
                })
            else:
                print("No telegram_chat_id provided, skipping bot notification")
            
            return jsonify(result), 200
        return jsonify({"error": "Presentation not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route("/api/presentations/<int:presentation_id>/control", methods=["POST"])
def control_presentation(presentation_id):
    """
    Expected body:
    {
      "action": "next" | "prev" | "goto",
      "target_slide": int (for the goto),
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
    else:
        target = data.get("target_slide")
        if not isinstance(target, int):
            return jsonify({"error": "Invalid target slide"}), 400
        #handling invalid inputs, this is what seemed best for me tbh
        elif (target <= 1):
            target=1
        elif (total_slides <= target):
            target=total_slides
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


@app.route("/api/presentations/<int:presentation_id>/convert-to-images", methods=["POST"])
def convert_presentation_to_images_endpoint(presentation_id):
    """Convert PPTX to individual slide images and return image URLs"""
    try:
        presentation = db.get_presentation_by_id(presentation_id)
        if not presentation:
            return jsonify({"error": "Presentation not found"}), 404
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        output_dir = "./slides"
        result = convert_pptx_to_images(pptx_path, output_dir, presentation_id)
        
        # Update slide count in database
        db.update_slide_metadata(presentation_id, slide_count=result["slide_count"])
        
        # Generate URLs for each slide image
        image_urls = [
            f"/api/presentations/{presentation_id}/slides/{i}"
            for i in range(1, result["slide_count"] + 1)
        ]
        
        # Emit WebSocket event to notify frontend of updated slides
        import time
        cache_bust_token = int(time.time() * 1000)
        
        socketio.emit(
            "presentation:slides_updated",
            {
                "presentation_id": presentation_id,
                "new_slide_count": result["slide_count"],
                "cache_bust": cache_bust_token
            }
        )
        print(f"Emitted presentation:slides_updated event for presentation {presentation_id} with {result['slide_count']} slides, cache_bust={cache_bust_token}")
        
        return jsonify({
            "presentation_id": presentation_id,
            "slide_count": result["slide_count"],
            "image_urls": image_urls,
            "image_dir": result["image_dir"]
        }), 200
    except Exception as e:
        print(f"Error converting presentation to images: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/presentations/<int:presentation_id>/slides/<int:slide_number>", methods=["GET"])
def serve_slide_image(presentation_id, slide_number):
    """Serve individual slide image with cache busting support"""
    try:
        # Construct path to slide image
        image_dir = f"./slides/presentation_{presentation_id}_images"
        image_path = os.path.join(image_dir, f"slide-{slide_number}.png")
        
        if not os.path.exists(image_path):
            return jsonify({"error": f"Slide {slide_number} image not found"}), 404
        
        # Check if version parameter is present (cache busting)
        version = request.args.get('v')
        
        response = send_file(image_path, mimetype='image/png')
        
        if version:
            # If version parameter is present, allow caching but make it revalidate
            response.headers['Cache-Control'] = 'public, max-age=86400, must-revalidate'
            response.headers['ETag'] = f'"{presentation_id}-{slide_number}-{version}"'
        else:
            # No version - shorter cache
            response.headers['Cache-Control'] = 'public, max-age=300'
        
        return response
    except Exception as e:
        print(f"Error serving slide image: {e}")
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


# AI ------------------------------------------------------------------------------------------------------------------- lero lero lero

@app.route("/api/ai/create-example", methods=["POST"])
def create_example():
    """
    Generate an example based on slide content and user input
    Returns 3 options for the user to choose from
    """
    try:
        if not GOOGLE_API_KEY:
            return jsonify({"error": "AI service not configured"}), 500
        
        data = request.json
        presentation_id = data.get("presentation_id")
        slide_number = data.get("slide_number")
        telegram_chat_id = data.get("telegram_chat_id")
        user_input = data.get("user_input", "")  # Text description or transcribed voice
        input_type = data.get("input_type", "text")  # "text" or "audio"
        voice_file_id = data.get("voice_file_id")  # Telegram file_id for voice messages
        
        print(f"AI: Creating example for presentation {presentation_id}, slide {slide_number}")
        print(f"    Input type: {input_type}, User request: {user_input[:50] if user_input and input_type=='text' else 'voice message'}")
        
        # Get presentation info
        presentation = db.get_presentation_by_id(presentation_id)
        if not presentation:
            return jsonify({"error": "Presentation not found"}), 404
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        # Read presentation content
        prs, content = read_presentation(pptx_path)
        
        # Generate examples using AI (returns 3 options separated by [next])
        ai_response = generate_example_slide(
            api_key=GOOGLE_API_KEY,
            presentation_content=content,
            user_input=user_input,
            slide_index=slide_number
        )
        
        # Split options
        options = [opt.strip() for opt in ai_response.split("[next]") if opt.strip()]
        
        # Ensure we have 3 options
        while len(options) < 3:
            options.append(f"Example option {len(options) + 1} - Please request again for more variety")
        options = options[:3]  # Take only first 3
        
        return jsonify({
            "presentation_id": presentation_id,
            "slide_number": slide_number,
            "options": options,
            "user_input": user_input
        }), 200
        
    except Exception as e:
        print(f"Error creating example: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/create-quiz", methods=["POST"])
def create_quiz():
    """
    Generate an open-ended quiz based on slide content
    Returns 3 question options for the user to choose from
    """
    try:
        if not GOOGLE_API_KEY:
            return jsonify({"error": "AI service not configured"}), 500
        
        data = request.json
        presentation_id = data.get("presentation_id")
        slide_number = data.get("slide_number")
        telegram_chat_id = data.get("telegram_chat_id")
        user_input = data.get("user_input", "")  # Optional user context
        
        print(f"AI: Creating quiz for presentation {presentation_id}, slide {slide_number}")
        
        # Get presentation info
        presentation = db.get_presentation_by_id(presentation_id)
        if not presentation:
            return jsonify({"error": "Presentation not found"}), 404
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        # Read presentation content
        prs, content = read_presentation(pptx_path)
        
        # Generate quiz questions using AI
        ai_response = generate_question_slide(
            api_key=GOOGLE_API_KEY,
            presentation_content=content,
            user_input=user_input,
            slide_index=slide_number,
            question_type="open-ended"
        )
        
        # Split options (each contains question + [Question Result:] + answer)
        options = [opt.strip() for opt in ai_response.split("[next]") if opt.strip()]
        
        # Ensure we have 3 options
        while len(options) < 3:
            options.append(f"Question option {len(options) + 1} - Please request again")
        options = options[:3]
        
        return jsonify({
            "presentation_id": presentation_id,
            "slide_number": slide_number,
            "options": options
        }), 200
        
    except Exception as e:
        print(f"Error creating quiz: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/create-quiz-alternatives", methods=["POST"])
def create_quiz_alternatives():
    """
    Generate a multiple choice quiz based on slide content
    Returns 3 question options for the user to choose from
    """
    try:
        if not GOOGLE_API_KEY:
            return jsonify({"error": "AI service not configured"}), 500
        
        data = request.json
        presentation_id = data.get("presentation_id")
        slide_number = data.get("slide_number")
        telegram_chat_id = data.get("telegram_chat_id")
        user_input = data.get("user_input", "")  # Optional user context
        
        print(f"AI: Creating quiz with alternatives for presentation {presentation_id}, slide {slide_number}")
        
        # Get presentation info
        presentation = db.get_presentation_by_id(presentation_id)
        if not presentation:
            return jsonify({"error": "Presentation not found"}), 404
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        # Read presentation content
        prs, content = read_presentation(pptx_path)
        
        # Generate multiple choice questions using AI
        ai_response = generate_question_slide(
            api_key=GOOGLE_API_KEY,
            presentation_content=content,
            user_input=user_input,
            slide_index=slide_number,
            question_type="multiple-choice"
        )
        
        # Split options
        options = [opt.strip() for opt in ai_response.split("[next]") if opt.strip()]
        
        # Ensure we have 3 options
        while len(options) < 3:
            options.append(f"Question option {len(options) + 1} - Please request again")
        options = options[:3]
        
        return jsonify({
            "presentation_id": presentation_id,
            "slide_number": slide_number,
            "options": options
        }), 200
        
    except Exception as e:
        print(f"Error creating quiz with alternatives: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/insert-slide", methods=["POST"])
def insert_slide():
    """
    Insert the selected AI-generated slide into the presentation
    This is called after the user chooses one of the 3 options
    
    Expected payload:
    {
        "presentation_id": int,
        "slide_content": str,  # The chosen option (full text)
        "slide_title": str,    # e.g., "Quiz", "Example"
        "slide_type": str,     # "example", "quiz", "quiz-alternatives"
        "insert_after": int,   # Slide number to insert after (current slide)
        "user_input": str,     # Original user request (for database)
        "telegram_chat_id": int
    }
    """
    try:
        print("="*80)
        print(f"[AI INSERT] Endpoint called at {__import__('datetime').datetime.now()}")
        print(f"[AI INSERT] Request data: {request.json}")
        print("="*80)
        
        if not GOOGLE_API_KEY:
            return jsonify({"error": "AI service not configured"}), 500
        
        data = request.json
        presentation_id = data.get("presentation_id")
        slide_content = data.get("slide_content")
        slide_title = data.get("slide_title", "AI Generated Slide")
        slide_type = data.get("slide_type", "example")
        insert_after = data.get("insert_after", 1)
        user_input = data.get("user_input", "")
        telegram_chat_id = data.get("telegram_chat_id")
        
        print(f"[AI INSERT] Inserting slide into presentation {presentation_id} after slide {insert_after}")
        print(f"[AI INSERT] Type: {slide_type}, Title: {slide_title}")
        
        # Get presentation info
        presentation = db.get_presentation_by_id(presentation_id)
        if not presentation:
            return jsonify({"error": "Presentation not found"}), 404
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        # Load presentation
        from pptx import Presentation as PptxPresentation
        prs = PptxPresentation(pptx_path)
        initial_slide_count = len(prs.slides)
        print(f"[AI INSERT] Initial slide count: {initial_slide_count}")
        
        # Separate question and answer if it's a quiz
        if "[Question Result:]" in slide_content:
            question_part = slide_content.split("[Question Result:]")[0].strip()
        else:
            question_part = slide_content
        
        # Determine question type for formatting
        question_type_format = "question"
        if slide_type in ["quiz-alternatives", "multiple-choice"]:
            question_type_format = "multiple-choice"
        elif slide_type == "example":
            question_type_format = "example"
        
        # Add the slide (appends to end)
        print(f"[AI INSERT] Calling add_slide() with title='{slide_title}', type='{question_type_format}'")
        add_slide(prs, slide_title, question_part, question_type=question_type_format)
        after_add_count = len(prs.slides)
        print(f"[AI INSERT] After add_slide(): {after_add_count} slides (added {after_add_count - initial_slide_count})")
        
        # Move the slide to the correct position (after insert_after)
        # PowerPoint slides are 0-indexed in the API
        # If insert_after=3 (1-based), we want to insert at index 3 (0-based), which is AFTER slide 3
        # Example: [0, 1, 2, 3, 4] - insert at index 3 means new slide becomes index 3, old index 3 becomes 4
        # NO! We want the new slide AFTER position 3, so it should be at index 4 in the final array
        # Current slides: 0, 1, 2, 3(current), 4, 5
        # After insert at position 4: 0, 1, 2, 3(current), 4(NEW), 5, 6
        
        slides = list(prs.slides)
        new_slide = slides[-1]  # The slide we just added (at the end)
        
        print(f"[AI INSERT] Moving slide from end (index {len(slides)-1}) to position after slide {insert_after}")
        print(f"[AI INSERT] Current slides before move: {[f'Slide {i+1}' for i in range(len(slides))]}")
        
        # insert_after is 1-based. To insert AFTER position N (1-based), we insert at index N (0-based)
        # Example: insert_after=3 means "after slide 3", so new slide becomes slide 4, insert at index 3
        target_index = insert_after  # This is correct: insert_after=3 (1-based) → index 3 (0-based) = position 4 (1-based)
        
        # Move slide by rearranging the XML
        xml_slides = prs.slides._sldIdLst
        slides_list = list(xml_slides)
        print(f"[AI INSERT] XML slides count before pop: {len(slides_list)}")
        moved_slide = slides_list.pop()  # Remove the last slide (the one we just added)
        print(f"[AI INSERT] XML slides count after pop: {len(slides_list)}")
        xml_slides.insert(target_index, moved_slide)  # Insert at target position
        print(f"[AI INSERT] XML slides count after insert: {len(list(xml_slides))}")
        print(f"[AI INSERT] Inserted slide at index {target_index} (position {target_index + 1} in 1-based numbering)")
        
        # Save the modified presentation
        prs.save(pptx_path)
        print(f"[AI INSERT] Saved presentation to {pptx_path}")
        
        # Reload to verify
        prs_verify = PptxPresentation(pptx_path)
        verify_count = len(prs_verify.slides)
        print(f"[AI INSERT] Verification: Reloaded PPTX has {verify_count} slides")
        
        # Convert to images - FORCE REGENERATION since we added a new slide
        output_dir = "./slides"
        print(f"[AI INSERT] Converting PPTX to images (force_regenerate=True)...")
        result = convert_pptx_to_images(pptx_path, output_dir, presentation_id, force_regenerate=True)
        print(f"[AI INSERT] Conversion result: {result['slide_count']} slides converted")
        
        # Update slide count in database
        new_slide_count = result["slide_count"]
        db.update_slide_metadata(presentation_id, slide_count=new_slide_count)
        
        # TODO: Save to database - the user's input and the AI response
        # db.add_question(
        #     presentation_id=presentation_id,
        #     question=user_input,
        #     answer=slide_content,
        #     slide_index=target_index + 1
        # )
        
        # Emit WebSocket event to notify frontend
        import time
        cache_bust_token = int(time.time() * 1000)  # millisecond timestamp
        
        socketio.emit(
            "presentation:slides_updated",
            {
                "presentation_id": presentation_id,
                "new_slide_count": new_slide_count,
                "inserted_at": target_index + 1,
                "cache_bust": cache_bust_token  # Force complete cache refresh
            }
        )
        print(f"[AI] Emitted slides_updated event: {new_slide_count} slides, cache_bust={cache_bust_token}")
        
        return jsonify({
            "success": True,
            "presentation_id": presentation_id,
            "new_slide_count": new_slide_count,
            "inserted_at": target_index + 1,
            "message": f"Slide inserted successfully after slide {insert_after}"
        }), 200
        
    except Exception as e:
        print(f"Error inserting slide: {e}")
        import traceback
        traceback.print_exc()
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
        
        # simulated the ai ans, will add it ltr (or never xd, not using that endpoint anymore)
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


#wont use this now, will add it from another one of the funcs
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
    socketio.run(app, host=HOST, port=PORT, debug=True)  #reminder for me, turn the debug off after its doen
