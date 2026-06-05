import React, { useState, useEffect, useRef, useCallback } from 'react';
import { LogEntry } from '../LogConsole';
import { openFileDialog, openFolderDialog, openFolder, spawnSidecar } from '../../hooks/useTauri';
import { listen } from '@tauri-apps/api/event';

interface ExternalTabProps {
  onLog: (entry: LogEntry) => void;
}

const ExternalTab: React.FC<ExternalTabProps> = ({ onLog }) => {
  const [pdfFile, setPdfFile] = useState('');
  const [employeeData, setEmployeeData] = useState('');
  const [outputFolder, setOutputFolder] = useState('');
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

  const handleBrowsePdf = async () => {
    const result = await openFileDialog({
      title: 'Select PDF file',
      filters: [{ name: 'PDF Files', extensions: ['pdf'] }],
    });
    if (result && typeof result === 'string') {
      setPdfFile(result);
      onLog({ id: Date.now().toString(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'INFO', message: `Selected PDF: ${result}` });
    }
  };

  const handleBrowseExcel = async () => {
    const result = await openFileDialog({
      title: 'Select Employee Data',
      filters: [{ name: 'Excel Files', extensions: ['xlsx', 'xls'] }],
    });
    if (result && typeof result === 'string') {
      setEmployeeData(result);
      onLog({ id: Date.now().toString(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'INFO', message: `Selected employee data: ${result}` });
    }
  };

  const handleBrowseFolder = async () => {
    const result = await openFolderDialog({ title: 'Select Output Folder' });
    if (result && typeof result === 'string') {
      setOutputFolder(result);
      onLog({ id: Date.now().toString(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'INFO', message: `Selected output folder: ${result}` });
    }
  };

  const handleGenerate = async () => {
    if (isProcessing) return;
    if (!pdfFile || !employeeData || !outputFolder) {
      onLog({ id: Date.now().toString(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'WARNING', message: 'Please fill in all required fields before processing.' });
      return;
    }

    setIsProcessing(true);
    onLog({ id: Date.now().toString(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'INFO', message: 'Starting external payslip processing...' });

    try {
      const result = (await spawnSidecar('process_external', [
        '--pdf', pdfFile,
        '--employee-data', employeeData,
        '--output-folder', outputFolder,
      ])) as Record<string, unknown> | undefined;

      if (result && result.success === false) {
        throw new Error((result.error as string) || 'Processing failed');
      }

      const processed = (result?.processed as number) || 0;
      const errors = (result?.errors as number) || 0;
      onLog({ id: Date.now().toString(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'SUCCESS', message: `Complete. ${processed} processed, ${errors} errors.` });

      if (outputFolder) {
        setTimeout(() => openFolder(outputFolder), 800);
      }
    } catch (err) {
      onLog({ id: Date.now().toString(), timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }), level: 'ERROR', message: `External processing failed: ${err}` });
    } finally {
      setIsProcessing(false);
    }
  };

  const getFileIcon = (type: string) => {
    if (type === 'pdf') return 'picture_as_pdf';
    if (type === 'excel') return 'table_chart';
    return 'folder_open';
  };

  return (
    <div className="animate-slide-up">
      <div className="card max-w-max-content-width mx-auto">
        <div className="mb-8">
          <h2 className="font-headline text-headline-lg text-text-primary">Split PDF</h2>
          <p className="text-text-secondary mt-1">Split a combined PDF payslip into individual encrypted files per employee.</p>
        </div>

        <div className="space-y-6">
          <div className="space-y-2">
            <label className="block text-label-md font-medium text-text-primary ml-1">PDF File</label>
            <div className="flex gap-3">
              <div className="relative flex-1 group">
                <input className="input-readonly pr-10" placeholder="No file selected" readOnly value={pdfFile} type="text" />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-text-muted">{getFileIcon('pdf')}</span>
              </div>
              <button onClick={handleBrowsePdf} className="btn-secondary">Browse</button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="block text-label-md font-medium text-text-primary ml-1">Employee Data</label>
            <div className="flex gap-3">
              <div className="relative flex-1 group">
                <input className="input-readonly pr-10" placeholder="Select employee data source (.csv, .xlsx)" readOnly value={employeeData} type="text" />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-text-muted">{getFileIcon('excel')}</span>
              </div>
              <button onClick={handleBrowseExcel} className="btn-secondary">Browse</button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="block text-label-md font-medium text-text-primary ml-1">Output Folder</label>
            <div className="flex gap-3">
              <div className="relative flex-1 group">
                <input className="input-readonly pr-10" placeholder="Select output folder" readOnly value={outputFolder} type="text" />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-text-muted">{getFileIcon('folder')}</span>
              </div>
              <button onClick={handleBrowseFolder} className="btn-secondary">Browse</button>
            </div>
          </div>

          <div className="pt-6 border-t border-outline-variant/30 mt-8">
            <button onClick={handleGenerate} disabled={isProcessing} className={`w-full btn-primary ${isProcessing ? 'opacity-70 cursor-not-allowed' : ''}`}>
              <span className="material-symbols-outlined">auto_mode</span>
              Generate Payslips
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExternalTab;
