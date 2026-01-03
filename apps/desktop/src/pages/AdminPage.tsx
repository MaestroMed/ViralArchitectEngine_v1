import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Eye, RefreshCw, Cpu, HardDrive, MemoryStick, Activity,
  AlertTriangle, CheckCircle, XCircle, Clock, Trash2,
  Play, Square, RotateCcw, Terminal, Loader2, Zap
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { api } from '@/lib/api';
import { useWebSocketStore, useToastStore } from '@/store';

interface SystemStats {
  cpu: { percent: number };
  memory: { percent: number; usedGb: number; totalGb: number };
  disk: { percent: number; usedGb: number; totalGb: number };
  gpu: { available: boolean; name?: string; memoryUsedGb: number; memoryTotalGb: number; utilization: number };
}

interface ServiceHealth {
  name: string;
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  lastCheck: string;
  message?: string;
  latencyMs: number;
}

interface LogEntry {
  timestamp: string;
  level: string;
  source: string;
  message: string;
  extra?: Record<string, unknown>;
}

interface AutoRecoveryConfig {
  enabled: boolean;
  cycleCount?: number;
}

interface MonitorStatus {
  uptime: number;
  uptimeFormatted: string;
  system: SystemStats;
  services: Record<string, ServiceHealth>;
  jobs: { total: number; stuck: number; items: unknown[] };
  logs: { total: number; errors: number; warnings: number };
  autoRecovery?: AutoRecoveryConfig;
}

export default function AdminPage() {
  const { addToast } = useToastStore();
  const { lastMessage } = useWebSocketStore();
  
  const [status, setStatus] = useState<MonitorStatus | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [logFilter, setLogFilter] = useState<string>('all');
  const logsEndRef = useRef<HTMLDivElement>(null);
  
  const loadStatus = useCallback(async () => {
    try {
      const response = await api.request<{ success: boolean; data: MonitorStatus }>('/monitor/status');
      if (response.success) {
        setStatus(response.data);
      }
    } catch (error) {
      console.error('Failed to load status:', error);
    } finally {
      setLoading(false);
    }
  }, []);
  
  const loadLogs = useCallback(async () => {
    try {
      const level = logFilter === 'all' ? undefined : logFilter;
      const response = await api.request<{ success: boolean; data: LogEntry[] }>(
        `/monitor/logs?limit=200${level ? `&level=${level}` : ''}`
      );
      if (response.success) {
        setLogs(response.data);
      }
    } catch (error) {
      console.error('Failed to load logs:', error);
    }
  }, [logFilter]);
  
  useEffect(() => {
    loadStatus();
    loadLogs();
  }, [loadStatus, loadLogs]);
  
  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadStatus();
      loadLogs();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadStatus, loadLogs]);
  
  // Handle WebSocket updates
  useEffect(() => {
    if (lastMessage?.type === 'MONITOR_STATUS') {
      setStatus(lastMessage.payload as MonitorStatus);
    } else if (lastMessage?.type === 'MONITOR_LOG') {
      setLogs((prev) => [lastMessage.payload as LogEntry, ...prev].slice(0, 200));
    }
  }, [lastMessage]);
  
  // Auto-scroll logs
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);
  
  const handleRecover = async () => {
    try {
      const response = await api.request<{ success: boolean; data: { recovered: number } }>(
        '/monitor/recover',
        { method: 'POST' }
      );
      if (response.success) {
        addToast({
          type: 'success',
          title: 'Recovery',
          message: `${response.data.recovered} job(s) récupéré(s)`,
        });
        loadStatus();
      }
    } catch (error) {
      addToast({ type: 'error', title: 'Erreur', message: 'Échec de la récupération' });
    }
  };
  
  const handleCleanup = async () => {
    try {
      const response = await api.request<{ success: boolean; data: { deleted: number } }>(
        '/monitor/cleanup-jobs?days=7',
        { method: 'POST' }
      );
      if (response.success) {
        addToast({
          type: 'success',
          title: 'Nettoyage',
          message: `${response.data.deleted} ancien(s) job(s) supprimé(s)`,
        });
      }
    } catch (error) {
      addToast({ type: 'error', title: 'Erreur', message: 'Échec du nettoyage' });
    }
  };
  
  const handleToggleAutoRecovery = async () => {
    try {
      const newValue = !status?.autoRecovery?.enabled;
      const response = await api.request<{ success: boolean; data: { enabled: boolean } }>(
        `/monitor/auto-recovery/toggle?enabled=${newValue}`,
        { method: 'POST' }
      );
      if (response.success) {
        addToast({
          type: 'success',
          title: 'Auto-Recovery',
          message: response.data.enabled ? 'Activé' : 'Désactivé',
        });
        loadStatus();
      }
    } catch (error) {
      addToast({ type: 'error', title: 'Erreur', message: 'Échec du toggle' });
    }
  };
  
  const handleForceWorkflowCheck = async () => {
    try {
      const response = await api.request<{ success: boolean; data: Record<string, number> }>(
        '/monitor/force-workflow-check',
        { method: 'POST' }
      );
      if (response.success) {
        const { stuckJobs, stuckProjects, restartedJobs, workflowActions } = response.data;
        const total = stuckJobs + stuckProjects + restartedJobs + workflowActions;
        addToast({
          type: total > 0 ? 'success' : 'info',
          title: 'Workflow Check',
          message: total > 0 
            ? `${stuckJobs} job(s) récupéré(s), ${stuckProjects} projet(s), ${restartedJobs} relancé(s), ${workflowActions} action(s)`
            : 'Aucune action nécessaire',
        });
        loadStatus();
      }
    } catch (error) {
      addToast({ type: 'error', title: 'Erreur', message: 'Échec de la vérification' });
    }
  };
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'text-green-400';
      case 'degraded': return 'text-amber-400';
      case 'unhealthy': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'degraded': return <AlertTriangle className="w-4 h-4 text-amber-400" />;
      case 'unhealthy': return <XCircle className="w-4 h-4 text-red-400" />;
      default: return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };
  
  const getLogColor = (level: string) => {
    switch (level) {
      case 'ERROR':
      case 'CRITICAL': return 'text-red-400 bg-red-500/10';
      case 'WARNING': return 'text-amber-400 bg-amber-500/10';
      case 'INFO': return 'text-blue-400';
      case 'DEBUG': return 'text-gray-500';
      default: return 'text-gray-400';
    }
  };
  
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };
  
  const ProgressBar = ({ value, color = 'blue' }: { value: number; color?: string }) => (
    <div className="h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
      <motion.div
        className={`h-full bg-${color}-500`}
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(100, value)}%` }}
        transition={{ duration: 0.5 }}
        style={{ backgroundColor: color === 'blue' ? '#3b82f6' : color === 'green' ? '#22c55e' : color === 'amber' ? '#f59e0b' : '#ef4444' }}
      />
    </div>
  );
  
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="px-8 py-6 border-b border-[var(--border-color)] bg-[var(--bg-card)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 relative">
              <Eye className="w-6 h-6 text-cyan-400" />
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full animate-pulse" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-[var(--text-primary)]">L'ŒIL</h1>
              <p className="text-sm text-[var(--text-muted)] mt-0.5">
                Monitoring & Administration
                {status && <span className="ml-2 text-green-400">• Uptime: {status.uptimeFormatted}</span>}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 px-3 py-1.5 bg-[var(--bg-secondary)] rounded-lg cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-4 h-4 rounded"
              />
              <span className="text-sm text-[var(--text-secondary)]">Auto-refresh</span>
            </label>
            <Button variant="secondary" size="sm" onClick={() => { loadStatus(); loadLogs(); }}>
              <RefreshCw className="w-4 h-4 mr-1" />
              Refresh
            </Button>
            <Button variant="secondary" size="sm" onClick={handleRecover}>
              <RotateCcw className="w-4 h-4 mr-1" />
              Recover
            </Button>
            <Button variant="secondary" size="sm" onClick={handleCleanup}>
              <Trash2 className="w-4 h-4 mr-1" />
              Cleanup
            </Button>
          </div>
        </div>
      </header>
      
      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-[var(--text-muted)]" />
          </div>
        ) : (
          <div className="grid grid-cols-12 gap-6">
            {/* System Stats */}
            <div className="col-span-8 space-y-4">
              {/* Stats Row */}
              <div className="grid grid-cols-4 gap-4">
                {/* CPU */}
                <Card className="p-4 bg-[var(--bg-card)]">
                  <div className="flex items-center gap-2 mb-2">
                    <Cpu className="w-4 h-4 text-blue-400" />
                    <span className="text-sm font-medium text-[var(--text-secondary)]">CPU</span>
                  </div>
                  <div className="text-2xl font-bold text-[var(--text-primary)]">
                    {status?.system.cpu.percent.toFixed(0)}%
                  </div>
                  <ProgressBar value={status?.system.cpu.percent || 0} />
                </Card>
                
                {/* Memory */}
                <Card className="p-4 bg-[var(--bg-card)]">
                  <div className="flex items-center gap-2 mb-2">
                    <MemoryStick className="w-4 h-4 text-purple-400" />
                    <span className="text-sm font-medium text-[var(--text-secondary)]">RAM</span>
                  </div>
                  <div className="text-2xl font-bold text-[var(--text-primary)]">
                    {status?.system.memory.percent.toFixed(0)}%
                  </div>
                  <div className="text-xs text-[var(--text-muted)] mt-1">
                    {status?.system.memory.usedGb.toFixed(1)} / {status?.system.memory.totalGb.toFixed(0)} GB
                  </div>
                  <ProgressBar value={status?.system.memory.percent || 0} color="purple" />
                </Card>
                
                {/* Disk */}
                <Card className="p-4 bg-[var(--bg-card)]">
                  <div className="flex items-center gap-2 mb-2">
                    <HardDrive className="w-4 h-4 text-amber-400" />
                    <span className="text-sm font-medium text-[var(--text-secondary)]">Disque</span>
                  </div>
                  <div className="text-2xl font-bold text-[var(--text-primary)]">
                    {status?.system.disk.percent.toFixed(0)}%
                  </div>
                  <div className="text-xs text-[var(--text-muted)] mt-1">
                    {status?.system.disk.usedGb.toFixed(0)} / {status?.system.disk.totalGb.toFixed(0)} GB
                  </div>
                  <ProgressBar value={status?.system.disk.percent || 0} color="amber" />
                </Card>
                
                {/* GPU */}
                <Card className="p-4 bg-[var(--bg-card)]">
                  <div className="flex items-center gap-2 mb-2">
                    <Zap className="w-4 h-4 text-green-400" />
                    <span className="text-sm font-medium text-[var(--text-secondary)]">GPU</span>
                  </div>
                  {status?.system.gpu.available ? (
                    <>
                      <div className="text-2xl font-bold text-[var(--text-primary)]">
                        {status.system.gpu.utilization.toFixed(0)}%
                      </div>
                      <div className="text-xs text-[var(--text-muted)] mt-1 truncate" title={status.system.gpu.name}>
                        {status.system.gpu.name?.split(' ').slice(0, 3).join(' ')}
                      </div>
                      <ProgressBar value={status.system.gpu.utilization} color="green" />
                    </>
                  ) : (
                    <div className="text-sm text-[var(--text-muted)]">Non disponible</div>
                  )}
                </Card>
              </div>
              
              {/* Logs */}
              <Card className="bg-[var(--bg-card)] overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-color)]">
                  <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-[var(--text-muted)]" />
                    <span className="font-medium text-[var(--text-primary)]">Logs</span>
                    <span className="text-xs text-[var(--text-muted)]">
                      ({logs.length} entrées)
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {['all', 'ERROR', 'WARNING', 'INFO'].map((level) => (
                      <button
                        key={level}
                        onClick={() => setLogFilter(level)}
                        className={`px-2 py-1 text-xs rounded transition-colors ${
                          logFilter === level
                            ? 'bg-[var(--accent-color)] text-white'
                            : 'text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)]'
                        }`}
                      >
                        {level === 'all' ? 'Tous' : level}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="h-80 overflow-y-auto font-mono text-xs bg-[#0d1117]">
                  {logs.length === 0 ? (
                    <div className="flex items-center justify-center h-full text-[var(--text-muted)]">
                      Aucun log
                    </div>
                  ) : (
                    <div className="p-2 space-y-0.5">
                      {logs.map((log, i) => (
                        <div
                          key={i}
                          className={`flex gap-2 px-2 py-1 rounded ${getLogColor(log.level)}`}
                        >
                          <span className="text-gray-500 shrink-0">{formatTime(log.timestamp)}</span>
                          <span className={`shrink-0 w-14 ${getLogColor(log.level)}`}>[{log.level}]</span>
                          <span className="text-cyan-400 shrink-0">{log.source.split('.').pop()}</span>
                          <span className="text-gray-300 break-all">{log.message}</span>
                        </div>
                      ))}
                      <div ref={logsEndRef} />
                    </div>
                  )}
                </div>
              </Card>
            </div>
            
            {/* Right sidebar */}
            <div className="col-span-4 space-y-4">
              {/* Services Health */}
              <Card className="p-4 bg-[var(--bg-card)]">
                <div className="flex items-center gap-2 mb-4">
                  <Activity className="w-4 h-4 text-[var(--text-muted)]" />
                  <span className="font-medium text-[var(--text-primary)]">Services</span>
                </div>
                <div className="space-y-3">
                  {status?.services && Object.entries(status.services).map(([name, health]) => (
                    <div key={name} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(health.status)}
                        <span className="text-sm text-[var(--text-primary)] capitalize">{name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-[var(--text-muted)]">
                          {health.latencyMs.toFixed(0)}ms
                        </span>
                        <span className={`text-xs font-medium ${getStatusColor(health.status)}`}>
                          {health.status}
                        </span>
                      </div>
                    </div>
                  ))}
                  {(!status?.services || Object.keys(status.services).length === 0) && (
                    <div className="text-sm text-[var(--text-muted)]">Aucun service surveillé</div>
                  )}
                </div>
              </Card>
              
              {/* Jobs Stats */}
              <Card className="p-4 bg-[var(--bg-card)]">
                <div className="flex items-center gap-2 mb-4">
                  <Play className="w-4 h-4 text-[var(--text-muted)]" />
                  <span className="font-medium text-[var(--text-primary)]">Jobs</span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center p-3 bg-[var(--bg-secondary)] rounded-lg">
                    <div className="text-2xl font-bold text-[var(--text-primary)]">
                      {status?.jobs.total || 0}
                    </div>
                    <div className="text-xs text-[var(--text-muted)]">Total</div>
                  </div>
                  <div className="text-center p-3 bg-[var(--bg-secondary)] rounded-lg">
                    <div className={`text-2xl font-bold ${(status?.jobs.stuck || 0) > 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {status?.jobs.stuck || 0}
                    </div>
                    <div className="text-xs text-[var(--text-muted)]">Bloqués</div>
                  </div>
                </div>
                
                {(status?.logs.errors || 0) > 0 && (
                  <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-red-400" />
                      <span className="text-sm text-red-400">
                        {status?.logs.errors} erreur(s) récente(s)
                      </span>
                    </div>
                  </div>
                )}
              </Card>
              
              {/* Auto-Recovery Panel */}
              <Card className="p-4 bg-[var(--bg-card)]">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-amber-400" />
                    <span className="font-medium text-[var(--text-primary)]">Auto-Recovery</span>
                  </div>
                  <button
                    onClick={handleToggleAutoRecovery}
                    className={`relative w-12 h-6 rounded-full transition-colors ${
                      status?.autoRecovery?.enabled 
                        ? 'bg-green-500' 
                        : 'bg-gray-600'
                    }`}
                  >
                    <motion.div
                      className="absolute top-1 w-4 h-4 bg-white rounded-full shadow"
                      animate={{ left: status?.autoRecovery?.enabled ? '1.5rem' : '0.25rem' }}
                      transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                    />
                  </button>
                </div>
                
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between text-[var(--text-muted)]">
                    <span>Statut</span>
                    <span className={status?.autoRecovery?.enabled ? 'text-green-400' : 'text-gray-400'}>
                      {status?.autoRecovery?.enabled ? '✓ Actif' : '○ Inactif'}
                    </span>
                  </div>
                  {status?.autoRecovery?.cycleCount && (
                    <div className="flex items-center justify-between text-[var(--text-muted)]">
                      <span>Cycles</span>
                      <span className="text-[var(--text-secondary)]">{status.autoRecovery.cycleCount}</span>
                    </div>
                  )}
                  <p className="text-xs text-[var(--text-muted)] mt-2 pt-2 border-t border-[var(--border-color)]">
                    Récupère automatiquement les jobs bloqués, relance les jobs échoués, et assure la continuité du workflow.
                  </p>
                </div>
              </Card>
              
              {/* Quick Actions */}
              <Card className="p-4 bg-[var(--bg-card)]">
                <div className="font-medium text-[var(--text-primary)] mb-4">Actions rapides</div>
                <div className="space-y-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    className="w-full justify-start"
                    onClick={handleForceWorkflowCheck}
                  >
                    <Zap className="w-4 h-4 mr-2 text-amber-400" />
                    Force Workflow Check
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="w-full justify-start"
                    onClick={handleRecover}
                  >
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Récupérer jobs bloqués
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="w-full justify-start"
                    onClick={handleCleanup}
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Nettoyer anciens jobs
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => window.location.reload()}
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Recharger l'application
                  </Button>
                </div>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

