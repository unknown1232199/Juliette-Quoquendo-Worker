use serde::{Deserialize, Serialize};
use std::io::{self, BufRead, Write};
use std::path::Path;

#[derive(Deserialize)]
struct Request {
    data_dir: String,
    voice: String,
    text: String,
}

#[derive(Serialize)]
struct Response {
    ok: bool,
    wav_base64: Option<String>,
    error: Option<String>,
}

fn handle(line: &str) -> Response {
    let request: Request = match serde_json::from_str(line) {
        Ok(value) => value,
        Err(error) => return failure(format!("invalid request: {error}")),
    };

    let voice = match quoquendo::Voice::find(Path::new(&request.data_dir), &request.voice) {
        Ok(value) => value,
        Err(error) => return failure(format!("voice load failed: {error}")),
    };

    let speech = match voice.say(&request.text) {
        Ok(value) => value,
        Err(error) => return failure(format!("speech generation failed: {error}")),
    };

    let wav = match quoquendo::export::encode(
        &speech,
        quoquendo::export::Format::Wav,
        None,
    ) {
        Ok(value) => value,
        Err(error) => return failure(format!("WAV encoding failed: {error}")),
    };

    Response {
        ok: true,
        wav_base64: Some(base64::Engine::encode(&base64::engine::general_purpose::STANDARD, wav)),
        error: None,
    }
}

fn failure(message: String) -> Response {
    Response { ok: false, wav_base64: None, error: Some(message) }
}

fn main() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut out = stdout.lock();

    for line in stdin.lock().lines() {
        let response = match line {
            Ok(line) => handle(&line),
            Err(error) => failure(format!("stdin read failed: {error}")),
        };
        let encoded = serde_json::to_string(&response)
            .unwrap_or_else(|_| r#"{"ok":false,"wav_base64":null,"error":"response serialization failed"}"#.to_string());
        if writeln!(out, "{encoded}").is_err() {
            break;
        }
        if out.flush().is_err() {
            break;
        }
    }
}
