import React, { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import {
  Radio, Play, Square, Trash2, Flame, Wind, AlertCircle,
  Activity, Loader, Info, Clock, Tv,
} from 'lucide-react'
import {
  createStream, listStreams, stopStream, deleteStream,
  getStreamMjpegUrl, createStreamStatsWS,
} from '../services/api.js'
import styles from './LiveStream.module.css'

const STATUS_CFG = {
  starting: { label: 'ПОДКЛЮЧЕНИЕ', color: 'warn',  icon: Loader },
  running:  { label: 'В ЭФИРЕ',     color: 'safe',  icon: Radio  },
  stopped:  { label: 'ОСТАНОВЛЕН',  color: 'smoke', icon: Square },
  error:    { label: 'ОШИБКА',      color: 'fire',  icon: AlertCircle },
}

const SAMPLE_URL = 'rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov'

export default function LiveStream() {
  const [streams, setStreams] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [rtspUrl, setRtspUrl] = useState('')
  const [streamName, setStreamName] = useState('')
  const [creating, setCreating] = useState(false)
  const [liveStats, setLiveStats] = useState(null)
  const wsRef = useRef(null)

  // ── Initial load + polling for stream list ────────────────────────────
  const loadList = async () => {
    try {
      const res = await listStreams()
      setStreams(res.data)
      // If selection was deleted on backend, clear it
      if (selectedId && !res.data.find(s => s.id === selectedId)) {
        setSelectedId(null)
        setLiveStats(null)
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    loadList()
    const i = setInterval(loadList, 5000)
    return () => clearInterval(i)
    // eslint-disable-next-line
  }, [])

  // ── WebSocket for selected stream stats ───────────────────────────────
  useEffect(() => {
    wsRef.current?.close()
    wsRef.current = null
    setLiveStats(null)

    if (!selectedId) return

    const ws = createStreamStatsWS(selectedId)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'stats') {
          setLiveStats(data)
        } else if (data.type === 'error') {
          toast.error('Поток недоступен')
        }
      } catch {}
    }
    ws.onerror = () => { /* silent — REST polling will fall back */ }

    return () => {
      try { ws.close() } catch {}
    }
  }, [selectedId])

  // ── Actions ───────────────────────────────────────────────────────────
  const handleCreate = async (e) => {
    e?.preventDefault()
    const url = rtspUrl.trim()
    if (!url) {
      toast.error('Введите RTSP URL')
      return
    }
    setCreating(true)
    try {
      const res = await createStream(url, streamName.trim() || null)
      toast.success('Поток запущен')
      setRtspUrl('')
      setStreamName('')
      await loadList()
      setSelectedId(res.data.id)
    } catch (e) {
      const msg = e.response?.data?.detail || 'Ошибка запуска потока'
      toast.error(msg)
    } finally {
      setCreating(false)
    }
  }

  const handleStop = async (id) => {
    try {
      await stopStream(id)
      toast.success('Поток остановлен')
      await loadList()
    } catch {
      toast.error('Не удалось остановить')
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Удалить этот поток?')) return
    try {
      await deleteStream(id)
      toast.success('Поток удалён')
      if (selectedId === id) setSelectedId(null)
      await loadList()
    } catch {
      toast.error('Не удалось удалить')
    }
  }

  const selected = streams.find(s => s.id === selectedId) || null
  // Prefer fresh WS data if available
  const view = liveStats || selected

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <h1 className={styles.title}>
          <span className={styles.titleAccent}>LIVE</span> ТРАНСЛЯЦИЯ
        </h1>
        <p className={styles.subtitle}>
          Подключите IP-камеру или любой RTSP/HTTP источник для детекции в реальном времени
        </p>
      </div>

      {/* Connect form */}
      <div className={styles.connectCard}>
        <div className={styles.connectHeader}>
          <Radio size={14} className={styles.connectHeaderIcon} />
          <span>ПОДКЛЮЧЕНИЕ ИСТОЧНИКА</span>
        </div>
        <form className={styles.connectForm} onSubmit={handleCreate}>
          <div className={styles.formGrid}>
            <label className={styles.formField}>
              <span className={styles.formLabel}>RTSP URL</span>
              <input
                type="text"
                className={styles.formInput}
                placeholder="rtsp://user:pass@192.168.0.10:554/stream"
                value={rtspUrl}
                onChange={(e) => setRtspUrl(e.target.value)}
                disabled={creating}
              />
            </label>
            <label className={styles.formField}>
              <span className={styles.formLabel}>Имя (необязательно)</span>
              <input
                type="text"
                className={styles.formInput}
                placeholder="Камера №1"
                value={streamName}
                onChange={(e) => setStreamName(e.target.value)}
                disabled={creating}
              />
            </label>
          </div>
          <div className={styles.formActions}>
            <button
              type="button"
              className={styles.sampleBtn}
              onClick={() => setRtspUrl(SAMPLE_URL)}
              disabled={creating}
            >
              Тестовый URL
            </button>
            <button
              type="submit"
              className={styles.connectBtn}
              disabled={creating || !rtspUrl.trim()}
            >
              {creating ? <Loader size={14} className={styles.spin} /> : <Play size={14} />}
              {creating ? 'Подключение...' : 'Подключить'}
            </button>
          </div>
        </form>
      </div>

      {/* Main split: viewer + sidebar */}
      <div className={styles.layout}>
        {/* Left — viewer */}
        <div className={styles.viewerCol}>
          {selected ? (
            <ViewerCard
              stream={selected}
              view={view}
              onStop={() => handleStop(selected.id)}
              onDelete={() => handleDelete(selected.id)}
            />
          ) : (
            <EmptyViewer />
          )}
        </div>

        {/* Right — streams list */}
        <div className={styles.sideCol}>
          <div className={styles.sideHeader}>
            <Tv size={12} />
            <span>АКТИВНЫЕ ПОТОКИ</span>
            <span className={styles.sideCounter}>{streams.length}</span>
          </div>
          <div className={styles.streamList}>
            {streams.length === 0 && (
              <div className={styles.sideEmpty}>Нет потоков</div>
            )}
            {streams.map(s => (
              <StreamRow
                key={s.id}
                stream={s}
                active={selectedId === s.id}
                onSelect={() => setSelectedId(s.id)}
                onStop={() => handleStop(s.id)}
                onDelete={() => handleDelete(s.id)}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Info cards */}
      <div className={styles.infoGrid}>
        <InfoCard
          icon={Radio}
          title="1. Подключение"
          text="Введите RTSP URL вашей IP-камеры или используйте тестовый поток."
        />
        <InfoCard
          icon={Flame}
          title="2. Детекция"
          text="YOLO анализирует кадры в реальном времени и подсвечивает огонь и дым."
        />
        <InfoCard
          icon={Activity}
          title="3. Мониторинг"
          text="Статистика обновляется в реальном времени через WebSocket."
        />
      </div>
    </div>
  )
}

/* ─── Subcomponents ─────────────────────────────────────────────────── */

function ViewerCard({ stream, view, onStop, onDelete }) {
  const cfg = STATUS_CFG[view?.status] || STATUS_CFG.stopped
  const StIcon = cfg.icon
  const isLive = view?.status === 'running' || view?.status === 'starting'
  const mjpegUrl = isLive ? getStreamMjpegUrl(stream.id) : null
  // Force img refresh when stream restarts
  const [imgKey] = useState(() => Date.now())

  return (
    <div className={styles.viewerCard}>
      {/* Title bar */}
      <div className={styles.viewerHead}>
        <div className={styles.viewerTitle}>
          <span className={styles.viewerName}>{view?.name || stream.name}</span>
          <span className={`${styles.statusPill} ${styles[`pill_${cfg.color}`]}`}>
            <StIcon size={10} className={cfg.color === 'warn' ? styles.spin : ''} />
            {cfg.label}
          </span>
        </div>
        <div className={styles.viewerActions}>
          {isLive && (
            <button className={styles.iconBtn} onClick={onStop} title="Остановить">
              <Square size={13} />
            </button>
          )}
          <button
            className={`${styles.iconBtn} ${styles.iconBtnDanger}`}
            onClick={onDelete}
            title="Удалить"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {/* Video frame */}
      <div className={styles.videoFrame}>
        {mjpegUrl ? (
          <img
            key={`${stream.id}-${imgKey}`}
            src={mjpegUrl}
            alt="Live stream"
            className={styles.videoImg}
          />
        ) : (
          <div className={styles.videoPlaceholder}>
            {view?.status === 'error' ? (
              <>
                <AlertCircle size={28} />
                <div className={styles.placeholderText}>
                  {view?.error_message || 'Ошибка подключения'}
                </div>
              </>
            ) : (
              <>
                <Square size={28} />
                <div className={styles.placeholderText}>Поток остановлен</div>
              </>
            )}
          </div>
        )}
        {isLive && (
          <div className={styles.liveBadge}>
            <span className={styles.liveDot} />
            LIVE
          </div>
        )}
        {view?.current_fps != null && isLive && (
          <div className={styles.fpsBadge}>
            {view.current_fps.toFixed(1)} FPS
          </div>
        )}
      </div>

      {/* Stats grid */}
      <div className={styles.statsGrid}>
        <StatTile label="Кадров"   value={view?.frames_total ?? 0} />
        <StatTile
          label="Обработано"
          value={view?.frames_processed ?? 0}
        />
        <StatTile
          label="Огонь"
          value={view?.fire_total ?? 0}
          color="fire"
          highlight={(view?.fire_total ?? 0) > 0}
        />
        <StatTile
          label="Дым"
          value={view?.smoke_total ?? 0}
          color="smoke"
          highlight={(view?.smoke_total ?? 0) > 0}
        />
        <StatTile
          label="Источник FPS"
          value={view?.source_fps ? view.source_fps.toFixed(0) : '—'}
        />
        <StatTile
          label="Разрешение"
          value={view?.width ? `${view.width}×${view.height}` : '—'}
        />
        <StatTile
          label="Аптайм"
          value={formatUptime(view?.uptime_seconds)}
        />
        <StatTile
          label="Всего детекций"
          value={view?.detections_total ?? 0}
          highlight={(view?.detections_total ?? 0) > 0}
          color="fire"
        />
      </div>

      {/* Recent detections log */}
      <div className={styles.logCard}>
        <div className={styles.logHead}>
          <Activity size={11} />
          <span>ЖУРНАЛ ДЕТЕКЦИЙ</span>
          <span className={styles.logCount}>
            {(view?.recent_detections ?? []).length}
          </span>
        </div>
        <div className={styles.logBody}>
          {(view?.recent_detections ?? []).length === 0 ? (
            <div className={styles.logEmpty}>Детекций пока нет</div>
          ) : (
            <div className={styles.logRows}>
              {[...(view.recent_detections || [])].reverse().map((d, i) => {
                const isFire = (d.label || '').toLowerCase().includes('fire')
                return (
                  <div key={i} className={styles.logRow}>
                    <span className={`${styles.logLabel} ${isFire ? styles.logFire : styles.logSmoke}`}>
                      {isFire ? <Flame size={10} /> : <Wind size={10} />}
                      {d.label}
                    </span>
                    <span className={styles.logFrame}>#{d.frame_number}</span>
                    <span className={styles.logConf}>{(d.confidence * 100).toFixed(1)}%</span>
                    <span className={styles.logTime}>{formatTimestamp(d.timestamp)}</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function EmptyViewer() {
  return (
    <div className={styles.emptyViewer}>
      <Tv size={48} />
      <div className={styles.emptyTitle}>Поток не выбран</div>
      <div className={styles.emptyHint}>
        Подключите новый источник или выберите существующий поток справа
      </div>
    </div>
  )
}

function StreamRow({ stream, active, onSelect, onStop, onDelete }) {
  const cfg = STATUS_CFG[stream.status] || STATUS_CFG.stopped
  const StIcon = cfg.icon
  return (
    <div
      className={`${styles.streamRow} ${active ? styles.streamRowActive : ''}`}
      onClick={onSelect}
    >
      <div className={`${styles.streamDot} ${styles[`dot_${cfg.color}`]}`}>
        <StIcon size={10} className={cfg.color === 'warn' ? styles.spin : ''} />
      </div>
      <div className={styles.streamInfo}>
        <div className={styles.streamName}>{stream.name}</div>
        <div className={styles.streamUrl}>{stream.rtsp_url}</div>
      </div>
      <div className={styles.streamActions}>
        {(stream.status === 'running' || stream.status === 'starting') && (
          <button
            className={styles.miniBtn}
            onClick={(e) => { e.stopPropagation(); onStop() }}
            title="Стоп"
          >
            <Square size={11} />
          </button>
        )}
        <button
          className={`${styles.miniBtn} ${styles.miniBtnDanger}`}
          onClick={(e) => { e.stopPropagation(); onDelete() }}
          title="Удалить"
        >
          <Trash2 size={11} />
        </button>
      </div>
    </div>
  )
}

function StatTile({ label, value, highlight, color }) {
  return (
    <div className={`${styles.statTile} ${highlight ? styles[`tile_${color}`] : ''}`}>
      <div className={styles.statTileLabel}>{label}</div>
      <div className={styles.statTileValue}>{value}</div>
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

/* ─── Helpers ────────────────────────────────────────────────────────── */

function formatUptime(seconds) {
  if (seconds == null) return '—'
  const s = Math.floor(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h}ч ${m}м`
  if (m > 0) return `${m}м ${sec}с`
  return `${sec}с`
}

function formatTimestamp(ts) {
  if (!ts) return '—'
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('ru-RU', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}
