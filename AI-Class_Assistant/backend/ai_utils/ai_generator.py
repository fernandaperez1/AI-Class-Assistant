from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
import textwrap
from google import genai
from openai import OpenAI
import os
import time
import re


# AI Provider Configuration
AI_PROVIDER = os.getenv('AI_PROVIDER', 'gemini').lower()  # 'gemini' or 'openai'
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
AI_MAX_RETRIES = int(os.getenv('AI_MAX_RETRIES', '3'))  # Maximum retry attempts
AI_RETRY_DELAY = float(os.getenv('AI_RETRY_DELAY', '2.0'))  # Delay between retries in seconds


def detect_language_from_content(presentation_content, slide_index):
    """
    returns a language name like "English", "Spanish", "French", etc. I use AI for this aswell btw
    """
    # content from first few slides (up to current slide)
    sample_text = "\n".join(presentation_content[:min(slide_index, 5)])
    
    sample_text = " ".join(sample_text.split())[:1000]
    
    if not sample_text.strip():
        return "English"  # Default fallback
    
    prompt = f"""Analyze the following presentation text and identify its primary language.
Respond with ONLY the language name in English (e.g., "English", "Spanish", "French", "German", "Portuguese", "Italian", "Chinese", "Japanese", etc.).
Do not include any explanation or additional text.

TEXT:
{sample_text}

LANGUAGE:"""
    
    try:
        response = _call_ai_model(prompt).strip()
        response = re.sub(r'["\']', '', response).strip()
        #only the first word if multiple words returned
        response = response.split()[0] if response else "English"
        print(f"[AI] Detected presentation language: {response}")
        return response
    except Exception as e:
        print(f"[AI] Language detection failed: {e}, defaulting to English")
        return "English"


def _call_ai_model(prompt, provider=None, retry_count=0):
    """
    Unified function to call either Gemini or OpenAI based on configuration.
    Includes automatic retry logic with exponential backoff.
    """
    provider = (provider or AI_PROVIDER).lower()
    
    try:
        if provider == 'gemini':
            if not GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY not set in environment variables")
            
            client = genai.Client(api_key=GOOGLE_API_KEY)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text
        
        elif provider == 'openai':
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not set in environment variables")
            
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o",  #using GPT-4o, might change, idk the costs xd
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert educational content creator. Generate clear, concise, and pedagogically sound content for classroom presentations. Follow the user's instructions precisely and maintain the specified format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        
        else:
            raise ValueError(f"Invalid AI_PROVIDER: {provider}. Must be 'gemini' or 'openai'")
    
    except Exception as e:
        #retry with exp backoff
        if retry_count < AI_MAX_RETRIES:
            retry_count += 1
            delay = AI_RETRY_DELAY * (2 ** (retry_count - 1))
            print(f"[AI] Request failed (attempt {retry_count}/{AI_MAX_RETRIES}): {str(e)}")
            print(f"[AI] Retrying in {delay:.1f} seconds...")
            time.sleep(delay)
            return _call_ai_model(prompt, provider, retry_count)
        else:
            print(f"[AI] All {AI_MAX_RETRIES} retry attempts failed for {provider.upper()}")
            raise Exception(f"AI model failed after {AI_MAX_RETRIES} attempts: {str(e)}")



def generate_question_slide(presentation_content, user_input, slide_index, question_type, language=None):
    """
    Generates quiz questions using the configured AI model based on presentation content up to slide_index.
    
    Args:
        presentation_content: List of slide content strings
        user_input: User's request/context for the question
        slide_index: Index of current slide (questions based on content up to this slide)
        question_type: "multiple-choice" or "open-ended" (desarrollo)
        language: optional language to use for the questions (e.g., "English", "Spanish")
    
    Returns:
        String containing 3 questions separated by [next], also they have the response after [Question Result:]
    """
    if not user_input or len(user_input) < 2:
        user_input = "no specific requirements provided"
    
    # Combine content from slides up to current index
    query_data = "\n\n".join(presentation_content[:slide_index])
    
    # Auto-detect language if not provided
    if not language:
        language = detect_language_from_content(presentation_content, slide_index)
    
    # Add language instruction
    language_instruction = f"The question and the response must be in {language}. "
    
    if question_type == "multiple-choice":
        prompt = f"""Create 3 multiple-choice quiz questions based on the presentation content below.

REQUIREMENTS:
- Each question should test understanding of key concepts from the presentation
- Include 4 options labeled A, B, C, D (each on its own line)
- After the options, add the separator [Question Result:] followed by the correct answer with a brief explanation
- Keep the total length under 500 characters per question
- {language_instruction}
- Format: Question text first, then options A-D, then [Question Result:] with answer
- Separate the 3 questions with [next]
- Do NOT number, label, or bullet the questions (no "Question 1:", "**Question 2:**", etc.)

USER CONTEXT: {user_input}

PRESENTATION CONTENT:
{query_data}

Generate exactly 3 questions following this format."""
    
    elif question_type == "open-ended":
        prompt = f"""Create 3 open-ended quiz questions based on the presentation content below.

REQUIREMENTS:
- Each question should encourage critical thinking and deeper understanding
- Questions should be clear and direct (no preamble)
- After each question, add the separator [Question Result:] followed by a concise model answer
- Keep questions under 200 characters and answers under 500 characters
- {language_instruction}
- Separate the 3 questions with [next]
- Do NOT number, label, or bullet the questions

USER CONTEXT: {user_input}

PRESENTATION CONTENT:
{query_data}

Generate exactly 3 open-ended questions."""
    
    else:
        raise ValueError(f"Invalid question_type: {question_type}")
    
    print(f"[AI] Generating {question_type} question for slide {slide_index} using {AI_PROVIDER.upper()}")
    
    return _call_ai_model(prompt)


def generate_example_slide(presentation_content, user_input, slide_index, language=None):
    """
    Generates examples using the configured AI model based on presentation content up to slide_index.
    
    Args:
        api_key: Google API key (deprecated - uses env var AI_PROVIDER instead)
        presentation_content: List of slide content strings
        user_input: User's request for what kind of example they want
        slide_index: Index of current slide
        language: Optional language to use for the examples (e.g., "English", "Spanish")
    
    Returns:
        String containing 3 examples separated by [next]
    """
    query_data = "\n\n".join(presentation_content[:slide_index])
    
    if not user_input or len(user_input) < 2:
        user_input = "no specific requirements provided"

    if not language:
        language = detect_language_from_content(presentation_content, slide_index)
    
    language_instruction = f"Write the examples in {language}. "

    prompt = f"""Generate 3 clear, concrete examples that help students understand the key concepts from the presentation.

REQUIREMENTS:
- Each example must be practical, real-world, and relatable to students
- Examples should be self-contained and descriptive (not questions or definitions)
- Focus on different aspects or applications of the main concept
- Keep each example under 700 characters
- {language_instruction}
- No titles, numbering, or extra formatting
- Separate examples with [next]

USER CONTEXT: {user_input}

PRESENTATION CONTENT:
{query_data}

Generate exactly 3 practical examples."""

    print(f"[AI] Generating example for slide {slide_index} using {AI_PROVIDER.upper()}")
    
    return _call_ai_model(prompt)


def generate_summary_slide(api_key, presentation_content, user_input, slide_index, language=None):
    """
    Generates an informative summary using the configured AI model based on presentation content up to slide_index.
    
    Args:
        api_key: Google API key (deprecated - uses env var AI_PROVIDER instead)
        presentation_content: List of slide content strings
        user_input: User's optional context (can be empty)
        slide_index: Index of current slide
        language: Optional language to use for the summary (e.g., "English", "Spanish")
    
    Returns:
        String containing 3 different summary perspectives separated by [next]
    """
    query_data = "\n\n".join(presentation_content[:slide_index])
    
    if not user_input or len(user_input) < 2:
        user_input = "no specific requirements provided"

    if not language:
        language = detect_language_from_content(presentation_content, slide_index)

    language_instruction = f"Write the summary in {language}. "

    prompt = f"""Generate 3 informative summaries of the presentation content, each with a different perspective.

REQUIREMENTS:
Summary 1: Comprehensive overview of all key concepts covered
Summary 2: Focus on the most important takeaways and practical applications
Summary 3: Structured outline of the main topics and subtopics covered

Each summary should be:
- Clear, educational, and informative for students reviewing the material
- Under 700 characters
- {language_instruction}
- Written without titles, numbering, or extra formatting
- Separated with [next]

USER CONTEXT: {user_input}

PRESENTATION CONTENT:
{query_data}

Generate exactly 3 summaries with different perspectives."""

    print(f"[AI] Generating summary for slide {slide_index} using {AI_PROVIDER.upper()}")
    
    return _call_ai_model(prompt)


def generate_class_overview(presentation_content, analytics=None, ai_slides_count=0, class_info=None):
    """
    Generates an AI-powered overview of the class analyzing teaching effectiveness.
    Provides one positive feedback and one improvement suggestion.
    
    Args:
        presentation_content: List of slide content strings
        analytics: Dict with analytics data (time_per_slide, slide_order, etc.)
        ai_slides_count: Number of AI-generated slides
        class_info: Dict with class information (name, subject, etc.)
    
    Returns:
        Dict with 'positive_feedback' and 'improvement_suggestion' keys
    """
    # add some context (this will break if the prs is too long cz I only load the first 10 slides)
    slides_summary = "\n\n".join(presentation_content[:10]) 
    total_slides = len(presentation_content)
    
    analytics_context = ""
    if analytics and analytics.get("time_per_slide"):
        time_per_slide = analytics["time_per_slide"]
        total_time_ms = analytics.get("total_time_ms", 0)
        
        times = list(time_per_slide.values())
        avg_time = sum(times) / len(times) if times else 0
        max_time_slide = max(time_per_slide.items(), key=lambda x: x[1]) if time_per_slide else None
        min_time_slide = min(time_per_slide.items(), key=lambda x: x[1]) if time_per_slide else None
        
        slide_order = analytics.get("slide_order", [])
        visit_count = {}
        for entry in slide_order:
            slide = entry.get("slide")
            visit_count[slide] = visit_count.get(slide, 0) + 1
        
        revisited_slides = {k: v for k, v in visit_count.items() if v > 1}
        
        analytics_context = f"""
PRESENTATION STATISTICS:
- Total Duration: {total_time_ms / 1000:.1f} seconds ({total_time_ms / 60000:.1f} minutes)
- Average Time per Slide: {avg_time / 1000:.1f} seconds
- Slide with Most Time: Slide {max_time_slide[0]} ({max_time_slide[1] / 1000:.1f}s)
- Slide with Least Time: Slide {min_time_slide[0]} ({min_time_slide[1] / 1000:.1f}s)
- Slides Revisited: {len(revisited_slides)} slides
- AI Interaction: {ai_slides_count} AI-generated content pieces
- Total Slide Transitions: {len(slide_order)}
"""
    else:
        analytics_context = "No presentation analytics available yet. This appears to be a new or unpresented class."
    
    # make the query context
    class_context = ""
    if class_info:
        class_context = f"""
CLASS INFORMATION:
- Subject: {class_info.get('subject', 'Unknown')}
- Difficulty Level: {class_info.get('difficulty_level', 'Unknown')}
- Language: {class_info.get('class_language', 'Unknown')}
"""
    
    prompt = f"""You are an expert educational consultant analyzing a classroom presentation. Based on the presentation content and delivery statistics, provide constructive feedback to help the teacher improve their teaching.

{class_context}

PRESENTATION CONTENT (Sample):
Total Slides: {total_slides}
{slides_summary}

{analytics_context}

TASK:
Analyze this presentation and provide:

1. ONE POSITIVE ASPECT: Identify one specific thing the teacher did well. This could be related to:
   - Content organization and clarity
   - Time management and pacing
   - Use of interactive AI features
   - Engagement techniques
   - Coverage of material

2. ONE IMPROVEMENT SUGGESTION: Identify one specific, actionable improvement. This could be related to:
   - Slides that need more/less time based on complexity
   - Pacing issues (too fast/slow on certain topics)
   - Content that might benefit from more examples or clarification
   - Better use of interactive features
   - Navigation patterns that suggest confusion

IMPORTANT:
- Be specific and reference actual data (slide numbers, times, etc.)
- Be constructive and encouraging
- Focus on actionable insights
- Keep each point concise (2-3 sentences max)
- If no analytics are available, focus on content quality and structure

Return your response in this exact format:
POSITIVE: [your positive feedback here]
IMPROVEMENT: [your improvement suggestion here]"""

    print(f"[AI] Generating class overview using {AI_PROVIDER.upper()}")
    
    try:
        response = _call_ai_model(prompt)
        
        lines = response.strip().split('\n')
        positive = ""
        improvement = ""
        
        for line in lines:
            if line.startswith("POSITIVE:"):
                positive = line.replace("POSITIVE:", "").strip()
            elif line.startswith("IMPROVEMENT:"):
                improvement = line.replace("IMPROVEMENT:", "").strip()
        
        # fallback 1
        if not positive or not improvement:
            parts = response.split("IMPROVEMENT:")
            if len(parts) == 2:
                positive = parts[0].replace("POSITIVE:", "").strip()
                improvement = parts[1].strip()
            else:
                # fallback 2 xddd (vender humo)
                positive = "The presentation shows good structure and content organization."
                improvement = response.strip()
        
        return {
            "positive_feedback": positive,
            "improvement_suggestion": improvement,
            "generated_at": time.time()
        }
    
    except Exception as e:
        print(f"[AI] Error generating class overview: {e}")
        return {
            "positive_feedback": "Unable to generate feedback at this time.",
            "improvement_suggestion": "Please try again later.",
            "error": str(e)
        }


def read_presentation(pptx_path):
    prs = Presentation(pptx_path)
    content = []
    for i, slide in enumerate(prs.slides, start=1):
        text = f"Slide {i}:\n"
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                text += shape.text + "\n"
        content.append(text)
    return prs, content

def add_slide(prs, title, body, question_type="question"):
    """
    Adds a professionally designed slide to the presentation with improved layout and text fitting.
    Features gradient background, proper text wrapping, and automatic font sizing.
    Creates slides completely from scratch without inheriting any layout styles (inheriting was a pain so I removed it).
    
    Args:
        prs: Presentation object
        title: Slide title
        body: Slide body content
        question_type: "question", "multiple-choice", "alternatives", or "example"
    
    Returns:
        The created slide object
    """
    # get a blank layout, not from the existing ones
    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    slide = prs.slides.add_slide(blank_layout)
    
    # Remove ALL inherited shapes and placeholders from the layout
    shapes_to_remove = list(slide.shapes)
    
    for shape in shapes_to_remove:
        try:
            sp = shape.element
            sp.getparent().remove(sp)
        except:
            #try diff way to remove
            try:
                slide.shapes._spTree.remove(shape.element)
            except:
                pass
    
    slide_width = prs.slide_width
    slide_height = prs.slide_height
    
    # Calculate proportional sizing based on slide dimensions
    # using 16:9 standard (10" x 5.625") as baseline
    baseline_height = Inches(5.625)
    size_ratio = slide_height / baseline_height
    
    # Margins - proportional to slide height
    side_margin = slide_width * 0.056
    top_margin = slide_height * 0.089
    title_height = slide_height * 0.142
    spacing = slide_height * 0.027
    bottom_margin = slide_height * 0.107
    
    #gradient background
    slide.background.fill.gradient()
    slide.background.fill.gradient_angle = 90.0
    slide.background.fill.gradient_stops[0].color.rgb = RGBColor(15, 32, 56)
    slide.background.fill.gradient_stops[1].color.rgb = RGBColor(0, 0, 0)
    
    #accent bar at top to id the type of slide
    accent_bar_height = slide_height * 0.027
    accent_bar = slide.shapes.add_shape(
        1,  #rectangle
        0, 0,
        slide_width, accent_bar_height
    )
    accent_bar.fill.solid()
    
    # Color code by question type
    if question_type.lower() in ["multiple-choice", "alternatives"]:
        accent_bar.fill.fore_color.rgb = RGBColor(68, 138, 255)  # Blue
    elif question_type.lower() in ["example", "ejemplos"]:
        accent_bar.fill.fore_color.rgb = RGBColor(46, 204, 113)  # Green
    elif question_type.lower() in ["summary", "resumen"]:
        accent_bar.fill.fore_color.rgb = RGBColor(155, 89, 182)  # Purple
    else:
        accent_bar.fill.fore_color.rgb = RGBColor(241, 196, 15)  # Gold
    
    accent_bar.line.fill.background()
    
    title_box = slide.shapes.add_textbox(
        side_margin, top_margin,
        slide_width - 2*side_margin, title_height
    )
    title_tf = title_box.text_frame
    title_tf.word_wrap = True
    title_tf.vertical_anchor = MSO_ANCHOR.TOP
    
    title_p = title_tf.paragraphs[0]
    title_p.text = title
    title_p.font.name = "Segoe UI"
    title_p.font.size = Pt(int(36 * size_ratio))  # Scale title font
    title_p.font.bold = True
    title_p.font.color.rgb = RGBColor(255, 255, 255)
    title_p.alignment = PP_ALIGN.LEFT
    
    content_top = top_margin + title_height + spacing
    content_width = slide_width - 2*side_margin
    content_height = slide_height - content_top - bottom_margin
    
    content_box = slide.shapes.add_textbox(
        side_margin, content_top,
        content_width, content_height
    )
    content_tf = content_box.text_frame
    content_tf.word_wrap = True
    content_tf.vertical_anchor = MSO_ANCHOR.TOP
    content_tf.margin_left = Pt(int(12 * size_ratio))
    content_tf.margin_right = Pt(int(12 * size_ratio))
    content_tf.margin_top = Pt(int(12 * size_ratio))
    content_tf.margin_bottom = Pt(int(12 * size_ratio))
    
    lines = []
    is_multiple_choice = question_type.lower() in ["multiple-choice", "alternatives"]
    
    raw_lines = body.strip().split("\n")
    
    for raw_line in raw_lines:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        
        #check if this is an option line (A, B, C, D, E)
        is_option = is_multiple_choice and len(raw_line) > 0 and raw_line[0] in ["A", "B", "C", "D", "E"] and (len(raw_line) == 1 or raw_line[1] in ['.', ')', ' ', ':'])
        
        lines.append({"text": raw_line, "is_option": is_option})
    
    #calculate optimal font size based on content volume (not using lines now, I am using chars)
    total_chars = sum(len(line["text"]) for line in lines)
    num_original_lines = len(lines)

    # Base font sizes scaled by slide dimensions
    # Multiple choice questions need smaller fonts due to more line breaks, this one needs more testing
    if is_multiple_choice:
        if total_chars < 200:
            base_font_size = 20
        elif total_chars < 400:
            base_font_size = 18
        elif total_chars < 600:
            base_font_size = 16
        elif total_chars < 800:
            base_font_size = 14
        else:
            base_font_size = 12
    else:
        if total_chars < 200:
            base_font_size = 24
        elif total_chars < 400:
            base_font_size = 20
        elif total_chars < 600:
            base_font_size = 18
        elif total_chars < 800:
            base_font_size = 16
        elif total_chars < 1000:
            base_font_size = 14
        else:
            base_font_size = 12
    
    font_size = int(base_font_size * size_ratio)
    
    for i, line_data in enumerate(lines):
        if i == 0:
            p = content_tf.paragraphs[0]
        else:
            p = content_tf.add_paragraph()
        
        p.text = line_data["text"]
        p.font.name = "Segoe UI"
        p.font.size = Pt(font_size)
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.LEFT
        p.line_spacing = 1.15 
        
        if line_data["is_option"]:
            # Style for multiple choice options
            p.space_before = Pt(int(8 * size_ratio))
            p.space_after = Pt(int(2 * size_ratio))
            p.font.bold = False
        else:
            # Style for regular text - minimal spacing
            p.space_before = Pt(0)
            p.space_after = Pt(int(6 * size_ratio))
    
    print(f"[AI] Professional slide added: '{title}' | Font: {font_size}pt | Lines: {num_original_lines} | Type: {question_type}")
    return slide
