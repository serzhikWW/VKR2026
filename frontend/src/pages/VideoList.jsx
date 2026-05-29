import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listVideos, deleteVideo } from '../services/api.js'
import { formatDistanceToNow, format } from 'date-fns'
import { ru } from 'date-fns/locale'
import toast from 'react-hot-toast'
import {
  Film, Trash2, Eye, CheckCircle, Clock, AlertTriangle,
  ChevronLeft, ChevronRight, Filter, Flame, Wind
} from 'lucide-react'
import styles from './VideoList.module.css'

const STATUS_OPTIONS = [
  { value: '', label: 'Все статусы' },
  { value: 'completed', label: 'Обработаны' },
  { value: 'processing', label: 'Обрабатываются' },
  { value: 'uploaded', label: 'Ожидают' },
  { value: 'failed', label: 'Ошибка' },
]

const STATUS_CFG = {
  completed: { label: 'ГОТОВО', icon: CheckCircle, color: 'safe' },
  processing: { label: 'ОБРАБОТКА', icon: Clock, color: 'warn' },
  uploaded: { label: 'ОЖИДАЕТ', icon: Clock, color: 'smoke' },
  failed: { label: 'ОШИБКА', icon: AlertTriangle, color: 'fire' },
}

const LABEL_CFG = {
  fire: { text: 'ОГОНЬ', color: 'fire' },
  smoke: { text: 'ДЫМ', color: 'smoke' },
  fire_and_smoke: { text: 'ОГОНЬ+ДЫМ', color: 'fire' },
  none: { text: 'ЧИСТО', color: 'safe' },
}

export default function VideoList() {
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await listVideos(page, 10, status || null)
      setData(res.data)
    } catch (e) {
      toast.error('Ошибка загрузки списка видео')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [page, status])

  const handleDelete = async (id, e) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm('Удалить это видео и все результаты?')) return
    setDeleting(id)
    try {
      await deleteVideo(id)
      toast.success('Видео удалено')
      load()
    } catch {
      toast.error('Ошибка удаления')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>
          <span className={styles.titleAccent}>АРХИВ</span> ВИДЕО
        </h1>
        <p className={styles.subtitle}>История обработанных видеозаписей</p>
      </div>

      {/* Filters */}
      <div className={styles.toolbar}>
        <div className={styles.filterGroup}>
          <Filter size={14} className={styles.filterIcon} />
          <select
            className={styles.filterSelect}
            value={status}
            onChange={e => { setStatus(e.target.value); setPage(1) }}
          >
            {STATUS_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        {data && (
          <span className={styles.totalCount}>
            {data.total} видео
          </span>
        )}
      </div>

      {/* Table */}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>#</th>
              <th>Файл</th>
              <th>Длительность</th>
              <th>Размер</th>
              <th>Статус</th>
              <th>Результат</th>
              <th>Детекций</th>
              <th>Загружено</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className={styles.skelRow}>
                  {Array.from({ length: 9 }).map((_, j) => (
                    <td key={j}><div className={styles.skel} /></td>
                  ))}
                </tr>
              ))
            ) : data?.items?.length === 0 ? (
              <tr>
                <td colSpan={9} className={styles.empty}>
                  <Film size={24} />
                  <span>Нет видео</span>
                </td>
              </tr>
            ) : data?.items?.map((v) => {
              const st = STATUS_CFG[v.status] || STATUS_CFG.uploaded
              const StatusIcon = st.icon
              const labelCfg = v.summary ? LABEL_CFG[v.summary?.overall_label] : null

              return (
                <tr key={v.id} className={styles.row}>
                  <td className={styles.idCell}>
                    <span className={styles.idBadge}>{v.id}</span>
                  </td>
                  <td className={styles.nameCell}>
                    <Link to={`/videos/${v.id}`} className={styles.nameLink}>
                      {v.original_filename}
                    </Link>
                  </td>
                  <td className={styles.mono}>
                    {v.duration ? `${Math.round(v.duration)}с` : '—'}
                  </td>
                  <td className={styles.mono}>
                    {v.file_size ? `${(v.file_size / 1024 / 1024).toFixed(1)} МБ` : '—'}
                  </td>
                  <td>
                    <span className={`${styles.statusBadge} ${styles[`s_${st.color}`]}`}>
                      <StatusIcon size={10} />
                      {st.label}
                    </span>
                  </td>
                  <td>
                    {labelCfg ? (
                      <span className={`${styles.labelBadge} ${styles[`l_${labelCfg.color}`]}`}>
                        {labelCfg.text}
                      </span>
                    ) : '—'}
                  </td>
                  <td className={styles.mono}>
                    {v.summary ? (
                      <span className={v.summary.total_detections > 0 ? styles.detectionCount : ''}>
                        {v.summary.total_detections}
                      </span>
                    ) : '—'}
                  </td>
                  <td className={`${styles.mono} ${styles.dateCell}`}>
                    {v.created_at
                      ? format(new Date(v.created_at), 'dd.MM.yy HH:mm')
                      : '—'}
                  </td>
                  <td>
                    <div className={styles.actions}>
                      <Link to={`/videos/${v.id}`} className={styles.actionBtn}>
                        <Eye size={13} />
                      </Link>
                      <button
                        className={`${styles.actionBtn} ${styles.deleteBtn}`}
                        onClick={(e) => handleDelete(v.id, e)}
                        disabled={deleting === v.id}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className={styles.pagination}>
          <button
            className={styles.pageBtn}
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            <ChevronLeft size={14} />
          </button>
          <span className={styles.pageInfo}>
            {page} / {data.pages}
          </span>
          <button
            className={styles.pageBtn}
            onClick={() => setPage(p => Math.min(data.pages, p + 1))}
            disabled={page === data.pages}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  )
}
