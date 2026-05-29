import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Upload from './pages/Upload.jsx'
import VideoDetail from './pages/VideoDetail.jsx'
import VideoList from './pages/VideoList.jsx'
import LiveStream from './pages/LiveStream.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#141920',
            color: '#e8edf5',
            border: '1px solid #1e2730',
            fontFamily: 'Share Tech Mono, monospace',
            fontSize: '13px',
          },
          success: { iconTheme: { primary: '#00e5a0', secondary: '#141920' } },
          error: { iconTheme: { primary: '#ff3d1f', secondary: '#141920' } },
        }}
      />
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="upload" element={<Upload />} />
          <Route path="live" element={<LiveStream />} />
          <Route path="videos" element={<VideoList />} />
          <Route path="videos/:id" element={<VideoDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
