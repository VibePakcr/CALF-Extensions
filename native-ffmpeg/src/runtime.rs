//! CPU-bounded FFmpeg producer and independent ffprobe/full-decode verifier.
use crate::common::*;
use anyhow::{ensure, Result};
use serde_json::{json, Value};
use std::{path::Path, process::Command};
fn tool(path: &str, args: Vec<String>, limit: usize) -> Result<(Vec<u8>, String)> {
    run(Command::new(path).args(args), None, 25, limit)
}
fn strings(items: &[&str]) -> Vec<String> {
    items.iter().map(|s| s.to_string()).collect()
}
fn result(request: &Value, state: &str) -> Value {
    json!({"schema":"calf.runtime.v1","requestId":request["requestId"],"state":state,"providerJobId":null,"usage":null})
}
fn execute(request: &Value, tools: &Value) -> Result<Value> {
    ensure!(request["operation"] == "execute", "execute_only");
    exact(&request["parameters"], &["profile"])?;
    let p = profile(&request["parameters"]["profile"])?;
    let (source, _, _) = scene_scope(request)?;
    let outputs = request["outputs"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("one_mp4_output_required"))?;
    ensure!(
        outputs.len() == 1 && outputs[0]["id"] == "video" && outputs[0]["mediaType"] == "video/mp4",
        "one_mp4_output_required"
    );
    let target = candidate(
        Path::new(s(&request["outputDirectory"])),
        s(&outputs[0]["path"]),
        false,
    )?;
    let width = p["width"].as_u64().unwrap();
    let height = p["height"].as_u64().unwrap();
    let fps = p["fps"].as_u64().unwrap();
    let filters=format!("scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}");
    let mut args = strings(&[
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-n",
        "-threads",
        "2",
        "-filter_threads",
        "1",
        "-filter_complex_threads",
        "1",
        "-protocol_whitelist",
        "file",
        "-format_whitelist",
        "mov",
        "-i",
    ]);
    args.push(source.to_string_lossy().into_owned());
    args.extend(strings(&[
        "-ss",
        &format!("{:.3}", p["startMs"].as_u64().unwrap() as f64 / 1000.0),
        "-t",
        &format!("{:.3}", p["durationMs"].as_u64().unwrap() as f64 / 1000.0),
        "-map",
        "0:v:0",
        "-sn",
        "-dn",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-vf",
        &filters,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-threads",
        "2",
    ]));
    if p["audio"] == true {
        args.extend(strings(&[
            "-map", "0:a:0", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "128k",
        ]));
    } else {
        args.push("-an".into())
    }
    args.extend(strings(&[
        "-movflags",
        "+faststart",
        "-fs",
        "67108864",
        "-f",
        "mp4",
    ]));
    args.push(target.to_string_lossy().into_owned());
    tool(s(&tools["ffmpeg"]["path"]), args, 262144)?;
    Ok(result(request, "succeeded"))
}
fn frame_rate(v: &str, fps: u64) -> bool {
    let mut parts = v.split('/');
    let Some(a) = parts.next().and_then(|n| n.parse::<u64>().ok()) else {
        return false;
    };
    let Some(b) = parts.next().and_then(|n| n.parse::<u64>().ok()) else {
        return false;
    };
    parts.next().is_none() && b > 0 && b.checked_mul(fps) == Some(a)
}
pub fn metadata(data: &Value, p: &Value) -> (Vec<String>, Value) {
    let mut errors = vec![];
    let Some(streams) = data["streams"].as_array() else {
        return (vec!["stream_inventory".into()], json!({}));
    };
    let video = streams
        .iter()
        .filter(|s| s["codec_type"] == "video")
        .collect::<Vec<_>>();
    let audio = streams
        .iter()
        .filter(|s| s["codec_type"] == "audio")
        .collect::<Vec<_>>();
    if video.len() != 1
        || audio.len() != usize::from(p["audio"] == true)
        || streams.len() != video.len() + audio.len()
    {
        return (vec!["stream_inventory".into()], json!({}));
    }
    let v = video[0];
    let fmt = &data["format"];
    let mut actual = json!({"width":v["width"],"height":v["height"],"fps":v["avg_frame_rate"],"frames":v["nb_read_frames"],"audio":!audio.is_empty(),"durationMs":null,"blackMs":null,"silenceMs":null});
    for field in ["width", "height"] {
        if v[field].as_u64().is_none() || v[field] != p[field] {
            errors.push(field.into());
        }
    }
    if v["codec_name"] != "h264" {
        errors.push("video_codec".into())
    }
    if v["pix_fmt"] != "yuv420p" {
        errors.push("pixel_format".into())
    }
    let fps = p["fps"].as_u64().unwrap();
    let duration = p["durationMs"].as_u64().unwrap();
    if !frame_rate(s(&v["avg_frame_rate"]), fps) {
        errors.push("frame_rate".into())
    }
    if s(&v["nb_read_frames"]).parse::<u64>().ok() != Some(duration * fps / 1000) {
        errors.push("frame_count".into())
    }
    for (index, observed) in [&fmt["duration"], &v["duration"]].iter().enumerate() {
        match s(observed).parse::<f64>() {
            Ok(value) if value.is_finite() => {
                let ms = value * 1000.0;
                if (ms - duration as f64).abs() > 50.0 {
                    errors.push("duration".into())
                }
                if index == 0 {
                    actual["durationMs"] = json!((ms * 1000.0).round() / 1000.0);
                }
            }
            _ => errors.push("duration_metadata".into()),
        }
    }
    if !s(&fmt["format_name"]).split(',').any(|v| v == "mp4")
        || !["isom", "iso2", "mp41", "mp42", "avc1"]
            .contains(&s(&fmt["tags"]["major_brand"]).trim())
    {
        errors.push("mp4_container".into())
    }
    if !audio.is_empty() {
        let a = audio[0];
        if a["codec_name"] != "aac" || a["sample_rate"] != "48000" || a["channels"] != 2 {
            errors.push("audio_specification".into())
        }
    }
    errors.sort();
    errors.dedup();
    (errors, actual)
}
fn validate(request: &Value, tools: &Value) -> Result<(String, Value)> {
    ensure!(request["operation"] == "validate", "validate_only");
    let check = &request["extra"]["check"];
    let manifest = &request["extra"]["manifest"];
    exact(&check["rule"]["parameters"], &["expected", "scopeSha256"])?;
    let expected = profile(&check["rule"]["parameters"]["expected"])?;
    let (_, scope, scope_hash) = scene_scope(request)?;
    ensure!(
        scope_hash == s(&check["rule"]["parameters"]["scopeSha256"]),
        "scope_hash_mismatch"
    );
    let artifacts = manifest["artifacts"]["files"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("video_artifact_required"))?;
    ensure!(
        artifacts.len() == 1
            && artifacts[0]["id"] == check["artifact"]
            && artifacts[0]["id"] == "video",
        "video_artifact_required"
    );
    let target = candidate(
        Path::new(s(&request["outputDirectory"])),
        s(&artifacts[0]["path"]),
        true,
    )?;
    ensure!(
        sha(&target)? == s(&artifacts[0]["sha256"]),
        "candidate_version_changed"
    );
    let mut detail = json!({"schema":"calf.media.ffmpeg.validation.v1","scopeSha256":scope_hash,"projectId":scope["projectId"],"sceneId":scope["sceneId"],"baseManifestDigest":scope["baseManifestDigest"],"profileSha256":digest(&expected)?,"artifactPath":target,"artifactSha256":artifacts[0]["sha256"],"checks":[],"measurements":null,"violations":[]});
    let mut args=strings(&["-v","error","-threads","2","-protocol_whitelist","file","-format_whitelist","mov","-count_frames","-show_entries","format=format_name,duration:format_tags=major_brand:stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,nb_read_frames,duration,sample_rate,channels","-of","json"]);
    args.push(target.to_string_lossy().into_owned());
    let raw = match tool(s(&tools["ffprobe"]["path"]), args, 262144) {
        Ok(v) => v.0,
        Err(e) if e.to_string() == "tool_nonzero" => {
            detail["violations"] = json!(["unreadable_media"]);
            return Ok(("VIOLATED".into(), detail));
        }
        Err(e) => return Err(e),
    };
    let data = decode(&raw)?;
    let (failures, actual) = metadata(&data, &expected);
    detail["measurements"] = actual;
    detail["checks"] = json!(["probe_and_frame_count"]);
    if !failures.is_empty() {
        detail["violations"] = json!(failures);
        return Ok(("VIOLATED".into(), detail));
    }
    let mut args = strings(&[
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-v",
        "info",
        "-xerror",
        "-err_detect",
        "explode",
        "-threads",
        "2",
        "-filter_threads",
        "1",
        "-protocol_whitelist",
        "file",
        "-format_whitelist",
        "mov",
        "-i",
    ]);
    args.push(target.to_string_lossy().into_owned());
    args.extend(strings(&["-map", "0:v:0"]));
    if expected["audio"] == true {
        args.extend(strings(&["-map", "0:a:0"]));
    }
    if !expected["maxBlackMs"].is_null() {
        args.extend(strings(&[
            "-vf",
            "blackdetect=d=0.1:pic_th=0.98:pix_th=0.1",
        ]));
    }
    if !expected["maxSilenceMs"].is_null() {
        args.extend(strings(&["-af", "silencedetect=noise=-50dB:d=0.1"]));
    }
    args.extend(strings(&["-threads", "2", "-f", "null", "-"]));
    let log = match tool(s(&tools["ffmpeg"]["path"]), args, 8192) {
        Ok(v) => v.1,
        Err(e) if e.to_string() == "tool_nonzero" => {
            detail["violations"] = json!(["full_decode"]);
            return Ok(("VIOLATED".into(), detail));
        }
        Err(e) => return Err(e),
    };
    detail["checks"]
        .as_array_mut()
        .unwrap()
        .push(json!("full_decode"));
    for (key, token, label) in [
        ("maxBlackMs", "black_duration", "blackMs"),
        ("maxSilenceMs", "silence_duration", "silenceMs"),
    ] {
        if expected[key].is_null() {
            continue;
        }
        let pattern = regex::Regex::new(&format!(r"{token}:\s*([0-9]+(?:\.[0-9]+)?)"))?;
        let mut maximum = 0.0_f64;
        for matched in pattern.captures_iter(&log) {
            let observed = matched[1].parse::<f64>()? * 1000.0;
            ensure!(observed.is_finite(), "invalid_detection_metadata");
            maximum = maximum.max(observed);
        }
        detail["measurements"][label] = json!((maximum * 1000.0).round() / 1000.0);
        detail["checks"].as_array_mut().unwrap().push(json!(label));
        if maximum > expected[key].as_u64().unwrap() as f64 + 1.0 {
            detail["violations"]
                .as_array_mut()
                .unwrap()
                .push(json!(label));
        }
    }
    ensure!(
        sha(&target)? == s(&artifacts[0]["sha256"]),
        "candidate_changed_during_check"
    );
    Ok((
        if detail["violations"].as_array().unwrap().is_empty() {
            "SATISFIED"
        } else {
            "VIOLATED"
        }
        .into(),
        detail,
    ))
}
pub fn worker(operation: &str, configuration: &Path, path: &Path) -> Result<Value> {
    let request = read_json(path)?;
    ensure!(
        request["schema"] == "calf.runtime.v1"
            && request["requestId"].is_string()
            && request["operation"] == operation,
        "unsupported_runtime_request"
    );
    if operation == "execute" {
        return Ok(
            match toolchain(configuration)
                .and_then(|tools| execute(&request, &tools))
                .and_then(|value| {
                    toolchain(configuration)?;
                    Ok(value)
                }) {
                Ok(value) => value,
                Err(e) => {
                    eprintln!(
                        "FFmpeg adapter stopped: {}",
                        e.to_string().chars().take(200).collect::<String>()
                    );
                    result(&request, "failed")
                }
            },
        );
    }
    ensure!(operation == "validate", "unsupported_runtime_operation");
    let (outcome, reason) = match toolchain(configuration)
        .and_then(|tools| validate(&request, &tools))
        .and_then(|value| {
            toolchain(configuration)?;
            Ok(value)
        }) {
        Ok((outcome, detail)) => {
            let raw = String::from_utf8(canonical(&detail)?)?;
            ensure!(raw.len() <= 2048, "validation_detail_limit");
            (outcome, raw)
        }
        Err(e) => (
            "UNKNOWN".into(),
            format!(
                "Media validation unavailable: {}",
                e.to_string().chars().take(300).collect::<String>()
            ),
        ),
    };
    Ok(
        json!({"schema":"calf.runtime.v1","requestId":request["requestId"],"checkId":request["extra"]["check"]["id"],"manifestDigest":request["extra"]["manifest"]["digest"],"outcome":outcome,"reason":reason}),
    )
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fps_ratio_and_missing_metadata_are_never_passed() {
        assert!(frame_rate("25/1", 25));
        for bad in [
            "25/0",
            "24/1",
            "25/1/1",
            "NaN",
            "18446744073709551615/18446744073709551615",
        ] {
            assert!(!frame_rate(bad, 25));
        }
        let p = json!({"width":320,"height":180,"fps":25,"durationMs":1000,"audio":true});
        assert_eq!(metadata(&json!({}), &p).0, vec!["stream_inventory"]);
    }
}
