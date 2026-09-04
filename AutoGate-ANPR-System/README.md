# University Vehicle Management System

An automated system for detecting and tracking vehicle entry/exit on university campus using number plate recognition.

## Features

- Real-time number plate detection using camera
- Automatic entry/exit logging with timestamps
- Attractive web dashboard with statistics
- Search functionality for vehicles
- Image capture for entry and exit
- SQLite database for data storage

## Requirements

- Python 3.7+
- OpenCV
- Tesseract OCR
- Flask
- Webcam or IP camera

## Installation

1. Install Python dependencies:
   ```bash
   pip install Flask opencv-python pytesseract Pillow
   ```

2. Install Tesseract OCR:
   - Download from: https://github.com/UB-Mannheim/tesseract/wiki
   - Install to default location (C:\Program Files\Tesseract-OCR\)

3. Ensure camera is connected and accessible.

## Usage

1. Start the web server:
   ```bash
   cd backend
   python app.py
   ```
   Server will run on http://localhost:5000

2. In a separate terminal, start the camera detection:
   ```bash
   cd backend
   python camera/single_cam.py
   ```

3. Open browser to http://localhost:5000 to view the dashboard.

## Project Structure

```
entery/
├── backend/
│   ├── app.py                 # Flask web application
│   ├── camera/
│   │   └── single_cam.py      # Camera detection script
│   ├── database/
│   │   └── db.py              # Database operations
│   ├── detector/
│   │   └── plate_detector.py  # Number plate detection
│   ├── utils/
│   │   └── helpers.py         # Utility functions
│   └── static/
│       └── images/            # Captured images
├── frontend/
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css      # Stylesheet
│   │   ├── js/
│   │   │   ├── dashboard.js   # Dashboard JavaScript
│   │   │   └── search.js      # Search JavaScript
│   │   └── images/            # Served images
│   └── templates/
│       ├── dashboard.html     # Main dashboard
│       └── search.html        # Search page
└── requirements.txt           # Python dependencies
```

## How It Works

1. Camera captures video frames
2. OpenCV processes frames to detect potential number plates
3. Tesseract OCR extracts text from detected regions
4. System validates and cleans the plate number
5. Checks database for existing entry
6. Logs entry or exit with timestamp and image
7. Web dashboard displays real-time statistics and logs

## API Endpoints

- `GET /` - Dashboard
- `GET /search` - Search page
- `GET /api/vehicles` - Get all vehicle records
- `GET /api/search?plate=ABC123` - Search vehicles by plate

## Notes

- The system uses a voting buffer to improve detection accuracy
- Minimum exit delay prevents false exits
- Images are stored in JPEG format with timestamps
- Database is SQLite for simplicity