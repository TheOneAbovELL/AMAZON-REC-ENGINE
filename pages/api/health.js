export default function handler(req, res) {
  res.status(200).json({
    status: "healthy",
    service: "amazon-rec-engine",
    architecture: process.env.BACKEND_URL ? "Option C (External Backend)" : "Option A (Vercel Built-in)",
    backend_url: process.env.BACKEND_URL || null,
    timestamp: new Date().toISOString(),
  });
}
