import React, { useState } from 'react';

export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 text-center">
      <div className="max-w-md w-full bg-slate-900 p-8 rounded-2xl border border-slate-800 shadow-2xl space-y-6">
        <div className="text-4xl">🎓</div>
        <h1 className="text-2xl font-bold text-white">Smart Attendance System</h1>
        <p className="text-sm text-slate-400">
          The React client is scaffolded and ready for custom components. You can also view the pre-built real-time interfaces directly in your browser:
        </p>

        <div className="space-y-3">
          <a
            href="http://localhost:8000/dashboard"
            target="_blank"
            rel="noreferrer"
            class="block w-full py-3 px-4 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl transition shadow-lg shadow-blue-500/20"
          >
            Open Live Instructor Dashboard
          </a>

          <a
            href="http://localhost:8000/enroll"
            target="_blank"
            rel="noreferrer"
            class="block w-full py-3 px-4 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold rounded-xl transition border border-slate-700"
          >
            Open Face Enrollment Station
          </a>
        </div>
      </div>
    </div>
  );
}
