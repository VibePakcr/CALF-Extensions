//! Append-only scene candidates and explicit compare-and-swap selection.
use crate::common::*;
use anyhow::{ensure, Result};
use serde_json::{json, Value};
use std::{
    fs,
    io::{Read, Write},
    path::{Path, PathBuf},
};
pub struct Lock {
    folder: PathBuf,
    token: String,
}
impl Lock {
    pub fn new(root: &Path) -> Result<Self> {
        let folder = root.join(".scene-selection-lock");
        fs::create_dir(&folder)
            .map_err(|_| anyhow::anyhow!("scene_selection_busy_or_unreconciled"))?;
        let token = id();
        json_new(
            &folder.join("owner.json"),
            &json!({"token":token,"pid":std::process::id()}),
        )?;
        Ok(Self { folder, token })
    }
}
impl Drop for Lock {
    fn drop(&mut self) {
        if read_json(&self.folder.join("owner.json")).is_ok_and(|v| v["token"] == self.token) {
            let _ = fs::remove_file(self.folder.join("owner.json"));
            let _ = fs::remove_dir(&self.folder);
        }
    }
}
pub fn create(path: &Path, scenes: &[String]) -> Result<Value> {
    no_links(path)?;
    ensure!(
        path.is_absolute()
            && !path.exists()
            && !path
                .components()
                .any(|c| c == std::path::Component::ParentDir),
        "new_project_folder_required"
    );
    ensure!(
        (1..=32).contains(&scenes.len())
            && scenes
                .iter()
                .collect::<std::collections::BTreeSet<_>>()
                .len()
                == scenes.len(),
        "scene_count"
    );
    for scene in scenes {
        name(scene)?;
    }
    fs::create_dir_all(path)?;
    root(path)?;
    for sub in ["versions", "manifests", "requests"] {
        fs::create_dir(path.join(sub))?;
    }
    let value = json!({"schema":"calf.media.project.v1","projectId":id(),"revision":0,"scenes":scenes.iter().map(|s|(s.clone(),Value::Null)).collect::<serde_json::Map<_,_>>()});
    let mut raw = canonical(&value)?;
    raw.push(b'\n');
    let h = format!("{:x}", sha2::Sha256::digest(&raw));
    write_new(&path.join("manifests").join(format!("{h}.json")), &raw)?;
    write_new(&path.join("manifest.json"), &raw)?;
    inspect(path)
}
pub fn manifest(path: &Path) -> Result<(Value, String)> {
    root(path)?;
    let file = path.join("manifest.json");
    let v = read_json(&file)?;
    exact(&v, &["schema", "projectId", "revision", "scenes"])?;
    ensure!(
        v["schema"] == "calf.media.project.v1" && v["revision"].as_u64().is_some(),
        "project_manifest_invalid"
    );
    name(s(&v["projectId"]))?;
    let scenes = v["scenes"]
        .as_object()
        .ok_or_else(|| anyhow::anyhow!("scene_count"))?;
    ensure!((1..=32).contains(&scenes.len()), "scene_count");
    for (scene, version) in scenes {
        name(scene)?;
        ensure!(
            version.is_null() || version.as_str().is_some_and(hex),
            "scene_version_invalid"
        );
    }
    Ok((v, sha(&file)?))
}
pub fn version_path(root: &Path, scene: &str, version: &str) -> Result<PathBuf> {
    name(scene)?;
    ensure!(hex(version), "version_identity");
    let path = root.join("versions").join(scene).join(version);
    no_links(&path)?;
    Ok(path)
}
pub fn validation(view: &Value) -> Result<Value> {
    ensure!(
        view["verified"] == true && view["outcome"] == "SATISFIED" && view["stale"] != true,
        "fresh_satisfied_evidence_required"
    );
    let receipt = &view["verification"];
    let manifest = &view["manifest"];
    ensure!(
        receipt.is_object()
            && manifest.is_object()
            && receipt["contractDigest"] == view["contractDigest"]
            && receipt["requestId"] == view["requestId"]
            && receipt["manifestDigest"] == manifest["digest"]
            && digest(&manifest["artifacts"])? == s(&manifest["digest"]),
        "manifest_receipt_binding"
    );
    let checks = receipt["checks"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("technical_check_required"))?;
    ensure!(
        checks.len() == 1
            && checks[0]["id"] == "media-technical"
            && checks[0]["outcome"] == "SATISFIED"
            && checks[0]["manifestDigest"] == manifest["digest"],
        "technical_check_required"
    );
    let detail = decode(s(&checks[0]["detail"]["reason"]).as_bytes())?;
    ensure!(
        detail["schema"] == "calf.media.ffmpeg.validation.v1"
            && detail["violations"].as_array().is_some_and(Vec::is_empty),
        "media_validation_detail"
    );
    Ok(detail)
}
pub fn read_version(root: &Path, scene: &str, version: &str, project: &str) -> Result<Value> {
    let folder = version_path(root, scene, version)?;
    let info = read_json(&folder.join("version.json"))?;
    let video = regular(&folder.join("video.mp4"), MEDIA)?;
    ensure!(
        info["schema"] == "calf.media.scene-version.v1"
            && info["sceneId"] == scene
            && info["version"] == version
            && info["projectId"] == project,
        "version_record_identity"
    );
    let detail = validation(&info["validatedView"])?;
    let files = info["validatedView"]["manifest"]["artifacts"]["files"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("approved_scene_changed"))?;
    ensure!(
        files.len() == 1
            && files[0]["id"] == "video"
            && sha(&video)? == s(&files[0]["sha256"])
            && fs::metadata(&video)?.len() == files[0]["bytes"].as_u64().unwrap_or(0),
        "approved_scene_changed"
    );
    ensure!(
        detail["sceneId"] == scene
            && detail["projectId"] == info["projectId"]
            && s(&detail["profileSha256"]) == digest(&info["profile"])?,
        "approved_scene_provenance"
    );
    Ok(info)
}
pub fn inspect(path: &Path) -> Result<Value> {
    let root = root(path)?;
    let (m, h) = manifest(&root)?;
    let mut selected = serde_json::Map::new();
    for (scene, version) in m["scenes"].as_object().unwrap() {
        if !version.is_null() {
            let info = read_version(&root, scene, s(version), s(&m["projectId"]))?;
            let artifact = &info["validatedView"]["manifest"]["artifacts"]["files"][0];
            selected.insert(scene.clone(),json!({"version":version,"path":version_path(&root,scene,s(version))?.join("video.mp4"),"sha256":artifact["sha256"],"work":info["validatedView"]["work"]}));
        }
    }
    Ok(json!({"manifest":m,"digest":h,"selected":selected}))
}
fn commit(root: &Path, expected: &str, value: &Value) -> Result<String> {
    ensure!(manifest(root)?.1 == expected, "project_manifest_changed");
    let mut raw = canonical(value)?;
    raw.push(b'\n');
    let h = format!("{:x}", sha2::Sha256::digest(&raw));
    let archived = root.join("manifests").join(format!("{h}.json"));
    if archived.exists() {
        ensure!(fs::read(&archived)? == raw, "manifest_archive_conflict");
    } else {
        write_new(&archived, &raw)?;
    }
    let pending = root.join(format!(".manifest-{}.tmp", id()));
    write_new(&pending, &raw)?;
    if sha(&root.join("manifest.json"))? != expected {
        return Err(anyhow::anyhow!("project_manifest_changed"));
    }
    fs::rename(pending, root.join("manifest.json"))?;
    Ok(h)
}
fn store_version(root: &Path, ticket: &Value, view: &Value, detail: &Value) -> Result<String> {
    let artifact = &view["manifest"]["artifacts"]["files"][0];
    let source = regular(Path::new(s(&detail["artifactPath"])), MEDIA)?;
    ensure!(
        sha(&source)? == s(&artifact["sha256"]) && detail["artifactSha256"] == artifact["sha256"],
        "checked_candidate_changed"
    );
    let version = digest(
        &json!({"work":view["work"],"manifest":view["manifest"]["digest"],"artifact":artifact["sha256"]}),
    )?;
    let folder = version_path(root, s(&ticket["sceneId"]), &version)?;
    fs::create_dir_all(&folder)?;
    no_links(&folder)?;
    let target = folder.join("video.mp4");
    if !target.exists() {
        let mut input = fs::File::open(source)?;
        let mut output = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&target)?;
        let mut buffer = [0; 32768];
        let mut copied = 0;
        loop {
            let size = input.read(&mut buffer)?;
            if size == 0 {
                break;
            }
            copied += size;
            ensure!(copied <= MEDIA as usize, "media_size_limit");
            output.write_all(&buffer[..size])?;
        }
        output.sync_all()?;
        let mut perms = fs::metadata(&target)?.permissions();
        perms.set_readonly(true);
        fs::set_permissions(&target, perms)?;
    }
    ensure!(
        sha(&target)? == s(&artifact["sha256"]),
        "incomplete_scene_copy_retained"
    );
    let proof = view
        .as_object()
        .unwrap()
        .iter()
        .filter(|(k, _)| {
            [
                "work",
                "requestId",
                "verified",
                "outcome",
                "manifest",
                "verification",
                "contractDigest",
                "adopted",
                "adoptedValid",
            ]
            .contains(&k.as_str())
        })
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect::<serde_json::Map<_, _>>();
    let record = json!({"schema":"calf.media.scene-version.v1","projectId":ticket["projectId"],"sceneId":ticket["sceneId"],"version":version,"profile":ticket["profile"],"validatedView":proof,"createdAt":chrono::Utc::now().to_rfc3339()});
    if !folder.join("version.json").exists() {
        json_new(&folder.join("version.json"), &record)?;
    }
    read_version(
        root,
        s(&ticket["sceneId"]),
        &version,
        s(&ticket["projectId"]),
    )?;
    Ok(version)
}
pub fn adopt(client: &Client, path: &Path, ticket: &Value) -> Result<Value> {
    let root = root(path)?;
    let _lock = Lock::new(&root)?;
    let current = inspect(&root)?;
    let m = &current["manifest"];
    ensure!(
        ticket["projectId"] == m["projectId"] && m["scenes"].get(s(&ticket["sceneId"])).is_some(),
        "ticket_project_or_scene_mismatch"
    );
    let mut view = client.call("inspect", json!({"work":ticket["work"]}))?;
    let detail = validation(&view)?;
    ensure!(
        view["contractDigest"] == ticket["contractDigest"]
            && view["verification"]["checks"][0]["detail"]["adapter"] == ticket["validator"],
        "ticket_native_contract_changed"
    );
    for field in ["sceneId", "projectId", "baseManifestDigest", "scopeSha256"] {
        ensure!(
            detail[field] == ticket[field],
            "ticket_scene_scope_mismatch"
        );
    }
    ensure!(
        s(&detail["profileSha256"]) == digest(&ticket["profile"])?,
        "ticket_profile_mismatch"
    );
    let wanted = digest(
        &json!({"work":view["work"],"manifest":view["manifest"]["digest"],"artifact":view["manifest"]["artifacts"]["files"][0]["sha256"]}),
    )?;
    if m["scenes"][s(&ticket["sceneId"])] == wanted {
        return Ok(current);
    }
    ensure!(
        current["digest"] == ticket["baseManifestDigest"],
        "project_changed_reconcile_before_adoption"
    );
    if view["adopted"].is_null() {
        view = client.call(
            "adopt",
            json!({"work":ticket["work"],"digest":view["manifest"]["digest"]}),
        )?;
    }
    ensure!(
        view["adoptedValid"] == true && view["adopted"]["digest"] == view["manifest"]["digest"],
        "native_adoption_not_confirmed"
    );
    let version = store_version(&root, ticket, &view, &detail)?;
    let fresh = client.call("inspect", json!({"work":ticket["work"]}))?;
    validation(&fresh)?;
    ensure!(
        fresh["adoptedValid"] == true && fresh["manifest"]["digest"] == view["manifest"]["digest"],
        "candidate_changed_during_adoption"
    );
    ensure!(
        inspect(&root)?["digest"] == current["digest"],
        "project_changed_during_adoption"
    );
    let mut next = m.clone();
    next["revision"] = json!(m["revision"].as_u64().unwrap() + 1);
    next["scenes"][s(&ticket["sceneId"])] = json!(version);
    commit(&root, s(&current["digest"]), &next)?;
    inspect(&root)
}
pub fn restore(path: &Path, scene: &str, version: &str, expected: &str) -> Result<Value> {
    let root = root(path)?;
    let _lock = Lock::new(&root)?;
    let current = inspect(&root)?;
    ensure!(current["digest"] == expected, "project_manifest_changed");
    ensure!(
        current["manifest"]["scenes"].get(scene).is_some(),
        "unknown_scene"
    );
    read_version(&root, scene, version, s(&current["manifest"]["projectId"]))?;
    let mut next = current["manifest"].clone();
    next["revision"] = json!(next["revision"].as_u64().unwrap() + 1);
    next["scenes"][scene] = json!(version);
    commit(&root, expected, &next)?;
    inspect(&root)
}

use sha2::Digest;
