# Pharma OCR Extraction API

Simple FastAPI backend and web UI for extracting medicine package data from images using local OCR.

The app extracts:

- lot or batch number
- expiration date
- manufacture date when detected
- raw OCR text
- OCR confidence

It runs locally with Docker. No paid OCR API, no cloud OCR service, and no LLM is required.

## Quick Explanation

This project reads text from medicine package photos.

The user uploads an image, or scans a frame with the laptop camera. The backend preprocesses the image, runs PaddleOCR, parses the detected text, and returns structured JSON.

The web UI also lets a human correct the result. This is important because OCR can miss text or read it incorrectly, especially on small, blurry, shiny, or rotated package labels.

## Tech Stack Used

- **Python 3.11**: backend language
- **FastAPI**: REST API and web server
- **PaddleOCR**: open-source OCR model for text detection and recognition
- **PaddlePaddle CPU**: local inference runtime used by PaddleOCR
- **OpenCV**: image preprocessing before OCR
- **Pydantic**: typed response schemas
- **Uvicorn**: FastAPI application server
- **Docker Compose**: one-command local runtime
- **uv**: dependency installation inside Docker

You do not need to install Python packages on your Mac when using Docker.

## Model Structure

```text
Image upload or camera frame
        |
        v
OpenCV preprocessing
        |
        v
PaddleOCR text detection and recognition
        |
        v
Raw detected text lines + OCR confidence
        |
        v
Rule-based parser
        |
        v
Machine extraction draft
        |
        v
Human-in-the-loop review and correction
        |
        v
Final reviewed JSON output
```

Simple structure:

```text
Backend API
|-- routes: receive uploads and return JSON
|-- preprocessing service: improves image readability
|-- OCR service: runs PaddleOCR
|-- parser service: extracts LOT / EXP / MFG fields
`-- schemas: defines structured API responses

Frontend UI
|-- image upload
|-- camera snapshot scan
|-- OCR result display
`-- human correction and reviewed JSON copy
```

## Why PaddleOCR Was Used

PaddleOCR was chosen because it fits the MVP requirements well:

- it is open-source
- it runs locally
- it does not require paid APIs
- it works on CPU
- it has strong text detection and recognition models
- it supports rotated text through text-line orientation handling
- it is easy to call from Python
- it can be deployed inside Docker

For this project, PaddleOCR is the right level of complexity. We only need to read printed package text, not train a custom model or run a heavy vision-language model.

## How PaddleOCR Is Used

PaddleOCR is used only to detect and recognize text in the image.

It does not decide what is a lot number or what is an expiration date. After OCR finishes, the parser searches the detected text for labels such as:

- `LOT`
- `BATCH`
- `EXP`
- `PER`
- `MFG`
- `MFD`
- `DOM`
- `FAB`

The parser then normalizes dates into this format:

```text
YYYY-MM
```

Examples:

```text
10/2026 -> 2026-10
08-2025 -> 2025-08
10/27   -> 2027-10
```

The OCR service lives here:

```text
app/services/ocr_service.py
```

The parser lives here:

```text
app/services/parser_service.py
```

## Docker OCR Models

Docker Compose configures lightweight PaddleOCR models:

```text
PP-OCRv5_mobile_det     text detection model
en_PP-OCRv5_mobile_rec  English text recognition model
```

These are good for an MVP because they are lighter than server-size OCR models.

On Mac M1, the Docker service uses:

```text
platform: linux/amd64
```

This is usually more stable for PaddlePaddle inside Docker on Apple Silicon. It can be slower than native execution, but it avoids many dependency and runtime problems.

## Run With Docker Only

Prerequisite:

- Docker Desktop installed and running

Start the app:

```bash
docker compose up --build
```

Open the web UI:

```text
http://localhost:8000/
```

Open Swagger API docs:

```text
http://localhost:8000/docs
```

Health check:

```bash
curl http://localhost:8000/health
```

Stop the app:

```bash
docker compose down
```

View logs:

```bash
docker compose logs -f pharma-ocr-api
```

If port `8000` is already used, create a `.env` file:

```bash
API_PORT=8001
```

Then start again:

```bash
docker compose up --build
```

Open:

```text
http://localhost:8001/
```

## First Run Note

The first OCR request can be slow because PaddleOCR may download model files.

Docker Compose stores PaddleOCR caches in Docker volumes, so later runs should be faster and should not redownload the same models.

## App Workflow

1. User opens `http://localhost:8000/`.
2. User uploads a medicine package photo or clicks `Use camera`.
3. The browser sends the image to `/extract/single`.
4. FastAPI validates that the upload is an image.
5. OpenCV preprocesses the image:
   - resize large images
   - grayscale conversion
   - denoise
   - contrast enhancement
6. PaddleOCR detects and reads text.
7. The parser extracts lot, expiration, and manufacture dates when possible.
8. The UI shows:
   - original image
   - parsed fields
   - confidence
   - detected text lines
   - editable JSON result
9. User can manually fix fields before copying the final JSON.

## Human-in-the-Loop Correction

OCR is not perfect, so the app treats the automatic result as a draft.

The human-in-the-loop step improves reliability because the user can compare the detected text with the original package image before copying the final JSON.

You can:

- edit the parsed lot number
- edit the expiration date
- edit the manufacture date
- edit detected OCR text lines
- assign a detected text line to `LOT`, `EXP`, or `MFG`
- mark the result as reviewed
- copy corrected JSON

Example: if OCR detects `09-2025` but the parser does not know it is the manufacture date, click `MFG` next to that detected line.

The UI copied JSON includes human review metadata:

```json
{
  "human_review": {
    "status": "reviewed",
    "corrected_fields": ["manufacture_date"],
    "reviewed_at": "2026-05-29T12:00:00.000Z"
  }
}
```

## Camera Scan

The web UI has a `Use camera` option.

It uses the browser camera on `localhost`, captures a frame, converts it to an image, and sends it to the same `/extract/single` endpoint.

This is snapshot-based OCR. It is not a continuous video stream to the backend.

If the camera does not open, check browser and macOS camera permissions for `127.0.0.1` or `localhost`.

## REST API

### Single Image

Endpoint:

```text
POST /extract/single
```

Request:

```bash
curl -X POST "http://localhost:8000/extract/single" \
  -F "file=@drug1.jpg"
```

Example response:

```json
{
  "filename": "drug1.jpg",
  "lot_number": "RN620",
  "expiration_date": "2026-10",
  "manufacture_date": "2023-10",
  "raw_text": ["LOT: RN620", "EXP: 10 2026", "DOM: 10 2023"],
  "confidence": 0.91
}
```

### Batch Images

Endpoint:

```text
POST /extract/batch
```

Request:

```bash
curl -X POST "http://localhost:8000/extract/batch" \
  -F "files=@drug1.jpg" \
  -F "files=@drug2.jpg"
```

Example response:

```json
{
  "results": [
    {
      "filename": "drug1.jpg",
      "lot_number": "RN620",
      "expiration_date": "2026-10",
      "manufacture_date": null,
      "raw_text": ["LOT: RN620", "EXP: 10 2026"],
      "confidence": 0.93
    },
    {
      "filename": "drug2.jpg",
      "lot_number": "K8NGWAHVKJ",
      "expiration_date": "2025-08",
      "manufacture_date": null,
      "raw_text": ["BATCH K8NGWAHVKJ", "EXP 08-2025"],
      "confidence": 0.89
    }
  ]
}
```

## Project Structure

```text
app/
|-- main.py
|-- routes/
|   `-- extract.py
|-- services/
|   |-- ocr_service.py
|   |-- parser_service.py
|   `-- preprocess_service.py
|-- schemas/
|   `-- response_schema.py
|-- static/
|   `-- index.html
|-- utils/
|   `-- image.py
`-- uploads/
```

Important files:

- `Dockerfile`: builds the backend image
- `docker-compose.yml`: runs the API with OCR cache volumes
- `pyproject.toml`: Python dependencies
- `uv.lock`: locked dependency versions
- `README.md`: project documentation

## Why No LLM Yet

An LLM is not required for the MVP.

The current pipeline is:

```text
OCR + deterministic parser + human correction
```

This is easier to test, cheaper to run, and more predictable for a pharmaceutical workflow.

A local LLM can be added later only for normalization suggestions, not as the source of truth.

## Limitations

- OCR accuracy depends on photo quality.
- Glare, blur, low contrast, curved boxes, and tiny printed text can reduce accuracy.
- Rule-based parsing may miss unusual layouts.
- The app does not verify medicine authenticity.
- The app does not do regulatory or medical validation.

## Future Improvements

- better mobile camera workflow
- confidence-based review queue
- smarter parser rules
- per-field confidence scores
- barcode or Data Matrix extraction
- local lightweight LLM normalization
- validation history and audit workflow
