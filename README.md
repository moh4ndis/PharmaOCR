# Pharma OCR Extraction API

FastAPI MVP backend for extracting pharmaceutical package fields from medicine package images using the standard PaddleOCR General OCR pipeline.

The API extracts:

- lot or batch number
- expiration date
- manufacture date, when present
- raw OCR text
- average OCR confidence

## Quick Explanation

This project is a local OCR backend for medicine package images. A user uploads a package photo or scans one with the laptop camera, the app reads the printed text, extracts important fields, and returns JSON.

It does not use an LLM or paid cloud OCR. The OCR model is PaddleOCR, and the field extraction is done with simple parser rules.

## Tech Stack Used

- **Python 3.11**: main backend language
- **FastAPI**: REST API and web app server
- **PaddleOCR**: open-source OCR model for text detection and recognition
- **PaddlePaddle CPU**: inference engine used by PaddleOCR
- **OpenCV**: image preprocessing before OCR
- **Pydantic**: structured API response schemas
- **Uvicorn**: ASGI server for FastAPI
- **uv**: Python dependency manager
- **Docker Compose**: repeatable local runtime

## Model Structure

```text
Image upload or camera frame
   ↓
OpenCV preprocessing
   ↓
PaddleOCR text detection + recognition
   ↓
Raw detected text lines
   ↓
Regex parser
   ↓
lot_number / expiration_date / manufacture_date
   ↓
Human correction UI
   ↓
Final JSON output
```

In simple terms:

1. **OpenCV** cleans the image so text is easier to read.
2. **PaddleOCR** finds and reads text from the image.
3. **Parser rules** search that text for labels like `LOT`, `EXP`, `PER`, `MFG`, `DOM`, and `FAB`.
4. **Date normalization** converts values such as `10/27` into `2027-10`.
5. **Human-in-the-loop UI** lets the user correct OCR or parser mistakes before copying JSON.
6. **Camera scan mode** captures a browser camera frame and sends it to the same OCR endpoint.

Docker uses these lightweight PaddleOCR models:

- `PP-OCRv5_mobile_det`: detects text areas in the image
- `en_PP-OCRv5_mobile_rec`: recognizes English text from detected areas

## Architecture

```text
app/
├── main.py
├── routes/
│   └── extract.py
├── services/
│   ├── ocr_service.py
│   ├── parser_service.py
│   └── preprocess_service.py
├── schemas/
│   └── response_schema.py
├── utils/
│   └── image.py
└── uploads/
```

Supporting runtime files:

- `Dockerfile` builds the API image with Python 3.11, `uv`, and locked dependencies.
- `docker-compose.yml` runs the API and keeps OCR/model caches in named Docker volumes.
- `pyproject.toml` is the dependency source of truth.
- `uv.lock` pins the resolved dependency versions.
- `requirements.txt` is exported from `uv.lock` for compatibility with pip-based tools.

The route layer accepts uploads and returns JSON. Image validation, OpenCV preprocessing, OCR, and parsing are separate services so the system can be extended later without turning the API handlers into a monolith.

## Standard PaddleOCR Choice

This project uses the official `paddleocr` Python package with its default capabilities: general OCR and document image preprocessing. We intentionally do not install heavier optional dependency groups such as `doc-parser`, `ie`, `trans`, or `all`, because this MVP only needs text extraction from medicine package images.

The installed inference engine is `paddlepaddle` CPU. This matches a lightweight Mac/local/Docker workflow and avoids PaddleOCR-VL or cloud OCR services. Local runs use PaddleOCR's standard English OCR configuration by default. Docker Compose sets explicit PP-OCRv5 mobile detection plus English mobile recognition models because that path is lighter for this MVP than the heavier server detector on Mac CPU Docker.

Official equivalent pip install commands:

```bash
python -m pip install paddlepaddle -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python -m pip install paddleocr
```

In this project, use `uv sync` instead; `pyproject.toml` and `uv.lock` already contain these dependencies.

## OCR Pipeline

1. Validate MIME type and decode the uploaded image with OpenCV.
2. Preprocess the image:
   - resize very large images
   - convert to grayscale
   - denoise
   - enhance contrast with CLAHE
3. Run standard PaddleOCR with English OCR and orientation handling for rotated text.
4. Normalize PaddleOCR output into text lines and confidence scores.
5. Parse raw OCR text using rule-based regex heuristics.
6. Return structured JSON.

## How PaddleOCR Is Used

PaddleOCR is used only for local text detection and recognition. It does not decide which text is a lot number or an expiration date. That field extraction is handled by the parser after OCR finishes.

The OCR logic lives in `app/services/ocr_service.py`:

1. `OCRService` lazy-loads PaddleOCR the first time an image is processed.
2. The service runs on CPU, not GPU.
3. For PaddleOCR 3.x, it uses `PaddleOCR(...).predict(image)`.
4. Text-line orientation is enabled with `use_textline_orientation=True` so rotated text is handled better.
5. Document orientation classification and document unwarping are disabled to keep the MVP lightweight.
6. In Docker, the service uses explicit mobile OCR models:
   - detection: `PP-OCRv5_mobile_det`
   - recognition: `en_PP-OCRv5_mobile_rec`
7. The raw PaddleOCR result is normalized into simple internal objects:
   - recognized text line
   - OCR confidence score
8. The rest of the app receives only `raw_text` and average `confidence`, keeping Paddle-specific result formats isolated inside the OCR service.

Current Docker OCR settings are configured in `docker-compose.yml`:

```bash
PADDLEOCR_DET_MODEL=PP-OCRv5_mobile_det
PADDLEOCR_REC_MODEL=en_PP-OCRv5_mobile_rec
PADDLEOCR_CPU_THREADS=4
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
```

`PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` skips PaddleX's startup connectivity probe. PaddleOCR may still download model files during the first real OCR request if they are not already cached. Docker named volumes keep those model files for later runs.

## Why PaddleOCR

PaddleOCR is open-source, runs locally, supports CPU inference, provides strong text detection and recognition models, and includes orientation handling for rotated text. The standard General OCR pipeline is the right fit here because medicine package extraction needs reliable text lines, not full document layout parsing or VLM reasoning. In PaddleOCR 2.x orientation is configured with angle classification; in PaddleOCR 3.x the equivalent text-line orientation option is enabled. This makes it a practical fit for an MVP where paid cloud OCR APIs, PaddleOCR-VL, custom model training, and cloud services are intentionally out of scope.

## Parsing Strategy

The parser looks for common pharmaceutical labels:

- `LOT`
- `BATCH`
- `EXP`
- `EXP DATE`
- `DOM`
- `MFG`
- `MFD`

Supported date formats include:

- `10 2026`
- `10/2026`
- `08-2025`
- `2026-10`

Dates are normalized to `YYYY-MM`, for example `10/2026` becomes `2026-10`.

Lot and batch values are normalized to uppercase alphanumeric strings such as `RN620` or `K8NGWAHVKJ`.

If no explicit `EXP` label is found, the parser uses the first standalone month/year value as an MVP expiration-date fallback. It also handles OCR output where labels and values are split into separate text columns, such as `LOT:`, `EXP:`, `10`, `2026`, `RN620`, `DOM:`, `10`, `2023`.

## Recommended Setup: Docker Compose

Docker Compose is the recommended way to run this MVP. It avoids local Python, PaddleOCR, PaddlePaddle, and OpenCV installation problems by building a repeatable container image.

Prerequisites:

- Docker Desktop for Mac
- Docker Compose, included with Docker Desktop

On Apple Silicon, the Compose service runs as `linux/amd64` for PaddlePaddle stability. This is slower than native execution but avoids Linux ARM Paddle runtime crashes observed during OCR inference on M1.

Optional environment file:

```bash
cp .env.example .env
```

Useful OCR settings in `.env`:

```bash
PADDLEOCR_DET_MODEL=PP-OCRv5_mobile_det
PADDLEOCR_REC_MODEL=en_PP-OCRv5_mobile_rec
PADDLEOCR_CPU_THREADS=4
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
```

Run the API:

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000/
```

The web UI keeps the uploaded package image or live camera preview visible on the left and shows parsed fields, detected OCR text, and JSON output on the right. Swagger remains available at:

```text
http://localhost:8000/docs
```

Health check:

```bash
curl http://localhost:8000/health
```

Stop the API:

```bash
docker compose down
```

View logs:

```bash
docker compose logs -f pharma-ocr-api
```

If port `8000` is already in use, edit `.env`:

```bash
API_PORT=8001
```

Then open:

```text
http://localhost:8001/docs
```

The first OCR request may be slower because PaddleOCR can download model files. The Compose file stores OCR/model caches in named volumes so later container starts do not have to redownload the same files.

## Docker Best Practices Used

- Dependencies are locked with `uv.lock`.
- The image installs dependencies before copying application code, improving Docker layer caching.
- The API runs as a non-root user.
- Runtime caches are stored in Docker named volumes.
- The container exposes only the FastAPI port.
- The image has a `/health` healthcheck.
- `.dockerignore` excludes local virtualenvs, caches, uploads, and secrets.

## Local Development With uv

This project uses `uv` for Python version management, dependency resolution, and local commands. The `.python-version` file pins the local runtime to Python 3.11.

```bash
brew install uv
uv python install 3.11
uv sync
```

Run the API:

```bash
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True uv run uvicorn app.main:app --reload
```

Open the interactive API docs:

```text
http://localhost:8000/docs
```

Open the built-in OCR workbench:

```text
http://localhost:8000/
```

PaddleOCR may download model files on the first real OCR request. The `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` flag skips PaddleX's startup connectivity probe; it does not replace the need for model files to exist locally or be downloadable on first use.

Regenerate the compatibility requirements file after dependency changes:

```bash
uv export --format requirements.txt --no-hashes --no-emit-project --output-file requirements.txt
```

## App Workflow

The runtime workflow is intentionally simple and follows the same pipeline for the web UI, single-image API, and batch API.

```text
User / Client
    |
    | uploads image
    v
FastAPI route
    |
    | validates upload and MIME type
    v
OpenCV preprocessing
    |
    | improves OCR readability
    v
PaddleOCR
    |
    | returns text lines and confidence scores
    v
Rule-based parser
    |
    | extracts LOT / EXP / MFG fields
    v
Structured JSON response
```

Detailed flow:

1. Client uploads one or more package images as `multipart/form-data`.
2. FastAPI receives the file in `app/routes/extract.py`.
3. `read_image_upload()` validates the MIME type and decodes the image bytes into an OpenCV image array.
4. `PreprocessService` resizes very large images, converts to grayscale, denoises, and improves contrast.
5. `OCRService` sends the processed image to PaddleOCR.
6. PaddleOCR detects text regions, recognizes the text, and returns OCR confidence scores.
7. `OCRService` converts PaddleOCR's output into a plain list of text lines plus average confidence.
8. `ParserService` searches the OCR text for package labels such as `LOT`, `BATCH`, `EXP`, `PER`, `DOM`, `FAB`, and `MFG`.
9. Dates such as `10/27`, `10 2026`, and `08-2025` are normalized to `YYYY-MM`.
10. The API returns structured JSON with parsed fields, raw OCR text, and confidence.

The built-in web UI uses the same `/extract/single` endpoint as API clients. After the user chooses an image, the browser keeps a local preview visible on the left, sends the file to the backend, and renders the parsed fields, OCR text, confidence, and JSON on the right.

For laptop camera scanning, the browser uses `getUserMedia` on `localhost`, captures a video frame into a JPEG image, and sends that image to `/extract/single`. The optional auto-scan mode repeats this snapshot process every few seconds; it is not a continuous video stream to the backend.

The UI also supports human-in-the-loop correction. Parsed fields are editable, detected OCR text lines are editable, and each detected line has quick assignment buttons for `LOT`, `EXP`, and `MFG`. For example, if OCR detects `09-2025` but the parser does not assign it as the manufacture date, click `MFG` on that detected text line and the corrected JSON updates immediately.

The API does not permanently store uploaded images in the MVP flow. The `app/uploads` directory is present for future extension points such as validation queues or audit workflows.

## Manual Docker Commands

Compose is preferred, but the image can also be built and run directly:

```bash
docker build -t pharma-ocr-api .
docker run --rm -p 8000:8000 pharma-ocr-api
```

## Example Requests

Single image extraction:

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

Batch extraction:

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

## Limitations

OCR accuracy depends on image quality, lighting, package curvature, glare, font size, and print contrast. Rule-based parsing is intentionally simple for the MVP, so unusual label layouts or heavily corrupted OCR text may require human review.

The API returns `null` for fields it cannot confidently parse from the OCR text. It does not perform medical validation, product lookup, or regulatory checks.

## Future Improvements

- mobile camera upload flow
- smarter continuous scan mode with duplicate-result filtering
- human-in-the-loop validation UI
- confidence-based review queue
- broader deterministic parser coverage
- per-field confidence scoring
- optional barcode or Data Matrix extraction
- test fixture set for common package layouts
