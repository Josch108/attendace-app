import React from 'react';

export default function App() {
  return (
    <div className="min-h-screen bg-[#090d16] text-slate-200 flex flex-col items-center justify-center p-6 text-center antialiased">
      <div className="max-w-md w-full bg-[#0d1322] p-8 rounded-xl border border-slate-800 shadow-sm space-y-6">
        <div className="w-12 h-12 mx-auto rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M9 3H5a2 2 0 00-2 2v4m0 6v4a2 2 0 002 2h4m6 0h4a2 2 0 002-2v-4m0-6V5a2 2 0 00-2-2h-4"/>
            <circle cx="12" cy="12" r="3" stroke-width="1.8"/>
          </svg>
        </div>
        
        <div className="space-y-1">
          <h1 className="text-xl font-semibold text-white tracking-tight">Smart Attendance System</h1>
          <p className="text-xs text-slate-400">
            Biometric facial recognition and continuous classroom attendance tracking platform.
          </p>
        </div>

        <div className="space-y-2.5 pt-2">
          <a
            href="http://localhost:8000/dashboard"
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg transition shadow-sm"
          >
            <span>Open Instructor Dashboard</span>
          </a>

          <a
            href="http://localhost:8000/enroll"
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-[#080c14] hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-medium rounded-lg transition border border-slate-800"
          >
            <span>Open Face Enrollment Station</span>
          </a>
        </div>
      </div>
    </div>
  );
}
