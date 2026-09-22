use std::path::{Path, PathBuf};
use std::process::Command;

fn resolve_file_path(file_name: &str) -> PathBuf {
    let path = Path::new(file_name);
    if path.exists() {
        return path.to_path_buf();
    }
    // Search current dir, ~/Downloads, ~/Pictures, ~/Documents
    let home = std::env::var("HOME").unwrap_or_else(|_| "/home/rythamo".to_string());
    for dir in &[".", "Downloads", "Pictures", "Documents"] {
        let candidate = if *dir == "." {
            PathBuf::from(file_name)
        } else {
            PathBuf::from(&home).join(dir).join(file_name)
        };
        if candidate.exists() {
            return candidate;
        }
    }
    PathBuf::from(file_name)
}

pub fn convert_file(file_name: &str, target_format: &str) -> String {
    let resolved = resolve_file_path(file_name);
    if !resolved.exists() {
        return format!("Error: File '{}' not found.", file_name);
    }

    let target_fmt = target_format.trim_start_matches('.').to_lowercase();
    let ext = resolved.extension().and_then(|s| s.to_str()).unwrap_or("").to_lowercase();
    let parent = resolved.parent().unwrap_or(Path::new("."));
    let stem = resolved.file_stem().and_then(|s| s.to_str()).unwrap_or("output");
    let out_file = parent.join(format!("{}.{}", stem, target_fmt));

    // Route 1: Documents (DOCX, PPTX, XLSX, ODT -> PDF, TXT)
    if ["docx", "doc", "pptx", "xlsx", "odt", "rtf"].contains(&ext.as_str()) 
        || (target_fmt == "pdf" && !["png", "jpg", "jpeg", "webp"].contains(&ext.as_str())) {
        let status = Command::new("libreoffice")
            .args(&["--headless", "--convert-to", &target_fmt, "--outdir"])
            .arg(parent)
            .arg(&resolved)
            .status();

        match status {
            Ok(s) if s.success() => format!("Converted '{}' to PDF successfully", file_name),
            Ok(_) => "Conversion failed via LibreOffice".to_string(),
            Err(e) => format!("LibreOffice execution error: {}", e),
        }
    }
    // Route 2: Images (PNG, JPG, WEBP, GIF, SVG, BMP, TIFF)
    else if ["png", "jpg", "jpeg", "webp", "gif", "svg", "bmp", "tiff"].contains(&ext.as_str()) 
        || ["png", "jpg", "jpeg", "webp"].contains(&target_fmt.as_str()) {
        let status = Command::new("magick")
            .arg(&resolved)
            .arg(&out_file)
            .status();

        match status {
            Ok(s) if s.success() => format!("Converted '{}' to '{}'", file_name, out_file.display()),
            Ok(_) => "ImageMagick conversion failed".to_string(),
            Err(e) => format!("ImageMagick error: {}", e),
        }
    }
    // Route 3: Audio & Video (MP4, MKV, AVI, MOV, WEBM, MP3, WAV, FLAC)
    else if ["mp4", "mkv", "avi", "mov", "webm", "mp3", "wav", "flac", "ogg", "m4a"].contains(&ext.as_str()) {
        let status = Command::new("ffmpeg")
            .args(&["-y", "-i"])
            .arg(&resolved)
            .arg(&out_file)
            .status();

        match status {
            Ok(s) if s.success() => format!("Converted '{}' to '{}'", file_name, out_file.display()),
            Ok(_) => "FFmpeg conversion failed".to_string(),
            Err(e) => format!("FFmpeg error: {}", e),
        }
    } else {
        format!("Unsupported conversion from .{} to .{}", ext, target_fmt)
    }
}

pub fn download_media(url: &str) -> String {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/home/rythamo".to_string());
    let dl_dir = format!("{}/Downloads", home);

    let status = Command::new("yt-dlp")
        .args(&[
            "-P", &dl_dir,
            "-f", "bv*[height<=1080]+ba/b[height<=1080]",
            "--merge-output-format", "mkv",
            url
        ])
        .status();

    match status {
        Ok(s) if s.success() => format!("Downloaded '{}' to ~/Downloads", url),
        Ok(_) => "Download failed via yt-dlp".to_string(),
        Err(e) => format!("yt-dlp execution error: {}", e),
    }
}

pub fn search_media(query: &str) -> String {
    let prefix = if query.to_lowercase().contains("bilibili") {
        "bilisearch3:"
    } else {
        "ytsearch3:"
    };

    let clean_query = query.replace("bilibili", "");
    let output = Command::new("yt-dlp")
        .args(&[
            "--flat-playlist",
            "--print", "%(title)s | %(duration_string)s | %(webpage_url)s",
            &format!("{}{}", prefix, clean_query.trim())
        ])
        .output();

    match output {
        Ok(out) if out.status.success() => {
            let res = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if res.is_empty() { "No results found.".to_string() } else { res }
        },
        _ => "Search failed.".to_string(),
    }
}
