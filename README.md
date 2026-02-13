# Kioku

Generate Japanese Anki cards from an image:
- Extract English text with EasyOCR
- Enrich reading/meaning/example fields with Groq
- Generate Japanese audio with Edge TTS
- Push notes directly into Anki via AnkiConnect

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- A [Groq API key](https://console.groq.com/keys)
- (Optional) [Anki](https://apps.ankiweb.net/) with the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on installed

## Quick Start

1. Copy the example env file and add your Groq API key:

```bash
cp .env.example .env
```

Edit `.env` and set `GROQ_API_KEY` to your key.

2. Build and run with Docker:

```bash
make docker-build
make docker-run
```

Or without Make:

```bash
pip wheel --no-deps -w dist/ .
docker build -t kioku:latest .
docker run -p 8000:8000 --env-file .env kioku:latest
```

3. Open `http://localhost:8000` in your browser.

**Note:** The first run will be slow as EasyOCR model files are downloaded. Subsequent starts will be faster.

## Configuration

Set the following in `.env`:

- `GROQ_API_KEY` (required)
- `GROQ_MODEL` (optional, default: `meta-llama/llama-4-scout-17b-16e-instruct`)
- `ANKI_CONNECT_URL` (optional, default: `http://localhost:8765`)

## AnkiConnect Setup

To push cards to Anki, you need Anki running with the AnkiConnect add-on. Set `ANKI_CONNECT_URL` in your `.env` to point to your Anki instance.

- If Anki is running on the same machine as Docker: use your machine's local IP (not `localhost`, since the Docker container can't reach the host's `localhost`). For example: `http://192.168.1.100:8765`.
- If using Docker Desktop: `http://host.docker.internal:8765` may work.

In AnkiConnect's add-on config (Tools > Add-ons > AnkiConnect > Config), make sure `webCorsOrigin` is set to `"*"` to allow requests from Kioku.

## Using from Other Devices

To access Kioku from a phone or another device on your network:

1. Find your host machine's local IP:
   - macOS: `ifconfig | grep "inet " | grep -v 127.0.0.1`
   - Linux: `ip addr show | grep "inet " | grep -v 127.0.0.1`
2. Open `http://<your-local-ip>:8000` from the other device.

For access outside your local network, you can expose port 8000 via router port forwarding or use a VPN like [Tailscale](https://tailscale.com/) or [WireGuard](https://www.wireguard.com/) to access your home network remotely.

## API Endpoints

- `POST /api/extract` — multipart form with `file`, returns extracted card objects
- `POST /api/generate` — JSON body with `cards` and optional `deck_name`, generates audio and pushes notes to Anki

## Running Without Docker

If you prefer not to use Docker, you can install Kioku directly:

```bash
pip install kioku-<version>.whl
```

Create a `.env` file with your `GROQ_API_KEY`, then run:

```bash
kioku
```

Build a wheel with `make build-wheel` — the `.whl` file will be in `dist/`.
