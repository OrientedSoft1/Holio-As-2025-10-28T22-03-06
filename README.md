# Holio As - Riff AI Studio

An AI-powered platform for building apps through natural language.

## Features
- Conversational AI chat interface
- Interactive project plan editor  
- Natural language to code generation (Python + React)
- Live app preview and testing
- One-click GitHub deployment
- Integration marketplace

## Tech Stack
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- **Backend:** FastAPI + Python
- **Database:** PostgreSQL
- **AI:** OpenAI GPT-4
- **Auth:** Stack Auth

## Project Structure
```
backend/
├── app/
│   ├── apis/       # FastAPI route handlers
│   └── libs/       # Reusable Python modules
├── main.py         # FastAPI app entry point
└── pyproject.toml  # Python dependencies

frontend/
├── src/
│   ├── pages/      # React page components
│   ├── components/ # Reusable UI components
│   └── utils/      # Frontend utilities
├── package.json    # NPM dependencies
└── index.html      # App entry point
```

## Getting Started

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend  
```bash
cd frontend
npm install
npm run dev
```

Built with ❤️ using Riff
