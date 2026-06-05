import React from 'react';
import { appWindow } from '@tauri-apps/api/window';

interface TopBarProps {
  title: string;
}

const TopBar: React.FC<TopBarProps> = ({ title }) => {
  const handleMinimize = async () => {
    await appWindow.minimize();
  };

  const handleMaximize = async () => {
    await appWindow.toggleMaximize();
  };

  const handleClose = async () => {
    await appWindow.close();
  };

  return (
    <header className="fixed top-0 right-0 w-[calc(100%-280px)] h-16 bg-surface border-b border-outline-variant flex justify-between items-center px-gutter z-40">
      <div className="flex items-center gap-4">
        <span className="font-headline text-headline-sm font-bold text-primary">EOS Payslip Tool</span>
        <span className="h-4 w-px bg-outline-variant"></span>
        <span className="text-on-surface-variant font-label text-label-md">{title}</span>
      </div>

      <div className="flex items-center gap-2">
        {/* Window Controls */}
        <div className="flex gap-2">
          <button
            onClick={handleMinimize}
            className="p-2 text-on-surface-variant hover:bg-surface-container-low rounded-full transition-transform active:scale-95"
          >
            <span className="material-symbols-outlined text-[20px]">minimize</span>
          </button>
          <button
            onClick={handleMaximize}
            className="p-2 text-on-surface-variant hover:bg-surface-container-low rounded-full transition-transform active:scale-95"
          >
            <span className="material-symbols-outlined text-[20px]">fullscreen</span>
          </button>
          <button
            onClick={handleClose}
            className="p-2 text-error hover:bg-error-container/20 rounded-full transition-transform active:scale-95"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>
      </div>
    </header>
  );
};

export default TopBar;
