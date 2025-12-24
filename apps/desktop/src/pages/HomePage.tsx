import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Plus, Search, FolderOpen, Clock, Film } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { ScoreCircle } from '@/components/ui/ScoreBar';
import { api } from '@/lib/api';
import { formatDuration, formatDate, truncate } from '@/lib/utils';
import { useToastStore, useJobsStore } from '@/store';

interface Project {
  id: string;
  name: string;
  sourceFilename: string;
  duration?: number;
  status: string;
  createdAt: string;
  updatedAt: string;
}

export default function HomePage() {
  const navigate = useNavigate();
  const { addToast } = useToastStore();
  const { addJob } = useJobsStore();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [importing, setImporting] = useState(false);

  const loadProjects = useCallback(async () => {
    try {
      const response = await api.listProjects(1, 50, search || undefined);
      setProjects(response.data?.items || []);
    } catch (error) {
      console.error('Failed to load projects:', error);
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleImport = async () => {
    if (!window.forge) {
      addToast({ type: 'error', title: 'Erreur', message: 'Fonctionnalité non disponible' });
      return;
    }

    setImporting(true);
    try {
      const filePath = await window.forge.openFile();
      if (!filePath) {
        setImporting(false);
        return;
      }

      // Create project
      const fileName = filePath.split(/[\\/]/).pop() || 'Sans titre';
      const projectName = fileName.replace(/\.[^.]+$/, '');

      const createResponse = await api.createProject(projectName, filePath);
      const project = createResponse.data;

      if (!project) {
        throw new Error('Failed to create project');
      }

      addToast({
        type: 'success',
        title: 'Projet créé',
        message: `"${projectName}" a été importé`,
      });

      // Start ingest
      const ingestResponse = await api.ingestProject(project.id);
      
      if (ingestResponse.data?.jobId) {
        addJob({
          id: ingestResponse.data.jobId,
          type: 'ingest',
          projectId: project.id,
          status: 'running',
          progress: 0,
          stage: 'Démarrage...',
        });
      }

      // Navigate to project
      navigate(`/project/${project.id}`);
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Erreur d\'importation',
        message: error instanceof Error ? error.message : 'Erreur inconnue',
      });
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="px-8 py-6 border-b border-[var(--border-color)] bg-[var(--bg-card)]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Projets</h1>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Gérez vos VODs et créez des clips viraux
            </p>
          </div>

          <Button onClick={handleImport} loading={importing}>
            <Plus className="w-4 h-4 mr-2" />
            Importer une vidéo
          </Button>
        </div>

        {/* Search */}
        <div className="mt-4 relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
          <input
            type="text"
            placeholder="Rechercher un projet..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-auto p-8">
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {[...Array(8)].map((_, i) => (
              <div
                key={i}
                className="h-48 bg-[var(--bg-tertiary)] rounded-xl animate-pulse"
              />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <EmptyState onImport={handleImport} importing={importing} />
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
          >
            {projects.map((project, index) => (
              <ProjectCard
                key={project.id}
                project={project}
                index={index}
                onClick={() => navigate(`/project/${project.id}`)}
              />
            ))}
          </motion.div>
        )}
      </div>
    </div>
  );
}

function ProjectCard({
  project,
  index,
  onClick,
}: {
  project: Project;
  index: number;
  onClick: () => void;
}) {
  const statusLabels: Record<string, string> = {
    created: 'Nouveau',
    ingesting: 'Importation...',
    ingested: 'Prêt',
    analyzing: 'Analyse...',
    analyzed: 'Analysé',
    ready: 'Prêt',
    error: 'Erreur',
  };

  const statusColors: Record<string, string> = {
    created: 'bg-gray-500/10 text-gray-400',
    ingesting: 'bg-amber-500/10 text-amber-500',
    ingested: 'bg-blue-500/10 text-blue-400',
    analyzing: 'bg-amber-500/10 text-amber-500',
    analyzed: 'bg-green-500/10 text-green-400',
    ready: 'bg-green-500/10 text-green-400',
    error: 'bg-red-500/10 text-red-400',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
    >
      <Card
        className="cursor-pointer hover:shadow-lg transition-all group bg-[var(--bg-card)] border border-[var(--border-color)]"
        onClick={onClick}
      >
        {/* Thumbnail placeholder */}
        <div className="aspect-video bg-[var(--bg-tertiary)] rounded-t-xl flex items-center justify-center">
          <Film className="w-12 h-12 text-[var(--text-muted)] opacity-30" />
        </div>

        {/* Info */}
        <div className="p-4">
          <h3 className="font-medium text-[var(--text-primary)] group-hover:text-[var(--accent-color)] truncate">
            {project.name}
          </h3>
          
          <p className="text-xs text-[var(--text-muted)] mt-1 truncate">
            {project.sourceFilename}
          </p>

          <div className="flex items-center justify-between mt-3">
            <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
              {project.duration && (
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatDuration(project.duration)}
                </span>
              )}
            </div>

            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${
                statusColors[project.status] || statusColors.created
              }`}
            >
              {statusLabels[project.status] || project.status}
            </span>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

function EmptyState({
  onImport,
  importing,
}: {
  onImport: () => void;
  importing: boolean;
}) {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center max-w-md">
        <div className="w-20 h-20 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center mx-auto mb-6">
          <FolderOpen className="w-10 h-10 text-[var(--text-muted)] opacity-50" />
        </div>
        
        <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
          Aucun projet
        </h2>
        
        <p className="text-[var(--text-muted)] mb-6">
          Importez votre première VOD pour commencer à créer des clips viraux
        </p>

        <Button onClick={onImport} loading={importing} size="lg">
          <Plus className="w-5 h-5 mr-2" />
          Importer une vidéo
        </Button>

        <p className="text-xs text-[var(--text-muted)] mt-4">
          Formats supportés : MP4, MKV, MOV, AVI, WebM
        </p>
      </div>
    </div>
  );
}


