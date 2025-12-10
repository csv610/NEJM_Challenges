.PHONY: help install download-all download-recent download-range download-dates clean

help:
	@echo "NEJM Image Challenges - Available targets:"
	@echo ""
	@echo "  make install              Install Python dependencies (cloudscraper, beautifulsoup4)"
	@echo ""
	@echo "  Download targets:"
	@echo "    make download-all       Download all challenges from 2005-10-13 to today (appends to nejm_questions.json)"
	@echo "    make download-recent    Download challenges from 2020-01-01 to today"
	@echo "    make download-range START=YYYYMMDD END=YYYYMMDD  Download date range"
	@echo "    make download-dates DATES=YYYYMMDD,YYYYMMDD,...   Download specific dates"
	@echo ""
	@echo "  Examples:"
	@echo "    make download-range START=20230101 END=20231231"
	@echo "    make download-dates DATES=20051013,20051020,20051027"
	@echo ""
	@echo "  Other targets:"
	@echo "    make clean              Clean up __pycache__ and test output files"
	@echo "    make help               Show this help message"

install:
	pip install cloudscraper beautifulsoup4

download-all:
	python batch_download.py

download-recent:
	python batch_download.py -s 20200101

download-range:
	@if [ -z "$(START)" ] || [ -z "$(END)" ]; then \
		echo "Error: START and END dates required"; \
		echo "Usage: make download-range START=YYYYMMDD END=YYYYMMDD"; \
		exit 1; \
	fi
	python batch_download.py -s $(START) -e $(END)

download-dates:
	@if [ -z "$(DATES)" ]; then \
		echo "Error: DATES required"; \
		echo "Usage: make download-dates DATES=YYYYMMDD,YYYYMMDD,..."; \
		exit 1; \
	fi
	python batch_download.py -d $(DATES)

clean:
	rm -rf __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf test_output
	find . -type f -name "*.pyc" -delete
