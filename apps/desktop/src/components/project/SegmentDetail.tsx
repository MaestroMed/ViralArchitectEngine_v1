import { useState } from 'react';
import { motion } from 'framer-motion';
import { Play, Download, Wand2, Clock, Tag, Lightbulb, Zap } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { ScoreBar, ScoreCircle } from '@/components/ui/ScoreBar';
import { api } from '@/lib/api';
import { formatDuration } from '@/lib/utils';
import { useJobsStore, useToastStore } from '@/store';

interface Segment {
  id: string;
  startTime: number;
  endTime: number;
  duration: number;
  topicLabel?: string;
  hookText?: string;
  transcript?: string;
  score: {
    total: number;
    hookStrength: number;
    payoff: number;
    humourReaction: number;
    tensionSurprise: number;
    clarityAutonomy: number;
    rhythm: number;
    reasons: string[];
    tags: string[];
  };
  coldOpenRecommended?: boolean;
}

interface SegmentDetailProps {
  segment: Segment;
  projectId: string;
  onExport: () => void;
}

export default function SegmentDetail({
  segment,
  projectId,
  onExport,
}: SegmentDetailProps) {
  const { addJob } = useJobsStore();
  const { addToast } = useToastStore();
  const [exporting, setExporting] = useState(false);
  const [variant, setVariant] = useState<'A' | 'B' | 'C'>('A');

  const handleExport = async () => {
    setExporting(true);
    try {
      const response = await api.exportSegment(projectId, {
        segmentId: segment.id,
        variant,
        includeCaptions: true,
        includeCover: true,
        includeMetadata: true,
      });

      if (response.data?.jobId) {
        addJob({
          id: response.data.jobId,
          type: 'export',
          projectId,
          status: 'running',
          progress: 0,
        });

        addToast({
          type: 'info',
          title: 'Export démarré',
          message: 'Le clip est en cours de génération',
        });
      }
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Erreur',
        message: 'Impossible de lancer l\'export',
      });
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-[var(--text-primary)]">
            {segment.topicLabel || 'Segment'}
          </h2>
          <div className="flex items-center gap-4 mt-2 text-sm text-[var(--text-muted)]">
            <span className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {formatDuration(segment.startTime)} - {formatDuration(segment.endTime)}
            </span>
            <span className="flex items-center gap-1">
              <Zap className="w-4 h-4" />
              {formatDuration(segment.duration)}
            </span>
          </div>
        </div>

        <ScoreCircle score={segment.score.total} size="lg" />
      </div>

      {/* Tags */}
      {segment.score.tags.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          {segment.score.tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-1 bg-[var(--bg-tertiary)] text-[var(--text-primary)] rounded text-sm"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      {/* Hook text */}
      {segment.hookText && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-viral-high/10 flex items-center justify-center flex-shrink-0">
                <Lightbulb className="w-4 h-4 text-viral-high" />
              </div>
              <div>
                <h4 className="text-sm font-medium text-[var(--text-primary)]">Hook détecté</h4>
                <p className="text-sm text-[var(--text-muted)] mt-1">
                  "{segment.hookText}"
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Score breakdown */}
      <Card>
        <CardContent className="p-4">
          <h4 className="font-medium text-[var(--text-primary)] mb-4">Analyse du score</h4>
          
          <div className="grid grid-cols-2 gap-4">
            <ScoreBar
              score={segment.score.hookStrength}
              max={25}
              label="Hook"
            />
            <ScoreBar
              score={segment.score.payoff}
              max={20}
              label="Payoff"
            />
            <ScoreBar
              score={segment.score.humourReaction}
              max={15}
              label="Humour"
            />
            <ScoreBar
              score={segment.score.tensionSurprise}
              max={15}
              label="Tension"
            />
            <ScoreBar
              score={segment.score.clarityAutonomy}
              max={15}
              label="Clarté"
            />
            <ScoreBar
              score={segment.score.rhythm}
              max={10}
              label="Rythme"
            />
          </div>

          {/* Reasons */}
          {segment.score.reasons.length > 0 && (
            <div className="mt-4 pt-4 border-t border-[var(--border-color)]">
              <h5 className="text-sm font-medium text-[var(--text-primary)] mb-2">
                Pourquoi ce score ?
              </h5>
              <ul className="space-y-1">
                {segment.score.reasons.map((reason, i) => (
                  <li
                    key={i}
                    className="text-sm text-[var(--text-muted)] flex items-start gap-2"
                  >
                    <span className="text-viral-high">•</span>
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cold open recommendation */}
      {segment.coldOpenRecommended && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 bg-viral-medium/10 border border-viral-medium/20 rounded-xl"
        >
          <div className="flex items-start gap-3">
            <Wand2 className="w-5 h-5 text-viral-medium flex-shrink-0" />
            <div>
              <h4 className="font-medium text-[var(--text-primary)]">
                Cold Open recommandé
              </h4>
              <p className="text-sm text-[var(--text-muted)] mt-1">
                Ce segment a un hook fort qui fonctionnerait bien en ouverture.
                Essayez le variant B pour un cold open automatique.
              </p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Variant selector */}
      <div>
        <h4 className="text-sm font-medium text-[var(--text-primary)] mb-2">Variant</h4>
        <div className="flex gap-2">
          {(['A', 'B', 'C'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setVariant(v)}
              className={`
                w-12 h-12 rounded-lg font-bold transition-all
                ${variant === v
                  ? 'bg-[var(--accent-color)] text-white'
                  : 'bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:bg-[var(--bg-secondary)]'
                }
              `}
            >
              {v}
            </button>
          ))}
        </div>
        <p className="text-xs text-[var(--text-muted)] mt-2">
          {variant === 'A' && 'Layout standard + sous-titres Forge Minimal'}
          {variant === 'B' && 'Cold open + sous-titres Impact Modern'}
          {variant === 'C' && 'Facecam large + sous-titres minimalistes'}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-4 border-t border-[var(--border-color)]">
        <Button onClick={handleExport} loading={exporting} className="flex-1">
          <Download className="w-4 h-4 mr-2" />
          Exporter Variant {variant}
        </Button>
      </div>
    </div>
  );
}




