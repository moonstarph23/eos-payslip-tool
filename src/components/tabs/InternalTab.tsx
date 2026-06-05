import React, { useState, useEffect, useRef, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import { LogEntry } from '../LogConsole';
import { openFileDialog, openFolder } from '../../hooks/useTauri';

interface InternalTabProps {
  onLog: (entry: LogEntry) => void;
}

const InternalTab: React.FC<InternalTabProps> = ({ onLog }) => {
  const [templateFile, setTemplateFile] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const logCounterRef = useRef(0);

  const makeLogId = useCallback(() => {
    return `${Date.now()}-${++logCounterRef.current}`;
  }, []);

  // Listen for sidecar stdout events — Strict Mode safe
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    let mounted = true;

    const setup = async () => {
      const cb = await listen<string>('sidecar-stdout', (event) => {
        if (!mounted) return;
        try {
          const parsed = JSON.parse(event.payload);
          if (parsed.type === 'log') {
            onLog({
              id: makeLogId(),
              timestamp: parsed.timestamp || new Date().toLocaleTimeString('en-GB', { hour12: false }),
              level: parsed.level || 'INFO',
              message: parsed.message,
            });
          }
        } catch {
          onLog({
            id: makeLogId(),
            timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
            level: 'INFO',
            message: event.payload,
          });
        }
      });
      if (mounted) {
        unlisten = cb;
      } else {
        cb();
      }
    };

    setup();

    return () => {
      mounted = false;
      unlisten?.();
    };
  }, [onLog, makeLogId]);

  const handleBrowse = async () => {
    const result = await openFileDialog({
      title: 'Select Excel Template',
      filters: [
        { name: 'Excel Macro Files', extensions: ['xlsm'] },
        { name: 'Excel Files', extensions: ['xlsx', 'xls'] },
      ],
    });
    if (result && typeof result === 'string') {
      setTemplateFile(result);
      onLog({
        id: makeLogId(),
        timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        level: 'INFO',
        message: `Selected template: ${result}`,
      });
    }
  };

  const handleGenerate = async () => {
    if (isProcessing) return;
    if (!templateFile) {
      onLog({
        id: makeLogId(),
        timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        level: 'WARNING',
        message: 'Please select an Excel template file first.',
      });
      return;
    }

    setIsProcessing(true);

    try {
      const result = await invoke<Record<string, unknown>>('spawn_sidecar', {
        command: 'process_internal',
        args: ['--template', templateFile],
      });

      if (result && typeof result === 'object') {
        if (result.success) {
          const processed = (result.processed as number) || 0;
          onLog({
            id: makeLogId(),
            timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
            level: 'SUCCESS',
            message: `Complete. Processed: ${processed} payslips.`,
          });

          // Open the folder containing the template (output files saved there)
          const templateFolder = templateFile.substring(0, templateFile.lastIndexOf('\\'));
          if (templateFolder) {
            setTimeout(() => openFolder(templateFolder), 800);
          }
        } else {
          onLog({
            id: makeLogId(),
            timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
            level: 'ERROR',
            message: `Failed: ${result.error || 'Unknown error'}`,
          });
        }
      }
    } catch (err) {
      onLog({
        id: makeLogId(),
        timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        level: 'ERROR',
        message: `Sidecar error: ${err instanceof Error ? err.message : String(err)}`,
      });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="animate-slide-up">
      <div className="max-w-max-content-width mx-auto space-y-gutter">
        <div className="card">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="font-headline text-headline-lg text-text-primary">Run Excel Macro Template</h2>
              <p className="font-body text-body-md text-text-secondary mt-1">Run the VBA macro template to generate payslips and the email manifest.</p>
            </div>
          </div>

          <div className="bg-surface-container-low border border-outline-variant rounded-lg p-4 flex gap-4 mb-element-gap">
            <span className="material-symbols-outlined text-warning">info</span>
            <div>
              <p className="font-label text-label-md text-text-primary">Important</p>
              <p className="font-body text-body-md text-text-secondary">
                Please ensure the 'Data' tab in your Excel template is updated with the current month's payroll information before proceeding.
              </p>
            </div>
          </div>

          <div className="space-y-6">
            <div>
              <label className="block font-label text-label-md text-text-primary mb-2">Excel Template (.xlsm)</label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">description</span>
                  <input
                    className="input-readonly pl-10"
                    readOnly
                    value={templateFile}
                    placeholder="Select Excel template file"
                    type="text"
                  />
                </div>
                <button onClick={handleBrowse} className="btn-secondary">
                  <span className="material-symbols-outlined">folder_open</span>
                  Browse
                </button>
              </div>
            </div>

            <div className="pt-4 space-y-4">
              <button
                onClick={handleGenerate}
                disabled={isProcessing}
                className={`w-full md:w-auto px-12 py-4 bg-primary-container text-on-primary rounded-lg font-headline text-headline-sm hover:scale-[1.02] hover:shadow-lg active:translate-y-[1px] active:scale-100 transition-all shadow-md flex items-center justify-center gap-3 ${isProcessing ? 'opacity-70 cursor-not-allowed' : ''}`}
              >
                <span className="material-symbols-outlined">play_circle</span>
                {isProcessing ? 'Processing...' : 'Generate Payslips'}
              </button>

              {isProcessing && (
                <div className="space-y-2">
                  <div className="flex justify-between items-end">
                    <span className="font-label text-label-md text-primary-container flex items-center gap-2">
                      <svg className="animate-spin h-4 w-4 text-primary-container" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" fill="currentColor"></path>
                      </svg>
                      Running Excel macro...
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InternalTab;
