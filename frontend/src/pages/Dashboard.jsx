import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Flame, Wind, Film, CheckCircle, Clock, AlertTriangle, ArrowRight, TrendingUp } from 'lucide-react'
import { getOverviewStats, listVideos } from '../services/api.js'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './Dashboard.module.css'

const STATUS_CONFIG = {
  completed: { label: 'Обработано', color: 'safe', icon: CheckCircle },
  processing: { label: 'Обрабатывается', color: 'warn', icon: Clock },
  uploaded: { label: 'Ожидает', color: 'smoke', icon: Clock },
  failed: { label: 'Ошибка', color: 'fire', icon: AlertTriangle },
}

const LABEL_CONFIG = {
  fire: { label: 'ОГОНЬ', color: 'fire' },
  smoke: { label: 'ДЫМ', color: 'smoke' },
  fire_and_smoke: { label: 'ОГОНЬ + ДЫМ', color: 'fire' },
  none: { label: 'ЧИСТО', color: 'safe' },
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [recentVideos, setRecentVideos] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [statsRes, videosRes] = await Promise.all([
          getOverviewStats(),
          listVideos(1, 5),
        ])
        setStats(statsRes.data)
        setRecentVideos(videosRes.data.items)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [])

  if (loading) return <LoadingSkeleton />

  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>
          <span className={styles.titleAccent}>СИСТЕМА</span> МОНИТОРИНГА
        </h1>
        <p className={styles.pageSubtitle}>Детекция огня и дыма — YOLO</p>
      </div>

      {/* Stats Grid */}
      <div className={styles.statsGrid}>
        <StatCard
          icon={Film}
          label="Всего видео"
          value={stats?.total_videos ?? 0}
          color="primary"
        />
        <StatCard
          icon={CheckCircle}
          label="Обработано"
          value={stats?.completed ?? 0}
          color="safe"
        />
        <StatCard
          icon={Flame}
          label="Детекций огня"
          value={stats?.total_fire_detections ?? 0}
          color="fire"
          pulse
        />
        <StatCard
          icon={Wind}
          label="Детекций дыма"
          value={stats?.total_smoke_detections ?? 0}
          color="smoke"
        />
      </div>

      {/* Processing queue */}
      {stats?.processing > 0 && (
        <div className={styles.alertBanner}>
          <Clock size={14} className={styles.alertIcon} />
          <span>{stats.processing} видео сейчас обрабатывается...</span>
          <div className={styles.alertProgress} />
        </div>
      )}

      {/* Recent Videos */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>ПОСЛЕДНИЕ ВИДЕО</h2>
          <Link to="/videos" className={styles.sectionLink}>
            Все видео <ArrowRight size={12} />
          </Link>
        </div>

        {recentVideos.length === 0 ? (
          <EmptyState />
        ) : (
          <div className={styles.videoList}>
            {recentVideos.map((v) => (
              <VideoRow key={v.id} video={v} />
            ))}
          </div>
        )}
      </div>

      {/* Quick Upload CTA */}
      <Link to="/upload" className={styles.uploadCta}>
        <div className={styles.uploadCtaLeft}>
          <Film size={20} />
          <div>
            <div className={styles.uploadCtaTitle}>Загрузить видео</div>
            <div className={styles.uploadCtaText}>MP4, AVI, MOV, MKV — до 500 МБ</div>
          </div>
        </div>
        <ArrowRight size={18} />
      </Link>
    </div>
  )
}

function StatCard({ icon: Icon, label, value, color, pulse }) {
  return (
    <div className={`${styles.statCard} ${styles[`stat_${color}`]}`}>
      <div className={styles.statIconWrap}>
        <Icon size={20} className={`${styles.statIcon} ${pulse ? styles.pulseFire : ''}`} />
      </div>
      <div className={styles.statValue}>{value.toLocaleString('ru-RU')}</div>
      <div className={styles.statLabel}>{label}</div>
    </div>
  )
}

function VideoRow({ video }) {
  const cfg = STATUS_CONFIG[video.status] || STATUS_CONFIG.uploaded
  const StatusIcon = cfg.icon
  const labelCfg = LABEL_CONFIG[video.summary?.overall_label] || null

  return (
    <Link to={`/videos/${video.id}`} className={styles.videoRow}>
      <div className={styles.videoRowLeft}>
        <div className={`${styles.videoStatus} ${styles[`status_${cfg.color}`]}`}>
          <StatusIcon size={12} />
        </div>
        <div>
          <div className={styles.videoName}>{video.original_filename}</div>
          <div className={styles.videoMeta}>
            {video.duration ? `${Math.round(video.duration)}с` : '—'}
            {' · '}
            {video.created_at
              ? formatDistanceToNow(new Date(video.created_at), { addSuffix: true, locale: ru })
              : '—'}
          </div>
        </div>
      </div>
      <div className={styles.videoRowRight}>
        {labelCfg && (
          <span className={`${styles.labelBadge} ${styles[`badge_${labelCfg.color}`]}`}>
            {labelCfg.label}
          </span>
        )}
        <ArrowRight size={14} className={styles.videoArrow} />
      </div>
    </Link>
  )
}

function EmptyState() {
  return (
    <div className={styles.empty}>
      <Film size={32} className={styles.emptyIcon} />
      <p>Нет видео. <Link to="/upload">Загрузите первое</Link></p>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className={styles.page}>
      <div className={styles.pageHeader}>
        <div className={styles.skelTitle} />
        <div className={styles.skelSub} />
      </div>
      <div className={styles.statsGrid}>
        {[1,2,3,4].map(i => <div key={i} className={styles.skelCard} />)}
      </div>
    </div>
  )
}
