import React, { useState, useEffect, useRef, useCallback } from 'react';
import { LogEntry } from '../LogConsole';
import { openFolderDialog, openFileDialog, openFolder, spawnSidecar } from '../../hooks/useTauri';
import { listen } from '@tauri-apps/api/event';

interface EncryptPayslipsTabProps {
  onLog: (entry: LogEntry) => void;
}

const EncryptPayslipsTab: React.FC<EncryptPayslipsTabProps> = ({ onLog }) => {
  const [pdfFolder, setPdfFolder] = useState('');
  const [payPeriod, setPayPeriod] = useState('');
  const [hrisFile, setHrisFile] = useState('');
  const [removePhrases, setRemovePhrases] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const logCounterRef = useRef(0);
  const makeLogId = useCallback(() => `${Date.now()}-${++logCounterRef.current}`, []);

  // Listen for sidecar real-time logs
  useEffect(() => {
    let unlistenOut: (() => void) | undefined;
    let mounted = true;

    const setup = async () => {
      unlistenOut = await listen<string>('sidecar-stdout', (event) => {
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
    };

    setup();
    return () => { mounted = false; unlistenOut?.(); };
  }, [onLog, makeLogId]);

  const handleBrowseFolder = async () => {
    const result = await openFolderDialog({ title: 'Select PDF Folder' });
    if (result && typeof result === 'string') {
      setPdfFolder(result);
      onLog({ id: makeLogId(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'INFO', message: `Selected PDF folder: ${result}` });
    }
  };

  const handleBrowseHris = async () => {
    const result = await openFileDialog({
      title: 'Select HRIS Excel File',
      filters: [{ name: 'Excel Files', extensions: ['xlsx', 'xls'] }],
    });
    if (result && typeof result === 'string') {
      setHrisFile(result);
      onLog({ id: makeLogId(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'INFO', message: `Selected HRIS file: ${result}` });
    }
  };

  const handleProcess = async () => {
    if (!pdfFolder || !payPeriod || !hrisFile) {
      onLog({ id: makeLogId(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'WARNING', message: 'Please fill in all fields before processing.' });
      return;
    }

    setIsProcessing(true);
    onLog({ id: makeLogId(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'INFO', message: 'Starting individual PDF encryption...' });

    try {
      const args = [
        '--pdf', pdfFolder,
        '--employee-data', hrisFile,
        '--period', payPeriod,
      ];
      if (removePhrases.trim()) {
        args.push('--remove-phrases', removePhrases.trim());
      }
      const result = (await spawnSidecar('process_individual', args)) as Record<string, unknown> | undefined;

      if (result && result.success === false) {
        const errMsg = (result.error as string) || 'Processing failed';
        const err = new Error(errMsg) as Error & { traceback?: string };
        if (result.traceback) {
          err.traceback = result.traceback as string;
        }
        throw err;
      }

      const encrypted = (result?.encrypted as number) || 0;
      const failed = (result?.failed as number) || 0;
      onLog({ id: makeLogId(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'SUCCESS', message: `Complete. ${encrypted} encrypted, ${failed} failed.` });

      // Open the PDF folder
      if (pdfFolder) {
        setTimeout(() => openFolder(pdfFolder), 800);
      }
    } catch (err) {
      let msg = `Encryption failed: ${err}`;
      if (err && typeof err === 'object') {
        const anyErr = err as Record<string, unknown>;
        if (anyErr.traceback) {
          msg += `\nDetails: ${anyErr.traceback}`;
        } else if (anyErr.error) {
          msg += `\nDetails: ${anyErr.error}`;
        }
      }
      onLog({ id: makeLogId(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'ERROR', message: msg });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="animate-slide-up">
      <div className="card max-w-max-content-width mx-auto">
        <div className="mb-8">
          <h2 className="font-headline text-headline-lg text-text-primary">Encrypt Payslips</h2>
          <p className="text-text-secondary mt-1">
            Password-protect individual PDF payslips using employee birthdays from HRIS data.
          </p>
        </div>

        <div className="space-y-6">
          {/* PDF Folder */}
          <div className="space-y-2">
            <label className="block text-label-md font-medium text-text-primary ml-1">PDF Folder</label>
            <div className="flex gap-3">
              <div className="relative flex-1 group">
                <input className="input-readonly pr-10" placeholder="No folder selected" readOnly value={pdfFolder} type="text" />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-text-muted">folder_open</span>
              </div>
              <button onClick={handleBrowseFolder} className="btn-secondary">Browse</button>
            </div>
            <p className="text-body-sm text-text-secondary ml-1">Folder containing individual PDF payslips.</p>
          </div>

          {/* Pay Period */}
          <div className="space-y-2">
            <label className="block text-label-md font-medium text-text-primary ml-1">Pay Period</label>
            <div className="relative flex-1 group">
              <input 
                className="input-field pr-10" 
                placeholder="e.g. June 2025" 
                value={payPeriod}
                onChange={(e) => setPayPeriod(e.target.value)}
                type="text" 
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-text-muted">calendar_month</span>
            </div>
            <p className="text-body-sm text-text-secondary ml-1">The pay period to include in the manifest.</p>
          </div>

          {/* HRIS File */}
          <div className="space-y-2">
            <label className="block text-label-md font-medium text-text-primary ml-1">HRIS File</label>
            <div className="flex gap-3">
              <div className="relative flex-1 group">
                <input className="input-readonly pr-10" placeholder="No file selected" readOnly value={hrisFile} type="text" />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-text-muted">description</span>
              </div>
              <button onClick={handleBrowseHris} className="btn-secondary">Browse</button>
            </div>
            <p className="text-body-sm text-text-secondary ml-1">HRIS Excel file with employee data (must contain columns: First name, Last name, Email (Personal), System ID, Date of birth, Employment status).</p>
          </div>

          {/* Phrases to Remove */}
          <div className="space-y-2">
            <label className="block text-label-md font-medium text-text-primary ml-1">Phrases to Remove from Filenames</label>
            <div className="relative flex-1 group">
              <textarea
                className="input-field w-full h-24 resize-none pr-10"
                placeholder="e.g. AA GMS, Salary, Company Name, May 2026_"
                value={removePhrases}
                onChange={(e) => setRemovePhrases(e.target.value)}
              />
              <span className="absolute right-3 top-3 material-symbols-outlined text-text-muted">edit</span>
            </div>
            <div className="bg-surface-container-low rounded-lg p-3 text-body-sm text-text-secondary ml-1 space-y-1">
              <p className="font-medium text-text-primary flex items-center gap-1">
                <span className="material-symbols-outlined text-[16px]">lightbulb</span>
                How to use
              </p>
              <p>PDF filenames often contain company prefixes or location codes before the employee name. Enter phrases here to strip them before matching with HRIS.</p>
              <p className="mt-1"><strong>Example 1:</strong> If your PDFs are named <code className="bg-surface-bright px-1 rounded">Payslip - AA GMS May 2026_Cristian Bacuta.pdf</code>, enter: <code className="bg-surface-bright px-1 rounded">Payslip - AA GMS May 2026_</code></p>
              <p><strong>Example 2:</strong> If named <code className="bg-surface-bright px-1 rounded">Salary_Romel Aquino_May 2026.pdf</code>, enter: <code className="bg-surface-bright px-1 rounded">Salary_,_May 2026</code></p>
              <p className="text-text-muted">Separate multiple phrases with commas. Matching is case-insensitive.</p>
            </div>
          </div>

          {/* Process Button */}
          <div className="pt-6 border-t border-outline-variant/30 mt-8">
            <button onClick={handleProcess} disabled={isProcessing} className={`w-full btn-primary ${isProcessing ? 'opacity-70 cursor-not-allowed' : ''}`}>
              <span className="material-symbols-outlined">lock</span>
              {isProcessing ? 'Encrypting...' : 'Encrypt Payslips'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EncryptPayslipsTab;