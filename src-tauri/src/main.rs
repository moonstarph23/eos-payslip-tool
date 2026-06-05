// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Command;
use serde::{Deserialize, Serialize};
use tauri::Manager;

#[derive(Serialize, Deserialize, Clone)]
struct Alias {
    email: String,
    display_name: String,
}

#[derive(Serialize, Deserialize, Clone)]
struct EmailAccount {
    email: String,
    app_password: String,
    #[serde(deserialize_with = "deserialize_aliases")]
    aliases: Vec<Alias>,
}

fn deserialize_aliases<'de, D>(deserializer: D) -> Result<Vec<Alias>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    use serde::de::{SeqAccess, Visitor};
    use std::fmt;

    struct AliasesVisitor;
    impl<'de> Visitor<'de> for AliasesVisitor {
        type Value = Vec<Alias>;

        fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
            formatter.write_str("a list of alias strings or alias objects")
        }

        fn visit_seq<A>(self, mut seq: A) -> Result<Self::Value, A::Error>
        where
            A: SeqAccess<'de>,
        {
            let mut aliases = Vec::new();
            while let Some(value) = seq.next_element::<serde_json::Value>()? {
                if let Some(s) = value.as_str() {
                    aliases.push(Alias {
                        email: s.to_string(),
                        display_name: String::new(),
                    });
                } else if let Some(obj) = value.as_object() {
                    aliases.push(Alias {
                        email: obj.get("email").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        display_name: obj.get("display_name").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                    });
                }
            }
            Ok(aliases)
        }
    }

    deserializer.deserialize_seq(AliasesVisitor)
}

#[derive(Serialize, Deserialize)]
struct EmailAccountsData {
    accounts: Vec<EmailAccount>,
}

#[tauri::command]
async fn select_file(title: String, filter_name: String, extensions: Vec<String>) -> Result<Option<String>, String> {
    let file_path = tauri::api::dialog::blocking::FileDialogBuilder::new()
        .set_title(&title)
        .add_filter(&filter_name, &extensions.iter().map(|s| s.as_str()).collect::<Vec<_>>())
        .pick_file();

    Ok(file_path.map(|p| p.to_string_lossy().to_string()))
}

#[tauri::command]
async fn select_files(title: String, filter_name: String, extensions: Vec<String>) -> Result<Option<Vec<String>>, String> {
    let file_paths = tauri::api::dialog::blocking::FileDialogBuilder::new()
        .set_title(&title)
        .add_filter(&filter_name, &extensions.iter().map(|s| s.as_str()).collect::<Vec<_>>())
        .pick_files();

    Ok(file_paths.map(|paths| paths.iter().map(|p| p.to_string_lossy().to_string()).collect()))
}

#[tauri::command]
async fn select_folder(title: String) -> Result<Option<String>, String> {
    let folder_path = tauri::api::dialog::blocking::FileDialogBuilder::new()
        .set_title(&title)
        .pick_folder();

    Ok(folder_path.map(|p| p.to_string_lossy().to_string()))
}

#[tauri::command]
async fn open_folder(path: String) -> Result<(), String> {
    let path = path.trim_end_matches('\\').trim_end_matches('/');

    // Determine if this looks like a file path (has extension after last separator)
    let looks_like_file = {
        let name = std::path::Path::new(&path)
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("");
        name.contains('.') && !name.starts_with('.')
    };

    #[cfg(target_os = "windows")]
    {
        if looks_like_file {
            Command::new("explorer")
                .arg("/select,".to_string() + &path)
                .spawn()
                .map_err(|e| format!("Failed to open folder: {}", e))?;
        } else {
            Command::new("explorer")
                .arg(&path)
                .spawn()
                .map_err(|e| format!("Failed to open folder: {}", e))?;
        }
    }

    #[cfg(target_os = "macos")]
    {
        let p = std::path::Path::new(&path);
        if looks_like_file {
            if let Some(parent) = p.parent() {
                Command::new("open")
                    .arg(parent)
                    .spawn()
                    .map_err(|e| format!("Failed to open folder: {}", e))?;
            }
        } else {
            Command::new("open")
                .arg(&path)
                .spawn()
                .map_err(|e| format!("Failed to open folder: {}", e))?;
        }
    }

    #[cfg(target_os = "linux")]
    {
        let p = std::path::Path::new(&path);
        if looks_like_file {
            if let Some(parent) = p.parent() {
                Command::new("xdg-open")
                    .arg(parent)
                    .spawn()
                    .map_err(|e| format!("Failed to open folder: {}", e))?;
            }
        } else {
            Command::new("xdg-open")
                .arg(&path)
                .spawn()
                .map_err(|e| format!("Failed to open folder: {}", e))?;
        }
    }

    Ok(())
}

#[tauri::command]
fn get_platform() -> String {
    #[cfg(target_os = "windows")]
    return "windows".to_string();

    #[cfg(target_os = "macos")]
    return "macos".to_string();

    #[cfg(target_os = "linux")]
    return "linux".to_string();
}

#[tauri::command]
async fn spawn_sidecar(
    command: String,
    args: Option<serde_json::Value>,
    window: tauri::Window,
) -> Result<serde_json::Value, String> {
    use tauri::api::process::{Command as TauriCommand, CommandEvent};

    let sidecar_command = TauriCommand::new_sidecar("python-sidecar")
        .map_err(|e| format!("Failed to create sidecar command: {}", e))?;

    let mut command_args = vec![command];

    if let Some(args_value) = args {
        if let Some(args_array) = args_value.as_array() {
            for arg in args_array {
                if let Some(arg_str) = arg.as_str() {
                    command_args.push(arg_str.to_string());
                }
            }
        }
    }

    let (mut rx, _child) = sidecar_command
        .args(&command_args)
        .spawn()
        .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

    let mut output = String::new();
    let mut error_output = String::new();

    while let Some(event) = rx.recv().await {
        match event {
            CommandEvent::Stdout(line) => {
                output.push_str(&line);
                output.push('\n');
                let _ = window.emit("sidecar-stdout", &line);
            }
            CommandEvent::Stderr(line) => {
                error_output.push_str(&line);
                error_output.push('\n');
                let _ = window.emit("sidecar-stderr", &line);
            }
            CommandEvent::Error(err) => {
                return Err(format!("Sidecar error: {}", err));
            }
            CommandEvent::Terminated(payload) => {
                if payload.code != Some(0) {
                    return Err(format!(
                        "Sidecar exited with code: {:?}. Stderr: {}",
                        payload.code, error_output
                    ));
                }
                break;
            }
            _ => {}
        }
    }

    // Parse the last valid JSON line as the result (sidecar emits logs + final result)
    let result_json = output.lines()
        .rev()
        .filter_map(|line| {
            let line = line.trim();
            if line.is_empty() { return None; }
            serde_json::from_str::<serde_json::Value>(line).ok()
        })
        .next();

    match result_json {
        Some(json) => {
            // If it's a wrapped result {"type": "result", "data": {...}}, unwrap it
            if let Some(data) = json.get("data") {
                Ok(data.clone())
            } else {
                Ok(json)
            }
        }
        None => Ok(serde_json::json!({
            "success": false,
            "error": "No valid JSON result from sidecar",
            "raw_output": output,
            "stderr": error_output
        })),
    }
}

#[tauri::command]
async fn get_email_accounts(app_handle: tauri::AppHandle) -> Result<Vec<EmailAccount>, String> {
    let config_dir = app_handle.path_resolver().app_config_dir()
        .ok_or("Failed to get config directory")?;
    let accounts_file = config_dir.join("email_accounts.json");
    
    if !accounts_file.exists() {
        return Ok(Vec::new());
    }
    
    let content = std::fs::read_to_string(&accounts_file)
        .map_err(|e| format!("Failed to read accounts file: {}", e))?;
    
    let data: EmailAccountsData = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse accounts: {}", e))?;
    
    Ok(data.accounts)
}

#[tauri::command]
async fn save_email_accounts(app_handle: tauri::AppHandle, accounts: Vec<EmailAccount>) -> Result<(), String> {
    let config_dir = app_handle.path_resolver().app_config_dir()
        .ok_or("Failed to get config directory")?;
    
    if !config_dir.exists() {
        std::fs::create_dir_all(&config_dir)
            .map_err(|e| format!("Failed to create config directory: {}", e))?;
    }
    
    let accounts_file = config_dir.join("email_accounts.json");
    let data = EmailAccountsData { accounts };
    let content = serde_json::to_string_pretty(&data)
        .map_err(|e| format!("Failed to serialize accounts: {}", e))?;
    
    std::fs::write(&accounts_file, content)
        .map_err(|e| format!("Failed to write accounts file: {}", e))?;
    
    Ok(())
}

#[tauri::command]
async fn check_update(app_handle: tauri::AppHandle) -> Result<String, String> {
    match app_handle.updater().check().await {
        Ok(update) => {
            if update.is_update_available() {
                Ok(format!("Update available: {} -> {}", update.current_version(), update.latest_version()))
            } else {
                Ok("No updates available. You're on the latest version!".to_string())
            }
        }
        Err(e) => Err(format!("Failed to check for updates: {}", e)),
    }
}

#[tauri::command]
async fn install_update(app_handle: tauri::AppHandle) -> Result<String, String> {
    match app_handle.updater().check().await {
        Ok(update) => {
            if update.is_update_available() {
                match update.download_and_install().await {
                    Ok(_) => Ok("Update installed successfully. Restart the app to apply.".to_string()),
                    Err(e) => Err(format!("Failed to install update: {}", e)),
                }
            } else {
                Ok("No updates available.".to_string())
            }
        }
        Err(e) => Err(format!("Failed to check for updates: {}", e)),
    }
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            #[cfg(debug_assertions)]
            {
                let window = app.get_window("main").unwrap();
                window.open_devtools();
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            select_file,
            select_files,
            select_folder,
            open_folder,
            get_platform,
            spawn_sidecar,
            get_email_accounts,
            save_email_accounts,
            check_update,
            install_update
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
