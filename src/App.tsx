import { useState, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import LogConsole, { LogEntry } from './components/LogConsole';
import ExternalTab from './components/tabs/ExternalTab';
import InternalTab from './components/tabs/InternalTab';
import EncryptPayslipsTab from './components/tabs/EncryptPayslipsTab';
import EmailTab from './components/tabs/EmailTab';
import SettingsTab from './components/tabs/SettingsTab';

function App() {
  const [activeTab, setActiveTab] = useState('external');
  const [logs, setLogs] = useState<LogEntry[]>([
    {
      id: '1',
      timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
      level: 'INFO',
      message: 'Application started',
    },
    {
      id: '2',
      timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
      level: 'INFO',
      message: 'Ready for PDF processing...',
    },
  ]);

  const addLog = useCallback((entry: LogEntry) => {
    setLogs(prev => [...prev, entry]);
  }, []);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  const getTabTitle = () => {
    switch (activeTab) {
      case 'external': return 'Split PDF';
      case 'internal': return 'Run Excel Macro Template';
      case 'encrypt': return 'Encrypt Payslips';
      case 'email': return 'Email Distribution';
      case 'settings': return 'Settings';
      default: return 'EOS Payslip Tool';
    }
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'external':
        return <ExternalTab onLog={addLog} />;
      case 'internal':
        return <InternalTab onLog={addLog} />;
      case 'encrypt':
        return <EncryptPayslipsTab onLog={addLog} />;
      case 'email':
        return <EmailTab onLog={addLog} />;
      case 'settings':
        return <SettingsTab />;
      default:
        return <ExternalTab onLog={addLog} />;
    }
  };

  return (
    <div className="flex h-screen bg-canvas overflow-hidden">
      {/* Sidebar */}
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main Content */}
      <div className="flex-1 ml-sidebar-width flex flex-col min-h-screen">
        {/* Top Bar */}
        <TopBar title={getTabTitle()} />

        {/* Content Area */}
        <main className="flex-1 mt-16 p-gutter overflow-y-auto pb-[240px]">
          {renderContent()}
        </main>

        {/* Log Console */}
        <LogConsole logs={logs} onClear={clearLogs} />
      </div>
    </div>
  );
}

export default App;
