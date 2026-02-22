# BioVerify UI

A modern web interface for the BioVerify video deepfake detection system.

## Features

- **Video Upload**: Drag-and-drop or click to upload videos for analysis
- **Real-time Progress**: Track analysis progress with automatic status updates
- **Results Display**: View verdict, confidence score, and detailed reasons
- **Evidence Viewer**: Explore rPPG signals, frequency spectra, and key metrics

## Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn/pnpm

### Installation

```bash
cd ui
npm install
```

### Development

Start the development server:

```bash
npm run dev
```

The app will be available at `http://localhost:3000`.

### Environment Variables

Create a `.env` file based on `.env.example`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_AUTH_TOKEN=your-auth-token-here
```

### Building for Production

```bash
npm run build
```

The production build will be in the `dist` directory.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
ui/
├── src/
│   ├── components/     # Reusable UI components
│   ├── pages/          # Page components
│   ├── services/       # API client
│   ├── hooks/          # Custom React hooks
│   ├── types/          # TypeScript type definitions
│   └── App.tsx         # Main app component with routing
├── public/             # Static assets
└── package.json
```

## API Integration

The UI communicates with the BioVerify API:

- `POST /analyses` - Upload video and create analysis job
- `GET /analyses/{id}` - Get analysis status and results
- `GET /analyses/{id}/evidence` - Get evidence artifacts with signed URLs
- `GET /health` - Health check endpoint

## Technologies

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **React Router** - Client-side routing
- **Tailwind CSS** - Styling
- **Axios** - HTTP client
- **Recharts** - Chart library (for future enhancements)
