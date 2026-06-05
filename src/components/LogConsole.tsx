import React, { useRef, useEffect } from 'react';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR' | 'DEBUG';
  message: string;
}

interface LogConsoleProps {
  logs: LogEntry[];
  onClear: () => void;
}

const LogConsole: React.FC<LogConsoleProps> = ({ logs, onClear }) => {
  const [isCollapsed, setIsCollapsed] = React.useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logEndRef.current && !isCollapsed) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isCollapsed]);

  const getLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'SUCCESS': return 'text-success';
      case 'WARNING': return 'text-warning';
      case 'ERROR': return 'text-error';
      case 'DEBUG': return 'text-on-secondary-container';
      default: return 'text-white';
    }
  };

  const validCount = logs.filter(l => l.level === 'SUCCESS').length;
  const warningCount = logs.filter(l => l.level === 'WARNING').length;
  const errorCount = logs.filter(l => l.level === 'ERROR').length;

  return (
    <footer 
      className="fixed bottom-0 right-0 w-[calc(100%-280px)] bg-on-secondary-fixed z-50 transition-all duration-300 ease-in-out"
      style={{ height: isCollapsed ? '40px' : '200px' }}
    >
      {/* Panel Header */}
      <div className="flex items-center justify-between px-6 py-2 bg-[#252542] border-t border-white/5">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary-fixed-dim text-sm">terminal</span>
            <span className="font-label text-label-md text-xs uppercase tracking-widest text-text-muted">Status Log</span>
          </div>
          <div className="h-4 w-px bg-white/10"></div>
          <div className="flex items-center gap-3">
            {validCount > 0 && (
              <span className="flex items-center gap-1 text-[10px] text-success">
                <span className="w-1.5 h-1.5 rounded-full bg-success"></span> {validCount} Valid
              </span>
            )}
            {warningCount > 0 && (
              <span className="flex items-center gap-1 text-[10px] text-warning">
                <span className="w-1.5 h-1.5 rounded-full bg-warning"></span> {warningCount} Warnings
              </span>
            )}
            {errorCount > 0 && (
              <span className="flex items-center gap-1 text-[10px] text-error">
                <span className="w-1.5 h-1.5 rounded-full bg-error"></span> {errorCount} Errors
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={onClear}
            className="p-1 hover:bg-white/10 rounded transition-colors"
          >
            <span className="material-symbols-outlined text-[18px] text-white/40 hover:text-white">delete_sweep</span>
          </button>
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 hover:bg-white/10 rounded transition-colors"
          >
            <span className="material-symbols-outlined text-[18px] text-white/40 hover:text-white transition-transform">
              {isCollapsed ? 'keyboard_arrow_up' : 'keyboard_arrow_down'}
            </span>
          </button>
        </div>
      </div>

      {/* Log Content */}
      {!isCollapsed && (
        <div className="p-4 font-mono text-mono-sm log-scrollbar overflow-y-auto" style={{ height: 'calc(200px - 40px)' }}>
          <div className="space-y-1">
            {logs.length === 0 ? (
              <div className="flex gap-4 opacity-50">
                <span className="text-text-muted shrink-0">[--:--:--]</span>
                <span className="text-on-secondary-container">No logs yet...</span>
              </div>
            ) : (
              logs.map((log) => (
                <div key={log.id} className="flex gap-4 animate-fade-in">
                  <span className="text-text-muted shrink-0">[{log.timestamp}]</span>
                  <span className={`shrink-0 font-bold ${getLevelColor(log.level)}`}>[{log.level}]</span>
                  <span className="text-white">{log.message}</span>
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      )}
    </footer>
  );
};

export default LogConsole;
