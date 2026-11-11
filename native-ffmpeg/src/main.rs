//! FFmpeg is a standalone optional extension, never part of CALF's execution authority.
mod common;
mod integration;
mod project;
mod runtime;
mod verify;
use anyhow::{ensure, Result};
use common::*;
use serde_json::{json, Value};
use std::path::Path;
const HELP:&str="CALF FFmpeg — native scene workflow extension
  calf-ffmpeg --version
  calf-ffmpeg --calf CORE --home RECORDS register --configuration NEW_FOLDER --ffmpeg FFMPEG --ffprobe FFPROBE
  calf-ffmpeg init --project NEW_FOLDER --scenes scene1 scene2
  calf-ffmpeg --calf CORE --home RECORDS request --project FOLDER --scene ID --source MP4 --registration FILE --key KEY --profile JSON
  calf-ffmpeg --calf CORE --home RECORDS run --ticket FILE
  calf-ffmpeg --calf CORE --home RECORDS adopt --project FOLDER --ticket FILE
  calf-ffmpeg --calf CORE --home RECORDS reconcile --project FOLDER --key KEY
  calf-ffmpeg inspect --project FOLDER
  calf-ffmpeg restore --project FOLDER --scene ID --version SHA --expected-manifest SHA
  calf-ffmpeg verify --calf CORE --ffmpeg FFMPEG --ffprobe FFPROBE --output NEW_FOLDER
Only this scene's selection can change. Previous versions, records and contracts
are retained. Rendering success is not verification. No model, Python, Node, SDK
runtime or daemon is required; installed FFmpeg/ffprobe and CALF are explicit dependencies.
";
fn arguments(args: &[String]) -> Result<(String, Value)> {
    let mut action = None;
    let mut data = json!({});
    let mut i = 0;
    while i < args.len() {
        let token = &args[i];
        if let Some(key) = token.strip_prefix("--") {
            ensure!(
                !key.is_empty() && data.get(key).is_none(),
                "duplicate_or_invalid_argument"
            );
            i += 1;
            if key == "scenes" {
                let start = i;
                while i < args.len() && !args[i].starts_with("--") {
                    i += 1;
                }
                ensure!(i > start, "scene_count");
                data[key] = json!(args[start..i]);
                continue;
            }
            data[key] = json!(args
                .get(i)
                .ok_or_else(|| anyhow::anyhow!("argument_value_required"))?);
        } else {
            ensure!(action.is_none(), "one_action_required");
            action = Some(token.clone());
        }
        i += 1;
    }
    Ok((
        action.ok_or_else(|| anyhow::anyhow!("action_required"))?,
        data,
    ))
}
fn required<'a>(v: &'a Value, key: &str) -> Result<&'a str> {
    v[key]
        .as_str()
        .ok_or_else(|| anyhow::anyhow!("argument_required:{key}"))
}
fn main_result() -> Result<Value> {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    if args == ["--version"] {
        return Ok(
            json!({"name":"CALF FFmpeg","pack":"calf.media.ffmpeg","version":env!("CARGO_PKG_VERSION"),"engine":"rust","protocol":"calf.runtime.v1","os":std::env::consts::OS,"arch":std::env::consts::ARCH,"pythonRequired":false,"sdkRequired":false}),
        );
    }
    if args.is_empty() || args == ["--help"] || args == ["-h"] {
        return Ok(json!({"usage":HELP}));
    }
    if args.first().is_some_and(|v| v == "worker") {
        ensure!(args.len() == 4, "worker_arguments");
        return runtime::worker(&args[1], Path::new(&args[2]), Path::new(&args[3]));
    }
    let (action, v) = arguments(&args)?;
    let allowed = match action.as_str() {
        "register" => vec!["calf", "home", "configuration", "ffmpeg", "ffprobe"],
        "init" => vec!["project", "scenes"],
        "request" => vec![
            "calf",
            "home",
            "project",
            "scene",
            "source",
            "registration",
            "key",
            "profile",
        ],
        "run" => vec!["calf", "home", "ticket"],
        "adopt" => vec!["calf", "home", "project", "ticket"],
        "reconcile" => vec!["calf", "home", "project", "key"],
        "inspect" => vec!["project"],
        "restore" => vec!["project", "scene", "version", "expected-manifest"],
        "verify" => vec!["calf", "ffmpeg", "ffprobe", "output"],
        _ => anyhow::bail!("unknown_action"),
    };
    exact(&v, &allowed)?;
    if action == "init" {
        let scenes = v["scenes"]
            .as_array()
            .ok_or_else(|| anyhow::anyhow!("scene_count"))?
            .iter()
            .map(|v| required(&json!({"s":v}), "s").map(str::to_owned))
            .collect::<Result<Vec<_>>>()?;
        return project::create(Path::new(required(&v, "project")?), &scenes);
    }
    if action == "inspect" {
        return project::inspect(Path::new(required(&v, "project")?));
    }
    if action == "restore" {
        return project::restore(
            Path::new(required(&v, "project")?),
            required(&v, "scene")?,
            required(&v, "version")?,
            required(&v, "expected-manifest")?,
        );
    }
    if action == "verify" {
        return verify::run_suite(
            Path::new(required(&v, "calf")?),
            Path::new(required(&v, "ffmpeg")?),
            Path::new(required(&v, "ffprobe")?),
            Path::new(required(&v, "output")?),
        );
    }
    let client = Client::new(
        Path::new(required(&v, "calf")?),
        Path::new(required(&v, "home")?),
    )?;
    match action.as_str() {
        "register" => integration::register(
            &client,
            Path::new(required(&v, "configuration")?),
            Path::new(required(&v, "ffmpeg")?),
            Path::new(required(&v, "ffprobe")?),
        ),
        "request" => integration::prepare(
            &client,
            Path::new(required(&v, "project")?),
            required(&v, "scene")?,
            Path::new(required(&v, "source")?),
            &read_json(Path::new(required(&v, "registration")?))?,
            required(&v, "key")?,
            &read_json(Path::new(required(&v, "profile")?))?,
            None,
        ),
        "run" => integration::run_scene(&client, &read_json(Path::new(required(&v, "ticket")?))?),
        "adopt" => project::adopt(
            &client,
            Path::new(required(&v, "project")?),
            &read_json(Path::new(required(&v, "ticket")?))?,
        ),
        "reconcile" => integration::reconcile(
            &client,
            Path::new(required(&v, "project")?),
            required(&v, "key")?,
        ),
        _ => anyhow::bail!("unknown_action"),
    }
}
fn main() {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    let run_action = arguments(&args).is_ok_and(|(action, _)| action == "run");
    match main_result() {
        Ok(value) => {
            let raw = serde_json::to_vec(&value).unwrap();
            if raw.len() > 1024 * 1024 {
                eprintln!("response_size_limit");
                std::process::exit(1)
            }
            println!("{}", String::from_utf8(raw).unwrap());
            if run_action && value["outcome"] != "SATISFIED" {
                std::process::exit(2)
            }
        }
        Err(error) => {
            eprintln!("{}", json!({"error":error.to_string()}));
            std::process::exit(1)
        }
    }
}
