from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
import textwrap
from google import genai
from dotenv import load_dotenv
import os

# Load the environment variables from .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in the .env file")


def generate_question_slide(api_key, data,user_input, idx, qtype):
    client = genai.Client(api_key=api_key)
    if len(user_input)<2:
        user_input="no user input"
    query_data = ("\n\n").join(data[:idx])
    if qtype=="multiple-choice":
        query_base = (
            f"Please help me create a quiz question based on the information given by the user, and the presentation I will give you. "
            f"The quiz question must be appropriate for a class presentation. "
            f"It should be a multiple choice question, and you should include the answer at the end, "
            f"separated from the question by this string [Question Result:]. "
            f"When answering, give the direct answer, be concise, and ensure the entire response "
            f"fits in a single slide (ideally under 500 characters). "
            f"Use 4 options labeled A, B, C, D, each on its own line. The question should be above this alternatives, without anything before it"
            f"The response must match the language used in the presentation slides I will give you"
            f"Give me 3 diferent questions, each separated by [next]"
        )
    elif (qtype=="open-ended"):
        query_base = (
            f"Please help me create a quiz question based on the presentation I will give you. "
            f"The quiz question must be appropriate for a class presentation. "
            f"It should be a open-ended question, and you should include the answer at the end, "
            f"separated from the question by this string [Question Result:]. "
            f"When answering, give the direct answer, be concise, and ensure the entire response "
            f"fits in a single slide (ideally under 500 characters, not considering the response). "
            f"The response must match the language used in the presentation slides I will give you"
            f"Give me 3 diferent questions, each separated by [next]"
        )
    query = query_base + "User input:\n"+user_input+"Presentation content:\n"+query_data

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=query
    )

    print(query)
    # print(response.text)
    return response.text

def generate_example_slide(api_key, data, user_input, idx):
    client = genai.Client(api_key=api_key)
    query_data = ("\n\n").join(data[:idx])
    if len(user_input)<2:
        user_input="no user input"

    query_base = (
        f"Please help me create an example based on the presentation I will give you. "
        f"The example must be appropriate for a class presentation. "
        f"When answering, give the direct answer, be concise, and ensure the entire response "
        f"fits in a single slide (ideally under 500 characters). "
        f"The response must match the language used in the presentation slides I will give you"
        f"Give me 3 diferent examples, each separated by [next]"
    )

    query = query_base + "User input:\n"+user_input+"Presentation content:\n"+query_data

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=query
    )

    print(query)
    # print(response.text)
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
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout

    slide_width = prs.slide_width
    slide_height = prs.slide_height

    # Fixed margins and positions
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
    content_top = top_margin + title_height + spacing
    content_width = slide_width - 2*side_margin
    content_height = slide_height - content_top - bottom_margin
    content_box = slide.shapes.add_textbox(
        side_margin, content_top,
        content_width, content_height
    )
    content_tf = content_box.text_frame
    content_tf.clear()
    content_tf.margin_top = 0
    content_tf.margin_bottom = 0
    content_tf.margin_left = 0
    content_tf.margin_right = 0

    # Preprocess body: split options into separate lines
    lines = []
    for line in body.strip().split("\n"):
        if question_type.lower() in ["multiple-choice", "alternatives"] and line.strip()[0] in ["A","B","C","D","E"]:
            lines.append(line.strip())
        else:
            # wrap long lines by spaces to fit approx 70 chars per line
            lines.extend(textwrap.wrap(line.strip(), width=70))

    # Start font size and minimum
    base_font_size = 20
    min_font_size = 10
    font_size = base_font_size

    # Iteratively reduce font until it fits horizontally and vertically
    while True:
        line_height_pt = font_size + 6
        total_height_pt = len(lines) * line_height_pt
        # Estimate line width in points: assume 0.5pt per char per font pt (conservative)
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

        # Bullets for multiple-choice questions
        if question_type.lower() in ["multiple-choice", "alternatives"] and line[0] in ["A","B","C","D","E"]:
            p.level = 0
            p.text = "• " + p.text[2:]  # remove "A)" etc, keep bullet

    print(f"Slide added: '{title}' with font size {font_size}pt, strictly fit")





def save_presentation(prs, output_path):
    prs.save(output_path)
    print(f"Presentation saved as: {output_path}")

def choose_response(response):
    options=response.split("[next]")
    for option in options:
        print(option)
    choice=int(input("Please choose an option from 1 to 3"))
    return options[choice-1]


# Input and output PowerPoint paths
input_path = r"/home/diego/Files/Dev/PDS/Class/Project3.1/data/ECG Presentation.pptx"
output_path = r"/home/diego/Files/Dev/PDS/Class/Project3.1/data/presentation_edited.pptx"

# 1. Read the presentation
prs, content = read_presentation(input_path)


# mode="question"
mode="example"
if mode=="question":
    # question types
    qtype1 = "open-ended"
    qtype2 = "multiple-choice"

    # Generate a question slide based on what the user asks and the presentation up to that point, the user asks via telegram
    response = generate_question_slide(api_key, content,"make a question about EEG", 4, qtype2)

    #the user then chooses one of the 3 quiz questions created (in the telegram bot he can also request 3 new questions or cancel the request)
    choice=choose_response(response)
    response=choice

    #then we add the quiz question to the pptx (hopefully in a duplicate, keep the og intact)
    add_slide(prs,"Quiz :)",response.split("[Question Result:]")[0])

else:
    # Generate a example slide based on what the user asks and the presentation up to that point, the user asks via telegram
    response = generate_example_slide(api_key, content,"make an example about EEG", 4)

    #the user then chooses one of the 3 examples created (in the telegram bot he can also request 3 new examples or cancel the request)
    choice=choose_response(response)
    response=choice

    #then we add the quiz question to the pptx (hopefully in a duplicate, keep the og intact)
    add_slide(prs,"Example :)",response.split("[Question Result:]")[0])

# 4. Save the modified presentation
save_presentation(prs, output_path)

