import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchPendingClips, approveClip, rejectClip, submitReview, getClipVideoUrl, type QueuedClip } from './api';

/** Score badge color */
function scoreColor(score: number): string {
  if (score >= 80) return 'text-forge-green';
  if (score >= 60) return 'text-forge-yellow';
  return 'text-forge-red';
}

function scoreBg(score: number): string {
  if (score >= 80) return 'bg-forge-green/20 border-forge-green/40';
  if (score >= 60) return 'bg-forge-yellow/20 border-forge-yellow/40';
  return 'bg-forge-red/20 border-forge-red/40';
}

/** Single clip card (full-screen vertical video) */
function ClipCard({
  clip,
  active,
  onApprove,
  onReject,
}: {
  clip: QueuedClip;
  active: boolean;
  onApprove: (clip: QueuedClip) => void;
  onReject: (clip: QueuedClip) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!videoRef.current) return;
    if (active) {
      videoRef.current.currentTime = 0;
      videoRef.current.play().then(() => setPlaying(true)).catch(() => {});
    } else {
      videoRef.current.pause();
      setPlaying(false);
    }
  }, [active]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (playing) {
      videoRef.current.pause();
      setPlaying(false);
    } else {
      videoRef.current.play().then(() => setPlaying(true)).catch(() => {});
    }
  };

  return (
    <div className="relative w-full h-full snap-start snap-always flex-shrink-0">
      {/* Video */}
      <video
        ref={videoRef}
        src={getClipVideoUrl(clip.id)}
        aria-label={`Aperçu vidéo : ${clip.title || 'Clip sans titre'}`}
        className="w-full h-full object-cover"
        loop
        muted={false}
        playsInline
        preload={active ? 'auto' : 'metadata'}
        onClick={togglePlay}
      />

      {/* Play/Pause indicator */}
      {!playing && active && (
        <div aria-hidden="true" className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-20 h-20 rounded-full bg-black/50 flex items-center justify-center">
            <svg className="w-10 h-10 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          </div>
        </div>
      )}

      {/* Top bar: score + channel */}
      <div className="absolute top-0 left-0 right-0 safe-top px-4 pt-3 pb-8 bg-gradient-to-b from-black/70 to-transparent">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium opacity-80">{clip.channelName || 'FORGE'}</span>
          <div className={`px-3 py-1 rounded-full border text-sm font-bold ${scoreBg(clip.viralScore)} ${scoreColor(clip.viralScore)}`}>
            {Math.round(clip.viralScore)}
          </div>
        </div>
      </div>

      {/* Bottom bar: title + actions */}
      <div className="absolute bottom-0 left-0 right-0 safe-bottom px-4 pb-4 pt-16 bg-gradient-to-t from-black/80 to-transparent">
        {/* Title & description */}
        <div className="mb-4">
          <h2 className="text-lg font-bold leading-tight line-clamp-2">
            {clip.title || 'Untitled Clip'}
          </h2>
          {clip.description && (
            <p className="text-sm text-white/60 mt-1 line-clamp-1">{clip.description}</p>
          )}
          {clip.hashtags.length > 0 && (
            <p className="text-xs text-forge-cyan mt-1 line-clamp-1">
              {clip.hashtags.slice(0, 5).join(' ')}
            </p>
          )}
          <p className="text-xs text-white/40 mt-1">
            {Math.round(clip.duration)}s
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => onReject(clip)}
            className="flex-1 py-3 rounded-xl bg-forge-red/20 border border-forge-red/40 text-forge-red font-bold text-base active:scale-95 transition-transform"
          >
            Rejeter
          </button>
          <button
            onClick={() => onApprove(clip)}
            className="flex-1 py-3 rounded-xl bg-forge-green/20 border border-forge-green/40 text-forge-green font-bold text-base active:scale-95 transition-transform"
          >
            Publier
          </button>
        </div>
      </div>
    </div>
  );
}

/** Empty state */
function EmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center px-8 text-center">
      <div className="text-6xl mb-4">
        <svg aria-hidden="true" className="w-20 h-20 text-forge-cyan/30 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
        </svg>
      </div>
      <h2 className="text-xl font-bold text-white/80 mb-2">Aucun clip en attente</h2>
      <p className="text-sm text-white/40">
        Les clips appara&icirc;tront ici quand le pipeline aura termin&eacute; l'analyse.
      </p>
    </div>
  );
}

/** Main App */
export default function App() {
  const [clips, setClips] = useState<QueuedClip[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeIndex, setActiveIndex] = useState(0);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);

  // Channel can be overridden via ?channel= query parameter or VITE_CHANNEL env var
  const channel = new URLSearchParams(window.location.search).get('channel')
    ?? import.meta.env.VITE_CHANNEL
    ?? undefined;

  const loadClips = useCallback(async () => {
    try {
      const data = await fetchPendingClips(channel);
      setClips(data);
    } catch (err) {
      console.error('Failed to load clips:', err);
    } finally {
      setLoading(false);
    }
  }, [channel]);

  useEffect(() => {
    loadClips();
    // Refresh every 60 seconds
    const interval = setInterval(loadClips, 60000);
    return () => clearInterval(interval);
  }, [loadClips]);

  // Track active clip via scroll position
  useEffect(() => {
    const feed = feedRef.current;
    if (!feed) return;

    const handleScroll = () => {
      const index = Math.round(feed.scrollTop / feed.clientHeight);
      setActiveIndex(index);
    };

    feed.addEventListener('scroll', handleScroll, { passive: true });
    return () => feed.removeEventListener('scroll', handleScroll);
  }, []);

  const showFeedback = (msg: string) => {
    setActionFeedback(msg);
    setTimeout(() => setActionFeedback(null), 1500);
  };

  const handleApprove = async (clip: QueuedClip) => {
    try {
      await approveClip(clip.id, {
        title: clip.title || undefined,
        hashtags: clip.hashtags,
      });
      await submitReview({
        segmentId: clip.segmentId,
        projectId: clip.projectId,
        rating: 4,
        qualityTags: ['publishable'],
        publishDecision: 'approve',
      });
      showFeedback('Approuve !');
      setClips((prev) => prev.filter((c) => c.id !== clip.id));
    } catch (err) {
      console.error('Approve failed:', err);
    }
  };

  const handleReject = async (clip: QueuedClip) => {
    try {
      await rejectClip(clip.id);
      await submitReview({
        segmentId: clip.segmentId,
        projectId: clip.projectId,
        rating: 2,
        qualityTags: ['skip'],
        publishDecision: 'reject',
      });
      showFeedback('Rejete');
      setClips((prev) => prev.filter((c) => c.id !== clip.id));
    } catch (err) {
      console.error('Reject failed:', err);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-forge-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (clips.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="h-full relative">
      {/* Vertical scroll feed */}
      <div
        ref={feedRef}
        className="clip-feed h-full overflow-y-scroll snap-y snap-mandatory"
      >
        {clips.map((clip, index) => (
          <div key={clip.id} className="h-full w-full">
            <ClipCard
              clip={clip}
              active={index === activeIndex}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          </div>
        ))}
      </div>

      {/* Clip counter */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 safe-top">
        <span className="text-xs text-white/50 bg-black/40 px-3 py-1 rounded-full">
          {activeIndex + 1} / {clips.length}
        </span>
      </div>

      {/* Action feedback toast */}
      {actionFeedback && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
          <div className={`px-8 py-4 rounded-2xl text-xl font-bold ${
            actionFeedback.includes('Approuve')
              ? 'bg-forge-green/90 text-black'
              : 'bg-forge-red/90 text-white'
          }`}>
            {actionFeedback}
          </div>
        </div>
      )}
    </div>
  );
}
