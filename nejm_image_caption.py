import os
import json
import base64
import time
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image
from io import BytesIO
from tqdm import tqdm
from pydantic import BaseModel, Field
import litellm

# Configure litellm
litellm.set_verbose = False
#litellm._turn_on_debug()


class MedicalImageCaption(BaseModel):
    """Pydantic model for medical image captions with structured fields."""
    classification: str = Field(..., description="Medical classification or category of the image")
    abnormality: str = Field(..., description="Identified abnormalities or findings (or 'Normal' if none)")
    caption: str = Field(..., description="Detailed caption describing the image contents and findings")


def image_to_base64(image_path: str) -> Optional[str]:
    """
    Convert an image file to base64 encoding.

    Args:
        image_path: Path to the image file

    Returns:
        Base64 encoded string or None if conversion fails
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if the image is in RGBA or other modes
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')

            # Save the image to a bytes buffer
            buffer = BytesIO()
            img.save(buffer, format="JPEG")
            # Encode the bytes to base64
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Error converting image {image_path} to base64: {str(e)}")
        return None


def generate_caption_with_model(image_base64: str, model: str, max_retries: int = 2) -> Optional[MedicalImageCaption]:
    """
    Generate a structured caption for an image using a specified LLM model via litellm.

    Args:
        image_base64: Base64 encoded image string
        model: Model identifier (e.g., 'gpt-4-vision', 'claude-3-vision', etc.)
        max_retries: Number of retries on failure

    Returns:
        MedicalImageCaption object or None if generation fails
    """
    prompt = """Analyze this medical image and provide structured information.

    Provide the following fields:
    - classification: The medical specialty or category (e.g., 'Radiology', 'Pathology', 'Dermatology')
    - abnormality: Identified abnormalities or key findings (or 'Normal' if no abnormalities detected)
    - caption: A detailed description of the image contents, anatomical structures, and clinical findings

    Focus on visible anatomical structures, clinical findings, and any notable features."""

    for attempt in range(max_retries):
        try:
            response = litellm.completion(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                response_format=MedicalImageCaption,
                temperature=0.2
            )

            # Parse the JSON response using Pydantic's model_validate_json
            return MedicalImageCaption.model_validate_json(response.choices[0].message.content)

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  Attempt {attempt + 1} failed for model {model}: {str(e)}. Retrying...")
            else:
                print(f"  Failed to generate caption with {model}: {str(e)}")

    return None


def get_image_id(image_path: str) -> str:
    """
    Extract image ID from file name.

    Args:
        image_path: Path to the image file

    Returns:
        Image ID (filename without extension)
    """
    return Path(image_path).stem


def read_images_from_folder(images_folder: str = "images") -> List[str]:
    """
    Read all image files from the specified folder.

    Args:
        images_folder: Path to the folder containing images

    Returns:
        List of full paths to image files
    """
    supported_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    image_paths = []

    images_path = Path(images_folder)
    if not images_path.exists():
        print(f"Error: Images folder '{images_folder}' does not exist.")
        return image_paths

    for image_file in sorted(images_path.iterdir()):
        if image_file.suffix.lower() in supported_formats:
            image_paths.append(str(image_file))

    return image_paths


def load_questions_mapping(questions_file: str = "nejm_questions.json") -> Dict[str, str]:
    """
    Load the questions file and create a mapping from image path to id.

    Args:
        questions_file: Path to the questions JSON file

    Returns:
        Dictionary mapping image paths to their IDs
    """
    image_to_id = {}
    try:
        with open(questions_file, 'r') as f:
            questions = json.load(f)
            for question in questions:
                image_path = question.get("image")
                question_id = question.get("id")
                if image_path and question_id:
                    image_to_id[image_path] = question_id
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load questions from {questions_file}: {str(e)}")
    return image_to_id


def load_existing_captions(output_file: str) -> Dict:
    """
    Load existing captions from JSON file if it exists.

    Args:
        output_file: Path to the JSON file

    Returns:
        Dictionary with existing captions or empty dict if file doesn't exist
    """
    if not os.path.exists(output_file):
        return {}

    try:
        with open(output_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load existing captions from {output_file}: {str(e)}")
        return {}


def caption_exists_for_image(captions_data: Dict, question_id: str) -> bool:
    """
    Check if a response already exists for a specific image.

    Args:
        captions_data: The captions data dictionary
        question_id: The question ID to check

    Returns:
        True if response exists, False otherwise
    """
    for image in captions_data.get("images", []):
        if image.get("id") == question_id and image.get("response"):
            return True
    return False


def get_existing_caption(captions_data: Dict, question_id: str) -> Optional[Dict]:
    """
    Retrieve an existing response for a specific image.

    Args:
        captions_data: The captions data dictionary
        question_id: The question ID to retrieve

    Returns:
        The response dict if it exists, None otherwise
    """
    for image in captions_data.get("images", []):
        if image.get("id") == question_id:
            response = image.get("response")
            if response:
                return response
    return None


def generate_captions_for_images(
    images_folder: str = "images",
    model: str = "gemini-3-flash",
    output_file: Optional[str] = None,
    image_id: Optional[str] = None,
    image_id_range: Optional[tuple] = None
) -> Dict:
    """
    Generate captions for images using a single model.
    Skips regeneration if captions already exist.

    Must provide one of: images_folder, image_id, or image_id_range

    Args:
        images_folder: Path to the folder containing images (default: "images")
        model: Model identifier (e.g., 'gemini-3-flash', 'gpt-4-vision', 'gpt-4o-mini')
        output_file: Path to output JSON file. If None, defaults to nejm_image_captions_{model_name}.json
        image_id: Process a specific image file path or ID (e.g., 'nejm_20051013' or '/path/to/nejm_20051013.jpg')
        image_id_range: Process a range of images by ID (start_id, end_id) inclusive

    Returns:
        Dictionary with image captions
    """
    # Generate output filename based on model if not provided
    if output_file is None:
        # Extract model name (handle formats like "gpt-4-vision" or "gemini-3-flash")
        model_name = model.replace("/", "-").replace(":", "-")
        output_file = f"nejm_image_captions_{model_name}.json"

    # Handle image_id as a file path
    if image_id and os.path.exists(image_id):
        image_paths = [image_id]
    else:
        # Read all images from folder
        image_paths = read_images_from_folder(images_folder)

        if not image_paths:
            print(f"No images found in {images_folder}")
            return {}

        # Filter images by specific ID or range
        if image_id:
            # Filter for specific image ID
            image_paths = [path for path in image_paths if get_image_id(path) == image_id]
            if not image_paths:
                print(f"No image found with ID: {image_id}")
                return {}
        elif image_id_range:
            # Filter for range of image IDs
            start_id, end_id = image_id_range
            filtered_paths = []
            for path in image_paths:
                current_id = get_image_id(path)
                if start_id <= current_id <= end_id:
                    filtered_paths.append(path)
            image_paths = filtered_paths
            if not image_paths:
                print(f"No images found in range: {start_id} to {end_id}")
                return {}

    # Load questions mapping to get question IDs for images
    image_to_id_mapping = load_questions_mapping()

    # Load existing captions
    captions_data = load_existing_captions(output_file)
    if not captions_data:
        captions_data = {
            "metadata": {
                "total_images": len(image_paths),
                "model": model,
                "images_folder": images_folder
            },
            "images": []
        }
    else:
        # Update metadata
        captions_data["metadata"]["total_images"] = len(image_paths)
        captions_data["metadata"]["model"] = model
        captions_data["metadata"]["images_folder"] = images_folder

    print(f"Found {len(image_paths)} images. Processing with model: {model}")

    # Track which images need new captions
    images_to_process = []

    # Process each image
    for image_path in image_paths:
        # Get the question ID from the mapping
        question_id = image_to_id_mapping.get(image_path)

        if not question_id:
            print(f"Warning: No question ID found for image {image_path}")
            continue

        # Check if caption already exists
        if not caption_exists_for_image(captions_data, question_id):
            images_to_process.append((question_id, image_path))

    if not images_to_process:
        print(f"All images already have captions. No regeneration needed.")
        return captions_data

    print(f"Processing {len(images_to_process)} images with missing captions...")

    for question_id, image_path in tqdm(images_to_process, desc="Processing images"):
        image_base64 = image_to_base64(image_path)

        if not image_base64:
            print(f"Skipping {question_id} - could not convert to base64")
            continue

        # Generate caption
        caption = generate_caption_with_model(image_base64, model)

        # Only add to captions data if successful
        if caption:
            image_entry = {
                "id": question_id,
                "image": image_path,
                "response": caption.model_dump()
            }
            captions_data["images"].append(image_entry)
            # Save to JSON immediately after each successful caption
            try:
                with open(output_file, 'w') as f:
                    json.dump(captions_data, f, indent=2, default=str)
            except Exception as e:
                print(f"Error saving captions to JSON: {str(e)}")
            # Sleep for 1 second after successful caption generation
            time.sleep(1)

    return captions_data


def load_captions_from_json(json_file: str) -> Dict:
    """
    Load previously generated captions from JSON file.

    Args:
        json_file: Path to the JSON file

    Returns:
        Dictionary with captions data
    """
    try:
        with open(json_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{json_file}' not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{json_file}'")
        return {}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate captions for NEJM images using litellm",
        epilog="Usage examples:\n"
               "  python nejm_image_caption.py --folder images --model gemini-3-flash\n"
               "  python nejm_image_caption.py --image-id nejm_20051013 --model gpt-4-vision\n"
               "  python nejm_image_caption.py --id-range nejm_20051001 nejm_20051231 --model gpt-4o-mini",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '-d', '--folder',
        type=str,
        default='images',
        help='Path to images folder (default: images)'
    )
    parser.add_argument(
        '-m', '--model',
        type=str,
        default='gemini-3-flash',
        help='LLM model to use for caption generation (default: gemini-3-flash)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output JSON file path (default: nejm_image_captions_{model_name}.json)'
    )
    parser.add_argument(
        '-i', '--image-id',
        type=str,
        default=None,
        help='Process a specific image ID (e.g., nejm_20051013)'
    )
    parser.add_argument(
        '-r', '--id-range',
        type=str,
        nargs=2,
        default=None,
        metavar=('START_ID', 'END_ID'),
        help='Process a range of images by ID (e.g., nejm_20051001 nejm_20051231)'
    )

    args = parser.parse_args()

    # Parse image ID range if provided
    image_id_range = None
    if args.id_range:
        image_id_range = (args.id_range[0], args.id_range[1])

    # Generate captions
    result = generate_captions_for_images(
        images_folder=args.folder,
        model=args.model,
        output_file=args.output,
        image_id=args.image_id,
        image_id_range=image_id_range
    )

    if result:
        print(f"\nSuccessfully processed images. Total in database: {len(result.get('images', []))}")
