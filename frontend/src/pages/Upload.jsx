import React, { useState, useCallback, useRef, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { Upload, Film, X, Loader, CheckCircle, Flame, Wind, AlertCircle } from 'lucide-react'
import { uploadVideo, createProgressWS } from '../services/api.js'
import styles from './Upload.module.css'

const ACCEPTED = { 'video/*': ['.mp4', '.avi', '.mov', '.mkv', '.webm'] }
const MAX_SIZE = 500 * 1024 * 1024

export default function UploadPage() {
  const [file, setFile] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [phase, setPhase] = useState('idle') // idle | uploading | processing | done | error
  const [processingData, setProcessingData] = useState(null)
  const [videoId, setVideoId] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const wsRef = useRef(null)
  const navigate = useNavigate()

  const onDrop = useCallback((accepted, rejected) => {
    if (rejected.length > 0) {
      toast.error('Неверный формат или файл слишком большой')
      return
    }
    if (accepted.length > 0) {
      setFile(accepted[0])
      setPhase('idle')
      setProcessingData(null)
      setVideoId(null)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxSize: MAX_SIZE,
    multiple: false,
    disabled: phase !== 'idle',
  })

  const startUpload = async () => {
    if (!file) return
    setPhase('uploading')
    setUploadProgress(0)
    try {
      const res = await uploadVideo(file, (pct) => setUploadProgress(pct))
      const id = res.data.id
      setVideoId(id)
      setPhase('processing')
      connectWS(id)
    } catch (e) {
      setPhase('error')
      setErrorMsg(e.response?.data?.detail || 'Ошибка загрузки')
      toast.error('Ошибка загрузки файла')
    }
  }

  const connectWS = (id) => {
    const ws = createProgressWS(id)
    wsRef.current = ws

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'heartbeat') return

      setProcessingData(data)

      if (data.status === 'completed') {
        setPhase('done')
        toast.success('Видео обработано!')
        ws.close()
      } else if (data.status === 'failed') {
        setPhase('error')
        setErrorMsg('Ошибка обработки видео')
        toast.error('Ошибка обработки')
        ws.close()
      }
    }

    ws.onerror = () => {
      // Fallback: poll
      pollStatus(id)
    }
  }

  const pollStatus = (id) => {
    const interval = setInterval(async () => {
      try {
        const { getVideo } = await import('../services/api.js')
        const res = await getVideo(id)
        const v = res.data
        if (v.status === 'completed') {
          setPhase('done')
          setProcessingData({ progress: 100, detections_found: v.detections_count })
          clearInterval(interval)
          toast.success('Видео обработано!')
        } else if (v.status === 'failed') {
          setPhase('error')
          setErrorMsg(v.error_message || 'Ошибка обработки')
          clearInterval(interval)
        }
      } catch { clearInterval(interval) }
    }, 3000)
  }

  const reset = () => {
    wsRef.current?.close()
    setFile(null)
    setPhase('idle')
    setProcessingData(null)
    setVideoId(null)
    setErrorMsg('')
    setUploadProgress(0)
  }

  const goToResult = () => {
    if (videoId) navigate(`/videos/${videoId}`)
  }

  const progress = processingData?.progress ?? 0
  const fireFound = processingData?.detections_found > 0

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>
          <span className={styles.titleAccent}>ЗАГРУЗКА</span> ВИДЕО
        </h1>
        <p className={styles.subtitle}>
          Система автоматически обнаружит огонь и дым с помощью YOLOv8
        </p>
      </div>

      <div className={styles.layout}>
        {/* Drop zone */}
        <div className={styles.dropCard}>
          {!file ? (
            <div
              {...getRootProps()}
              className={`${styles.dropzone} ${isDragActive ? styles.dropzoneActive : ''}`}
            >
              <input {...getInputProps()} />
              <div className={styles.dropIcon}>
                <Upload size={32} />
              </div>
              <p className={styles.dropTitle}>
                {isDragActive ? 'Отпустите файл...' : 'Перетащите видео сюда'}
              </p>
              <p className={styles.dropHint}>или нажмите для выбора файла</p>
              <div className={styles.dropFormats}>
                {['MP4', 'AVI', 'MOV', 'MKV', 'WEBM'].map(f => (
                  <span key={f} className={styles.formatTag}>{f}</span>
                ))}
              </div>
              <p className={styles.dropLimit}>Максимальный размер: 500 МБ</p>
            </div>
          ) : (
            <div className={styles.fileInfo}>
              <div className={styles.fileIcon}>
                <Film size={24} />
              </div>
              <div className={styles.fileMeta}>
                <div className={styles.fileName}>{file.name}</div>
                <div className={styles.fileSize}>
                  {(file.size / 1024 / 1024).toFixed(1)} МБ
                </div>
              </div>
              {phase === 'idle' && (
                <button className={styles.removeBtn} onClick={reset}>
                  <X size={14} />
                </button>
              )}
            </div>
          )}

          {/* Upload Button */}
          {file && phase === 'idle' && (
            <button className={styles.uploadBtn} onClick={startUpload}>
              <Flame size={16} />
              Начать анализ
            </button>
          )}
        </div>

        {/* Progress & Status */}
        {phase !== 'idle' && (
          <div className={styles.statusCard}>
            {/* Upload phase */}
            {phase === 'uploading' && (
              <PhaseBlock
                title="ЗАГРУЗКА ФАЙЛА"
                icon={<Upload size={16} />}
                color="warn"
              >
                <div className={styles.progressBar}>
                  <div className={styles.progressFill} style={{ width: `${uploadProgress}%`, '--color': 'var(--warn)' }} />
                </div>
                <div className={styles.progressLabel}>{uploadProgress}%</div>
              </PhaseBlock>
            )}

            {/* Processing phase */}
            {(phase === 'processing') && (
              <PhaseBlock
                title="ОБРАБОТКА НЕЙРОСЕТЬЮ"
                icon={<Loader size={16} className={styles.spin} />}
                color="fire"
              >
                <div className={styles.progressBar}>
                  <div
                    className={styles.progressFill}
                    style={{ width: `${progress}%`, '--color': 'var(--fire)' }}
                  />
                </div>
                <div className={styles.progressStats}>
                  <span>{Math.round(progress)}%</span>
                  <span>
                    Кадр {processingData?.current_frame ?? 0} / {processingData?.total_frames ?? '?'}
                  </span>
                  <span>
                    <Flame size={11} />
                    {processingData?.detections_found ?? 0} детекций
                  </span>
                </div>
              </PhaseBlock>
            )}

            {/* Done */}
            {phase === 'done' && (
              <PhaseBlock
                title="АНАЛИЗ ЗАВЕРШЁН"
                icon={<CheckCircle size={16} />}
                color="safe"
              >
                <div className={styles.resultSummary}>
                  <div className={`${styles.resultBadge} ${processingData?.detections_found > 0 ? styles.badgeDanger : styles.badgeSafe}`}>
                    {processingData?.detections_found > 0
                      ? `⚠ Обнаружено ${processingData.detections_found} событий`
                      : '✓ Угрозы не обнаружены'}
                  </div>
                </div>
                <div className={styles.doneActions}>
                  <button className={styles.viewResultBtn} onClick={goToResult}>
                    Просмотр результатов
                  </button>
                  <button className={styles.newUploadBtn} onClick={reset}>
                    Новое видео
                  </button>
                </div>
              </PhaseBlock>
            )}

            {/* Error */}
            {phase === 'error' && (
              <PhaseBlock
                title="ОШИБКА"
                icon={<AlertCircle size={16} />}
                color="fire"
              >
                <p className={styles.errorText}>{errorMsg}</p>
                <button className={styles.newUploadBtn} onClick={reset}>
                  Попробовать снова
                </button>
              </PhaseBlock>
            )}
          </div>
        )}
      </div>

      {/* Instructions */}
      <div className={styles.infoGrid}>
        <InfoCard icon={Upload} title="1. Загрузка" text="Перетащите видеофайл в область загрузки или нажмите для выбора." />
        <InfoCard icon={Flame} title="2. Детекция" text="YOLOv8 анализирует каждый кадр и обнаруживает огонь и дым в реальном времени." />
        <InfoCard icon={Film} title="3. Результат" text="Получите аннотированное видео и подробную статистику детекций." />
      </div>
    </div>
  )
}

function PhaseBlock({ title, icon, color, children }) {
  return (
    <div className={`${styles.phaseBlock} ${styles[`phase_${color}`]}`}>
      <div className={styles.phaseHeader}>
        <span className={styles.phaseIcon}>{icon}</span>
        <span className={styles.phaseTitle}>{title}</span>
      </div>
      <div className={styles.phaseContent}>{children}</div>
    </div>
  )
}

function InfoCard({ icon: Icon, title, text }) {
  return (
    <div className={styles.infoCard}>
      <Icon size={18} className={styles.infoIcon} />
      <div className={styles.infoTitle}>{title}</div>
      <div className={styles.infoText}>{text}</div>
    </div>
  )
}
