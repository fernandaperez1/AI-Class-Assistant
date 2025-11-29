"""
Test script for designing and previewing AI-generated slides.
This allows rapid iteration on slide design without running the full backend.

Usage:
    python test_slide_design.py <path_to_presentation.pptx>
    
The script will add test slides to the presentation and save it as *_test.pptx
"""

import sys
from pathlib import Path
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR


# Example content with typical lengths for different slide types
EXAMPLE_QUIZ_OPEN = """What are the three main components of the cardiovascular system and how do they work together to maintain homeostasis?

[Question Result:] The three main components are the heart (pumps blood), blood vessels (transport blood), and blood (carries nutrients and oxygen). They work together by circulating oxygenated blood from the heart through arteries to body tissues, then returning deoxygenated blood through veins back to the heart for reoxygenation."""

EXAMPLE_QUIZ_MULTIPLE = """Which of the following best describes the function of mitochondria in cellular respiration?

A. They store genetic information for the cell
B. They produce ATP through oxidative phosphorylation
C. They synthesize proteins from amino acids
D. They package and transport cellular materials

[Question Result:] B. They produce ATP through oxidative phosphoration. Mitochondria are the powerhouse of the cell, converting glucose and oxygen into ATP (adenosine triphosphate), which is the primary energy currency used by cells for various metabolic processes."""

EXAMPLE_EXAMPLE = """Real-world example: Consider a smartphone's battery management system. When you charge your phone, the charging circuit monitors the battery voltage and temperature, adjusting the current flow to prevent overcharging. This is similar to how the endocrine system uses negative feedback - when blood glucose rises after eating, the pancreas releases insulin to lower it, and when it drops too low, glucagon is released to raise it. Both systems continuously monitor and adjust to maintain optimal levels."""

EXAMPLE_SUMMARY = """This presentation covered the fundamental principles of cellular biology:

1. Cell Structure: We explored prokaryotic and eukaryotic cells, including the cell membrane, nucleus, mitochondria, and endoplasmic reticulum.

2. Cellular Processes: We examined cellular respiration, cell division (mitosis/meiosis), and cell signaling.

3. Applications: Understanding cellular biology helps in disease research, vaccine development, and genetic engineering."""


def add_test_slide(prs, title, body, question_type="question"):
    """
    Test version of add_slide function for rapid design iteration.
    Creates slides completely from scratch without inheriting any layout styles.
    
    Args:
        prs: Presentation object
        title: Slide title
        body: Slide body content
        question_type: "question", "multiple-choice", "example", or "summary"
    
    Returns:
        The created slide object
    """
    # Use the blank layout (index 6) or create a completely blank slide
    # This ensures we don't inherit any formatting
    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    slide = prs.slides.add_slide(blank_layout)
    
    # Remove ALL inherited shapes and placeholders from the layout
    # This includes title placeholders, content placeholders, footers, etc.
    shapes_to_remove = list(slide.shapes)
    print(f"  Found {len(shapes_to_remove)} inherited shapes to remove")
    
    for shape in shapes_to_remove:
        try:
            sp = shape.element
            sp.getparent().remove(sp)
        except:
            # If we can't remove it normally, try alternative method
            try:
                slide.shapes._spTree.remove(shape.element)
            except:
                pass
    
    slide_width = prs.slide_width
    slide_height = prs.slide_height
    
    # Calculate proportional sizing based on slide dimensions
    # Use 16:9 standard (10" x 5.625") as baseline
    baseline_height = Inches(5.625)
    size_ratio = slide_height / baseline_height
    
    # Margins - proportional to slide height
    side_margin = slide_width * 0.056  # ~0.75" on 13.33" width
    top_margin = slide_height * 0.089  # ~0.5" on 5.625" height
    title_height = slide_height * 0.142  # ~0.8" on 5.625" height
    spacing = slide_height * 0.027  # ~0.15" on 5.625" height
    bottom_margin = slide_height * 0.107  # ~0.6" on 5.625" height
    
    # Gradient background
    slide.background.fill.gradient()
    slide.background.fill.gradient_angle = 90.0
    slide.background.fill.gradient_stops[0].color.rgb = RGBColor(15, 32, 56)
    slide.background.fill.gradient_stops[1].color.rgb = RGBColor(0, 0, 0)
    
    # Accent bar at top - proportional height
    accent_bar_height = slide_height * 0.027  # ~0.15" on 5.625" height
    accent_bar = slide.shapes.add_shape(
        1,  # rectangle
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
    
    # Title box
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
    
    # Content box
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
    
    # Parse content lines
    lines = []
    is_multiple_choice = question_type.lower() in ["multiple-choice", "alternatives"]
    
    raw_lines = body.strip().split("\n")
    
    for raw_line in raw_lines:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        
        # Check if this is an option line (A, B, C, D, E)
        is_option = is_multiple_choice and len(raw_line) > 0 and raw_line[0] in ["A", "B", "C", "D", "E"] and (len(raw_line) == 1 or raw_line[1] in ['.', ')', ' ', ':'])
        
        lines.append({"text": raw_line, "is_option": is_option})
    
    # Calculate optimal font size based on content volume
    total_chars = sum(len(line["text"]) for line in lines)
    num_original_lines = len(lines)

    # Base font sizes scaled by slide dimensions
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
    
    # Add content paragraphs
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
            # Style for regular text
            p.space_before = Pt(0)
            p.space_after = Pt(int(6 * size_ratio))
    
    print(f"✅ Added slide: '{title}' | Font: {font_size}pt | Lines: {num_original_lines} | Chars: {total_chars} | Type: {question_type}")
    return slide


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_slide_design.py <path_to_presentation.pptx>")
        print("\nExample:")
        print("  python test_slide_design.py my_presentation.pptx")
        sys.exit(1)
    
    pptx_path = Path(sys.argv[1])
    
    if not pptx_path.exists():
        print(f"❌ Error: File not found: {pptx_path}")
        sys.exit(1)
    
    print(f"\n📂 Loading presentation: {pptx_path}")
    prs = Presentation(str(pptx_path))
    
    print(f"📊 Original slide count: {len(prs.slides)}")
    print(f"📐 Slide dimensions: {prs.slide_width.inches:.2f}\" x {prs.slide_height.inches:.2f}\"\n")

    print("🎨 Adding test slides...\n")
    
    add_test_slide(
        prs,
        "AI Quiz ❓",
        EXAMPLE_QUIZ_OPEN,
        "question"
    )
    
    add_test_slide(
        prs,
        "AI Quiz ❓",
        EXAMPLE_QUIZ_MULTIPLE,
        "multiple-choice"
    )
    
    add_test_slide(
        prs,
        "AI Example",
        EXAMPLE_EXAMPLE,
        "example"
    )
    
    add_test_slide(
        prs,
        "AI Summary",
        EXAMPLE_SUMMARY,
        "summary"
    )
    
    # Save test version
    output_path = pptx_path.parent / f"{pptx_path.stem}_test{pptx_path.suffix}"
    prs.save(str(output_path))
    
    print(f"\n💾 Saved test presentation: {output_path}")
    print(f"📊 New slide count: {len(prs.slides)}")
    print("\n✨ Open the file to review the slide designs!")


if __name__ == "__main__":
    main()
