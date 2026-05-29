import React, { useEffect, useState, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { getVideo, getDetections, deleteVideo as apiDeleteVideo } from '../services/api.js'
import { format } from 'date-fns'
import toast from 'react-hot-toast'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import {
  ArrowLeft, Flame, Wind, Clock, CheckCircle, AlertTriangle,
  Download, Trash2, Play, BarChart2, List, Info, AlertCircle
} from 'lucide-react'
import styles from './VideoDetail.module.css'

// Backend base URL — all video stream URLs must point to port 8000, not 3000
const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

// Convert relative path from API response to absolute backend URL
function abs(path) {
  if (!path) return null
  if (path.startsWith('http')) return path
  return `${API_BASE}${path}`
}

const STATUS_CFG = {
  completed: { label: 'ГОТОВО',       icon: CheckCircle,    color: 'safe'  },
  processing: { label: 'ОБРАБОТКА',   icon: Clock,          color: 'warn'  },
  uploaded:   { label: 'ОЖИДАЕТ',     icon: Clock,          color: 'smoke' },
  failed:     { label: 'ОШИБКА',      icon: AlertTriangle,  color: 'fire'  },
}

const LABEL_CFG = {
  fire:           { text: 'ОБНАРУЖЕН ОГОНЬ',      bg: 'fire'  },
  smoke:          { text: 'ОБНАРУЖЕН ДЫМ',        bg: 'smoke' },
  fire_and_smoke: { text: 'ОГОНЬ И ДЫМ',          bg: 'fire'  },
  none:           { text: 'УГРОЗ НЕ ОБНАРУЖЕНО',  bg: 'safe'  },
}

export default function VideoDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [video, setVideo]       = useState(null)
  const [detections, setDetections] = useState([])
  const [chartData, setChartData]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const pollRef = useRef(null)

  const load = async () => {
    try {
      const [vRes, dRes] = await Promise.all([
        getVideo(id),
        getDetections(id, { limit: 500 }),
      ])
      setVideo(vRes.data)
      setDetections(dRes.data)
      buildChart(vRes.data, dRes.data)
    } catch {
      toast.error('Ошибка загрузки данных')
    } finally {
      setLoading(false)
    }
  }

  const buildChart = (v, dets) => {
    if (!v?.duration || !dets.length) return
    const step = Math.max(1, Math.floor(v.duration / 30))
    const buckets = {}
    dets.forEach(d => {
      const t = Math.floor(d.timestamp / step) * step
      if (!buckets[t]) buckets[t] = { time: t, fire: 0, smoke: 0 }
      if (d.label === 'fire') buckets[t].fire++
      else if (d.label === 'smoke') buckets[t].smoke++
    })
    setChartData(Object.values(buckets).sort((a, b) => a.time - b.time))
  }

  useEffect(() => {
    load()
    pollRef.current = setInterval(() => {
      if (video?.status === 'processing' || video?.status === 'uploaded') load()
      else clearInterval(pollRef.current)
    }, 5000)
    return () => clearInterval(pollRef.current)
  }, [id])

  const handleDelete = async () => {
    if (!confirm('Удалить это видео и все результаты?')) return
    try {
      await apiDeleteVideo(id)
      toast.success('Видео удалено')
      navigate('/videos')
    } catch { toast.error('Ошибка удаления') }
  }

  if (loading) return <div className={styles.loading}><Clock size={20} /> Загрузка...</div>
  if (!video)  return <div className={styles.loading}>Видео не найдено</div>

  const st       = STATUS_CFG[video.status] || STATUS_CFG.uploaded
  const StatusIcon = st.icon
  const labelCfg = video.summary ? LABEL_CFG[video.summary.overall_label] : null
  const fireCount  = video.summary?.fire_detections  ?? 0
  const smokeCount = video.summary?.smoke_detections ?? 0
  const totalDets  = video.summary?.total_detections ?? 0

  // Absolute stream URLs
  const streamUrl  = abs(video.video_url)
  const resultUrl  = abs(video.processed_video_url)
  // Download URL: same stream endpoint with ?download=1 so backend sets Content-Disposition: attachment
  const downloadUrl = resultUrl ? `${resultUrl}?download=1` : null

  return (
    <div className={styles.page}>
      {/* Breadcrumb */}
      <div className={styles.breadcrumb}>
        <Link to="/videos" className={styles.backLink}><ArrowLeft size={14} />Архив</Link>
        <span className={styles.breadSep}>/</span>
        <span className={styles.breadCurrent}>{video.original_filename}</span>
      </div>

      {/* Header */}
      <div className={styles.pageHeader}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}>{video.original_filename}</h1>
          <div className={styles.headerMeta}>
            <span className={`${styles.statusBadge} ${styles[`s_${st.color}`]}`}>
              <StatusIcon size={10} />{st.label}
            </span>
            {video.created_at && (
              <span className={styles.metaItem}>
                {format(new Date(video.created_at), 'dd.MM.yyyy HH:mm')}
              </span>
            )}
          </div>
        </div>
        <div className={styles.headerActions}>
          {downloadUrl && (
            <a href={downloadUrl} className={styles.actionBtn} target="_blank" rel="noreferrer">
              <Download size={14} />Скачать результат
            </a>
          )}
          <button className={`${styles.actionBtn} ${styles.deleteBtn}`} onClick={handleDelete}>
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Alert */}
      {labelCfg && (
        <div className={`${styles.alertBanner} ${styles[`alert_${labelCfg.bg}`]}`}>
          {labelCfg.bg === 'fire' ? <Flame size={16} /> :
           labelCfg.bg === 'smoke' ? <Wind size={16} /> : <CheckCircle size={16} />}
          <span className={styles.alertText}>{labelCfg.text}</span>
          {totalDets > 0 && <span className={styles.alertCount}>{totalDets} детекций</span>}
        </div>
      )}

      {/* Stats */}
      <div className={styles.statsRow}>
        <StatMini label="Длительность"    value={video.duration    ? `${Math.round(video.duration)}с` : '—'} />
        <StatMini label="Кадров"          value={video.total_frames?.toLocaleString('ru-RU') ?? '—'} />
        <StatMini label="FPS"             value={video.fps         ? video.fps.toFixed(1) : '—'} />
        <StatMini label="Разрешение"      value={video.width       ? `${video.width}×${video.height}` : '—'} />
        <StatMini label="Размер"          value={video.file_size   ? `${(video.file_size/1024/1024).toFixed(1)} МБ` : '—'} />
        <StatMini label="Детекций огня"   value={fireCount}  highlight={fireCount > 0} color="fire" />
        <StatMini label="Детекций дыма"   value={smokeCount} color="smoke" />
        <StatMini label="Время обработки" value={video.summary?.processing_time ? `${video.summary.processing_time.toFixed(1)}с` : '—'} />
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        {[
          { id: 'overview', label: 'Обзор',    icon: Info     },
          { id: 'chart',    label: 'График',   icon: BarChart2 },
          { id: 'list',     label: 'Детекции', icon: List     },
          { id: 'video',    label: 'Видео',    icon: Play     },
        ].map(({ id: tid, label, icon: Icon }) => (
          <button
            key={tid}
            className={`${styles.tab} ${activeTab === tid ? styles.tabActive : ''}`}
            onClick={() => setActiveTab(tid)}
          >
            <Icon size={13} />{label}
          </button>
        ))}
      </div>

      <div className={styles.tabContent}>
        {activeTab === 'overview' && <OverviewTab video={video} />}
        {activeTab === 'chart'    && <ChartTab chartData={chartData} />}
        {activeTab === 'list'     && <DetectionsList detections={detections} />}
        {activeTab === 'video'    && <VideoTab resultUrl={resultUrl} streamUrl={streamUrl} />}
      </div>
    </div>
  )
}

/* ─── Sub-components ─────────────────────────────────────────── */

function StatMini({ label, value, highlight, color }) {
  return (
    <div className={styles.statMini}>
      <div className={styles.statMiniLabel}>{label}</div>
      <div className={`${styles.statMiniValue} ${highlight ? styles[`val_${color}`] : ''}`}>{value}</div>
    </div>
  )
}

function OverviewTab({ video }) {
  const s = video.summary
  if (!s) return (
    <div className={styles.noData}>
      {video.status === 'processing'
        ? <><Clock size={20}/> Видео обрабатывается...</>
        : <><Info size={20}/> Нет данных</>}
    </div>
  )
  return (
    <div className={styles.overviewGrid}>
      <OverviewCard title="СТАТИСТИКА ДЕТЕКЦИЙ">
        <OverviewStat label="Всего событий"    value={s.total_detections} />
        <OverviewStat label="Огонь"            value={s.fire_detections}  color="fire"  />
        <OverviewStat label="Дым"              value={s.smoke_detections} color="smoke" />
        <OverviewStat label="Макс. уверенность" value={s.max_confidence ? `${(s.max_confidence*100).toFixed(1)}%` : '—'} />
        <OverviewStat label="Ср. уверенность"  value={s.avg_confidence  ? `${(s.avg_confidence*100).toFixed(1)}%`  : '—'} />
      </OverviewCard>
      <OverviewCard title="ВРЕМЕННЫЕ МЕТКИ">
        <OverviewStat label="Первая детекция"    value={s.first_detection_time != null ? `${s.first_detection_time.toFixed(1)}с` : '—'} />
        <OverviewStat label="Последняя детекция" value={s.last_detection_time  != null ? `${s.last_detection_time.toFixed(1)}с`  : '—'} />
        <OverviewStat label="Кадров обработано"  value={s.frames_processed?.toLocaleString('ru-RU') ?? '—'} />
        <OverviewStat label="Время анализа"      value={s.processing_time ? `${s.processing_time.toFixed(1)}с` : '—'} />
      </OverviewCard>
    </div>
  )
}

function OverviewCard({ title, children }) {
  return (
    <div className={styles.overviewCard}>
      <div className={styles.overviewCardTitle}>{title}</div>
      <div className={styles.overviewStats}>{children}</div>
    </div>
  )
}

function OverviewStat({ label, value, color }) {
  return (
    <div className={styles.overviewStat}>
      <span className={styles.overviewStatLabel}>{label}</span>
      <span className={`${styles.overviewStatValue} ${color ? styles[`val_${color}`] : ''}`}>{value}</span>
    </div>
  )
}

function ChartTab({ chartData }) {
  if (!chartData.length)
    return <div className={styles.noData}><BarChart2 size={20}/> Нет данных для графика</div>
  return (
    <div className={styles.chartWrap}>
      <div className={styles.chartTitle}>ДЕТЕКЦИИ ПО ВРЕМЕНИ</div>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={chartData} margin={{ top:10, right:10, left:-20, bottom:0 }}>
          <defs>
            <linearGradient id="gFire"  x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#ff3d1f" stopOpacity={0.4}/>
              <stop offset="95%" stopColor="#ff3d1f" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="gSmoke" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#8b9ab0" stopOpacity={0.4}/>
              <stop offset="95%" stopColor="#8b9ab0" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e2730"/>
          <XAxis dataKey="time" tickFormatter={v=>`${v}с`} tick={{fill:'#7a8fa8',fontSize:10,fontFamily:'Share Tech Mono'}} axisLine={{stroke:'#1e2730'}}/>
          <YAxis tick={{fill:'#7a8fa8',fontSize:10,fontFamily:'Share Tech Mono'}} axisLine={{stroke:'#1e2730'}}/>
          <Tooltip contentStyle={{background:'#0f1318',border:'1px solid #1e2730',borderRadius:'4px',fontFamily:'Share Tech Mono',fontSize:'11px',color:'#e8edf5'}} labelFormatter={v=>`Время: ${v}с`}/>
          <Legend wrapperStyle={{fontFamily:'Share Tech Mono',fontSize:'11px',color:'#7a8fa8'}}/>
          <Area type="monotone" dataKey="fire"  name="Огонь" stroke="#ff3d1f" fill="url(#gFire)"  strokeWidth={2}/>
          <Area type="monotone" dataKey="smoke" name="Дым"   stroke="#8b9ab0" fill="url(#gSmoke)" strokeWidth={2}/>
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function DetectionsList({ detections }) {
  if (!detections.length)
    return <div className={styles.noData}><List size={20}/> Нет детекций</div>
  return (
    <div className={styles.detList}>
      <div className={styles.detHeader}>
        <span>Метка</span><span>Время</span><span>Кадр</span>
        <span>Уверенность</span><span>Координаты (x1,y1,x2,y2)</span>
      </div>
      <div className={styles.detRows}>
        {detections.slice(0, 200).map((d, i) => (
          <div key={d.id || i} className={styles.detRow}>
            <span className={`${styles.detLabel} ${d.label==='fire'?styles.detFire:styles.detSmoke}`}>
              {d.label==='fire'?<Flame size={10}/>:<Wind size={10}/>}{d.label}
            </span>
            <span className={styles.mono}>{d.timestamp.toFixed(2)}с</span>
            <span className={styles.mono}>{d.frame_number}</span>
            <span className={styles.mono}>
              <span className={styles.confBar} style={{'--w':`${d.confidence*100}%`}}/>
              {(d.confidence*100).toFixed(1)}%
            </span>
            <span className={styles.mono}>
              {d.bbox_x1!=null
                ?`${Math.round(d.bbox_x1)},${Math.round(d.bbox_y1)},${Math.round(d.bbox_x2)},${Math.round(d.bbox_y2)}`
                :'—'}
            </span>
          </div>
        ))}
        {detections.length > 200 && (
          <div className={styles.detMore}>... и ещё {detections.length-200} детекций</div>
        )}
      </div>
    </div>
  )
}

function VideoTab({ resultUrl, streamUrl }) {
  const [error, setError] = useState(false)
  const videoRef = useRef(null)
  const url = resultUrl || streamUrl
  const label = resultUrl ? 'АННОТИРОВАННОЕ ВИДЕО' : 'ОРИГИНАЛЬНОЕ ВИДЕО'

  if (!url) return <div className={styles.noData}><Play size={20}/> Видео недоступно</div>

  return (
    <div className={styles.videoTab}>
      <div className={styles.videoLabel}>{label}</div>
      {error ? (
        <div className={styles.videoError}>
          <AlertCircle size={20}/>
          <span>Не удалось загрузить видео в плеере.</span>
          <a href={url} target="_blank" rel="noreferrer" className={styles.videoOpenLink}>
            Открыть в новой вкладке →
          </a>
        </div>
      ) : (
        <video
          ref={videoRef}
          key={url}
          className={styles.videoPlayer}
          controls
          preload="metadata"
          onError={() => setError(true)}
        >
          {/* Provide src via <source> — better error handling than src attribute */}
          <source src={url} type="video/mp4" />
          <source src={url} type="video/webm" />
          Ваш браузер не поддерживает HTML5 видео.
        </video>
      )}
      <div className={styles.videoActions}>
        <a href={`${url}?download=1`} className={styles.videoDownloadBtn} target="_blank" rel="noreferrer">
          <Download size={13}/> Скачать файл
        </a>
        <a href={url} target="_blank" rel="noreferrer" className={styles.videoOpenBtn}>
          Открыть напрямую →
        </a>
      </div>
    </div>
  )
}