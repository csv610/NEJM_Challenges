"""
Batch downloader for NEJM Image Challenges by date range or specific dates.
Default: Downloads all challenges from 20051013 to today.
Requires: pip install cloudscraper beautifulsoup4

Usage:
    python batch_download.py                                    # Download all (20051013 to today)
    python batch_download.py -s 20200101                        # From 2020 to today
    python batch_download.py -s 20051013 -e 20051027            # Specific range
    python batch_download.py -d 20051013,20051020,20051027      # Specific dates
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from nejm_downloader import NEJMDownloader


def parse_date_string(date_str: str) -> Optional[datetime]:
    """
    Parse a date string in YYYYMMDD format.

    Args:
        date_str: Date string in YYYYMMDD format

    Returns:
        datetime object or None if parsing fails
    """
    try:
        return datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        print(f"Error: Invalid date format '{date_str}'. Please use YYYYMMDD format.")
        return None


def generate_date_range(start_date: datetime, end_date: datetime) -> List[datetime]:
    """
    Generate a list of dates in weekly increments between start and end dates.

    Args:
        start_date: Start date (datetime object)
        end_date: End date (datetime object)

    Returns:
        List of datetime objects for each week
    """
    dates = []
    current_date = start_date

    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(weeks=1)

    return dates


def date_to_challenge_id(date: datetime) -> str:
    """
    Convert a datetime object to a challenge ID (YYYYMMDD format).

    Args:
        date: datetime object

    Returns:
        Challenge ID as string in YYYYMMDD format
    """
    return date.strftime("%Y%m%d")


def download_challenge(challenge_id: str, temp_dir: str) -> Optional[dict]:
    """
    Download a single challenge and return its data.
    Silently skips if not found or on error.

    Args:
        challenge_id: Challenge ID in YYYYMMDD format
        temp_dir: Temporary directory for storing images

    Returns:
        Dictionary with challenge data or None if download fails
    """
    try:
        downloader = NEJMDownloader(challenge_id, output_dir=temp_dir)
        result = downloader.download_question()

        # Check if we got valid data
        if not result.get("question") or not result.get("options"):
            return None

        # Extract the date from challenge_id for the JSON
        date_obj = datetime.strptime(challenge_id, "%Y%m%d")
        formatted_date = date_obj.strftime("%B %d,%Y")

        # Convert to JSON-compatible format
        return {
            "id": challenge_id,
            "date": formatted_date,
            "question": result.get("question"),
            "options": result.get("options", {}),
            "image": result.get("image"),
            "answer": None  # Will be filled manually or from existing data
        }
    except Exception:
        # Silently skip on any error
        return None


def load_existing_data(json_file: str) -> Tuple[dict, list]:
    """
    Load existing NEJM data and create a lookup by ID.

    Args:
        json_file: Path to existing JSON file

    Returns:
        Tuple of (lookup dictionary mapping IDs to data, list of all items)
    """
    if not os.path.exists(json_file):
        return {}, []

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        if not isinstance(data, list):
            return {}, []

        # Create lookup by ID
        lookup = {}
        for item in data:
            item_id = str(item.get("id"))
            lookup[item_id] = item

        return lookup, data
    except (json.JSONDecodeError, FileNotFoundError):
        return {}, []


def merge_challenge_data(downloaded: dict, existing_data: dict) -> dict:
    """
    Merge downloaded challenge data with existing data (for answer info).

    Args:
        downloaded: Downloaded challenge data
        existing_data: Lookup of existing challenge data

    Returns:
        Merged challenge data
    """
    challenge_id = str(downloaded.get("id"))

    if challenge_id in existing_data:
        existing = existing_data[challenge_id]
        # Keep answer from existing data if available
        if existing.get("answer"):
            downloaded["answer"] = existing.get("answer")
        # Keep image path from existing if available
        if existing.get("image"):
            downloaded["image"] = existing.get("image")

    return downloaded


def batch_download(dates: List[datetime], output_file: str = "nejm_questions.json", existing_file: str = "nejm_questions.json") -> None:
    """
    Download challenges for multiple dates and append to JSON file.

    Args:
        dates: List of datetime objects for challenges to download
        output_file: Output JSON file path (will append to existing)
        existing_file: Path to existing data file (for checking what's already downloaded)
    """
    if not dates:
        print("No dates specified for download.")
        return

    # Create temporary directory for images
    temp_dir = "."

    # Load existing data for deduplication and merging
    existing_data_lookup, existing_data_list = load_existing_data(existing_file)

    # Download all challenges
    new_challenges = []
    challenge_ids = [date_to_challenge_id(date) for date in dates]

    # Filter out already downloaded challenges
    to_download = []
    skipped = 0
    for challenge_id in challenge_ids:
        if challenge_id in existing_data_lookup:
            # Check if image exists in the data
            existing = existing_data_lookup[challenge_id]
            if existing.get("image"):  # Image is present and not None/empty
                skipped += 1
            else:
                to_download.append(challenge_id)  # Image missing, re-download
        else:
            to_download.append(challenge_id)  # Not in existing data, download

    # Process downloads silently
    for challenge_id in to_download:
        print(challenge_id, end=' ', flush=True)
        downloaded = download_challenge(challenge_id, temp_dir)

        if downloaded:
            # Merge with existing data if available
            merged = merge_challenge_data(downloaded, existing_data_lookup)
            new_challenges.append(merged)
            time.sleep(1)

    if not new_challenges:
        print("\nNo new challenges downloaded.")
        return

    # Append to JSON file instead of overwriting
    all_challenges = existing_data_list + new_challenges

    try:
        with open(output_file, 'w') as f:
            json.dump(all_challenges, f, indent=4)

        print(f"\n✓ Downloaded {len(new_challenges)}, Total: {len(all_challenges)}")
    except Exception as e:
        print(f"Error: {str(e)}")


def main():
    # Default dates
    default_start = "20051013"  # Oct 13, 2005
    today = datetime.now().strftime("%Y%m%d")

    parser = argparse.ArgumentParser(
        description="Batch download NEJM Image Challenges by date range or specific dates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all (20051013 to today, appends to nejm_questions.json)
  python batch_download.py

  # From 2020 to today
  python batch_download.py -s 20200101

  # Specific date range
  python batch_download.py -s 20051013 -e 20051027

  # Specific dates only
  python batch_download.py -d 20051013,20051020,20051027

  # Custom output file
  python batch_download.py -o my_questions.json
        """
    )

    parser.add_argument(
        '-s', '--start-date',
        type=str,
        default=default_start,
        help=f'Start date in YYYYMMDD format (default: {default_start})'
    )
    parser.add_argument(
        '-e', '--end-date',
        type=str,
        default=today,
        help=f'End date in YYYYMMDD format (default: {today})'
    )
    parser.add_argument(
        '-d', '--dates',
        type=str,
        help='Comma-separated dates in YYYYMMDD format (e.g., 20051013,20051020,20051027)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='nejm_questions.json',
        help='Output JSON file path (default: nejm_questions.json)'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.dates and (args.start_date != default_start or args.end_date != today):
        print("Error: Cannot use -d with -s or -e. Choose either date range or specific dates.")
        return

    # Generate list of dates
    dates = []

    if args.start_date and args.end_date:
        start = parse_date_string(args.start_date)
        end = parse_date_string(args.end_date)

        if not start or not end:
            return

        if start > end:
            print("Error: Start date cannot be after end date")
            return

        dates = generate_date_range(start, end)

    elif args.dates:
        date_strings = [d.strip() for d in args.dates.split(',')]

        for date_str in date_strings:
            date_obj = parse_date_string(date_str)
            if date_obj:
                dates.append(date_obj)

        if not dates:
            return

    # Start download
    batch_download(dates, output_file=args.output, existing_file=args.output)


if __name__ == "__main__":
    main()
