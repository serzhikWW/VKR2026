import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
})

// Videos
export const uploadVideo = (file, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/api/videos/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress) onProgress(Math.round((e.loaded * 100) / e.total))
    },
  })
}

export const listVideos = (page = 1, size = 10, status = null) => {
  const params = { page, size }
  if (status) params.status = status
  return api.get('/api/videos/', { params })
}

export const getVideo = (id) => api.get(`/api/videos/${id}`)
export const deleteVideo = (id) => api.delete(`/api/videos/${id}`)

// Detections
export const getDetections = (videoId, params = {}) =>
  api.get(`/api/detections/video/${videoId}`, { params })

export const getDetectionSummary = (videoId) =>
  api.get(`/api/detections/summary/${videoId}`)

export const getOverviewStats = () =>
  api.get('/api/detections/stats/overview')

// WebSocket
export const WS_BASE = (import.meta.env.VITE_WS_URL || 'ws://localhost:8000')

export const createProgressWS = (videoId) => {
  return new WebSocket(`${WS_BASE}/ws/progress/${videoId}`)
}

export default api
