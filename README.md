# Dealership Chatbot Frontend

A modern React frontend application for a dealership website built with React 18, Vite, TypeScript, and Tailwind CSS.

## Features

- 🚀 **React 18** - Latest React features
- ⚡ **Vite** - Fast build tool and dev server
- 📘 **TypeScript** - Type-safe development
- 🎨 **Tailwind CSS** - Utility-first CSS framework
- 💬 **Floating Chatbot Button** - Bottom-right floating button for chatbot interaction

## Getting Started

### Prerequisites

- Node.js (v18 or higher recommended)
- npm or yarn
- Python 3.11

### Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Open your browser and navigate to `http://localhost:5173`

### Build for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
├── src/
│   ├── components/
│   │   ├── Header.tsx          # Navigation header
│   │   ├── Hero.tsx            # Hero section with "Drive Your Dream"
│   │   ├── Features.tsx        # Service features grid
│   │   ├── About.tsx           # About section
│   │   ├── Services.tsx        # Services list section
│   │   └── ChatbotButton.tsx   # Floating chatbot button
│   ├── App.tsx                 # Main app component
│   ├── main.tsx               # React entry point
│   └── index.css              # Global styles with Tailwind
├── index.html                 # HTML template
├── vite.config.ts            # Vite configuration
├── tsconfig.json             # TypeScript configuration
├── tailwind.config.js        # Tailwind CSS configuration
└── package.json              # Dependencies and scripts
```

## Components

### Header
Navigation bar with logo, menu items, and "Start Now" button.

### Hero
Full-screen hero section with "Drive Your Dream" messaging and car imagery.

### Features
Grid of four service features:
- Comprehensive Inspection
- Affordable Financing
- Extended Warranty
- 24/7 Support

### About
Two-column layout showcasing Auto Emporium with image and description.

### Services
Dark-themed section with service list and car imagery.

### ChatbotButton
Floating button in the bottom-right corner that opens/closes a chatbot interface.

## Customization

### Images
Replace placeholder images in:
- `Hero.tsx` - Hero section background and car image
- `About.tsx` - Car image in about section
- `Services.tsx` - Car image in services section

### Chatbot Integration
The `ChatbotButton` component is connected to a FastAPI backend that uses LangChain with memory capabilities. The "Start Now" buttons throughout the site will open the chatbot interface.

#### Backend Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables (create a `.env` file):
```bash
OPENAI_API_KEY=your-openai-api-key-here
MEMORY_SERVER_URL=http://localhost:8000
VITE_API_URL=http://localhost:8001
```

3. Start the FastAPI backend:
```bash
python api.py
```

The API will run on `http://localhost:8001` by default.

#### Running the Full Stack

1. Start the backend (in one terminal):
```bash
python api.py
```

2. Start the frontend (in another terminal):
```bash
npm run dev
```

3. Open `http://localhost:5173` in your browser

## License

MIT

