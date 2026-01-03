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

import { useLayoutEditorStore, useSubtitleStyleStore, useToastStore, useIntroStore, INTRO_PRESETS } from '@/store';
import { api } from '@/lib/api';
import { ExportModal } from '@/components/export/ExportModal';
import { TemplateStudio } from '@/components/editor/TemplateStudio';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { Timeline } from '@/components/editor/Timeline';
import { Canvas9x16 } from '@/components/editor/Canvas9x16';
import { SourcePreview } from '@/components/editor/SourcePreview';
import { WordTiming } from '@/components/editor/KaraokeSubtitles';

interface Project {
  id: string;
  name: string;
  duration?: number;
}

interface Segment {
  id: string;
  startTime: number;
  endTime: number;
  duration: number;
  transcript?: string;
  topicLabel?: string;
  hookText?: string;
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
  const { config: introConfig, setConfig: setIntroConfig, setEnabled: setIntroEnabled, applyPreset: applyIntroPreset } = useIntroStore();

  // Active panel
  const [activePanel, setActivePanel] = useState<'layout' | 'subtitles' | 'intro' | 'templates'>('layout');
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
  
  // Extract word timings from timeline transcript layer
  const transcriptLayer = timeline?.layers?.find((l: any) => l.type === 'transcript');
  const wordTimings: WordTiming[] = transcriptLayer?.words || [];
  
  // Video source info
  const videoSize = timeline?.faceDetections?.[0]?.video_size || { width: 1920, height: 1080 };

  const handleExport = async (options: any) => {
    if (!selectedSegment || !project) return;
    try {
      // Build layoutConfig from editor zones
      const facecamZone = zones.find(z => z.type === 'facecam');
      const contentZone = zones.find(z => z.type === 'content');
      
      const layoutConfig = {
        facecam: facecamZone ? {
          x: facecamZone.x,
          y: facecamZone.y,
          width: facecamZone.width,
          height: facecamZone.height,
          sourceCrop: facecamZone.sourceCrop,
        } : undefined,
        content: contentZone ? {
          x: contentZone.x,
          y: contentZone.y,
          width: contentZone.width,
          height: contentZone.height,
          sourceCrop: contentZone.sourceCrop,
        } : undefined,
        facecamRatio: facecamZone ? facecamZone.height / 100 : 0.4,
      };
      
      const response = await api.exportSegment(project.id, {
        segmentId: selectedSegment.id,
        variant: 'A',
        platform: 'tiktok',
        includeCaptions: options.includeSubtitles,
        burnSubtitles: options.burnSubtitles,
        includeCover: options.exportCover,
        includeMetadata: options.exportMetadata,
        includePost: false,
        useNvenc: true,
        captionStyle: options.captionStyle,
        layoutConfig,
        introConfig: introConfig.enabled ? introConfig : undefined,
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
          setTrimStart(seg.startTime);
          setTrimEnd(seg.endTime);
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

  // Sync video time with selected segment
  useEffect(() => {
    if (selectedSegment) {
      setCurrentTime(trimStart);
    }
  }, [selectedSegment, trimStart]);

  // Playback controls - Canvas9x16 manages actual playback via isPlaying state
  const handlePlayPause = useCallback(() => {
    setIsPlaying((prev) => !prev);
  }, []);

  const handleSeek = useCallback((time: number) => {
    const clampedTime = Math.max(trimStart, Math.min(trimEnd || 9999, time));
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
              {selectedSegment?.topicLabel || 'Éditeur de clip'} • {formatDuration(clipDuration)}
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
                setTrimStart(seg.startTime);
                setTrimEnd(seg.endTime);
              }
            }}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm"
          >
            {segments.map((seg) => (
              <option key={seg.id} value={seg.id}>
                {seg.topicLabel || 'Segment'} ({formatDuration(seg.duration)}) - Score: {seg.score?.total || 0}
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
                  setTrimStart(seg.startTime);
                  setTrimEnd(seg.endTime);
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
                    <div className="truncate font-medium">{seg.topicLabel || 'Segment'}</div>
                    <div className="text-gray-500">{formatDuration(seg.duration)}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* CENTER: Source + Canvas Preview */}
        <div className="flex-1 flex flex-col bg-[#080808]">
          {/* Canvas area with source and output */}
          <div className="flex-1 flex gap-4 p-4">
            {/* Source Preview (16:9) */}
            <div className="flex-1 flex flex-col bg-[#111] rounded-xl overflow-hidden border border-white/10">
              <SourcePreview
                videoSrc={`http://localhost:8420/media/${projectId}/proxy`}
                currentTime={currentTime}
                isPlaying={isPlaying}
                videoSize={videoSize}
              />
            </div>
            
            {/* Output Preview (9:16) */}
            <div className="flex flex-col items-center justify-center">
              <div className="text-xs text-gray-500 font-mono mb-2">
                9:16 • 1080×1920
              </div>
              <div className="relative" style={{ width: CANVAS_WIDTH, height: CANVAS_HEIGHT }}>
                <Canvas9x16
                  videoSrc={`http://localhost:8420/media/${projectId}/proxy`}
                  currentTime={currentTime}
                  isPlaying={isPlaying}
                  currentSubtitle={selectedSegment?.transcript || ''}
                  faceDetections={faceDetections}
                  wordTimings={wordTimings.filter(w => w.start >= trimStart && w.end <= trimEnd).map(w => ({
                    ...w,
                    start: w.start - trimStart,
                    end: w.end - trimStart,
                  }))}
                  clipStartTime={trimStart}
                  clipDuration={clipDuration}
                  onTimeUpdate={(time) => {
                    setCurrentTime(time);
                    if (time >= trimEnd) {
                      setCurrentTime(trimStart);
                    }
                  }}
                  onPlayPause={() => setIsPlaying(!isPlaying)}
                />
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
                activePanel === 'intro' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-400'
              }`}
              onClick={() => setActivePanel('intro')}
            >
              <Play className="w-4 h-4" /> Intro
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
            {activePanel === 'intro' && (
              <IntroPanel
                config={introConfig}
                segmentTitle={selectedSegment?.topicLabel || ''}
                onConfigChange={setIntroConfig}
                onApplyPreset={applyIntroPreset}
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
        segmentName={selectedSegment?.topicLabel || 'Segment'}
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
        <div className="space-y-4">
          {/* Target position (9:16 canvas) */}
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">
              Position cible (9:16)
            </h4>
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

          {/* Source crop (16:9 source) */}
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
              Crop source (16:9)
              <span className="text-xs text-blue-400 font-normal">(Glisse sur la vidéo gauche)</span>
            </h4>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-gray-500">X (0-1)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={(selectedZone.sourceCrop?.x ?? 0).toFixed(2)}
                  onChange={(e) => onZoneUpdate(selectedZone.id, { 
                    sourceCrop: { 
                      ...selectedZone.sourceCrop || { x: 0, y: 0, width: 1, height: 1 },
                      x: Math.max(0, Math.min(1, Number(e.target.value)))
                    }
                  })}
                  className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500">Y (0-1)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={(selectedZone.sourceCrop?.y ?? 0).toFixed(2)}
                  onChange={(e) => onZoneUpdate(selectedZone.id, { 
                    sourceCrop: { 
                      ...selectedZone.sourceCrop || { x: 0, y: 0, width: 1, height: 1 },
                      y: Math.max(0, Math.min(1, Number(e.target.value)))
                    }
                  })}
                  className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500">Largeur (0-1)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.1"
                  max="1"
                  value={(selectedZone.sourceCrop?.width ?? 1).toFixed(2)}
                  onChange={(e) => onZoneUpdate(selectedZone.id, { 
                    sourceCrop: { 
                      ...selectedZone.sourceCrop || { x: 0, y: 0, width: 1, height: 1 },
                      width: Math.max(0.1, Math.min(1, Number(e.target.value)))
                    }
                  })}
                  className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500">Hauteur (0-1)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.1"
                  max="1"
                  value={(selectedZone.sourceCrop?.height ?? 1).toFixed(2)}
                  onChange={(e) => onZoneUpdate(selectedZone.id, { 
                    sourceCrop: { 
                      ...selectedZone.sourceCrop || { x: 0, y: 0, width: 1, height: 1 },
                      height: Math.max(0.1, Math.min(1, Number(e.target.value)))
                    }
                  })}
                  className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm"
                />
              </div>
            </div>
            
            {/* Auto-track toggle for facecam */}
            {selectedZone.type === 'facecam' && (
              <label className="flex items-center gap-2 mt-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedZone.autoTrack ?? false}
                  onChange={(e) => onZoneUpdate(selectedZone.id, { autoTrack: e.target.checked })}
                  className="w-4 h-4 rounded bg-white/10 border-white/20"
                />
                <span className="text-xs text-gray-400">Auto-tracking (suit le visage)</span>
              </label>
            )}
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
    { id: 'viral-glow', label: 'Viral Glow', color: '#00FF88' },
    { id: 'wave-gradient', label: 'Wave', color: '#FFD700' },
  ];

  const fonts = [
    { id: 'Inter', label: 'Inter', style: 'font-sans' },
    { id: 'Impact', label: 'Impact', style: 'font-impact' },
    { id: 'Montserrat', label: 'Montserrat', style: 'font-montserrat' },
    { id: 'Poppins', label: 'Poppins', style: 'font-poppins' },
    { id: 'Oswald', label: 'Oswald', style: 'font-oswald' },
    { id: 'Bebas Neue', label: 'Bebas Neue', style: 'font-bebas' },
    { id: 'Bangers', label: 'Bangers', style: 'font-bangers' },
    { id: 'Permanent Marker', label: 'Permanent Marker', style: 'font-marker' },
    { id: 'Anton', label: 'Anton', style: 'font-anton' },
    { id: 'Righteous', label: 'Righteous', style: 'font-righteous' },
  ];

  const positions = [
    { id: 'top', label: 'Haut' },
    { id: 'center', label: 'Centre' },
    { id: 'bottom', label: 'Bas' },
  ];

  const animations = [
    { id: 'none', label: 'Aucune' },
    { id: 'fade', label: 'Fondu' },
    { id: 'pop', label: 'Pop ⭐' },
    { id: 'bounce', label: 'Rebond 🔥' },
    { id: 'glow', label: 'Glow ✨' },
    { id: 'wave', label: 'Wave 🌊' },
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

      {/* Font selector with preview */}
      <div>
        <label className="text-sm font-medium text-gray-400 block mb-2">Police</label>
        <div className="space-y-1 max-h-40 overflow-auto bg-white/5 rounded-lg p-2">
          {fonts.map((font) => (
            <button
              key={font.id}
              onClick={() => onStyleChange({ fontFamily: font.id })}
              className={`w-full p-2 rounded-lg text-left transition-colors flex items-center justify-between ${
                style.fontFamily === font.id
                  ? 'bg-blue-500/30 border border-blue-500'
                  : 'hover:bg-white/10 border border-transparent'
              }`}
            >
              <span 
                className="text-white text-lg"
                style={{ fontFamily: font.id }}
              >
                {font.label}
              </span>
              <span 
                className="text-xs text-gray-500"
                style={{ fontFamily: font.id }}
              >
                Abc
              </span>
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
              onClick={() => onStyleChange({ position: pos.id, positionY: undefined })}
              className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
                style.position === pos.id && !style.positionY
                  ? 'bg-blue-500 text-white'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10'
              }`}
            >
              {pos.label}
            </button>
          ))}
        </div>
      </div>

      {/* Custom Y Position */}
      <div>
        <label className="text-sm font-medium text-gray-400 block mb-2">
          Hauteur personnalisée: {style.positionY ?? 'Auto'}
          {style.positionY && <span className="text-xs text-gray-500 ml-2">(0=haut, 960=milieu, 1920=bas)</span>}
        </label>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min="0"
            max="1920"
            step="10"
            value={style.positionY ?? 960}
            onChange={(e) => onStyleChange({ positionY: Number(e.target.value) })}
            className="flex-1"
          />
          <input
            type="number"
            min="0"
            max="1920"
            value={style.positionY ?? ''}
            placeholder="Auto"
            onChange={(e) => onStyleChange({ positionY: e.target.value ? Number(e.target.value) : undefined })}
            className="w-16 bg-white/5 border border-white/10 rounded px-2 py-1 text-sm text-center"
          />
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>↑ Haut</span>
          <span>Entre cam/content (~750)</span>
          <span>Bas ↓</span>
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

// Intro panel - Enhanced with live preview
function IntroPanel({
  config,
  segmentTitle,
  onConfigChange,
  onApplyPreset,
}: {
  config: any;
  segmentTitle: string;
  onConfigChange: (updates: any) => void;
  onApplyPreset: (preset: string) => void;
}) {
  const [activeSection, setActiveSection] = useState<'style' | 'text' | 'animation'>('style');
  const [animPhase, setAnimPhase] = useState<'hidden' | 'enter' | 'wobble' | 'exit'>('hidden');

  // Initialize title with segment title if empty
  useEffect(() => {
    if (config && !config.title && segmentTitle) {
      onConfigChange({ title: segmentTitle });
    }
  }, [segmentTitle, config]);

  // Guard against undefined config
  if (!config) {
    return (
      <div className="p-4 text-center text-gray-400">
        <p>Chargement de la configuration...</p>
      </div>
    );
  }

  // Trigger preview animation - swoosh style
  const playPreview = () => {
    setAnimPhase('hidden');
    setTimeout(() => setAnimPhase('enter'), 100);
    setTimeout(() => setAnimPhase('wobble'), 600);
    setTimeout(() => setAnimPhase('exit'), (config.duration || 2) * 1000 - 400);
    setTimeout(() => setAnimPhase('hidden'), (config.duration || 2) * 1000 + 300);
  };

  // Get label animation styles for swoosh effect
  const getLabelStyle = (): React.CSSProperties => {
    const baseStyle: React.CSSProperties = {
      transition: 'all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)',
    };
    
    switch (animPhase) {
      case 'hidden':
        return { ...baseStyle, transform: 'translateX(-120%) rotate(-5deg)', opacity: 0 };
      case 'enter':
        return { ...baseStyle, transform: 'translateX(0) rotate(0deg)', opacity: 1 };
      case 'wobble':
        return { 
          ...baseStyle, 
          transform: 'translateX(0) rotate(0deg)', 
          opacity: 1,
          animation: 'wobble 2s ease-in-out infinite',
        };
      case 'exit':
        return { ...baseStyle, transform: 'translateX(120%) rotate(5deg)', opacity: 0, transition: 'all 0.4s ease-in' };
      default:
        return baseStyle;
    }
  };

  // Preset visual configs
  const VISUAL_PRESETS = [
    { key: 'minimal', label: 'Minimal', icon: '◯', gradient: 'from-gray-600 to-gray-800', desc: 'Épuré & pro' },
    { key: 'neon', label: 'Néon', icon: '⚡', gradient: 'from-cyan-500 to-blue-600', desc: 'Vibrant & flashy' },
    { key: 'gaming', label: 'Gaming', icon: '🎮', gradient: 'from-purple-600 to-pink-600', desc: 'Dynamique' },
    { key: 'elegant', label: 'Élégant', icon: '✨', gradient: 'from-amber-500 to-orange-600', desc: 'Raffiné' },
  ];

  // Font options with preview
  const FONTS = [
    { value: 'Inter', label: 'Inter', style: 'font-sans' },
    { value: 'Montserrat', label: 'Montserrat', style: 'font-sans font-bold' },
    { value: 'Space Grotesk', label: 'Space Grotesk', style: 'font-mono' },
    { value: 'Playfair Display', label: 'Playfair', style: 'font-serif italic' },
    { value: 'Oswald', label: 'Oswald', style: 'font-sans uppercase tracking-wider' },
    { value: 'Bebas Neue', label: 'Bebas', style: 'font-sans uppercase tracking-widest' },
  ];

  // Animation options
  const ANIMATIONS = [
    { value: 'fade', label: 'Fondu', icon: '○', desc: 'Apparition douce' },
    { value: 'swoosh', label: 'Swoosh', icon: '➜', desc: 'Étiquette animée' },
    { value: 'zoom', label: 'Zoom', icon: '◎', desc: 'Effet d\'échelle' },
    { value: 'slide', label: 'Glisser', icon: '↑', desc: 'Entrée par le bas' },
  ];

  return (
    <div className="space-y-4">
      {/* CSS for wobble animation */}
      <style>{`
        @keyframes wobble {
          0%, 100% { transform: translateX(0) rotate(0deg); }
          25% { transform: translateX(0) rotate(-1deg); }
          75% { transform: translateX(0) rotate(1deg); }
        }
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>

      {/* Live Preview Card */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-gray-900 to-black border border-white/10">
        {/* Preview container - 9:16 aspect ratio scaled down */}
        <div 
          className="relative mx-auto bg-black overflow-hidden"
          style={{ width: '100%', aspectRatio: '9/12' }}
        >
          {/* Video background simulation (blurred) */}
          <div 
            className="absolute inset-0"
            style={{ 
              background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%)',
              filter: `blur(${config.backgroundBlur || 15}px)`,
              transform: 'scale(1.1)', // Prevent blur edge artifacts
            }}
          />
          
          {/* Overlay for depth */}
          <div className="absolute inset-0 bg-black/30" />
          
          {/* Animated Label/Étiquette */}
          <div className="absolute inset-0 flex items-center justify-center p-3 overflow-hidden">
            <div 
              className="relative"
              style={getLabelStyle()}
            >
              {/* Label background with gradient */}
              <div 
                className="relative px-5 py-4 rounded-2xl shadow-2xl"
                style={{
                  background: `linear-gradient(135deg, ${config.badgeColor || '#00FF88'}15, ${config.titleColor || '#FFFFFF'}10)`,
                  border: `2px solid ${config.badgeColor || '#00FF88'}40`,
                  backdropFilter: 'blur(10px)',
                  boxShadow: `0 10px 40px ${config.badgeColor || '#00FF88'}30, 0 0 60px ${config.badgeColor || '#00FF88'}10`,
                }}
              >
                {/* Shimmer effect */}
                <div 
                  className="absolute inset-0 rounded-2xl opacity-30"
                  style={{
                    background: `linear-gradient(90deg, transparent, ${config.titleColor || '#FFFFFF'}20, transparent)`,
                    backgroundSize: '200% 100%',
                    animation: animPhase === 'wobble' ? 'shimmer 3s infinite' : 'none',
                  }}
                />
                
                {/* Badge/Pseudo at top */}
                {(config.badgeText || '@etostark') && (
                  <div 
                    className="text-center text-xs font-bold uppercase tracking-widest mb-1"
                    style={{ color: config.badgeColor || '#00FF88' }}
                  >
                    {config.badgeText || '@etostark'}
                  </div>
                )}
                
                {/* Title */}
                <h2 
                  className="text-center font-bold leading-tight"
                  style={{ 
                    color: config.titleColor || '#FFFFFF',
                    fontSize: `${Math.min((config.titleSize || 72) / 4, 20)}px`,
                    fontFamily: config.titleFont || 'Montserrat',
                    textShadow: `0 2px 20px ${config.titleColor || '#FFFFFF'}50`,
                  }}
                >
                  {config.title || 'Titre du clip'}
                </h2>
                
                {/* Decorative line */}
                <div 
                  className="mt-2 mx-auto h-0.5 rounded-full"
                  style={{ 
                    width: '60%',
                    background: `linear-gradient(90deg, transparent, ${config.badgeColor || '#00FF88'}, transparent)`,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Duration indicator */}
          <div className="absolute bottom-2 right-2 px-2 py-0.5 bg-black/60 rounded text-[10px] text-white/70">
            {config.duration || 2}s
          </div>
          
          {/* Phase indicator for debug */}
          <div className="absolute bottom-2 left-2 px-2 py-0.5 bg-black/60 rounded text-[10px] text-white/50">
            {animPhase === 'hidden' ? '⏸️' : animPhase === 'enter' ? '➡️' : animPhase === 'wobble' ? '〰️' : '⬅️'}
          </div>
        </div>

        {/* Play preview button */}
        <button
          onClick={playPreview}
          className="absolute top-2 right-2 p-2.5 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 rounded-full transition-all shadow-lg group"
        >
          <Play className="w-4 h-4 text-white group-hover:scale-110 transition-transform" />
        </button>

        {/* Enable toggle overlay */}
        <div className="absolute top-2 left-2">
          <button
            onClick={() => onConfigChange({ enabled: !config.enabled })}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
              config.enabled 
                ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                : 'bg-white/10 text-gray-400 border border-white/10'
            }`}
          >
            <div className={`w-2 h-2 rounded-full ${config.enabled ? 'bg-green-400' : 'bg-gray-500'}`} />
            {config.enabled ? 'Activé' : 'Désactivé'}
          </button>
        </div>
      </div>

      {/* Section tabs */}
      <div className="flex gap-1 p-1 bg-white/5 rounded-lg">
        {[
          { key: 'style', label: '🎨 Style' },
          { key: 'text', label: '✏️ Texte' },
          { key: 'animation', label: '🎬 Anim' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveSection(tab.key as any)}
            className={`flex-1 py-2 px-3 rounded-md text-xs font-medium transition-all ${
              activeSection === tab.key 
                ? 'bg-blue-500 text-white shadow-lg' 
                : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Style Section */}
      {activeSection === 'style' && (
        <div className="space-y-4">
          {/* Visual Presets */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wider block mb-2">Presets</label>
            <div className="grid grid-cols-2 gap-2">
              {VISUAL_PRESETS.map((preset) => (
                <button
                  key={preset.key}
                  onClick={() => onApplyPreset(preset.key)}
                  className={`relative overflow-hidden p-3 rounded-xl border transition-all group ${
                    config.animation === (INTRO_PRESETS as any)[preset.key]?.animation
                      ? 'border-blue-500 ring-2 ring-blue-500/20'
                      : 'border-white/10 hover:border-white/30'
                  }`}
                >
                  <div className={`absolute inset-0 bg-gradient-to-br ${preset.gradient} opacity-20 group-hover:opacity-30 transition-opacity`} />
                  <div className="relative">
                    <span className="text-lg">{preset.icon}</span>
                    <div className="text-sm font-medium text-white mt-1">{preset.label}</div>
                    <div className="text-[10px] text-gray-400">{preset.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Colors */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wider block mb-2">Titre</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={config.titleColor || '#FFFFFF'}
                  onChange={(e) => onConfigChange({ titleColor: e.target.value })}
                  className="w-10 h-10 rounded-lg cursor-pointer border-0 bg-transparent"
                />
                <input
                  type="text"
                  value={config.titleColor || '#FFFFFF'}
                  onChange={(e) => onConfigChange({ titleColor: e.target.value })}
                  className="flex-1 bg-white/5 border border-white/10 rounded-lg px-2 py-1.5 text-xs font-mono"
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wider block mb-2">Badge</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={config.badgeColor || '#00FF88'}
                  onChange={(e) => onConfigChange({ badgeColor: e.target.value })}
                  className="w-10 h-10 rounded-lg cursor-pointer border-0 bg-transparent"
                />
                <input
                  type="text"
                  value={config.badgeColor || '#00FF88'}
                  onChange={(e) => onConfigChange({ badgeColor: e.target.value })}
                  className="flex-1 bg-white/5 border border-white/10 rounded-lg px-2 py-1.5 text-xs font-mono"
                />
              </div>
            </div>
          </div>

          {/* Background blur */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wider">Flou arrière-plan</label>
              <span className="text-xs text-gray-400">{config.backgroundBlur ?? 15}px</span>
            </div>
            <input
              type="range"
              min="0"
              max="40"
              value={config.backgroundBlur ?? 15}
              onChange={(e) => onConfigChange({ backgroundBlur: Number(e.target.value) })}
              className="w-full accent-blue-500"
            />
          </div>
        </div>
      )}

      {/* Text Section */}
      {activeSection === 'text' && (
        <div className="space-y-4">
          {/* Title input */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wider block mb-2">Titre principal</label>
            <input
              type="text"
              value={config.title || ''}
              onChange={(e) => onConfigChange({ title: e.target.value })}
              placeholder="Titre accrocheur..."
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
            />
          </div>

          {/* Badge input */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wider block mb-2">Badge (@pseudo)</label>
            <input
              type="text"
              value={config.badgeText || ''}
              onChange={(e) => onConfigChange({ badgeText: e.target.value })}
              placeholder="@votrepseudo"
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
            />
          </div>

          {/* Font selector */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wider block mb-2">Police</label>
            <div className="grid grid-cols-3 gap-2">
              {FONTS.map((font) => (
                <button
                  key={font.value}
                  onClick={() => onConfigChange({ titleFont: font.value })}
                  className={`p-2 rounded-lg border text-center transition-all ${
                    config.titleFont === font.value
                      ? 'border-blue-500 bg-blue-500/10'
                      : 'border-white/10 hover:border-white/20'
                  }`}
                >
                  <span className={`text-sm ${font.style}`}>{font.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Title size */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wider">Taille</label>
              <span className="text-xs text-gray-400">{config.titleSize || 72}px</span>
            </div>
            <input
              type="range"
              min="48"
              max="120"
              value={config.titleSize || 72}
              onChange={(e) => onConfigChange({ titleSize: Number(e.target.value) })}
              className="w-full accent-blue-500"
            />
          </div>
        </div>
      )}

      {/* Animation Section */}
      {activeSection === 'animation' && (
        <div className="space-y-4">
          {/* Animation type */}
          <div>
            <label className="text-xs font-medium text-gray-500 uppercase tracking-wider block mb-2">Type d'animation</label>
            <div className="grid grid-cols-2 gap-2">
              {ANIMATIONS.map((anim) => (
                <button
                  key={anim.value}
                  onClick={() => onConfigChange({ animation: anim.value })}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    config.animation === anim.value
                      ? 'border-blue-500 bg-blue-500/10'
                      : 'border-white/10 hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xl opacity-60">{anim.icon}</span>
                    <div>
                      <div className="text-sm font-medium">{anim.label}</div>
                      <div className="text-[10px] text-gray-400">{anim.desc}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Duration */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-xs font-medium text-gray-500 uppercase tracking-wider">Durée de l'intro</label>
              <span className="text-xs text-gray-400">{config.duration || 2}s</span>
            </div>
            <input
              type="range"
              min="1"
              max="5"
              step="0.5"
              value={config.duration || 2}
              onChange={(e) => onConfigChange({ duration: Number(e.target.value) })}
              className="w-full accent-blue-500"
            />
            <div className="flex justify-between text-[10px] text-gray-500 mt-1">
              <span>1s</span>
              <span>3s</span>
              <span>5s</span>
            </div>
          </div>

          {/* Preview button */}
          <button
            onClick={playPreview}
            className="w-full py-3 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 rounded-xl text-sm font-medium text-white transition-all flex items-center justify-center gap-2"
          >
            <Play className="w-4 h-4" />
            Prévisualiser l'animation
          </button>
        </div>
      )}

      {/* Status indicator */}
      <div className={`p-3 rounded-xl border transition-all ${
        config.enabled 
          ? 'bg-green-500/5 border-green-500/20' 
          : 'bg-white/5 border-white/10'
      }`}>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${config.enabled ? 'bg-green-400 animate-pulse' : 'bg-gray-500'}`} />
          <span className="text-xs text-gray-400">
            {config.enabled 
              ? `Intro de ${config.duration || 2}s sera ajoutée à l'export`
              : 'Intro désactivée'
            }
          </span>
        </div>
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
