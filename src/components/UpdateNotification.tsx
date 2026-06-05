import React from 'react';
import { useUpdater } from '../hooks/useUpdater';

const UpdateNotification: React.FC = () => {
  const { updateInfo, checking, installUpdate: startInstall } = useUpdater();

  if (checking) {
    return (
      <div className="fixed top-20 right-8 z-50 bg-surface-card border border-outline-variant rounded-lg shadow-premium p-4 max-w-sm animate-fade-in">
        <div className="flex items-center gap-3">
          <svg className="animate-spin h-5 w-5 text-primary-container" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" fill="currentColor"></path>
          </svg>
          <span className="text-text-primary font-label text-label-md">Checking for updates...</span>
        </div>
      </div>
    );
  }

  if (!updateInfo.available) {
    return null;
  }

  return (
    <div className="fixed top-20 right-8 z-50 bg-surface-card border border-primary-container/30 rounded-lg shadow-premium p-4 max-w-sm animate-slide-up">
      <div className="flex items-start gap-3">
        <div className="p-2 bg-primary-container/10 rounded-lg shrink-0">
          <span className="material-symbols-outlined text-primary-container">system_update</span>
        </div>
        <div className="flex-1">
          <h4 className="font-headline text-headline-sm text-text-primary">Update Available</h4>
          <p className="text-text-secondary text-body-sm mt-1">
            Version {updateInfo.version} is now available. You're currently on {updateInfo.currentVersion}.
          </p>
          <div className="flex gap-2 mt-3">
            <button 
              onClick={startInstall}
              className="px-4 py-2 bg-primary-container text-white rounded-button font-label text-label-md text-sm hover:scale-[1.02] active:translate-y-px transition-all"
            >
              Install Now
            </button>
            <button 
              onClick={() => {}}
              className="px-4 py-2 border border-outline-variant text-text-secondary rounded-button font-label text-label-md text-sm hover:bg-surface-container-low transition-colors"
            >
              Later
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UpdateNotification;
