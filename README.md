# Lumeet - Recruitment Dashboard

A beautiful, modern recruitment dashboard for connecting with creator applicants, featuring a glassy iOS-inspired design.

## Features

- **Clean Sidebar Navigation**: Dashboard, Recruit, and Messages sections
- **Applicant Cards Grid**: Display creator applicants in a responsive 3-column grid
- **Glassy iOS Aesthetic**: Frosted glass backgrounds with soft shadows and purple accents
- **Modern UI**: Built with React and Tailwind CSS

## Getting Started

### Installation

```bash
npm install
```

### Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

### Late API Environment Variables (backend)

Set these before starting `uvicorn`:

- `LATE_API_KEY` (required for `/api/late/*`)
- `LATE_API_BASE_URL` (optional, default `https://getlate.dev/api/v1`)
- `LATE_CONNECT_REDIRECT_URL` (optional default callback URL)
- `LATE_REQUEST_TIMEOUT_SEC` (optional, default `20`)
- `PUBLIC_BACKEND_BASE_URL` (optional, default `http://127.0.0.1:8000`)

### Late Scheduling Flow

After a video is generated in the **Create** tab, use **Schedule to Social** to:

1. Create a Late profile
2. Connect a social account via OAuth
3. Refresh connected accounts
4. Write caption + choose accounts + schedule/publish

Backend endpoints used by the frontend:

- `POST /api/late/profiles`
- `GET /api/late/connect-url`
- `GET /api/late/accounts`
- `POST /api/late/posts`

### Development

```bash
npm run dev
```

Open your browser and navigate to `http://localhost:5173`

### Build

```bash
npm run build
```

## Tech Stack

- React 18
- Vite
- Tailwind CSS
- Lucide React (icons)

## Design Features

- Frosted glass backgrounds with backdrop blur
- Soft shadows and hover effects
- Rounded corners (2xl)
- Purple gradient accents
- Responsive grid layout
- Smooth transitions and animations

