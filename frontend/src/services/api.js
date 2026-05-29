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

// Live RTSP Streams
export const createStream = (rtsp_url, name = null) =>
  api.post('/api/streams/', { rtsp_url, name })

export const listStreams = () => api.get('/api/streams/')

export const getStream = (id) => api.get(`/api/streams/${id}`)

export const stopStream = (id) => api.post(`/api/streams/${id}/stop`)

export const deleteStream = (id) => api.delete(`/api/streams/${id}`)

export const getStreamMjpegUrl = (id) =>
  `${API_BASE}/api/streams/${id}/mjpeg`

// WebSocket
export const WS_BASE = (import.meta.env.VITE_WS_URL || 'ws://localhost:8000')

export const createProgressWS = (videoId) => {
  return new WebSocket(`${WS_BASE}/ws/progress/${videoId}`)
}

export const createStreamStatsWS = (streamId) => {
  return new WebSocket(`${WS_BASE}/ws/streams/${streamId}`)
}

export default api
