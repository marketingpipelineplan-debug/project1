#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Child;
use std::sync::Mutex;
use tauri::Manager;

struct LocalWorker(Mutex<Option<Child>>);

fn main() {
    let app = tauri::Builder::default()
        .manage(LocalWorker(Mutex::new(None)))
        .setup(|app| {
            // Development uses scripts/dev.mjs. Release builds require a system
            // Python until the worker is packaged as a per-platform sidecar.
            #[cfg(not(debug_assertions))]
            {
                use std::process::{Command, Stdio};
                let data_dir = app.path().app_data_dir()?;
                std::fs::create_dir_all(&data_dir)?;
                let worker_path = data_dir.join("local_worker.py");
                std::fs::write(&worker_path, include_str!("../../server/app.py"))?;
                std::fs::write(data_dir.join("intelligence.py"), include_str!("../../server/intelligence.py"))?;
                std::fs::write(data_dir.join("public_trends.py"), include_str!("../../server/public_trends.py"))?;
                std::fs::write(data_dir.join("trend_client.py"), include_str!("../../server/trend_client.py"))?;
                std::fs::write(data_dir.join("trend_contract.py"), include_str!("../../server/trend_contract.py"))?;
                std::fs::write(data_dir.join("release_config.json"), include_str!("../../server/release_config.json"))?;
                std::fs::write(data_dir.join("brain.py"), include_str!("../../server/brain.py"))?;
                std::fs::write(data_dir.join("brain_studio.py"), include_str!("../../server/brain_studio.py"))?;
                std::fs::write(data_dir.join("brain_playbook.json"), include_str!("../../server/brain_playbook.json"))?;
                std::fs::write(data_dir.join("vercel_trends.py"), include_str!("../../server/vercel_trends.py"))?;
                let python = if cfg!(target_os = "windows") { "python" } else { "python3" };
                let mut command = Command::new(python);
                command.arg(worker_path)
                    .env("GOODFORM_DB", data_dir.join("goodform.sqlite3"))
                    .stdin(Stdio::null());
                #[cfg(target_os = "windows")]
                {
                    use std::os::windows::process::CommandExt;
                    command.creation_flags(0x08000000);
                }
                let child = command.spawn()?;
                *app.state::<LocalWorker>().0.lock().unwrap() = Some(child);
            }
            #[cfg(debug_assertions)]
            let _ = app;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Could not start Goodform");
    app.run(|app, event| {
        if let tauri::RunEvent::Exit = event {
            if let Some(mut child) = app.state::<LocalWorker>().0.lock().unwrap().take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    });
}
