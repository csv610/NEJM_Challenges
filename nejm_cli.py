import os
import json
import re
import base64
import random
import argparse
from io import BytesIO
from datetime import datetime
from openai import OpenAI
from PIL import Image
from tqdm import tqdm
from tabulate import tabulate

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")

try:
    client = OpenAI(api_key=api_key)
except Exception as e:
    raise ConnectionError(f"Failed to initialize OpenAI client: {str(e)}")

# Load data
def load_data(json_file):
    try:
        with open(json_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: The file '{json_file}' was not found.")
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from the file '{json_file}'. The file may be corrupted.")
    except PermissionError:
        print(f"Error: Permission denied when trying to read the file '{json_file}'.")
    except Exception as e:
        print(f"An unexpected error occurred while loading data: {str(e)}")
    return []

def image_to_base64(image_path):
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if the image is in RGBA or Grayscale (L) mode
            if img.mode in ('RGBA'):
                img = img.convert('RGB')
            # Save the image to a bytes buffer
            buffer = BytesIO()
            img.save(buffer, format="JPEG")
            # Encode the bytes to base64
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Error converting image to base64: {str(e)}")
        return None

def format_question_and_options(question, options):
    # Format the question and options
    options_str = "\n".join([f"{chr(65 + i)}. {option}" for i, option in enumerate(options)])
    result = f"Question: {question}\n\nOptions:\n{options_str}"
    result += "Give answer as a single character from (A,B,C,D,E)" 
    return result

def generate_prompt(question, options):
    return f"""You are provided with clinical information that may include visual elements. 
Based on the patterns and clues present, answer the following question:

Question: {question}

Options:
{chr(10).join([f"{chr(65 + i)}. {opt}" for i, opt in enumerate(options)])}

Instructions:
1. Select the most appropriate answer option (A, B, C, D, or E).
2. Identify the medical specialty most relevant to this clinical scenario.

Format your response as follows:
Answer: [Single letter A-E]
Specialty: [Relevant medical specialty]

Focus on clinical reasoning based on observable signs or likely conditions."""

def query_gpt(question, options, image_path, model):
    prompt = generate_prompt(question, options)
    
    image_base64 = image_to_base64(image_path)
    if not image_base64:
        return None

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
#                {"role": "system", "content": "You are a medical expert specializing in answering multi-model questions.You have to respect PHI guidelines."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}", "detail":"low"}}
                ]}
            ],

            top_p = 0.9, 
            frequency_penalty=0.0,
            presence_penalty=0.2,
            temperature=0.3,
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"An error occurred while querying GPT: {str(e)}")
        return None



# Extract answer from response
def extract_answers(response):
    lines = response.split('\n')
    vlm_answer = "N/A"
    for line in lines:
        if line.startswith("Answer:"):
            match = re.match(r"Answer: ([A-E])", line)
            if match:
                vlm_answer = match.group(1)
            break
    return vlm_answer

# Write results to a file using tabulate
def write_results_to_file(outfile, results):
    headers = ["ID", "Date", "Correct Answer", "LLM Answer", "Score"]
    ca = "center"
    align=(ca, ca, ca, ca, ca)
    table = tabulate(results, headers=headers, tablefmt="grid", colalign=align)
    outfile.write(table + "\n")

# Process a single question
def process_question(question, model):
    question_id = question.get('ID', 'N/A')
    question_text = question.get('Question', None)
    options = question.get('Options', [])
    image_path = question.get('Image', None)
    correct_answer = question.get('Answer', 'N/A')
    date = question.get('Date', 'N/A')

    if question_text and options and image_path and os.path.exists(image_path):
        print( "Asking ..... " )
        response = query_gpt(question_text, options, image_path, model)
        if response:
            print( response )
            vlm_answer = extract_answers(response)
            score = 1 if vlm_answer == correct_answer else 0
            return [question_id, date, correct_answer, vlm_answer, score]
        else:
            return [question_id, date, correct_answer, "N/A", 0]
    else:
        print("Please ensure the question, options, and image are available.")
        return [question_id, date, correct_answer, "N/A", 0]

# Main CLI app
def main():
    parser = argparse.ArgumentParser(description="Medical Image Analysis using OpenAI GPT")
    parser.add_argument('-m', '--model', type=str, default='gpt-4o', help='Model to use for GPT (default: gpt-4o)')
    parser.add_argument('-n', '--nsamples', type=int, help='Number of samples to evaluate (default: all questions)')
    parser.add_argument('-r', '--random', action='store_true', help='Use random sampling of questions (only if specified)')
    parser.add_argument('-s', '--start_id', type=int, default=0, help='Starting question ID if using sequential selection')
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        return

    json_file = "nejm.json"
    model = args.model  # Set model from arguments
    results_file = f"{model}_results.txt"

    # Ensure output file can be created or written to
    try:
        with open(results_file, 'w') as f:
            pass
    except Exception as e:
        print(f"Error: Cannot write to results file '{results_file}': {str(e)}")
        return

    questions = load_data(json_file)
    total_questions = len(questions)
    nsamples = total_questions if args.nsamples is None else min(args.nsamples, total_questions)  # Use all questions if nsamples not provided

    if args.random:
        sampled_questions = random.sample(questions, nsamples)
    else:
        end_id = min(args.start_id + nsamples , total_questions)  # Ensure end_id does not exceed total questions
        sampled_questions = questions[args.start_id-1:end_id-1]

    final_score = 0
    results = []

    for question in tqdm(sampled_questions, desc="Processing questions"):
        result = process_question(question, model)
        final_score += result[-1]  # Add score to final score
        results.append(result)

    with open(results_file, 'w') as outfile:
        write_results_to_file(outfile, results)

    print(f"\nFinal Score: {final_score} out of {nsamples}")

if __name__ == "__main__":
    main()

