//! Full local synthetic-media acceptance; uses public CALF APIs only.
use crate::{common::*, integration, project};
use anyhow::{ensure, Result};
use serde_json::{json, Value};
use std::{fs, path::Path, process::Command};
pub const CHECKS: [&str; 5] = [
    "current-native-satisfied",
    "exact-candidate-and-profile",
    "media-technical-contract",
    "scene-scope-and-project-cas",
    "approved-scenes-preserved",
];
pub fn run_suite(core: &Path, ffmpeg: &Path, ffprobe: &Path, output: &Path) -> Result<Value> {
    no_links(output)?;
    ensure!(
        output.is_absolute() && !output.exists(),
        "new_verification_folder_required"
    );
    fs::create_dir_all(output)?;
    root(output)?;
    let source = output.join("source-서울-東京.mp4");
    let args = [
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-n",
        "-threads",
        "2",
        "-filter_threads",
        "1",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=320x180:rate=25:duration=3",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=3",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-threads",
        "2",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-t",
        "3",
    ];
    run(
        Command::new(ffmpeg).args(args).arg(&source),
        None,
        25,
        262144,
    )?;
    let source_sha = sha(&source)?;
    let client = Client::new(core, &output.join("records"))?;
    let project = output.join("project");
    project::create(&project, &["scene1".into(), "scene2".into()])?;
    let registration =
        integration::register(&client, &output.join("configuration"), ffmpeg, ffprobe)?;
    let profile = json!({"width":320,"height":180,"fps":25,"startMs":0,"durationMs":1000,"audio":true,"maxBlackMs":100,"maxSilenceMs":100});
    let first = integration::prepare(
        &client,
        &project,
        "scene1",
        &source,
        &registration,
        "first",
        &profile,
        None,
    )?;
    let one = integration::run_scene(&client, &first)?;
    ensure!(
        one["outcome"] == "SATISFIED" && one["verified"] == true,
        "native_check_not_satisfied"
    );
    let selected_one = project::adopt(&client, &project, &first)?;
    let first_version = s(&selected_one["manifest"]["scenes"]["scene1"]).to_owned();
    ensure!(
        integration::prepare(
            &client,
            &project,
            "scene1",
            &source,
            &registration,
            "first",
            &profile,
            None
        )? == first,
        "duplicate_request_changed"
    );
    ensure!(
        integration::run_scene(&client, &first)?["manifest"]["digest"] == one["manifest"]["digest"],
        "duplicate_request_executed"
    );
    let second = integration::prepare(
        &client,
        &project,
        "scene2",
        &source,
        &registration,
        "second",
        &profile,
        None,
    )?;
    let two = integration::run_scene(&client, &second)?;
    ensure!(two["outcome"] == "SATISFIED", "second_check_not_satisfied");
    let adopted = project::adopt(&client, &project, &second)?;
    let other = adopted["selected"]["scene2"].clone();
    let protected_path = Path::new(s(&other["path"]));
    let protected_sha = sha(protected_path)?;
    let mut revised = profile.clone();
    revised["startMs"] = json!(1000);
    let third = integration::prepare(
        &client,
        &project,
        "scene1",
        &source,
        &registration,
        "revision",
        &revised,
        None,
    )?;
    let three = integration::run_scene(&client, &third)?;
    ensure!(
        three["outcome"] == "SATISFIED",
        "revised_check_not_satisfied"
    );
    let latest = project::adopt(&client, &project, &third)?;
    ensure!(
        latest["selected"]["scene2"] == other && sha(protected_path)? == protected_sha,
        "unrelated_approved_scene_changed"
    );
    ensure!(
        latest["manifest"]["scenes"]["scene1"] != first_version,
        "new_candidate_not_separate"
    );
    ensure!(
        project::restore(&project, "scene1", &first_version, "0".repeat(64).as_str()).is_err(),
        "stale_manifest_was_accepted"
    );
    let restored = project::restore(&project, "scene1", &first_version, s(&latest["digest"]))?;
    ensure!(
        restored["selected"]["scene2"] == other
            && restored["manifest"]["scenes"]["scene1"] == first_version,
        "restore_changed_wrong_scene"
    );
    let mut expected = profile.clone();
    expected["width"] = json!(352);
    let negative = integration::prepare(
        &client,
        &project,
        "scene1",
        &source,
        &registration,
        "wrong-spec",
        &profile,
        Some(&expected),
    )?;
    let result = integration::run_scene(&client, &negative)?;
    ensure!(
        result["outcome"] == "VIOLATED"
            && result["verification"]["checks"][0]["outcome"] == "VIOLATED",
        "wrong_media_spec_was_accepted"
    );
    let before = project::inspect(&project)?;
    ensure!(
        project::adopt(&client, &project, &negative).is_err()
            && project::inspect(&project)? == before,
        "invalid_candidate_adopted"
    );
    ensure!(
        integration::prepare(
            &client,
            &project,
            "scene1",
            &source,
            &registration,
            "first",
            &revised,
            None
        )
        .is_err(),
        "conflicting_request_key_accepted"
    );
    ensure!(
        integration::reconcile(&client, &project, "first")? == first,
        "reconcile_changed_request"
    );
    ensure!(
        sha(&source)? == source_sha && sha(protected_path)? == protected_sha,
        "existing_bytes_changed"
    );
    let report = json!({"status":"PASS","implementation":"Rust-native","platform":std::env::consts::OS,"arch":std::env::consts::ARCH,"extensionVersion":env!("CARGO_PKG_VERSION"),"modelCalls":0,"pythonRuntimeRequired":false,"sdkRuntimeRequired":false,"checks":CHECKS.iter().map(|name|json!({"check":name,"passed":true,"tests":1,"skipped":0})).collect::<Vec<_>>(),"additionalChecks":["same request is not resubmitted","wrong output profile remains VIOLATED","stale project selection is refused","restoration selects the retained validated version","source and other approved scene bytes unchanged"]});
    json_new(&output.join("report.json"), &report)?;
    Ok(report)
}
