mod needle;
mod needle_ffi;
mod tools;

use serde::Serialize;

#[derive(Serialize)]
pub struct AskResponse {
    pub tool: Option<String>,
    pub args: serde_json::Value,
    pub confidence: f32,
    pub reasoning: String,
}

#[tauri::command]
fn ask(query: String) -> AskResponse {
    let (calls, confidence, reasoning) = needle::route(&query);

    if let Some(first_call) = calls.into_iter().next() {
        AskResponse {
            tool: Some(first_call.tool),
            args: first_call.args,
            confidence,
            reasoning,
        }
    } else {
        AskResponse {
            tool: None,
            args: serde_json::Value::Object(Default::default()),
            confidence,
            reasoning,
        }
    }
}

#[tauri::command]
fn execute_tool(tool: String, args: serde_json::Value) -> String {
    needle::execute(&tool, &args)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
                .invoke_handler(tauri::generate_handler![ask, execute_tool])
        .run(tauri::generate_context!())
        .expect("error while running ry1 application");
}
