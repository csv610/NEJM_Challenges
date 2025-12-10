#!/usr/bin/env python3
"""
Enhanced NEJM CLI for downloading and managing challenges.
Supports individual challenge downloads, date range downloads, and batch processing.

Usage:
    # Download all challenges (20051013 to today)
    python nejm_batch_cli.py download

    # Download from specific year to today
    python nejm_batch_cli.py download -s 20200101

    # Download date range
    python nejm_batch_cli.py download -s 20051013 -e 20051027

    # Download specific dates only
    python nejm_batch_cli.py download -d 20051013,20051020,20051027

    # Save to custom file
    python nejm_batch_cli.py download -o all_questions.json

    # List available date range and examples
    python nejm_batch_cli.py info
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional

from batch_download import (
    batch_download,
    date_to_challenge_id,
    generate_date_range,
    parse_date_string,
    load_existing_data
)


def cmd_download(args):
    """Handle download command."""
    dates = []

    # Single date
    if args.single_date:
        date_obj = parse_date_string(args.single_date)
        if not date_obj:
            return 1
        dates = [date_obj]

    # Specific dates
    elif args.dates:
        date_strings = [d.strip() for d in args.dates.split(',')]

        for date_str in date_strings:
            date_obj = parse_date_string(date_str)
            if date_obj:
                dates.append(date_obj)

        if not dates:
            return 1

    # Date range (default or specified)
    else:
        start = parse_date_string(args.start_date)
        end = parse_date_string(args.end_date)

        if not start or not end:
            return 1

        if start > end:
            print("Error: Start date cannot be after end date")
            return 1

        dates = generate_date_range(start, end)

    # Start download (will append new challenges to existing file)
    batch_download(dates, output_file=args.output, existing_file=args.output)

    return 0


def cmd_info(args):
    """Display information about available challenges."""
    print("\n" + "="*70)
    print("NEJM Image Challenge Database Information")
    print("="*70)

    start_date = datetime(2005, 10, 13)
    end_date = datetime(2025, 10, 9)

    print(f"\nDatabase Coverage:")
    print(f"  Start Date: {start_date.strftime('%B %d, %Y')} ({start_date.strftime('%Y%m%d')})")
    print(f"  End Date:   {end_date.strftime('%B %d, %Y')} ({end_date.strftime('%Y%m%d')})")

    # Calculate total weeks
    total_weeks = (end_date - start_date).days // 7 + 1

    print(f"\nTotal Challenges: {total_weeks} (one per week)")

    print(f"\nDate Format:")
    print(f"  Dates are specified in YYYYMMDD format")
    print(f"  Example: {start_date.strftime('%Y%m%d')} = {start_date.strftime('%B %d, %Y')}")

    print(f"\nExample Commands:")
    print(f"  All challenges (default: {start_date.strftime('%Y%m%d')} to today):")
    print(f"    python nejm_batch_cli.py download")
    print(f"\n  Single challenge:")
    print(f"    python nejm_batch_cli.py download -sd {start_date.strftime('%Y%m%d')}")
    print(f"\n  Date range (first month):")
    first_month_end = start_date + timedelta(weeks=4)
    print(f"    python nejm_batch_cli.py download -s {start_date.strftime('%Y%m%d')} -e {first_month_end.strftime('%Y%m%d')}")
    print(f"\n  From specific year to today:")
    print(f"    python nejm_batch_cli.py download -s 20240101")
    print(f"\n  Specific dates:")
    sample_dates = [start_date, start_date + timedelta(weeks=1), start_date + timedelta(weeks=2)]
    dates_str = ','.join([d.strftime('%Y%m%d') for d in sample_dates])
    print(f"    python nejm_batch_cli.py download -d {dates_str}")

    print(f"\nOutput Files:")
    print(f"  Default: nejm_questions.json (appends new questions)")
    print(f"  Custom: -o my_questions.json")

    print("\n" + "="*70 + "\n")

    return 0


def cmd_status(args):
    """Show download status and statistics."""
    json_file = args.file or "nejm.json"

    if not os.path.exists(json_file):
        print(f"File not found: {json_file}")
        return 1

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        print(f"\n{'='*70}")
        print(f"File: {json_file}")
        print(f"{'='*70}")
        print(f"Total Questions: {len(data)}")

        if data:
            # Extract dates from first and last entry
            first_date_str = data[0].get('Date', 'N/A')
            last_date_str = data[-1].get('Date', 'N/A')

            print(f"Date Range: {first_date_str} to {last_date_str}")
            print(f"First ID: {data[0].get('ID', 'N/A')}")
            print(f"Last ID: {data[-1].get('ID', 'N/A')}")

            # Count questions with answers
            answered = sum(1 for q in data if q.get('Answer'))
            print(f"With Answers: {answered}/{len(data)}")

            # Count questions with images
            with_images = sum(1 for q in data if q.get('Image'))
            print(f"With Images: {with_images}/{len(data)}")

        print(f"{'='*70}\n")
        return 0

    except json.JSONDecodeError:
        print(f"Error: Invalid JSON file: {json_file}")
        return 1
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1


def main():
    # Default dates
    default_start = "20051013"  # Oct 13, 2005
    today = datetime.now().strftime("%Y%m%d")

    parser = argparse.ArgumentParser(
        description="NEJM Image Challenge Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Download command
    download_parser = subparsers.add_parser('download', help='Download challenges')
    date_group = download_parser.add_mutually_exclusive_group()
    date_group.add_argument('-sd', '--single-date', type=str, help='Single date in YYYYMMDD format')
    date_group.add_argument('-d', '--dates', type=str, help='Comma-separated dates in YYYYMMDD format')

    download_parser.add_argument('-s', '--start-date', type=str, default=default_start, help=f'Start date in YYYYMMDD format (default: {default_start})')
    download_parser.add_argument('-e', '--end-date', type=str, default=today, help=f'End date in YYYYMMDD format (default: {today})')
    download_parser.add_argument('-o', '--output', type=str, default='nejm_questions.json', help='Output JSON file (default: nejm_questions.json)')
    download_parser.set_defaults(func=cmd_download)

    # Info command
    info_parser = subparsers.add_parser('info', help='Show database information')
    info_parser.set_defaults(func=cmd_info)

    # Status command
    status_parser = subparsers.add_parser('status', help='Show download status')
    status_parser.add_argument('-f', '--file', type=str, default='nejm_questions.json', help='JSON file to check (default: nejm_questions.json)')
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()

    # If no command, show help
    if not args.command:
        parser.print_help()
        return 0

    # Execute command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
