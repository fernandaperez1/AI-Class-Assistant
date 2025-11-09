from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
import textwrap
from google import genai
import os


#WARNING, IM USING GEMINI 2.0 EXPERIMENTAL, NOT 2.5 FLASH, NEED TO CHECK WHICH ONE IS BETTER, 2.0 EXP IS FOR REASONING SUPPOSEDLY

def generate_question_slide(api_key, presentation_content, user_input, slide_index, question_type, language=None):
    """
    Generates quiz questions using the Gemini API based on presentation content up to slide_index, might change this because I am not sure of the context I should give the AI for the example.
    Args:
        api_key: Google API key ()
        presentation_content: List of slide content strings
        user_input: User's request/context for the question
        slide_index: Index of current slide (questions based on content up to this slide)
        question_type: "multiple-choice" or "open-ended" (desarrollo)
        language: optional language to use for the questions (e.g., "English", "Spanish")
    Returns:
        String containing 3 questions separated by [next], also they have the response after [Question Result:]
    """
    client = genai.Client(api_key=api_key)
    
    if not user_input or len(user_input) < 2:
        user_input = "no user input"
    
    # Combine content from slides up to current index
    query_data = "\n\n".join(presentation_content[:slide_index])
    
    # Add language instruction if provided
    language_instruction = ""
    if language:
        language_instruction = f"The question and the response must be in {language}. "
    else:
        language_instruction = "The question and the response must match the language used in the presentation slides I will give you. "
    
    if question_type == "multiple-choice":
        query_base = (
            f"Please help me create a quiz question based on the information given by the user, and the presentation I will give you. "
            f"The quiz question must be appropriate for a class presentation. "
            f"It should be a multiple choice question, and you should include the answer at the end, "
            f"separated from the question by this string [Question Result:]. "
            f"When answering, give the direct answer, be concise, and ensure the entire response "
            f"fits in a single slide (ideally under 500 characters per question). "
            f"Use 4 options labeled A, B, C, D, each on its own line. The question should be above these alternatives, without anything before it. "
            f"{language_instruction}"
            f"Give me 3 different questions, each separated by [next]"
        )
    elif question_type == "open-ended":
        query_base = (
            f"Please help me create a quiz question based on the presentation I will give you. "
            f"The quiz question must be appropriate for a class presentation. "
            f"It should be an open-ended question, and you should include the answer at the end, "
            f"separated from the question by this string [Question Result:]. "
            f"When answering, give the direct answer, be concise, and ensure the entire response, only include the question, without anything before it"
            f"fits in a single slide (ideally under 500 characters per question, not considering the response). "
            f"{language_instruction}"
            f"Give me 3 different questions, each separated by [next]"
        )
    else:
        raise ValueError(f"Invalid question_type: {question_type}")
    
    query = query_base + "\nUser input:\n" + user_input + "\n\nPresentation content:\n" + query_data
    
    print(f"[AI] Generating {question_type} question for slide {slide_index}")
    
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=query
    )
    
    return response.text


def generate_example_slide(api_key, presentation_content, user_input, slide_index, language=None):
    """
    Generates examples using the Gemini API based on presentation content up to slide_index. The ai can get dumb sometimes and do shit, must fix this so that the examples are real examples
    Args:
        api_key: Google API key
        presentation_content: List of slide content strings
        user_input: User's request for what kind of example they want
        slide_index: Index of current slide
        language: Optional language to use for the examples (e.g., "English", "Spanish")
    Returns:
        String containing 3 examples separated by [next] (literally xd)
    """
    client = genai.Client(api_key=api_key)
    
    query_data = "\n\n".join(presentation_content[:slide_index])
    
    if not user_input or len(user_input) < 2:
        user_input = "no user input"

    # same sht
    language_instruction = ""
    if language:
        language_instruction = f"Write the examples in {language}. "
    else:
        language_instruction = "Write in the same tone and language style as the presentation slides. "

    query_base = (
        f"You will receive a presentation and, optionally, a user request. "
        f"Your goal is to generate exactly 3 clear, concrete examples that help students understand the key concepts from the presentation. "
        f"If the user does not request anything specific, base the examples on the main topic or core concept of the presentation. "
        f"Each example must be self-contained, descriptive, and practical—not a question or definition. "
        f"Keep each example under 700 characters. {language_instruction}"
        f"Separate examples with [next], with no titles, numbering, or explanations. "
        f"Output only the examples."
    )
    query = query_base + "\nUser input:\n" + user_input + "\n\nPresentation content:\n" + query_data
    print(f"[AI] Generating example for slide {slide_index}")
    response=client.models.generate_content(model="gemini-2.0-flash-exp",contents=query)
    return response.text


def generate_summary_slide(api_key, presentation_content, user_input, slide_index, language=None):
    """
    Generates an informative summary using the Gemini API based on presentation content up to slide_index.
    Args:
        api_key: Google API key
        presentation_content: List of slide content strings
        user_input: User's optional context (can be empty)
        slide_index: Index of current slide
        language: Optional language to use for the summary (e.g., "English", "Spanish")
    Returns:
        String containing 3 different summary perspectives separated by [next]
    """
    client = genai.Client(api_key=api_key)
    
    query_data = "\n\n".join(presentation_content[:slide_index])
    
    if not user_input or len(user_input) < 2:
        user_input = "no user input"

    language_instruction = ""
    if language:
        language_instruction = f"Write the summary in {language}. "
    else:
        language_instruction = "Write in the same tone and language style as the presentation slides. "

    query_base = (
        f"You will receive presentation slides and need to generate exactly 3 informative summaries. "
        f"Each summary should provide a different perspective or focus on the content covered so far: "
        f"1) A comprehensive overview of all key concepts, "
        f"2) A focus on the most important takeaways and practical applications, "
        f"3) A structured outline of the main topics and subtopics covered. "
        f"Each summary must be clear, educational, and informative for students reviewing the material. "
        f"Keep each summary under 700 characters. {language_instruction}"
        f"Separate summaries with [next], with no titles, numbering, or extra formatting. "
        f"Output only the summaries."
    )
    query = query_base + "\nUser input:\n" + user_input + "\n\nPresentation content:\n" + query_data
    print(f"[AI] Generating summary for slide {slide_index}")
    response = client.models.generate_content(model="gemini-2.0-flash-exp", contents=query)
    return response.text


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
    Adds a new slide to the presentation with black background and white text.
    Automatically adjusts font size to fit content. This is what we need to fix to compete
    Args:
        prs: Presentation object
        title: Slide title
        body: Slide body content
        question_type: "question", "multiple-choice", "alternatives", or "example"
    Returns:
        The created slide object
    """
    # Find an available blank layout (prefer index 6, but fallback to last or first available)
    num_layouts = len(prs.slide_layouts)
    if num_layouts > 6:
        layout_index = 6
    elif num_layouts > 0:
        # Try to use the last layout (often blank) or first one if only one exists
        layout_index = num_layouts - 1
    else:
        raise ValueError("Presentation has no slide layouts available")
    
    slide = prs.slides.add_slide(prs.slide_layouts[layout_index])
    
    slide_width = prs.slide_width
    slide_height = prs.slide_height
    # Fixed margins and positions (all so that we can customize)
    side_margin = Pt(36)
    top_margin = Pt(36)
    title_height = Pt(72)
    spacing = Pt(24)
    bottom_margin = Pt(36)

    # Black background
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(0, 0, 0)

    # Title textbox
    title_box = slide.shapes.add_textbox(
        side_margin, top_margin,
        slide_width - 2*side_margin, title_height
    )
    title_tf = title_box.text_frame
    title_tf.clear()
    title_p = title_tf.add_paragraph()
    title_p.text = title
    title_p.font.name = "Calibri Light"
    title_p.font.size = Pt(32)
    title_p.font.color.rgb = RGBColor(255, 255, 255)
    
    # Content textbox
    content_top=top_margin + title_height + spacing
    content_width=slide_width-2*side_margin
    content_height=slide_height-content_top-bottom_margin
    content_box=slide.shapes.add_textbox(
        side_margin, content_top,
        content_width, content_height
    )
    content_tf = content_box.text_frame
    content_tf.clear()
    content_tf.margin_top=0
    content_tf.margin_bottom=0
    content_tf.margin_left= 0
    content_tf.margin_right=0
    
    # Preprocess body: split options into separate lines
    lines = []
    for line in body.strip().split("\n"):
        if question_type.lower() in ["multiple-choice", "alternatives"] and line.strip() and line.strip()[0] in ["A","B","C","D","E"]:
            lines.append(line.strip())
        else:
            # wrap long lines by spaces to fit approx 70 chars per line
            if line.strip():
                lines.extend(textwrap.wrap(line.strip(), width=70))
    
    # Start font size and minimum
    base_font_size = 20
    min_font_size = 10
    font_size = base_font_size
    
    # Iteratively reduce font until it fits horizontally and vertically
    while True:
        line_height_pt = font_size + 6
        total_height_pt = len(lines) * line_height_pt
        # Estimate line width in points: assume 0.5pt per char per font pt (I am being overkill here, just in case)
        max_line_width_pt = max(sum(font_size * 0.5 for c in line) for line in lines) if lines else 0
        
        if total_height_pt <= content_height and max_line_width_pt <= content_width:
            break
        font_size -= 1
        if font_size < min_font_size:
            font_size = min_font_size
            break
    
    # Add paragraphs
    for line in lines:
        if not line.strip():
            continue
        p = content_tf.add_paragraph()
        p.text = line.strip()
        p.font.name = "Arial"
        p.font.size = Pt(font_size)
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.space_after = Pt(6)
        
        # multiple-choice questions
        if question_type.lower() in ["multiple-choice", "alternatives"] and line.strip() and line.strip()[0] in ["A","B","C","D","E"]:
            p.level = 0
            p.text = " " + p.text 
    print(f"[AI] Slide added: '{title}' with font size {font_size}pt")
    return slide
