import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from db import database as db
from pptx_utils import extract_text_from_pptx, convert_pptx_to_pdf, get_slide_count, convert_pptx_to_images
from ai_utils import generate_question_slide, generate_example_slide, generate_summary_slide, generate_class_overview, read_presentation, add_slide
import shutil
from pptx import Presentation as PptxPresentation #only using it as fallback
import traceback
import random
import string
from datetime import datetime, timedelta
import time

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
        # generate a 6-character code
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
            print(f"[TELEGRAM] Account linked: user_id={user['id']}, telegram_chat_id={data['telegram_chat_id']}")
            
            # Emit WebSocket event to notify frontend that account was linked
            socketio.emit("telegram:linked", {
                "user_id": user["id"],
                "firebase_uid": user["firebase_uid"],
                "telegram_chat_id": user["telegram_chat_id"]
            })
            
            return jsonify(user), 200
        return jsonify({"error": "Invalid or expired code"}), 400
    except Exception as e:
        print(f"[TELEGRAM] Error linking account: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/telegram/unlink", methods=["POST"])
def unlink_telegram():
    """unlink Telegram account"""
    try:
        data = request.json
        user = db.unlink_telegram_account(
            telegram_chat_id=data["telegram_chat_id"]
        )
        if user:
            return jsonify(user), 200
        return jsonify({"error": "Access error or user not linked"}), 400
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
            class_name=data.get("class_name"),
            class_language=data.get("class_language")
        )
        return jsonify(new_class), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500  
    
@app.route("/api/classes/<int:class_id>/delete", methods=["DELETE"])
def delete_class_endpoint(class_id):
    """Delete a class and all associated files"""
    try:
        data = request.json
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        print(f"[DELETE] Deleting class {class_id} and associated files")
        
        #get presentation info before deleting from database
        presentation = db.get_presentation_by_class_id(class_id)
        
        if presentation:
            presentation_id = presentation["id"]
            original_path = presentation.get("original_pptx_path")
            
            print(f"[DELETE] Found presentation {presentation_id} for class {class_id}")
            
            #delete PPTX files (original and base)
            if original_path and os.path.exists(original_path):
                try:
                    os.remove(original_path)
                    print(f"[DELETE] Deleted PPTX: {original_path}")
                except Exception as e:
                    print(f"[DELETE] Error deleting PPTX: {e}")
            
            base_path = f"{original_path}_base" if original_path else None
            if base_path and os.path.exists(base_path):
                try:
                    os.remove(base_path)
                    print(f"[DELETE] Deleted base PPTX: {base_path}")
                except Exception as e:
                    print(f"[DELETE] Error deleting base PPTX: {e}")
            
            #delete slide images directory
            image_dir = f"./slides/presentation_{presentation_id}_images"
            if os.path.exists(image_dir):
                try:
                    shutil.rmtree(image_dir)
                    print(f"[DELETE] Deleted images directory: {image_dir}")
                except Exception as e:
                    print(f"[DELETE] Error deleting images: {e}")
            
            #delete PDF files
            try:
                pdf_files = [f for f in os.listdir("./slides") 
                           if f.startswith(f"presentation_{presentation_id}_") and f.endswith(".pdf")]
                for pdf_file in pdf_files:
                    pdf_path = os.path.join("./slides", pdf_file)
                    os.remove(pdf_path)
                    print(f"[DELETE] Deleted PDF: {pdf_path}")
            except Exception as e:
                print(f"[DELETE] Error deleting PDFs: {e}")
        
        #delete from database
        class_return = db.delete_class(class_id, user_id)
        
        if class_return:
            print(f"[DELETE] Successfully deleted class {class_id} from database")
            return jsonify({
                **class_return,
                "files_deleted": True,
                "message": "Class and all associated files deleted successfully"
            }), 200
        else:
            return jsonify({"error": "Class not found or not authorized"}), 404

    except Exception as e:
        print(f"[DELETE] Exception: {e}")
        traceback.print_exc()
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

        os.makedirs("./uploads", exist_ok=True)

        save_path = f"./uploads/class_{class_id}_{pptx_file.filename}"
        base_save_path = f"./uploads/class_{class_id}_{pptx_file.filename}_base"
        
        #save the original file
        pptx_file.save(save_path)
        print(f"[UPLOAD] Saved presentation to {save_path}")
        
        #validate the uploaded file (because idk why some files are getting corrupted)
        file_size = os.path.getsize(save_path)
        print(f"[UPLOAD] File size: {file_size} bytes")
        
        if file_size<1024:
            os.remove(save_path)
            return jsonify({"error": "Uploaded file is too small or corrupted"}), 400
        
        # Verify it's a valid PPTX
        try:
            test_prs = PptxPresentation(save_path)
            slide_count = len(test_prs.slides)
            print(f"[UPLOAD] Valid PPTX with {slide_count} slides")
        except Exception as e:
            print(f"[UPLOAD] Invalid PPTX file: {str(e)}")
            os.remove(save_path)
            return jsonify({"error": f"Invalid PPTX file: {str(e)}"}), 400
        
        # Create a backup copy for reset functionality
        # Need to copy the file instead of saving twice, cz it was corrupting the files
        shutil.copyfile(save_path, base_save_path)
        print(f"[UPLOAD] Created backup at {base_save_path}")

        presentation = db.create_presentation(
            class_id=class_id,
            original_pptx_path=save_path
        )

        return jsonify(presentation), 201
    except Exception as e:
        print("Error uploading PPTX:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/classes/<int:class_id>/presentation/reset", methods=["POST"])
def reset_presentation(class_id):
    """Reset a presentation to its original state from the _base copy"""
    try:
        #get presentation info from DB
        presentation = db.get_presentation_by_class_id(class_id)
        if not presentation:
            return jsonify({"error": "Presentation not found"}), 404

        presentation_id = presentation["id"]
        original_path = presentation["original_pptx_path"]
        base_path = f"{original_path}_base"

        #check if base file exists
        if not os.path.exists(base_path):
            return jsonify({"error": "_base file not found. Please re-upload the presentation."}), 404
        
        #check if its corrupted
        base_size = os.path.getsize(base_path)
        if base_size < 1024:
            return jsonify({
                "error": f"Base file is corrupted (size: {base_size} bytes). Please re-upload the presentation."
            }), 400

        print(f"[RESET] Resetting presentation {presentation_id} to original state")
        print(f"[RESET] Original path: {original_path}")
        print(f"[RESET] Base path: {base_path}")
        print(f"[RESET] Base file exists: {os.path.exists(base_path)}")
        print(f"[RESET] Original file exists: {os.path.exists(original_path)}")
        
        #overwrite the original PPTX with the _base copy
        shutil.copyfile(base_path, original_path)
        print(f"[RESET] Copied {base_path} to {original_path}")
        print(f"[RESET] File size after copy: {os.path.getsize(original_path)} bytes")
        if not os.path.exists(original_path):
            raise Exception(f"Failed to copy file to {original_path}")
        
        #get the slide count from the reset PPTX
        try:
            reset_slide_count = get_slide_count(original_path)
            print(f"[RESET] Reset presentation has {reset_slide_count} slides")
        except Exception as e:
            print(f"[RESET] Error getting slide count: {str(e)}")
            print(f"[RESET] Trying to load with python-pptx directly...")
            prs = PptxPresentation(original_path)
            reset_slide_count = len(prs.slides)
            print(f"[RESET] Direct load successful: {reset_slide_count} slides")
        
        #Update slide count in database
        db.update_slide_metadata(presentation_id,slide_count=reset_slide_count)
        
        # Delete all AI-generated slides from database since we're resetting to original
        deleted_count = db.delete_presentation_ai_slides(presentation_id)
        print(f"[RESET] Deleted {deleted_count} AI slides from database")
        
        # Reset the ai_generated_slide_indices array
        db.reset_ai_generated_slide_indices(presentation_id)
        print(f"[RESET] Reset ai_generated_slide_indices array")
        
        # Delete old slide images directory
        image_dir = f"./slides/presentation_{presentation_id}_images"
        if os.path.exists(image_dir):
            shutil.rmtree(image_dir)
            print(f"[RESET] Deleted old images from {image_dir}")
        
        # Delete old PDF if it exists
        pdf_files = [f for f in os.listdir("./slides") if f.startswith(f"presentation_{presentation_id}_") and f.endswith(".pdf")]
        for pdf_file in pdf_files:
            pdf_path = os.path.join("./slides", pdf_file)
            os.remove(pdf_path)
            print(f"[RESET] Deleted old PDF: {pdf_path}")
        
        #regenerate images from the reset PPTX (so that the user does not have to wait again, but this has some issues if the user does not wait)
        output_dir = "./slides"
        result = convert_pptx_to_images(original_path, output_dir, presentation_id, force_regenerate=True)
        print(f"[RESET] Regenerated {result['slide_count']} slide images")
        
        #socket event to notify frontend
        cache_bust_token = int(time.time() * 1000)
        
        socketio.emit(
            "presentation:slides_updated",
            {
                "presentation_id": presentation_id,
                "new_slide_count": reset_slide_count,
                "cache_bust": cache_bust_token,
                "reset": True
            }
        )
        print(f"[RESET] Emitted slides_updated event with {reset_slide_count} slides")
        
        # Get updated presentation data
        updated_presentation = db.get_presentation_by_id(presentation_id)

        return jsonify({
            "message": "Presentation reset successfully",
            "presentation": updated_presentation,
            "slide_count": reset_slide_count
        }), 200

    except Exception as e:
        print("Error resetting PPTX:", e)
        traceback.print_exc()
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
    

@app.route("/api/presentations/<int:presentation_id>/analytics", methods=["POST"])
def save_analytics(presentation_id):
    """Save presentation analytics data"""
    try:
        data = request.json
        slide_order = data.get("slide_order", [])
        time_per_slide = data.get("time_per_slide", {})
        total_time_ms = data.get("total_time_ms", 0)
        
        print(f"[ANALYTICS] Saving analytics for presentation {presentation_id}")
        print(f"[ANALYTICS] Total slides visited:{len(slide_order)}")
        print(f"[ANALYTICS] Total time:{total_time_ms}ms ({total_time_ms/1000:.2f}s)")
        
        result = db.save_presentation_analytics(
            presentation_id=presentation_id,
            slide_order=slide_order,
            time_per_slide=time_per_slide,
            total_time_ms=total_time_ms
        )
        
        return jsonify(result), 201
    except Exception as e:
        print(f"[ANALYTICS] Error saving analytics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/presentations/<int:presentation_id>/analytics", methods=["GET"])
def get_analytics(presentation_id):
    """Get presentation analytics data (using this for the info tab only)"""
    try:
        analytics = db.get_presentation_analytics(presentation_id)
        return jsonify(analytics), 200
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



@app.route("/api/presentations/<int:presentation_id>/ai-slides", methods=["POST"])
def add_ai_slide_endpoint(presentation_id):
    """Add an AI-generated slide (example or question) to a presentation"""
    try:
        data = request.json
        ai_slide = db.add_ai_slide(
            presentation_id=presentation_id,
            slide_content=data["slide_content"],
            user_input=data["user_input"],
            answer=data.get("answer"),  # Optional for examples
            slide_index=data.get("slide_index")
        )
        return jsonify(ai_slide), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/presentations/<int:presentation_id>/ai-slides", methods=["GET"])
def get_ai_slides(presentation_id):
    """Get all AI-generated slides for a presentation"""
    try:
        ai_slides = db.get_presentation_ai_slides(presentation_id)
        return jsonify(ai_slides), 200
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
    """Get presentation information including slide count, availability, and analytics, its all meshed into one func, should split"""
    try:
        presentation = db.get_presentation_by_class_id(class_id)
        if not presentation:
            return jsonify({"error": "No presentation found for this class"}), 404
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        slide_count = get_slide_count(pptx_path)

        analytics = db.get_latest_presentation_analytics(presentation["id"])
        ai_slides = db.get_presentation_ai_slides(presentation["id"])
        
        return jsonify({
            "presentation_id": presentation["id"],
            "class_id": class_id,
            "slide_count": slide_count,
            "pptx_path": pptx_path,
            "started_at": presentation.get("started_at"),
            "ended_at": presentation.get("ended_at"),
            "duration_seconds": presentation.get("duration_seconds"),
            "ai_generated_slide_indices": presentation.get("ai_generated_slide_indices", []),
            "ai_slides_count": len(ai_slides),
            "ai_slides": ai_slides,
            "analytics": analytics
        }), 200
    except Exception as e:
        print(f"Error getting presentation info: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/classes/<int:class_id>/ai-overview", methods=["POST"])
def generate_ai_overview(class_id):
    """Generate AI-powered overview and feedback for the class presentation (this should count I think, like for the extra analytic)"""
    try:
        class_info=db.get_class_by_id(class_id)
        if not class_info:
            return jsonify({"error": "Class not found"}), 404

        presentation = db.get_presentation_by_class_id(class_id)
        if not presentation:
            return jsonify({"error": "No presentation found for this class"}), 404
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        _, presentation_content = read_presentation(pptx_path)

        analytics = db.get_latest_presentation_analytics(presentation["id"])
        ai_slides = db.get_presentation_ai_slides(presentation["id"])

        print(f"[AI] Generating class overview for class {class_id}")
        overview = generate_class_overview(
            presentation_content=presentation_content,
            analytics=analytics,
            ai_slides_count=len(ai_slides),
            class_info=class_info
        )
        
        return jsonify(overview), 200
        
    except Exception as e:
        print(f"Error generating AI overview: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/classes/<int:class_id>/presentation/download", methods=["GET"])
def download_presentation(class_id):
    try:
        presentation=db.get_presentation_by_class_id(class_id)
        if not presentation:
            return jsonify({"error": "No presentation found for this class"}), 404
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        #extract filename from path
        filename = os.path.basename(pptx_path)
        if filename.startswith(f"class_{class_id}_"):
            filename=filename[len(f"class_{class_id}_"):]
        
        print(f"[DOWNLOAD] Serving PPTX: {pptx_path} as {filename}")
        
        return send_file(
            pptx_path,
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(f"Error downloading presentation: {e}")
        traceback.print_exc()
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
        user_input = data.get("user_input", "")  #text description or transcribed voice (the transcript is done in the bot btw)
        input_type = data.get("input_type", "text")  # "text" or "audio"
        voice_file_id = data.get("voice_file_id")  # Telegram file_id for voice messages
        
        print(f"AI: Creating example for presentation {presentation_id}, slide {slide_number}")
        print(f"    Input type: {input_type}, User request: {user_input[:50] if user_input and input_type=='text' else 'voice message'}")
        
        # Get presentation info
        presentation = db.get_presentation_by_id(presentation_id)
        if not presentation:
            return jsonify({"error": "Presentation not found"}), 404
        
        #class info to retrieve language
        class_info = db.get_class_by_id(presentation.get("class_id"))
        class_language = class_info.get("class_language") if class_info else None
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        # Read presentation content
        prs, content = read_presentation(pptx_path)
        
        # Generate examples using AI (returns 3 options separated by [next])
        ai_response = generate_example_slide(
            presentation_content=content,
            user_input=user_input,
            slide_index=slide_number,
            language=class_language
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
        
        class_info = db.get_class_by_id(presentation.get("class_id"))
        class_language = class_info.get("class_language") if class_info else None
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        # Read presentation content
        prs, content = read_presentation(pptx_path)
        
        # Generate quiz questions using AI
        ai_response = generate_question_slide(
            presentation_content=content,
            user_input=user_input,
            slide_index=slide_number,
            question_type="open-ended",
            language=class_language
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
        
        presentation = db.get_presentation_by_id(presentation_id)
        if not presentation:
            return jsonify({"error": "Presentation not found"}), 404
        
        class_info = db.get_class_by_id(presentation.get("class_id"))
        class_language = class_info.get("class_language") if class_info else None
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        #read presentation content
        prs, content = read_presentation(pptx_path)
        
        # Generate multiple choice questions using AI
        ai_response = generate_question_slide(
            presentation_content=content,
            user_input=user_input,
            slide_index=slide_number,
            question_type="multiple-choice",
            language=class_language
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
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/create-summary", methods=["POST"])
def create_summary():
    """
    Generate an informative summary based on slide content up to current position
    Returns 3 summary options for the user to choose from
    """
    try:
        if not GOOGLE_API_KEY:
            return jsonify({"error": "AI service not configured"}), 500
        
        data = request.json
        presentation_id = data.get("presentation_id")
        slide_number = data.get("slide_number")
        telegram_chat_id = data.get("telegram_chat_id")
        user_input = data.get("user_input", "")
        
        print(f"AI: Creating summary for presentation {presentation_id}, slide {slide_number}")
        
        presentation = db.get_presentation_by_id(presentation_id)
        if not presentation:
            return jsonify({"error": "Presentation not found"}), 404
        
        class_info = db.get_class_by_id(presentation.get("class_id"))
        class_language = class_info.get("class_language") if class_info else None
        
        pptx_path = presentation.get("original_pptx_path")
        if not pptx_path or not os.path.exists(pptx_path):
            return jsonify({"error": "PPTX file not found"}), 404
        
        prs, content = read_presentation(pptx_path)
        
        #generate summaries using AI
        ai_response = generate_summary_slide(
            api_key=GOOGLE_API_KEY,
            presentation_content=content,
            user_input=user_input,
            slide_index=slide_number,
            language=class_language
        )
        
        options = [opt.strip() for opt in ai_response.split("[next]") if opt.strip()]
        
        while len(options) < 3:
            options.append(f"Summary option {len(options) + 1} - Please request again for more variety")
        options = options[:3]
        
        return jsonify({
            "presentation_id": presentation_id,
            "slide_number": slide_number,
            "options": options,
            "user_input": user_input
        }), 200
        
    except Exception as e:
        print(f"Error creating summary: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/insert-slide", methods=["POST"])
def insert_slide():
    """
    Insert the selected AI-generated slide into the presentation
    This is called after the user chooses one of the 3 options, here I am adding all of the new slides logic, so it also has db code
    
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
        elif slide_type == "summary":
            question_type_format = "example"  # Use same formatting as examples
        
        # Add the slide (appends to end)
        print(f"[AI INSERT] Calling add_slide() with title='{slide_title}', type='{question_type_format}'")
        add_slide(prs, slide_title, question_part, question_type=question_type_format)
        after_add_count = len(prs.slides)
        print(f"[AI INSERT] After add_slide(): {after_add_count} slides (added {after_add_count - initial_slide_count})")
        
        slides = list(prs.slides)
        new_slide = slides[-1]  # The slide we just added (at the end)
        
        print(f"[AI INSERT] Moving slide from end (index {len(slides)-1}) to position after slide {insert_after}")
        print(f"[AI INSERT] Current slides before move: {[f'Slide {i+1}' for i in range(len(slides))]}")
        

        target_index = insert_after 
        
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
        
        # Convert to images - FORCE REGENERATION since we added a new slide (this aint working in W10 and idk why ffs)
        output_dir = "./slides"
        print(f"[AI INSERT] Converting PPTX to images (force_regenerate=True)...")
        result = convert_pptx_to_images(pptx_path, output_dir, presentation_id, force_regenerate=True)
        print(f"[AI INSERT] Conversion result: {result['slide_count']} slides converted")
        
        # Update slide count in database
        new_slide_count = result["slide_count"]
        db.update_slide_metadata(presentation_id, slide_count=new_slide_count)
        
        # needed to update the idx of the slides after inserting new ones, this will be a pain when checking the view sequence
        # If we insert at position 5, all AI slides at position >= 5 need to be incremented
        updated_slides = db.update_ai_slide_indices_after_insertion(presentation_id, target_index + 1)
        if updated_slides:
            print(f"[AI INSERT] Updated {len(updated_slides)} existing AI slide indices after position {target_index + 1}")
            for slide in updated_slides:
                print(f"  - AI slide {slide['id']} now at position {slide['slide_index']}")
        
        # Save AI-generated slide to database with user input
        #for examples answer is None
        # For questions answer contains the quiz answer
        if question_type_format == "example":
            answer = None
            slide_content_to_save = slide_content
        elif "[Question Result:]" in slide_content:
            # Quiz with answer, split and save both parts
            parts = slide_content.split("[Question Result:]", 1)
            slide_content_to_save = parts[0].strip()
            answer = parts[1].strip() if len(parts) > 1 else None
        else:
            # Quiz without explicit answer marker (shouldnt happen but geminy is dumb lately)
            slide_content_to_save = question_part
            answer = None
        
        db.add_ai_slide(
            presentation_id=presentation_id,
            slide_content=slide_content_to_save,
            user_input=user_input,
            answer=answer,
            slide_index=target_index + 1
        )
        print(f"[AI INSERT] Saved AI slide to database at position {target_index + 1} (type: {question_type_format})")
        print(f"[AI INSERT] Content length: {len(slide_content_to_save)}, Answer: {'Yes' if answer else 'None'}")
        
        # Add the slide index to the ai_generated_slide_indices array
        db.add_ai_generated_slide(presentation_id, target_index + 1)
        print(f"[AI INSERT] Added slide index {target_index + 1} to ai_generated_slide_indices")
        
        # Emit WebSocket event to notify frontend
        cache_bust_token = int(time.time() * 1000)
        
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



#not using this anymore, it was a placeholder for before
# @socketio.on("bot_message")
# def handle_bot_message(data):
#     """
#     Handle messages from the Telegram bot (need to complete it, it will be a pretty big func)
#     Expected data:
#     {
#         "telegram_chat_id": int,
#         "question": str,
#         "presentation_id": int,
#         "slide_index": int (optional)
#     }
#     """
#     print("Received from bot:", data)
    
#     try:
#         # Get user from telegram chat ID
#         user = db.get_user_by_telegram_chat_id(data["telegram_chat_id"])
#         if not user:
#             emit("bot_response", {"error": "User not found"})
#             return
        
#         # Simulated AI answer (legacy endpoint, not actively used)
#         answer = f"AI response to: {data['question']}"
        
#         # Save as AI slide if presentation_id provided
#         if "presentation_id" in data:
#             db.add_ai_slide(
#                 presentation_id=data["presentation_id"],
#                 slide_content=answer,
#                 user_input=data["question"],
#                 answer=None,  # Legacy endpoint, no specific answer
#                 slide_index=data.get("slide_index")
#             )
        
#         emit("bot_response", {
#             "answer": answer,
#             "user_id": user["id"]
#         })
        
#     except Exception as e:
#         print(f"Error handling bot message: {e}")
#         emit("bot_response", {"error": str(e)})


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
