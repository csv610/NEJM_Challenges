#!/usr/bin/env python3
"""
Convert NEJM questions from JSON to LaTeX format.
Reads nejm_questions.json and generates a LaTeX document.
"""

import json
import os
import unicodedata
from pathlib import Path

# Configuration for image resizing
MAX_IMAGE_HEIGHT = '0.50\\textheight'  # Maximum height for images (60% of page height)
MAX_IMAGE_WIDTH = '0.90\\textwidth'   # Maximum width for images (95% of page width)


def escape_latex(text):
    """Escape special LaTeX characters in text."""
    if not text:
        return text

    # Remove problematic control characters and combining marks
    cleaned_text = []
    for char in text:
        code = ord(char)
        # Skip control characters
        if code < 32 and char not in '\n\t':
            continue
        # Skip control character range
        if 0x0080 <= code <= 0x009F:
            continue
        # Skip combining diacritical marks
        if 0x0300 <= code <= 0x036F:
            continue
        cleaned_text.append(char)

    text = ''.join(cleaned_text)

    # Order matters - escape backslash first
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\_'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
        # Handle smart quotes and apostrophes
        (''', r"'"),  # Right single quotation mark
        (''', r"'"),  # Left single quotation mark
        ('"', r'"'),  # Left double quotation mark
        ('"', r'"'),  # Right double quotation mark
        ('–', r'-'),  # En dash
        ('—', r'-'),  # Em dash
        ('−', r'-'),  # Unicode minus sign (U+2212)
    ]

    for char, replacement in replacements:
        text = text.replace(char, replacement)

    return text


def estimate_text_height(question_data, has_answer=True):
    """Estimate vertical space consumed by text in LaTeX points."""

    # LaTeX constants (11pt article, fullpage package)
    BASELINESKIP_PT = 13.2  # 11pt * 1.2 line spacing

    # Section header + date
    header_height = BASELINESKIP_PT * 1.2  # \section* with larger font
    date_height = BASELINESKIP_PT + 6  # date line + \vspace{6pt}

    # Question text (estimate ~80 chars per line at 11pt in 6.5" width)
    question_text = question_data.get('question', '')
    question_lines = max(1, len(question_text) // 80 + 1)
    question_height = question_lines * BASELINESKIP_PT + 12  # + \vspace{12pt}

    # Options header
    options_header = BASELINESKIP_PT

    # Five options (A-E) - estimate lines per option
    options = question_data.get('options', {})
    total_option_lines = 0
    for key in ['A', 'B', 'C', 'D', 'E']:
        if key in options:
            option_text = options[key]
            # Account for label "A. " reducing effective width
            option_lines = max(1, len(option_text) // 75 + 1)
            total_option_lines += option_lines
    options_height = total_option_lines * BASELINESKIP_PT

    # Answer (if present)
    answer_height = 0
    if has_answer and question_data.get('answer'):
        answer_height = BASELINESKIP_PT + 12  # line + \vspace{12pt}

    # Image header
    image_header = BASELINESKIP_PT

    total = (header_height + date_height + question_height +
             options_header + options_height + answer_height + image_header)

    return total


def read_questions(json_file):
    """Read questions from JSON file."""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def read_image_scales(scale_file='imagescale.txt'):
    """Read image scales from scale table. Returns dict with id as key and scale as value."""
    scales = {}
    if not os.path.exists(scale_file):
        return scales

    with open(scale_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines[1:]:  # Skip header
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                try:
                    image_id = parts[0]
                    scale = float(parts[1])
                    scales[image_id] = scale
                except (ValueError, IndexError):
                    continue

    return scales


def calculate_optimal_scale(image_path, text_height_pt, question_id):
    """Calculate optimal image scale to fit on page with text."""
    from PIL import Image
    import os

    # LaTeX page constants
    TEXTHEIGHT_PT = 650.4  # 9.0" with fullpage package
    TEXTWIDTH_PT = 469.8   # 6.5" with fullpage package
    MAX_IMAGE_HEIGHT_RATIO = 0.60  # Images occupy max 60% of page height
    MAX_IMAGE_WIDTH_RATIO = 0.95   # Images occupy max 95% of page width
    DEFAULT_SCALE = 1.0

    # Check image exists
    if not os.path.exists(image_path):
        print(f"Warning: Image not found for question {question_id}: {image_path}")
        return DEFAULT_SCALE

    try:
        # Read image dimensions
        img = Image.open(image_path)
        img_width_px, img_height_px = img.size
        aspect_ratio = img_width_px / img_height_px

        # Calculate maximum dimensions
        max_height_pt = TEXTHEIGHT_PT * MAX_IMAGE_HEIGHT_RATIO
        max_width_pt = TEXTWIDTH_PT * MAX_IMAGE_WIDTH_RATIO

        # Calculate target dimensions maintaining aspect ratio
        # Start with max height constraint
        target_height_pt = max_height_pt
        target_width_pt = target_height_pt * aspect_ratio

        # If width exceeds max, constrain to max width
        if target_width_pt > max_width_pt:
            target_width_pt = max_width_pt
            target_height_pt = target_width_pt / aspect_ratio

        # Scale relative to \textwidth
        scale = target_width_pt / TEXTWIDTH_PT

        # Clamp to reasonable range [0.3, 0.95]
        scale = max(0.3, min(0.95, scale))
        scale = round(scale, 2)

        print(f"Question {question_id}: {img_width_px}x{img_height_px} "
              f"(AR: {aspect_ratio:.2f}), Scale: {scale}")

        return scale

    except Exception as e:
        print(f"Warning: Error processing image for {question_id}: {e}")
        return DEFAULT_SCALE


def extract_scales_from_latex(latex_file):
    """Extract image scales from existing LaTeX file. Returns dict with id as key and scale as value."""
    scales = {}
    if not os.path.exists(latex_file):
        return scales

    import re
    try:
        with open(latex_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Pattern to match: \section*{Question N (ID: <id>)} ... \includegraphics[width=<scale>\textwidth,...]
        # We need to find pairs of question IDs and their corresponding image scales
        sections = re.split(r'\\section\*\{Question', content)

        for section in sections[1:]:  # Skip first split (before any section)
            # Extract question ID from section header
            id_match = re.search(r'\(ID: ([^)]+)\)', section)
            if not id_match:
                continue
            question_id = id_match.group(1)

            # Extract width scale from includegraphics command
            width_match = re.search(r'\\includegraphics\[width=([0-9.]+)\\textwidth', section)
            if width_match:
                try:
                    scale = float(width_match.group(1))
                    scales[question_id] = scale
                except ValueError:
                    continue
    except Exception:
        pass  # If parsing fails, just return empty scales

    return scales


def calculate_automatic_scales(questions):
    """Calculate automatic scales for all questions."""
    auto_scales = {}

    for q in questions:
        question_id = q.get('id', 'unknown')
        image_path = q.get('image', '')

        if not image_path:
            continue

        # Estimate text height
        has_answer = q.get('answer') is not None
        text_height_pt = estimate_text_height(q, has_answer=has_answer)

        # Calculate optimal scale
        scale = calculate_optimal_scale(image_path, text_height_pt, question_id)
        auto_scales[str(question_id)] = scale

    return auto_scales


def create_latex_document(questions, output_file, image_scales=None):
    """Create a LaTeX document from questions."""
    if image_scales is None:
        image_scales = {}

    latex_content = []

    # Document preamble
    latex_content.append(r'\documentclass[11pt]{article}')
    latex_content.append(r'\usepackage[utf8]{inputenc}')
    latex_content.append(r'\usepackage[T1]{fontenc}')
    latex_content.append(r'\usepackage{lmodern}')
    latex_content.append(r'\usepackage{textgreek}')
    latex_content.append(r'\usepackage{fullpage}')
    latex_content.append(r'\usepackage{graphicx}')
    latex_content.append(r'\usepackage{xcolor}')
    latex_content.append(r'\usepackage{fancyvrb}')
    latex_content.append('')

    latex_content.append(r'\title{NEJM Medical Challenge Questions}')
    latex_content.append(r'\author{}')
    latex_content.append(r'\date{}')
    latex_content.append('')

    latex_content.append(r'\begin{document}')
    latex_content.append(r'\maketitle')
    latex_content.append(r'\tableofcontents')
    latex_content.append(r'\newpage')
    latex_content.append('')

    # Add questions
    for idx, q in enumerate(questions, 1):
        question_id = q.get('id', f'q{idx}')
        date = q.get('date', 'Unknown date')
        question_text = q.get('question', '')
        options = q.get('options', {})
        image_path = q.get('image', '')
        answer = q.get('answer', None)

        # Start new page for each question (except first one)
        if idx > 1:
            latex_content.append(r'\newpage')
            latex_content.append('')

        # Question section
        latex_content.append(r'\section*{Question ' + str(idx) + r' (ID: ' +
                           escape_latex(str(question_id)) + r')}')
        latex_content.append(r'\textbf{Date: }' + escape_latex(date))
        latex_content.append(r'\vspace{6pt}')
        latex_content.append('')

        # Question text
        escaped_question = escape_latex(question_text)
        latex_content.append(escaped_question)
        latex_content.append(r'\vspace{12pt}')
        latex_content.append('')

        # Options
        latex_content.append(r'\textbf{Options:}')
        latex_content.append(r'\begin{enumerate}')

        for option_key in ['A', 'B', 'C', 'D', 'E']:
            if option_key in options:
                option_text = options[option_key]
                escaped_option = escape_latex(option_text)
                latex_content.append(r'\item[' + option_key + r'.] ' + escaped_option)

        latex_content.append(r'\end{enumerate}')
        latex_content.append('')

        # Answer (if provided)
        if answer:
            latex_content.append(r'\textbf{Answer: }' + escape_latex(str(answer)))
            latex_content.append(r'\vspace{12pt}')
            latex_content.append('')

        # Image (if available)
        if image_path:
            if os.path.exists(image_path):
                latex_content.append(r'\textbf{Image:}')
                latex_content.append(r'\begin{center}')
                # Get scale for this image: manual override > automatic > default
                if str(question_id) in image_scales:
                    scale = image_scales[str(question_id)]
                else:
                    # Calculate automatic scale
                    has_answer = answer is not None
                    text_height_pt = estimate_text_height(q, has_answer=has_answer)
                    scale = calculate_optimal_scale(image_path, text_height_pt, question_id)
                # Use width and height constraints to ensure image fits on page with keepaspectratio
                latex_content.append(r'\includegraphics[width=' + str(scale) + r'\textwidth,height=' + MAX_IMAGE_HEIGHT + r',width=' + MAX_IMAGE_WIDTH + r',keepaspectratio]{' +
                                   image_path.replace('\\', '/') + r'}')
                latex_content.append(r'\end{center}')
                latex_content.append(r'\vspace{12pt}')
            else:
                latex_content.append(r'\textit{[Image not found: ' +
                                   escape_latex(image_path) + r']}')
                latex_content.append(r'\vspace{12pt}')


    # End document
    latex_content.append(r'\end{document}')

    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(latex_content))

    print(f"LaTeX document created: {output_file}")


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Convert NEJM questions from JSON to LaTeX format'
    )
    parser.add_argument(
        '--input',
        default='nejm_questions.json',
        help='Input JSON file (default: nejm_questions.json)'
    )
    parser.add_argument(
        '--output',
        default='nejm_questions.tex',
        help='Output LaTeX file (default: nejm_questions.tex)'
    )
    parser.add_argument(
        '--calculate-scales',
        action='store_true',
        help='Calculate automatic scales and save to imagescale_auto.txt'
    )
    parser.add_argument(
        '--auto-scale',
        action='store_true',
        help='Use automatic scaling for images without manual scales'
    )
    args = parser.parse_args()

    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        return

    # Read questions
    print(f"Reading questions from {args.input}...")
    questions = read_questions(args.input)
    print(f"Found {len(questions)} questions")

    # If --calculate-scales, compute and save automatic scales
    if args.calculate_scales:
        print("Calculating automatic image scales...")
        auto_scales = calculate_automatic_scales(questions)

        with open('imagescale_auto.txt', 'w', encoding='utf-8') as f:
            f.write("id\tscale\n")
            for qid in sorted(auto_scales.keys()):
                f.write(f"{qid}\t{auto_scales[qid]}\n")

        print(f"Automatic scales saved to imagescale_auto.txt")
        return

    # Use automatic scaling for all questions
    print("Using automatic scaling for all questions")
    image_scales = {}  # Empty dict - all scales will be auto-calculated

    # Create LaTeX document
    print(f"Creating LaTeX document...")
    create_latex_document(questions, args.output, image_scales)
    print(f"Successfully created {args.output}")


if __name__ == '__main__':
    main()
