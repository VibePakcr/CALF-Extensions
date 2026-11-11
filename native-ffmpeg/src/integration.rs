use crate::{common::*, project};
use anyhow::{ensure, Result};
use serde_json::{json, Value};
use std::{fs, path::Path};
pub fn register(client: &Client, folder: &Path, ffmpeg: &Path, ffprobe: &Path) -> Result<Value> {
    no_links(folder)?;
    ensure!(
        folder.is_absolute() && !folder.exists(),
        "new_configuration_folder_required"
    );
    let mut tools = json!({"schema":"calf.media.ffmpeg.toolchain.v1"});
    for (key, path) in [("ffmpeg", ffmpeg), ("ffprobe", ffprobe)] {
        let p = regular(&real(path)?, 128 * 1024 * 1024)?;
        tools[key] = json!({"path":p,"sha256":sha(&p)?});
    }
    fs::create_dir_all(folder)?;
    root(folder)?;
    let config = folder.join("toolchain.json");
    json_new(&config, &tools)?;
    toolchain(&config)?;
    let binary = regular(&real(&std::env::current_exe()?)?, 128 * 1024 * 1024)?;
    let identity = digest(&json!({"binary":sha(&binary)?,"toolchain":tools}))?;
    let registration = json!({"schema":"calf.media.ffmpeg.registration.v1","executor":format!("ffmpeg-{}",&identity[..24]),"validator":format!("ffprobe-{}",&identity[..24]),"configuration":config,"implementation":"Rust-native"});
    for (role, mode) in [("executor", "execute"), ("validator", "validate")] {
        let adapter = json!({"schema":1,"id":registration[role],"role":role,"command":[binary,"worker",mode,config],"files":[config,tools["ffmpeg"]["path"],tools["ffprobe"]["path"]],"capabilities":{"asynchronous":false,"query":false,"cancel":false},"class":"light"});
        client.call("register", json!({"adapter":adapter}))?;
    }
    json_new(&folder.join("registration.json"), &registration)?;
    Ok(registration)
}
fn input(path: &Path, id: &str, media: &str) -> Result<Value> {
    let p = regular(path, if id == "source" { MEDIA } else { 65536 })?;
    Ok(json!({"id":id,"path":p,"sha256":sha(&p)?,"mediaType":media}))
}
fn ticket(spec: &Value, result: &Value, plan: &Value, scope: &str, registration: &Value) -> Value {
    json!({"schema":"calf.media.scene-ticket.v1","work":result["work"],"contractDigest":result["contractDigest"],"sceneId":plan["sceneId"],"projectId":plan["projectId"],"baseManifestDigest":plan["baseManifestDigest"],"scopeSha256":scope,"profile":spec["checks"][0]["rule"]["parameters"]["expected"],"executor":registration["executor"],"validator":registration["validator"]})
}
pub fn prepare(
    client: &Client,
    path: &Path,
    scene: &str,
    source: &Path,
    registration: &Value,
    key: &str,
    settings: &Value,
    expected: Option<&Value>,
) -> Result<Value> {
    let root = root(path)?;
    name(scene)?;
    name(key)?;
    let producer = profile(settings)?;
    let checker = profile(expected.unwrap_or(settings))?;
    let source = input(&real(source)?, "source", "video/mp4")?;
    let intent = json!({"sceneId":scene,"source":source,"profile":producer,"expected":checker,"executor":registration["executor"],"validator":registration["validator"]});
    let folder = root.join("requests").join(key);
    let _lock = project::Lock::new(&root)?;
    let current = project::inspect(&root)?;
    ensure!(
        current["manifest"]["scenes"].get(scene).is_some(),
        "unknown_scene"
    );
    if folder.exists() {
        ensure!(
            read_json(&folder.join("intent.json"))? == intent,
            "request_key_conflict"
        );
        ensure!(
            folder.join("ticket.json").exists(),
            "submission_uncertain_reconcile_request"
        );
        return read_json(&folder.join("ticket.json"));
    }
    fs::create_dir(&folder)?;
    json_new(&folder.join("intent.json"), &intent)?;
    let plan = json!({"schema":"calf.media.scene-plan.v1","projectId":current["manifest"]["projectId"],"baseManifestDigest":current["digest"],"sceneId":scene,"sourceSha256":source["sha256"]});
    let plan_file = folder.join("scene-plan.json");
    json_new(&plan_file, &plan)?;
    let scope = sha(&plan_file)?;
    let spec = json!({"schema":"calf.work.v1","key":format!("media-{}-{key}",s(&plan["projectId"])),"title":format!("Scene {scene} / {key}"),"adapter":registration["executor"],"parameters":{"profile":producer},"inputs":[source,input(&plan_file,"scene-plan","application/json")?],"outputs":[{"id":"video","path":"video.mp4","mediaType":"video/mp4","minBytes":1,"maxBytes":MEDIA}],"checks":[{"id":"media-technical","artifact":"video","kind":"adapter","rule":{"adapter":registration["validator"],"parameters":{"expected":checker,"scopeSha256":scope}}}],"budget":{"maxAttempts":1,"timeoutMs":30000,"maxOutputBytes":MEDIA},"adoption":"manual"});
    json_new(&folder.join("spec.json"), &spec)?;
    let result = client.call("submit", json!({"spec":spec}))?;
    let ticket = ticket(&spec, &result, &plan, &scope, registration);
    json_new(&folder.join("ticket.json"), &ticket)?;
    Ok(ticket)
}
pub fn reconcile(client: &Client, path: &Path, key: &str) -> Result<Value> {
    let root = root(path)?;
    name(key)?;
    let _lock = project::Lock::new(&root)?;
    let folder = root.join("requests").join(key);
    if folder.join("ticket.json").exists() {
        return read_json(&folder.join("ticket.json"));
    }
    let spec = read_json(&folder.join("spec.json"))?;
    let plan = read_json(&folder.join("scene-plan.json"))?;
    let list = client.call("list", json!({}))?;
    let matches = list["works"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("work_list"))?
        .iter()
        .filter(|r| r["key"] == spec["key"])
        .collect::<Vec<_>>();
    ensure!(
        matches.len() == 1,
        "submission_not_confirmed_do_not_resubmit"
    );
    let view = client.call("inspect", json!({"work":matches[0]["work"]}))?;
    let registration =
        json!({"executor":spec["adapter"],"validator":spec["checks"][0]["rule"]["adapter"]});
    let ticket = ticket(
        &spec,
        &view,
        &plan,
        &sha(&folder.join("scene-plan.json"))?,
        &registration,
    );
    json_new(&folder.join("ticket.json"), &ticket)?;
    Ok(ticket)
}
pub fn run_scene(client: &Client, ticket: &Value) -> Result<Value> {
    let view = client.call("inspect", json!({"work":ticket["work"]}))?;
    if view["phase"] == "ready" {
        client.call("step", json!({"work":ticket["work"]}))
    } else {
        Ok(view)
    }
}
