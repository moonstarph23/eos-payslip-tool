import { useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';

interface UpdateInfo {
  available: boolean;
  version?: string;
  currentVersion?: string;
  body?: string;
  date?: string;
}

export function useUpdater() {
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo>({ available: false });
  const [checking, setChecking] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Listen for updater events from Rust
  useEffect(() => {
    let unlisten: (() => void) | undefined;

    const setupListener = async () => {
      unlisten = await listen<{
        error: string | null;
        status: string;
      }>('tauri://update-status', (event) => {
        console.log('Update status:', event.payload);
      });
    };

    setupListener();

    return () => {
      if (unlisten) unlisten();
    };
  }, []);

  const checkForUpdates = useCallback(async () => {
    setChecking(true);
    setError(null);
    
    try {
      const result = await invoke<string>('check_update');
      
      // Parse the result to determine if update is available
      if (result.includes('Update available')) {
        // Extract version info from string
        const match = result.match(/(.+) -> (.+)/);
        if (match) {
          setUpdateInfo({
            available: true,
            currentVersion: match[1]?.trim(),
            version: match[2]?.trim(),
          });
        }
      } else {
        setUpdateInfo({ available: false });
      }
      
      return result;
    } catch (err) {
      const errorMsg = typeof err === 'string' ? err : (err instanceof Error ? err.message : String(err));
      setError(errorMsg);
      return errorMsg;
    } finally {
      setChecking(false);
    }
  }, []);

  const installUpdate = useCallback(async () => {
    setInstalling(true);
    setError(null);
    
    try {
      const result = await invoke<string>('install_update');
      return result;
    } catch (err) {
      const errorMsg = typeof err === 'string' ? err : (err instanceof Error ? err.message : String(err));
      setError(errorMsg);
      return errorMsg;
    } finally {
      setInstalling(false);
    }
  }, []);

  // Check on mount (after a delay so app is ready)
  useEffect(() => {
    const timer = setTimeout(() => {
      checkForUpdates();
    }, 5000); // Check after 5 seconds

    return () => clearTimeout(timer);
  }, [checkForUpdates]);

  return {
    updateInfo,
    checking,
    installing,
    error,
    checkForUpdates,
    installUpdate,
  };
}
