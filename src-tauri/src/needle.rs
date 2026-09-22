use crate::needle_ffi;
use crate::tools;
use std::sync::Once;

pub struct ToolCall {
    pub tool: String,
    pub args: serde_json::Value,
    pub output: String,
}

static mut LAST_CONFIDENCE: f32 = 0.0;
static mut LAST_REASONING: Option<String> = None;
static INIT: Once = Once::new();

fn ensure_init() {
    INIT.call_once(|| {
        let candidates = [
            "src-tauri/tools.json",
            "tools.json",
            "/home/rythamo/truing stuff/ry1/src-tauri/tools.json",
        ];
        let mut tools_json = "[]".to_string();
        for p in &candidates {
            if let Ok(content) = std::fs::read_to_string(p) {
                tools_json = content;
                break;
            }
        }
        let _ = needle_ffi::init(&tools_json, None);
    });
}

pub fn route(query: &str) -> (Vec<ToolCall>, f32, String) {
    let clean = query.trim();
    if clean.len() < 3 {
        return (vec![], 0.0, "Query too short".to_string());
    }

    ensure_init();
    needle_ffi::reset();

    let Some(v) = needle_ffi::complete(clean, 256) else {
        return (vec![], 0.0, "Model execution failed".to_string());
    };

    let confidence = v.get("confidence").and_then(|c| c.as_f64()).unwrap_or(0.0) as f32;
    let reasoning = v.get("reasoning").and_then(|r| r.as_str()).unwrap_or("").to_string();

    unsafe {
        LAST_CONFIDENCE = confidence;
        LAST_REASONING = Some(reasoning.clone());
    }

    // Check for ungrounded / hallucinated arguments
    if let Some(validation) = v.get("validation") {
        if let Some(ungrounded) = validation.get("ungrounded").and_then(|u| u.as_array()) {
            if !ungrounded.is_empty() {
                return (vec![], confidence, "Command unrecognized (Hallucinated parameters)".to_string());
            }
        }
    }

    let calls = match v.get("function_calls").and_then(|c| c.as_array()) {
        Some(c) if !c.is_empty() => c,
        _ => return (vec![], confidence, "No matching tool found".to_string()),
    };

    let mut tool_calls = Vec::new();
    for call in calls {
        let name = match call.get("name").and_then(|n| n.as_str()) {
            Some(n) => n,
            None => continue,
        };
        let args = call.get("arguments").cloned().unwrap_or(serde_json::Value::Object(Default::default()));

        // Tool-specific structural validation
        if name == "download_media" {
            let url = args.get("url").and_then(|u| u.as_str()).unwrap_or("");
            if !url.contains("http://") && !url.contains("https://") {
                return (vec![], confidence, "Download requires a valid web URL".to_string());
            }
        } else if name == "convert_file" {
            let has_fmt = args.get("target_format").is_some() || args.get("format").is_some();
            if !has_fmt {
                return (vec![], confidence, "Conversion requires a target format".to_string());
            }
        }

        if confidence < 0.05 {
            return (vec![], confidence, "Command unrecognized (Low confidence)".to_string());
        }

        tool_calls.push(ToolCall {
            tool: name.to_string(),
            args,
            output: String::new(),
        });
    }

    (tool_calls, confidence, reasoning)
}

pub fn execute(tool: &str, args: &serde_json::Value) -> String {
    match tool {
        "convert_file" => {
            let file = args.get("file_name")
                .or_else(|| args.get("file_path"))
                .or_else(|| args.get("input_file"))
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let fmt = args.get("target_format")
                .or_else(|| args.get("format"))
                .or_else(|| args.get("output_format"))
                .and_then(|v| v.as_str())
                .unwrap_or("");
            tools::convert_file(file, fmt)
        }
        "download_media" => {
            let url = args.get("url").and_then(|v| v.as_str()).unwrap_or("");
            tools::download_media(url)
        }
        "search_media" => {
            let q = args.get("query").and_then(|v| v.as_str()).unwrap_or("");
            tools::search_media(q)
        }
        _ => format!("Unknown tool: {}", tool),
    }
}
