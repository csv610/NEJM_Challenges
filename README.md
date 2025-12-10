# NEJM Image Challenges

A Python-based tool for downloading and managing New England Journal of Medicine (NEJM) Image Challenges. This project provides both CLI and batch download capabilities to collect medical imaging questions and answers from NEJM's weekly image challenges.

## Features

- **Batch Download**: Download multiple challenges by date range or specific dates
- **Single Challenge Download**: Retrieve individual challenges with full metadata
- **Data Persistence**: Store challenges in structured JSON format with lowercase keys
- **Deduplication**: Automatically detect and skip already-downloaded challenges
- **Data Merging**: Preserve answers and image paths when updating existing data
- **Flexible Options Format**: Challenge options stored as dictionary (A, B, C, D keys)
- **Web Scraping**: Uses CloudScraper to handle website protections

## Requirements

- Python 3.6+
- `cloudscraper` - For web scraping with protection bypass
- `beautifulsoup4` - For HTML parsing

## Installation

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd NEJM_Challenges

# Install dependencies
make install
# or
pip install cloudscraper beautifulsoup4
```

## Usage

### Using Make Commands

The Makefile provides convenient targets for common operations:

```bash
# Install dependencies
make install

# Download all challenges from 2005-10-13 to today
make download-all

# Download challenges from 2020-01-01 to today
make download-recent

# Download specific date range
make download-range START=20230101 END=20231231

# Download specific dates
make download-dates DATES=20051013,20051020,20051027

# Clean up cache and temporary files
make clean

# Display help
make help
```

### Direct Python Usage

#### Batch Download by Date Range

```bash
# Download all challenges
python batch_download.py

# Download from specific start date to today
python batch_download.py -s 20200101

# Download specific date range
python batch_download.py -s 20200101 -e 20201231

# Download specific dates
python batch_download.py -d 20051013,20051020,20051027

# Download to custom output file
python batch_download.py -o my_challenges.json
```

#### CLI Download

```bash
# Download single challenge by date
python nejm_cli.py 20051013

# With custom output directory
python nejm_cli.py 20051013 --output ./challenges
```

## Output Format

Challenges are stored in JSON format with the following structure:

```json
{
  "id": "20051013",
  "date": "October 13, 2005",
  "question": "A 62-year-old man presents with...",
  "options": {
    "A": "First option text",
    "B": "Second option text",
    "C": "Third option text",
    "D": "Fourth option text"
  },
  "image": "path/to/image.jpg",
  "answer": "B"
}
```

**Field Descriptions:**
- `id`: Unique challenge identifier in YYYYMMDD format
- `date`: Human-readable date (Month Day, Year)
- `question`: Full question text with clinical scenario
- `options`: Multiple choice options (A, B, C, D keys with answer texts)
- `image`: Path or URL to the associated medical image
- `answer`: Correct answer letter (A, B, C, or D), initially null

## Project Structure

```
NEJM_Challenges/
├── batch_download.py          # Batch downloader for multiple challenges
├── nejm_downloader.py         # Core downloader module
├── nejm_cli.py                # CLI tool for single challenge download
├── nejm_batch_cli.py          # Alternative batch CLI interface
├── sl_nejm.py                 # Search/lookup utilities
├── sl_nejm_weblink.py         # Web link extraction utilities
├── nejm_questions.json        # Downloaded challenges database
├── Makefile                   # Build and task automation
├── .gitignore                 # Git ignore patterns
├── README.md                  # This file
└── test_output/               # Directory for test runs (ignored by git)
```

## API Reference

### NEJMDownloader Class

The core `NEJMDownloader` class handles single challenge downloads:

```python
from nejm_downloader import NEJMDownloader

# Initialize downloader
downloader = NEJMDownloader(challenge_id="20051013", output_dir=".")

# Download and parse challenge
result = downloader.download_question()

# Access challenge data
question = result.get("question")
options = result.get("options")  # Returns dict with A, B, C, D keys
image = result.get("image")
```

### Batch Download Functions

Key functions in `batch_download.py`:

- `parse_date_string(date_str)` - Parse YYYYMMDD format dates
- `generate_date_range(start_date, end_date)` - Generate weekly date increments
- `download_challenge(challenge_id, temp_dir)` - Download single challenge
- `load_existing_data(json_file)` - Load and index existing challenges
- `merge_challenge_data(downloaded, existing_data)` - Merge new and existing data
- `batch_download(dates, output_file, existing_file)` - Main batch download logic

## Date Format

All dates must be in **YYYYMMDD format**:
- `20051013` = October 13, 2005
- `20201231` = December 31, 2020
- `20250101` = January 1, 2025

NEJM Image Challenges started on October 13, 2005.

## Troubleshooting

### Connection Issues

If you encounter connection errors, the script automatically retries. Ensure you have:
- Active internet connection
- Latest version of `cloudscraper` (`pip install --upgrade cloudscraper`)

### Invalid Date Format

Dates must be in YYYYMMDD format. Invalid formats will produce an error:
```
Error: Invalid date format '2020-01-01'. Please use YYYYMMDD format.
```

### File Permissions

Ensure write permissions in the output directory:
```bash
# Fix permissions if needed
chmod 755 .
```

### Missing Dependencies

Install all required packages:
```bash
pip install -r requirements.txt
# or
make install
```

## JSON File Management

### Updating Existing Database

The batch downloader automatically:
1. Checks for existing challenges by ID
2. Skips already-downloaded challenges
3. Preserves answer data during updates
4. Appends new challenges to the file

### Manual JSON Editing

To manually add or modify challenge data:

```json
{
  "id": "20051013",
  "date": "October 13, 2005",
  "question": "...",
  "options": {
    "A": "...",
    "B": "...",
    "C": "...",
    "D": "..."
  },
  "image": "path/to/image.jpg",
  "answer": "B"
}
```

## Performance

- **Batch Download**: ~1-2 seconds per challenge (network dependent)
- **Date Range**: Weekly increments (10 challenges per year)
- **Storage**: ~50-100 KB per challenge with images

## Contributing

Contributions are welcome! Areas for improvement:
- Additional export formats (CSV, Excel)
- Enhanced error handling and logging
- Performance optimizations
- Test coverage

## License

This project is for educational purposes. Please ensure compliance with NEJM's terms of service when downloading content.

## Disclaimer

This tool is designed for educational and research purposes. Users are responsible for ensuring compliance with the New England Journal of Medicine's terms of service and applicable copyright laws.

## Support

For issues, questions, or suggestions:
1. Check the troubleshooting section above
2. Review existing code comments
3. Verify Python version compatibility (3.6+)

---

**Last Updated**: December 2025
**Status**: Active Development
