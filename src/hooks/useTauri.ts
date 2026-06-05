import { invoke } from '@tauri-apps/api/tauri';
import { open } from '@tauri-apps/api/dialog';

/**
 * Opens a file dialog for selecting a single file
 */
export async function selectFile(
  title: string,
  filterName: string,
  extensions: string[]
): Promise<string | null> {
  try {
    const result = await invoke<string | null>('select_file', {
      title,
      filterName,
      extensions,
    });
    return result;
  } catch (err) {
    console.error('Error selecting file:', err);
    return null;
  }
}

/**
 * Opens a folder dialog for selecting a directory
 */
export async function selectFolder(title: string): Promise<string | null> {
  try {
    const result = await invoke<string | null>('select_folder', { title });
    return result;
  } catch (err) {
    console.error('Error selecting folder:', err);
    return null;
  }
}

/**
 * Opens a folder in the system's file explorer
 */
export async function openFolder(path: string): Promise<void> {
  try {
    await invoke('open_folder', { path });
  } catch (err) {
    console.error('Error opening folder:', err);
  }
}

/**
 * Gets the current platform (windows, macos, linux)
 */
export async function getPlatform(): Promise<string> {
  try {
    return await invoke<string>('get_platform');
  } catch (err) {
    console.error('Error getting platform:', err);
    return 'unknown';
  }
}

/**
 * Spawns the Python sidecar with a command
 */
export async function spawnSidecar(
  command: string,
  args?: string[]
): Promise<unknown> {
  try {
    const result = await invoke<unknown>('spawn_sidecar', {
      command,
      args,
    });
    return result;
  } catch (err) {
    console.error('Error spawning sidecar:', err);
    throw err;
  }
}

/**
 * Helper to open file dialog using Tauri API directly
 * This is simpler and doesn't require Rust commands
 */
export async function openFileDialog(options?: {
  multiple?: boolean;
  filters?: { name: string; extensions: string[] }[];
  title?: string;
}): Promise<string | string[] | null> {
  try {
    return await open({
      multiple: options?.multiple ?? false,
      filters: options?.filters,
      title: options?.title,
    });
  } catch (err) {
    console.error('Error in file dialog:', err);
    return null;
  }
}

/**
 * Helper to open folder dialog using Tauri API directly
 */
export async function openFolderDialog(options?: {
  title?: string;
}): Promise<string | null> {
  try {
    return await open({
      directory: true,
      title: options?.title,
    }) as string | null;
  } catch (err) {
    console.error('Error in folder dialog:', err);
    return null;
  }
}
