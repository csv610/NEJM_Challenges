import streamlit as st
import json
import os
import re
from datetime import datetime
import base64
from openai import OpenAI
from PIL import Image

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    raise ValueError("Missing OpenAI API key")

client = OpenAI(api_key=api_key)

# Set page config
st.set_page_config(layout="wide", page_title="NEJM Image Challenge")

# Load data
@st.cache_data
def load_data(json_file):
    try:
        with open(json_file, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        st.error(f"Error loading data: {str(e)}")
        return []

# Parse question date
def parse_question_date(question_date):
    try:
        match = re.search(r"(\w+)\s+(\d{1,2}),\s*(\d{4})", question_date)
        if match:
            return datetime.strptime(f"{match.group(1)} {match.group(2)}, {match.group(3)}", "%B %d, %Y")
    except ValueError:
        pass
    return None

# Convert image to base64
def image_to_base64(image_path):
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if the image is in RGBA mode
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            # Save the image to a bytes buffer
            from io import BytesIO
            buffer = BytesIO()
            img.save(buffer, format="JPEG")
            # Encode the bytes to base64
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        st.error(f"Error converting image to base64: {str(e)}")
        return None

# Query GPT
def query_gpt(question, options, image_path, model):
#    prompt = generate_prompt(question, options)
    prompt  = question + "Options: " + options
    print(prompt)
    image_base64 = image_to_base64(image_path)
    if not image_base64:
        return None

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a medical expert specializing in image analysis and diagnosis."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]}
            ],
            temperature = 0.3,
            top_p = 0.9,
            frequency_penalty = 0.0,
            presence_penalty = 0.2,
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"An error occurred while querying GPT: {str(e)}")
        return None

# Generate GPT prompt
def generate_prompt(question, options):
    return f"""Analyze the medical image and answer the following question:

Question: {question}

Options:
{chr(10).join([f"{chr(65 + i)}. {opt}" for i, opt in enumerate(options)])}

Instructions:
1. Examine the image carefully.
2. Select the best answer option (A, B, C, D, or E).
3. Identify the medical specialty most relevant to this question.
#4. Provide a detailed explanation for your choice. 
#including:
#   - Why the chosen option is correct
#   - Why each of the other options is incorrect
#   - Any relevant observations from the image

Format your response as follows:
Answer: [Single letter A-E]
Specialty: [Relevant medical specialty]
#Explanation:
#[Your detailed explanation]
#Note: Be concise but thorough in your explanation. If you're unsure about any aspect, state your level of confidence and explain your reasoning."""

# Display GPT response
def display_gpt_response(response):
    if not response:
        st.warning("No response received from GPT. Please try again.")
        return

    lines = response.split('\n')
    answer = specialty = None
    explanation_lines = []
    
    for line in lines:
        if line.startswith("Answer:"):
            answer = line.split(":")[1].strip()
        elif line.startswith("Specialty:"):
            specialty = line.split(":")[1].strip()
        elif line.startswith("Explanation:"):
            explanation_lines = lines[lines.index(line)+1:]
            break
    
    if answer:
        st.write(f"**GPT Answer:** {answer}")
    else:
        st.warning("Answer not available in the response.")
        st.write(response)
        return

    if specialty:
        st.write(f"**Specialty:** {specialty}")

    if explanation_lines:
        st.write("**Explanation:**")
        for line in explanation_lines:
            st.write(f"- {line.strip()}")

# Display question
def display_question(question, full_image=False, image_width=800):
    st.write(f"**Date:** {question.get('Date', 'N/A')}")
    st.write(f"**Question:** {question.get('Question', 'N/A')}")
    st.write("**Options:**")
    for i, option in enumerate(question.get('Options', []), start=1):
        st.write(f"({chr(64 + i)}) {option}")
    st.write(f"**Answer:** {question.get('Answer', 'N/A')}")
    
    image_path = question.get('Image', None)
    if image_path and os.path.exists(image_path):
        try:
            st.image(image_path, caption=f"Image: {os.path.basename(image_path)}", 
                     use_column_width=full_image, width=None if full_image else image_width)
        except Exception as e:
            st.error(f"Error displaying image: {str(e)}")
    else:
        st.write("**Image:** No image available")

# Sidebar controls
def sidebar_controls(total_questions):
    st.sidebar.title("NEJM Image Challenge")
    
    # Initialize question_index in session state if not already
    if 'question_index' not in st.session_state:
        st.session_state.question_index = 0

    # Buttons to navigate questions
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Previous") and st.session_state.question_index > 0:
            st.session_state.question_index -= 1
    with col2:
        if st.button("Next") and st.session_state.question_index < total_questions - 1:
            st.session_state.question_index += 1

    # Slider to select questions
    st.session_state.question_index = st.sidebar.slider("Select a question:", 0, total_questions - 1, st.session_state.question_index)

    full_image = st.sidebar.checkbox("Use Full Image Width", value=False)
    image_width = st.sidebar.number_input("Set Image Width", min_value=100, max_value=2000, value=800, step=50)
    model = st.sidebar.selectbox("Select Model:", ["gpt-4o-mini", "gpt-4o"], index=0)
    
    return st.session_state.question_index, full_image, image_width, model

# Main Streamlit app
def main():
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        return

    json_file = "nejm_questions.json"
    questions = load_data(json_file)
    total_questions = len(questions)

    question_index, full_image, image_width, model = sidebar_controls(total_questions)
    
    current_question = questions[question_index]
    display_question(current_question, full_image, image_width)
    
    st.sidebar.write(f"Question {question_index + 1} of {total_questions}")
    
    if st.sidebar.button("Ask VLM"):
        question_text = current_question.get('Question', None)
        options = current_question.get('Options', [])
        image_path = current_question.get('Image', None)
        
        if question_text and options and image_path and os.path.exists(image_path):
            with st.spinner("Querying GPT Vision..."):
                response = query_gpt(question_text, options, image_path, model)
            st.success("GPT Vision's Response:")
            display_gpt_response(response)
        else:
            st.warning("Please ensure the question, options, and image are available.")

if __name__ == "__main__":
    main()

