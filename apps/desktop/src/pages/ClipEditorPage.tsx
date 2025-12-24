import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  Download,
  Layers,
  Type,
  Save,
  Check,
} from 'lucide-react';

import { useLayoutEditorStore, useSubtitleStyleStore, useToastStore } from '@/store';
import { api } from '@/lib/api';
import { ExportModal } from '@/components/export/ExportModal';
import { TemplateStudio } from '@/components/editor/TemplateStudio';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { Timeline } from '@/components/editor/Timeline';
import { Canvas9x16 } from '@/components/editor/Canvas9x16';

interface Project {
  id: string;
  name: string;
  duration?: number;
}

interface Segment {
  id: string;
  start_time: number;
  end_time: number;
  duration: number;
  transcript?: string;
  topic_label?: string;
  hook_text?: string;
  score?: { total: number };
}

export default function ClipEditorPage() {
  useKeyboardShortcuts();
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { addToast } = useToastStore();

  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasContainerRef = useRef<HTMLDivElement>(null);

  // State
  const [project, setProject] = useState<Project | null>(null);
  const [timeline, setTimeline] = useState<any>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [selectedSegment, setSelectedSegment] = useState<Segment | null>(null);
  const [loading, setLoading] = useState(true);

  // Playback
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(0);

  // Stores
  const { zones, selectedZoneId, presetName, setZones, updateZone, setSelectedZone, applyPreset } = useLayoutEditorStore();
  const { style: subtitleStyle, presetName: subtitlePreset, setStyle: setSubtitleStyle, applyPreset: applySubtitlePreset } = useSubtitleStyleStore();

  // Active panel
  const [activePanel, setActivePanel] = useState<'layout' | 'subtitles' | 'templates'>('layout');
  const [showExportModal, setShowExportModal] = useState(false);

  // Canvas dimensions (9:16 ratio)
  const CANVAS_WIDTH = 360;
  const CANVAS_HEIGHT = 640;

  // Derived data
  const clipDuration = trimEnd - trimStart || (selectedSegment?.duration || 0);
  const audioLayer = timeline?.layers?.find((l: any) => l.type === 'audio_energy');
  // Normalize waveform data to number[]
  const waveformData = audioLayer?.data?.map((d: any) => typeof d === 'number' ? d : d.value) || [];
  const faceDetections = timeline?.faceDetections || [];

  const handleExport = async (options: any) => {
    if (!selectedSegment || !project) return;
    try {
      const response = await api.exportSegment(project.id, {
        segmentId: selectedSegment.id,
        variant: 'A',
        platform: 'tiktok',
        includeCaptions: options.includeSubtitles,
        includeCover: options.exportCover,
        includeMetadata: options.exportMetadata,
        includePost: false,
        useNvenc: true,
      });
      
      if (response.data?.jobId) {
        addToast({
          type: 'success',
          title: 'Export lancé 🚀',
          message: 'Votre clip a été ajouté à la file d\'attente'
        });
        setShowExportModal(false);
      }
    } catch (e) {
      console.error(e);
      addToast({
        type: 'error',
        title: 'Erreur',
        message: 'Impossible de lancer l\'export'
      });
    }
  };

  // Load data
  useEffect(() => {
    async function load() {
      if (!projectId) return;
      setLoading(true);
      try {
        const [projectRes, segmentsRes, timelineRes] = await Promise.all([
          api.getProject(projectId),
          api.getSegments(projectId),
          api.getTimeline(projectId),
        ]);
        setProject(projectRes.data);
        setTimeline(timelineRes.data);
        const segs = segmentsRes.data?.items || [];
        setSegments(segs);

        // Select segment from URL or first one
        const segmentId = searchParams.get('segment');
        const seg = segmentId ? segs.find((s: Segment) => s.id === segmentId) : segs[0];
        if (seg) {
          setSelectedSegment(seg);
          setTrimStart(seg.start_time);
          setTrimEnd(seg.end_time);
        }
      } catch (err) {
        console.error('Failed to load:', err);
        addToast({ type: 'error', title: 'Erreur', message: 'Impossible de charger le projet' });
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [projectId, searchParams, addToast]);

  // Sync video time with trim range
  useEffect(() => {
    if (videoRef.current && selectedSegment) {
      videoRef.current.currentTime = trimStart;
      setCurrentTime(trimStart);
    }
  }, [selectedSegment, trimStart]);

  // Video time update
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const onTimeUpdate = () => {
      const time = video.currentTime;
      setCurrentTime(time);
      // Loop within trim range
      if (time >= trimEnd) {
        video.currentTime = trimStart;
      }
    };
    const onEnded = () => setIsPlaying(false);

    video.addEventListener('timeupdate', onTimeUpdate);
    video.addEventListener('ended', onEnded);
    return () => {
      video.removeEventListener('timeupdate', onTimeUpdate);
      video.removeEventListener('ended', onEnded);
    };
  }, [trimStart, trimEnd]);

  // Playback controls
  const handlePlayPause = useCallback(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  }, [isPlaying]);

  const handleSeek = useCallback((time: number) => {
    const clampedTime = Math.max(trimStart, Math.min(trimEnd, time));
    if (videoRef.current) {
      videoRef.current.currentTime = clampedTime;
    }
    setCurrentTime(clampedTime);
  }, [trimStart, trimEnd]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      switch (e.key) {
        case ' ':
          e.preventDefault();
          handlePlayPause();
          break;
        case 'ArrowLeft':
          handleSeek(currentTime - (e.shiftKey ? 5 : 1));
          break;
        case 'ArrowRight':
          handleSeek(currentTime + (e.shiftKey ? 5 : 1));
          break;
        case 'm':
          setIsMuted((m) => !m);
          break;
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [currentTime, handlePlayPause, handleSeek]);

  // Handle zone drag
  const handleZoneDrag = useCallback((zoneId: string, deltaX: number, deltaY: number) => {
    const zone = zones.find((z) => z.id === zoneId);
    if (!zone) return;
    
    const newX = Math.max(0, Math.min(100 - zone.width, zone.x + (deltaX / CANVAS_WIDTH) * 100));
    const newY = Math.max(0, Math.min(100 - zone.height, zone.y + (deltaY / CANVAS_HEIGHT) * 100));
    
    updateZone(zoneId, { x: newX, y: newY });
  }, [zones, updateZone]);

  // Handle zone resize
  const handleZoneResize = useCallback((zoneId: string, corner: string, deltaX: number, deltaY: number) => {
    const zone = zones.find((z) => z.id === zoneId);
    if (!zone) return;

    const dw = (deltaX / CANVAS_WIDTH) * 100;
    const dh = (deltaY / CANVAS_HEIGHT) * 100;

    let newX = zone.x;
    let newY = zone.y;
    let newW = zone.width;
    let newH = zone.height;

    if (corner.includes('right')) {
      newW = Math.max(10, Math.min(100 - zone.x, zone.width + dw));
    }
    if (corner.includes('left')) {
      const maxDelta = zone.width - 10;
      const clampedDw = Math.max(-maxDelta, Math.min(zone.x, -dw));
      newX = zone.x - clampedDw;
      newW = zone.width + clampedDw;
    }
    if (corner.includes('bottom')) {
      newH = Math.max(10, Math.min(100 - zone.y, zone.height + dh));
    }
    if (corner.includes('top')) {
      const maxDelta = zone.height - 10;
      const clampedDh = Math.max(-maxDelta, Math.min(zone.y, -dh));
      newY = zone.y - clampedDh;
      newH = zone.height + clampedDh;
    }

    updateZone(zoneId, { x: newX, y: newY, width: newW, height: newH });
  }, [zones, updateZone]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[var(--bg-primary)]">
        <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-[var(--bg-primary)]">
        <p className="text-[var(--text-muted)]">Projet non trouvé</p>
        <button className="mt-4 btn" onClick={() => navigate('/')}>Retour</button>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-[#0a0a0a] text-white overflow-hidden">
      {/* Header */}
      <header className="h-14 flex items-center justify-between px-4 border-b border-white/10 bg-[#111] flex-shrink-0">
        <div className="flex items-center gap-3">
          <button
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
            onClick={() => navigate(`/project/${projectId}`)}
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="font-semibold">{project.name}</h1>
            <p className="text-xs text-gray-400">
              {selectedSegment?.topic_label || 'Éditeur de clip'} • {formatDuration(clipDuration)}
            </p>
          </div>
        </div>

        {/* Segment selector */}
        <div className="flex items-center gap-4">
          <select
            value={selectedSegment?.id || ''}
            onChange={(e) => {
              const seg = segments.find((s) => s.id === e.target.value);
              if (seg) {
                setSelectedSegment(seg);
                setTrimStart(seg.start_time);
                setTrimEnd(seg.end_time);
              }
            }}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm"
          >
            {segments.map((seg) => (
              <option key={seg.id} value={seg.id}>
                {seg.topic_label || 'Segment'} ({formatDuration(seg.duration)}) - Score: {seg.score?.total || 0}
              </option>
            ))}
          </select>

          <button
            className="px-4 py-2 bg-green-500 hover:bg-green-600 rounded-lg font-medium flex items-center gap-2 transition-colors"
            onClick={() => setShowExportModal(true)}
          >
            <Download className="w-4 h-4" />
            Exporter
          </button>
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT: Mini segment list */}
        <div className="w-48 border-r border-white/10 bg-[#0d0d0d] flex flex-col">
          <div className="p-3 border-b border-white/10">
            <h3 className="text-sm font-medium text-gray-400">Segments</h3>
          </div>
          <div className="flex-1 overflow-auto p-2 space-y-1">
            {segments.map((seg) => (
              <button
                key={seg.id}
                onClick={() => {
                  setSelectedSegment(seg);
                  setTrimStart(seg.start_time);
                  setTrimEnd(seg.end_time);
                }}
                className={`w-full p-2 rounded-lg text-left text-xs transition-colors ${
                  selectedSegment?.id === seg.id
                    ? 'bg-blue-500/20 border border-blue-500'
                    : 'hover:bg-white/5 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold ${
                    (seg.score?.total || 0) >= 60 ? 'bg-green-500' : 'bg-gray-600'
                  }`}>
                    {seg.score?.total || 0}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="truncate font-medium">{seg.topic_label || 'Segment'}</div>
                    <div className="text-gray-500">{formatDuration(seg.duration)}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* CENTER: Canvas Preview */}
        <div className="flex-1 flex flex-col bg-[#080808]">
          {/* Canvas area */}
          <div className="flex-1 flex items-center justify-center p-6">
            <div className="relative" style={{ width: CANVAS_WIDTH, height: CANVAS_HEIGHT }}>
              <Canvas9x16
                videoSrc={`http://localhost:8420/media/${projectId}/proxy`}
                currentTime={currentTime}
                isPlaying={isPlaying}
                currentSubtitle={selectedSegment?.transcript ? getCurrentSubtitle(selectedSegment.transcript, currentTime - trimStart, clipDuration) : undefined}
                faceDetections={faceDetections}
                onTimeUpdate={(time) => {
                  setCurrentTime(time);
                  if (time >= trimEnd) {
                    setCurrentTime(trimStart);
                  }
                }}
                onPlayPause={() => setIsPlaying(!isPlaying)}
              />

              {/* Format badge */}
              <div className="absolute -top-8 left-0 text-xs text-gray-500 font-mono">
                9:16 • 1080×1920
              </div>
            </div>
          </div>

          {/* Controls */}
          <div className="h-32 border-t border-white/10 bg-[#0d0d0d] p-4">
            {/* Transport controls */}
            <div className="flex items-center justify-center gap-4 mb-4">
              <button
                className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                onClick={() => handleSeek(trimStart)}
              >
                <SkipBack className="w-5 h-5" />
              </button>
              <button
                className="p-3 rounded-full bg-white text-black hover:bg-gray-200 transition-colors"
                onClick={handlePlayPause}
              >
                {isPlaying ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 ml-0.5" />}
              </button>
              <button
                className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                onClick={() => handleSeek(trimEnd)}
              >
                <SkipForward className="w-5 h-5" />
              </button>
              <button
                className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                onClick={() => setIsMuted(!isMuted)}
              >
                {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
              </button>
              <span className="text-sm font-mono text-gray-400 ml-4">
                {formatTime(currentTime - trimStart)} / {formatTime(clipDuration)}
              </span>
            </div>

            {/* Timeline */}
            <Timeline
              duration={clipDuration}
              waveformData={waveformData}
              onSeek={handleSeek}
            />
          </div>
        </div>

        {/* RIGHT: Layout & Subtitle controls */}
        <div className="w-80 border-l border-white/10 bg-[#0d0d0d] flex flex-col">
          {/* Tabs */}
          <div className="flex border-b border-white/10">
            <button
              className={`flex-1 py-3 text-sm font-medium flex items-center justify-center gap-2 border-b-2 transition-colors ${
                activePanel === 'layout' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400'
              }`}
              onClick={() => setActivePanel('layout')}
            >
              <Layers className="w-4 h-4" /> Layout
            </button>
            <button
              className={`flex-1 py-3 text-sm font-medium flex items-center justify-center gap-2 border-b-2 transition-colors ${
                activePanel === 'subtitles' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400'
              }`}
              onClick={() => setActivePanel('subtitles')}
            >
              <Type className="w-4 h-4" /> Sous-titres
            </button>
            <button
              className={`flex-1 py-3 text-sm font-medium flex items-center justify-center gap-2 border-b-2 transition-colors ${
                activePanel === 'templates' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400'
              }`}
              onClick={() => setActivePanel('templates')}
            >
              <Save className="w-4 h-4" /> Templates
            </button>
          </div>

          {/* Panel content */}
          <div className="flex-1 overflow-auto p-4">
            {activePanel === 'layout' && (
              <LayoutPanel
                zones={zones}
                selectedZoneId={selectedZoneId}
                presetName={presetName}
                onZoneSelect={setSelectedZone}
                onZoneUpdate={updateZone}
                onApplyPreset={applyPreset}
              />
            )}
            {activePanel === 'subtitles' && (
              <SubtitlePanel
                style={subtitleStyle}
                presetName={subtitlePreset}
                onStyleChange={setSubtitleStyle}
                onApplyPreset={applySubtitlePreset}
              />
            )}
            {activePanel === 'templates' && (
              <TemplateStudio />
            )}
          </div>
        </div>
      </div>

      {/* Export Modal */}
      <ExportModal
        isOpen={showExportModal}
        onClose={() => setShowExportModal(false)}
        segmentName={selectedSegment?.topic_label || 'Segment'}
        duration={clipDuration}
        onExport={handleExport}
      />
    </div>
  );
}

// Zone renderer with drag & resize
function ZoneRenderer({
  zone,
  videoRef,
  canvasWidth,
  canvasHeight,
  isSelected,
  onSelect,
  onDrag,
  onResize,
}: {
  zone: { id: string; type: string; x: number; y: number; width: number; height: number };
  videoRef: React.RefObject<HTMLVideoElement>;
  canvasWidth: number;
  canvasHeight: number;
  isSelected: boolean;
  onSelect: () => void;
  onDrag: (dx: number, dy: number) => void;
  onResize: (corner: string, dx: number, dy: number) => void;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState<string | null>(null);
  const lastPos = useRef({ x: 0, y: 0 });

  const style = {
    left: `${zone.x}%`,
    top: `${zone.y}%`,
    width: `${zone.width}%`,
    height: `${zone.height}%`,
  };

  const handleMouseDown = (e: React.MouseEvent, action: 'drag' | string) => {
    e.stopPropagation();
    onSelect();
    lastPos.current = { x: e.clientX, y: e.clientY };
    if (action === 'drag') {
      setIsDragging(true);
    } else {
      setIsResizing(action);
    }
  };

  useEffect(() => {
    if (!isDragging && !isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - lastPos.current.x;
      const dy = e.clientY - lastPos.current.y;
      lastPos.current = { x: e.clientX, y: e.clientY };

      if (isDragging) {
        onDrag(dx, dy);
      } else if (isResizing) {
        onResize(isResizing, dx, dy);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      setIsResizing(null);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, isResizing, onDrag, onResize]);

  const borderColor = zone.type === 'facecam' ? 'border-purple-500' : 'border-blue-500';
  const bgColor = zone.type === 'facecam' ? 'bg-purple-500/20' : 'bg-blue-500/20';

  return (
    <div
      className={`absolute overflow-hidden transition-shadow ${isSelected ? 'ring-2 ring-white z-10' : ''}`}
      style={style}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
    >
      {/* Video crop */}
      <div className={`absolute inset-0 ${bgColor} flex items-center justify-center`}>
        {videoRef.current && (
          <video
            className="w-full h-full object-cover"
            src={videoRef.current.src}
            ref={(el) => {
              if (el && videoRef.current) {
                el.currentTime = videoRef.current.currentTime;
                el.muted = true;
                // Sync playback
                const sync = () => {
                  if (videoRef.current) el.currentTime = videoRef.current.currentTime;
                };
                videoRef.current.addEventListener('timeupdate', sync);
              }
            }}
          />
        )}
      </div>

      {/* Label */}
      <div className={`absolute top-1 left-1 px-2 py-0.5 rounded text-xs font-medium uppercase ${
        zone.type === 'facecam' ? 'bg-purple-500' : 'bg-blue-500'
      }`}>
        {zone.type}
      </div>

      {/* Selection handles */}
      {isSelected && (
        <>
          {/* Drag handle */}
          <div
            className="absolute inset-0 cursor-move"
            onMouseDown={(e) => handleMouseDown(e, 'drag')}
          />

          {/* Resize corners */}
          {['top-left', 'top-right', 'bottom-left', 'bottom-right'].map((corner) => (
            <div
              key={corner}
              className={`absolute w-3 h-3 bg-white rounded-sm cursor-${corner.replace('-', '')}-resize`}
              style={{
                [corner.includes('top') ? 'top' : 'bottom']: '-4px',
                [corner.includes('left') ? 'left' : 'right']: '-4px',
              }}
              onMouseDown={(e) => handleMouseDown(e, corner)}
            />
          ))}

          {/* Edge handles */}
          {['top', 'bottom', 'left', 'right'].map((edge) => (
            <div
              key={edge}
              className={`absolute bg-white/50 ${
                edge === 'top' || edge === 'bottom'
                  ? 'h-1 left-3 right-3 cursor-ns-resize'
                  : 'w-1 top-3 bottom-3 cursor-ew-resize'
              }`}
              style={{ [edge]: '-2px' }}
              onMouseDown={(e) => handleMouseDown(e, edge)}
            />
          ))}
        </>
      )}
    </div>
  );
}

// Subtitle overlay
function SubtitleOverlay({ text, style }: { text: string; style: any }) {
  if (!text) return null;

  const positionStyle = {
    top: style.position === 'top' ? '10%' : style.position === 'center' ? '50%' : undefined,
    bottom: style.position === 'bottom' ? '15%' : undefined,
    transform: style.position === 'center' ? 'translateY(-50%)' : undefined,
  };

  return (
    <div
      className="absolute left-4 right-4 text-center z-30 pointer-events-none"
      style={positionStyle}
    >
      <span
        style={{
          fontFamily: style.fontFamily,
          fontSize: style.fontSize * 0.5, // Scale down for preview
          fontWeight: style.fontWeight,
          color: style.color,
          backgroundColor: style.backgroundColor,
          WebkitTextStroke: style.outlineWidth > 0 ? `${style.outlineWidth * 0.5}px ${style.outlineColor}` : undefined,
          padding: '4px 12px',
          borderRadius: '4px',
        }}
      >
        {text}
      </span>
    </div>
  );
}

// Layout panel
function LayoutPanel({
  zones,
  selectedZoneId,
  presetName,
  onZoneSelect,
  onZoneUpdate,
  onApplyPreset,
}: {
  zones: any[];
  selectedZoneId: string | null;
  presetName: string;
  onZoneSelect: (id: string | null) => void;
  onZoneUpdate: (id: string, updates: any) => void;
  onApplyPreset: (preset: string) => void;
}) {
  const presets = [
    { id: 'facecam-top', label: 'Facecam en haut', icon: '🎥' },
    { id: 'facecam-bottom', label: 'Facecam en bas', icon: '🎬' },
    { id: 'split-50-50', label: '50/50', icon: '⬛' },
    { id: 'pip-corner', label: 'PIP coin', icon: '📺' },
    { id: 'content-only', label: 'Contenu seul', icon: '🖼' },
  ];

  const selectedZone = zones.find((z) => z.id === selectedZoneId);

  return (
    <div className="space-y-6">
      {/* Presets */}
      <div>
        <h4 className="text-sm font-medium text-gray-400 mb-3">Presets</h4>
        <div className="grid grid-cols-2 gap-2">
          {presets.map((preset) => (
            <button
              key={preset.id}
              onClick={() => onApplyPreset(preset.id)}
              className={`p-3 rounded-lg text-left transition-colors ${
                presetName === preset.id
                  ? 'bg-blue-500/20 border border-blue-500'
                  : 'bg-white/5 border border-white/10 hover:bg-white/10'
              }`}
            >
              <span className="text-xl mb-1 block">{preset.icon}</span>
              <span className="text-xs">{preset.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Zones list */}
      <div>
        <h4 className="text-sm font-medium text-gray-400 mb-3">Zones</h4>
        <div className="space-y-2">
          {zones.map((zone) => (
            <button
              key={zone.id}
              onClick={() => onZoneSelect(zone.id)}
              className={`w-full p-3 rounded-lg text-left transition-colors ${
                selectedZoneId === zone.id
                  ? 'bg-white/10 border border-white/20'
                  : 'bg-white/5 border border-transparent hover:bg-white/10'
              }`}
            >
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded ${zone.type === 'facecam' ? 'bg-purple-500' : 'bg-blue-500'}`} />
                <span className="font-medium capitalize">{zone.type}</span>
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {Math.round(zone.x)}%, {Math.round(zone.y)}% • {Math.round(zone.width)}×{Math.round(zone.height)}%
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Selected zone controls */}
      {selectedZone && (
        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-3">
            Zone: {selectedZone.type}
          </h4>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-gray-500">X (%)</label>
                <input
                  type="number"
                  value={Math.round(selectedZone.x)}
                  onChange={(e) => onZoneUpdate(selectedZone.id, { x: Number(e.target.value) })}
                  className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500">Y (%)</label>
                <input
                  type="number"
                  value={Math.round(selectedZone.y)}
                  onChange={(e) => onZoneUpdate(selectedZone.id, { y: Number(e.target.value) })}
                  className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500">Largeur (%)</label>
                <input
                  type="number"
                  value={Math.round(selectedZone.width)}
                  onChange={(e) => onZoneUpdate(selectedZone.id, { width: Number(e.target.value) })}
                  className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500">Hauteur (%)</label>
                <input
                  type="number"
                  value={Math.round(selectedZone.height)}
                  onChange={(e) => onZoneUpdate(selectedZone.id, { height: Number(e.target.value) })}
                  className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tips */}
      <div className="bg-white/5 rounded-lg p-3 text-xs text-gray-400">
        <p className="font-medium text-white mb-1">💡 Astuce</p>
        <p>Glisse les zones sur le canvas pour les repositionner. Utilise les coins pour redimensionner.</p>
      </div>
    </div>
  );
}

// Subtitle panel
function SubtitlePanel({
  style,
  presetName,
  onStyleChange,
  onApplyPreset,
}: {
  style: any;
  presetName: string;
  onStyleChange: (updates: any) => void;
  onApplyPreset: (preset: string) => void;
}) {
  const presets = [
    { id: 'default', label: 'Standard', color: '#FFFFFF' },
    { id: 'mrbeast', label: 'MrBeast', color: '#FF0000' },
    { id: 'minimalist', label: 'Minimaliste', color: '#888888' },
    { id: 'karaoke', label: 'Karaoké', color: '#00BFFF' },
  ];

  const positions = [
    { id: 'top', label: 'Haut' },
    { id: 'center', label: 'Centre' },
    { id: 'bottom', label: 'Bas' },
  ];

  const animations = [
    { id: 'none', label: 'Aucune' },
    { id: 'fade', label: 'Fondu' },
    { id: 'pop', label: 'Pop' },
    { id: 'bounce', label: 'Rebond' },
    { id: 'typewriter', label: 'Machine' },
  ];

  return (
    <div className="space-y-6">
      {/* Presets */}
      <div>
        <h4 className="text-sm font-medium text-gray-400 mb-3">Style</h4>
        <div className="grid grid-cols-2 gap-2">
          {presets.map((preset) => (
            <button
              key={preset.id}
              onClick={() => onApplyPreset(preset.id)}
              className={`p-3 rounded-lg transition-colors ${
                presetName === preset.id
                  ? 'bg-blue-500/20 border border-blue-500'
                  : 'bg-white/5 border border-white/10 hover:bg-white/10'
              }`}
            >
              <div
                className="w-full h-6 rounded mb-2 flex items-center justify-center text-xs font-bold"
                style={{ backgroundColor: preset.color === '#FFFFFF' ? '#333' : preset.color + '30', color: preset.color }}
              >
                Aa
              </div>
              <span className="text-xs">{preset.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Font size */}
      <div>
        <label className="text-sm font-medium text-gray-400 block mb-2">
          Taille: {style.fontSize}px
        </label>
        <input
          type="range"
          min="24"
          max="72"
          value={style.fontSize}
          onChange={(e) => onStyleChange({ fontSize: Number(e.target.value) })}
          className="w-full"
        />
      </div>

      {/* Colors */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 block mb-1">Couleur texte</label>
          <input
            type="color"
            value={style.color}
            onChange={(e) => onStyleChange({ color: e.target.value })}
            className="w-full h-8 rounded cursor-pointer"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Couleur highlight</label>
          <input
            type="color"
            value={style.highlightColor}
            onChange={(e) => onStyleChange({ highlightColor: e.target.value })}
            className="w-full h-8 rounded cursor-pointer"
          />
        </div>
      </div>

      {/* Position */}
      <div>
        <label className="text-sm font-medium text-gray-400 block mb-2">Position</label>
        <div className="flex gap-2">
          {positions.map((pos) => (
            <button
              key={pos.id}
              onClick={() => onStyleChange({ position: pos.id })}
              className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
                style.position === pos.id
                  ? 'bg-blue-500 text-white'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10'
              }`}
            >
              {pos.label}
            </button>
          ))}
        </div>
      </div>

      {/* Animation */}
      <div>
        <label className="text-sm font-medium text-gray-400 block mb-2">Animation</label>
        <select
          value={style.animation}
          onChange={(e) => onStyleChange({ animation: e.target.value })}
          className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
        >
          {animations.map((anim) => (
            <option key={anim.id} value={anim.id}>{anim.label}</option>
          ))}
        </select>
      </div>

      {/* Outline */}
      <div>
        <label className="text-sm font-medium text-gray-400 block mb-2">
          Contour: {style.outlineWidth}px
        </label>
        <input
          type="range"
          min="0"
          max="6"
          value={style.outlineWidth}
          onChange={(e) => onStyleChange({ outlineWidth: Number(e.target.value) })}
          className="w-full"
        />
      </div>
    </div>
  );
}

// Helper: get current subtitle word
function getCurrentSubtitle(transcript: string, time: number, duration: number): string {
  if (!transcript || duration <= 0) return '';
  const words = transcript.split(' ');
  const wordsPerSecond = words.length / duration;
  const wordIndex = Math.floor(time * wordsPerSecond);
  
  // Show a few words around current position
  const start = Math.max(0, wordIndex - 2);
  const end = Math.min(words.length, wordIndex + 5);
  return words.slice(start, end).join(' ');
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}m ${secs}s`;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
