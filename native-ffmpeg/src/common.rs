//! Native extension protocol helpers. Work execution authority stays in CALF.
use anyhow::{ensure, Result};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Component, Path, PathBuf},
    process::{Command, Stdio},
    time::{Duration, Instant},
};
pub const MEDIA: u64 = 64 * 1024 * 1024;
pub fn s(v: &Value) -> &str {
    v.as_str().unwrap_or("")
}
pub fn canonical(v: &Value) -> Result<Vec<u8>> {
    Ok(serde_json::to_vec(v)?)
}
pub fn digest(v: &Value) -> Result<String> {
    Ok(format!("{:x}", Sha256::digest(canonical(v)?)))
}
pub fn sha(path: &Path) -> Result<String> {
    let mut f = File::open(path)?;
    let mut h = Sha256::new();
    let mut b = [0; 32768];
    loop {
        let n = f.read(&mut b)?;
        if n == 0 {
            break;
        }
        h.update(&b[..n]);
    }
    Ok(format!("{:x}", h.finalize()))
}
pub fn id() -> String {
    uuid::Uuid::new_v4().simple().to_string()
}
pub fn exact(v: &Value, keys: &[&str]) -> Result<()> {
    ensure!(
        v.as_object()
            .is_some_and(|m| m.len() == keys.len() && keys.iter().all(|k| m.contains_key(*k))),
        "invalid_fields"
    );
    Ok(())
}
pub fn hex(v: &str) -> bool {
    v.len() == 64
        && v.bytes()
            .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
}
pub fn name(v: &str) -> Result<()> {
    ensure!(
        !v.is_empty()
            && v.len() <= 64
            && v.bytes()
                .all(|c| c.is_ascii_alphanumeric() || b"_-".contains(&c)),
        "scene_id_invalid"
    );
    let stem = v.to_ascii_uppercase();
    ensure!(
        !["CON", "PRN", "AUX", "NUL"].contains(&stem.as_str())
            && !(stem.len() == 4
                && (stem.starts_with("COM") || stem.starts_with("LPT"))
                && stem.as_bytes()[3].is_ascii_digit()),
        "reserved_portable_name"
    );
    Ok(())
}
pub fn no_links(path: &Path) -> Result<()> {
    for p in path.ancestors() {
        if let Ok(m) = fs::symlink_metadata(p) {
            ensure!(!m.file_type().is_symlink(), "physical_path_required");
            #[cfg(windows)]
            {
                use std::os::windows::fs::MetadataExt;
                ensure!(m.file_attributes() & 0x400 == 0, "reparse_point_refused");
            }
        }
    }
    Ok(())
}
pub fn real(path: &Path) -> Result<PathBuf> {
    let p = fs::canonicalize(path)?;
    #[cfg(windows)]
    {
        let raw = p.to_string_lossy();
        if let Some(v) = raw.strip_prefix(r"\\?\UNC\") {
            return Ok(PathBuf::from(format!(r"\\{v}")));
        }
        if let Some(v) = raw.strip_prefix(r"\\?\") {
            return Ok(PathBuf::from(v));
        }
    }
    Ok(p)
}
pub fn root(path: &Path) -> Result<PathBuf> {
    no_links(path)?;
    ensure!(
        path.is_absolute()
            && !path.components().any(|c| c == Component::ParentDir)
            && path.is_dir()
            && real(path)? == path,
        "physical_project_folder_required"
    );
    Ok(path.into())
}
pub fn regular(path: &Path, max: u64) -> Result<PathBuf> {
    no_links(path)?;
    ensure!(
        path.is_absolute()
            && !path.components().any(|c| c == Component::ParentDir)
            && real(path)? == path,
        "physical_absolute_file_required"
    );
    let m = fs::metadata(path)?;
    ensure!(m.is_file() && m.len() <= max, "file_type_or_size");
    Ok(path.into())
}
pub fn decode(raw: &[u8]) -> Result<Value> {
    use serde::de::{Deserialize, Deserializer, Error, MapAccess, SeqAccess, Visitor};
    struct Data(Value);
    struct Json;
    impl<'de> Deserialize<'de> for Data {
        fn deserialize<D: Deserializer<'de>>(d: D) -> std::result::Result<Self, D::Error> {
            d.deserialize_any(Json)
        }
    }
    impl<'de> Visitor<'de> for Json {
        type Value = Data;
        fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
            f.write_str("bounded JSON with unique keys")
        }
        fn visit_bool<E: Error>(self, v: bool) -> std::result::Result<Data, E> {
            Ok(Data(json!(v)))
        }
        fn visit_i64<E: Error>(self, v: i64) -> std::result::Result<Data, E> {
            Ok(Data(json!(v)))
        }
        fn visit_u64<E: Error>(self, v: u64) -> std::result::Result<Data, E> {
            Ok(Data(json!(v)))
        }
        fn visit_f64<E: Error>(self, v: f64) -> std::result::Result<Data, E> {
            serde_json::Number::from_f64(v)
                .map(|v| Data(Value::Number(v)))
                .ok_or_else(|| E::custom("nonfinite_json"))
        }
        fn visit_str<E: Error>(self, v: &str) -> std::result::Result<Data, E> {
            Ok(Data(json!(v)))
        }
        fn visit_string<E: Error>(self, v: String) -> std::result::Result<Data, E> {
            Ok(Data(json!(v)))
        }
        fn visit_unit<E: Error>(self) -> std::result::Result<Data, E> {
            Ok(Data(Value::Null))
        }
        fn visit_map<A: MapAccess<'de>>(self, mut a: A) -> std::result::Result<Data, A::Error> {
            let mut m = serde_json::Map::new();
            while let Some((k, Data(v))) = a.next_entry::<String, Data>()? {
                if m.insert(k, v).is_some() {
                    return Err(A::Error::custom("duplicate_key"));
                }
                if m.len() > 512 {
                    return Err(A::Error::custom("object_limit"));
                }
            }
            Ok(Data(Value::Object(m)))
        }
        fn visit_seq<A: SeqAccess<'de>>(self, mut a: A) -> std::result::Result<Data, A::Error> {
            let mut v = vec![];
            while let Some(Data(item)) = a.next_element()? {
                v.push(item);
                if v.len() > 4096 {
                    return Err(A::Error::custom("array_limit"));
                }
            }
            Ok(Data(Value::Array(v)))
        }
    }
    Ok(serde_json::from_slice::<Data>(raw)?.0)
}
pub fn read_json(path: &Path) -> Result<Value> {
    regular(path, 65536)?;
    decode(&fs::read(path)?)
}
pub fn write_new(path: &Path, raw: &[u8]) -> Result<()> {
    no_links(path)?;
    let mut opts = OpenOptions::new();
    opts.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        opts.mode(0o600);
    }
    let mut file = opts.open(path)?;
    file.write_all(raw)?;
    file.sync_all()?;
    Ok(())
}
pub fn json_new(path: &Path, value: &Value) -> Result<()> {
    let mut raw = canonical(value)?;
    raw.push(b'\n');
    write_new(path, &raw)
}
pub fn profile(v: &Value) -> Result<Value> {
    exact(
        v,
        &[
            "width",
            "height",
            "fps",
            "startMs",
            "durationMs",
            "audio",
            "maxBlackMs",
            "maxSilenceMs",
        ],
    )?;
    for (field, lo, hi) in [
        ("width", 16, 1280),
        ("height", 16, 720),
        ("startMs", 0, 3600000),
        ("durationMs", 100, 30000),
    ] {
        ensure!(
            v[field].as_u64().is_some_and(|n| n >= lo && n <= hi),
            "profile_range:{field}"
        );
    }
    ensure!(
        v["width"].as_u64().unwrap() % 2 == 0 && v["height"].as_u64().unwrap() % 2 == 0,
        "dimensions_must_be_even"
    );
    let fps = v["fps"].as_u64().unwrap_or(0);
    let duration = v["durationMs"].as_u64().unwrap();
    ensure!(
        [24, 25, 30].contains(&fps) && duration * fps % 1000 == 0,
        "duration_or_fps"
    );
    ensure!(v["audio"].is_boolean(), "audio_boolean_required");
    for field in ["maxBlackMs", "maxSilenceMs"] {
        ensure!(
            v[field].is_null() || v[field].as_u64().is_some_and(|n| n >= 100 && n <= duration),
            "detection_range"
        );
    }
    ensure!(
        v["audio"] == true || v["maxSilenceMs"].is_null(),
        "silence_check_requires_audio"
    );
    Ok(v.clone())
}
pub fn toolchain(path: &Path) -> Result<Value> {
    let v = read_json(path)?;
    exact(&v, &["schema", "ffmpeg", "ffprobe"])?;
    ensure!(
        v["schema"] == "calf.media.ffmpeg.toolchain.v1",
        "toolchain_schema"
    );
    for key in ["ffmpeg", "ffprobe"] {
        exact(&v[key], &["path", "sha256"])?;
        let p = regular(Path::new(s(&v[key]["path"])), 128 * 1024 * 1024)?;
        ensure!(sha(&p)? == s(&v[key]["sha256"]), "tool_identity_changed");
    }
    Ok(v)
}
pub fn candidate(output: &Path, relative: &str, existing: bool) -> Result<PathBuf> {
    let output = root(output)?;
    ensure!(
        !relative.is_empty()
            && !relative.contains(['\\', ':', '\0'])
            && !relative.starts_with('/')
            && relative.split('/').all(|p| !matches!(p, "" | "." | "..")),
        "candidate_path"
    );
    let target = output.join(relative);
    no_links(&target)?;
    if existing {
        return regular(&target, MEDIA);
    }
    ensure!(!target.exists(), "candidate_already_exists");
    fs::create_dir_all(target.parent().unwrap())?;
    ensure!(
        real(target.parent().unwrap())?.starts_with(&output),
        "candidate_parent_escape"
    );
    Ok(target)
}
pub fn scene_scope(request: &Value) -> Result<(PathBuf, Value, String)> {
    let refs = request["inputs"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("source_and_scene_plan_required"))?;
    ensure!(refs.len() == 2, "source_and_scene_plan_required");
    let source = refs
        .iter()
        .find(|r| r["id"] == "source")
        .ok_or_else(|| anyhow::anyhow!("source_required"))?;
    let plan = refs
        .iter()
        .find(|r| r["id"] == "scene-plan")
        .ok_or_else(|| anyhow::anyhow!("scene_plan_required"))?;
    let file = regular(Path::new(s(&source["path"])), MEDIA)?;
    let p = regular(Path::new(s(&plan["path"])), 65536)?;
    ensure!(
        sha(&file)? == s(&source["sha256"]) && sha(&p)? == s(&plan["sha256"]),
        "input_hash_mismatch"
    );
    let data = read_json(&p)?;
    exact(
        &data,
        &[
            "schema",
            "projectId",
            "baseManifestDigest",
            "sceneId",
            "sourceSha256",
        ],
    )?;
    name(s(&data["projectId"]))?;
    name(s(&data["sceneId"]))?;
    ensure!(
        data["schema"] == "calf.media.scene-plan.v1"
            && hex(s(&data["baseManifestDigest"]))
            && data["sourceSha256"] == source["sha256"],
        "scene_plan_identity"
    );
    Ok((file, data, s(&plan["sha256"]).to_owned()))
}

// Children inherit CALF's owned process group/job. This layer never creates a
// detached process, shell, resident worker or authority-granting service.
pub fn run(
    cmd: &mut Command,
    input: Option<&[u8]>,
    seconds: u64,
    out_limit: usize,
) -> Result<(Vec<u8>, String)> {
    cmd.stdin(if input.is_some() {
        Stdio::piped()
    } else {
        Stdio::null()
    })
    .stdout(Stdio::piped())
    .stderr(Stdio::piped());
    let mut child = cmd.spawn()?;
    if let Some(raw) = input {
        if let Err(error) = child.stdin.take().unwrap().write_all(raw) {
            let _ = child.kill();
            let _ = child.wait();
            return Err(error.into());
        }
    }
    let mut out = child.stdout.take().unwrap();
    let mut err = child.stderr.take().unwrap();
    let a = std::thread::spawn(move || {
        let mut raw = vec![];
        out.by_ref()
            .take(out_limit as u64 + 1)
            .read_to_end(&mut raw)
            .map(|_| raw)
    });
    let b = std::thread::spawn(move || {
        let mut raw = vec![];
        err.by_ref().take(65537).read_to_end(&mut raw).map(|_| raw)
    });
    let deadline = Instant::now() + Duration::from_secs(seconds);
    let mut timed_out = false;
    let status = loop {
        if let Some(status) = child.try_wait()? {
            break status;
        }
        if Instant::now() > deadline {
            timed_out = true;
            let _ = child.kill();
            break child.wait()?;
        }
        std::thread::sleep(Duration::from_millis(25));
    };
    let output = a
        .join()
        .map_err(|_| anyhow::anyhow!("tool_reader_failed"))??;
    let errors = b
        .join()
        .map_err(|_| anyhow::anyhow!("tool_reader_failed"))??;
    ensure!(!timed_out, "tool_timeout");
    ensure!(
        output.len() <= out_limit && errors.len() <= 65536,
        "tool_output_limit"
    );
    ensure!(status.success(), "tool_nonzero");
    Ok((output, String::from_utf8_lossy(&errors).into_owned()))
}
pub struct Client {
    pub binary: PathBuf,
    pub home: PathBuf,
    pin: String,
}
impl Client {
    pub fn new(binary: &Path, home: &Path) -> Result<Self> {
        let binary = regular(binary, 128 * 1024 * 1024)?;
        no_links(home)?;
        ensure!(
            home.is_absolute() && !home.components().any(|c| c == Component::ParentDir),
            "records_path_required"
        );
        Ok(Self {
            pin: sha(&binary)?,
            binary,
            home: home.into(),
        })
    }
    pub fn call(&self, action: &str, mut data: Value) -> Result<Value> {
        ensure!(sha(&self.binary)? == self.pin, "core_identity_changed");
        data["op"] = json!("work");
        data["home"] = json!(self.home);
        data["action"] = json!(action);
        let raw = canonical(&data)?;
        ensure!(raw.len() <= 65536, "request_limit");
        let (out, _) = run(
            Command::new(&self.binary).arg("api"),
            Some(&raw),
            120,
            1024 * 1024,
        )?;
        ensure!(sha(&self.binary)? == self.pin, "core_identity_changed");
        let value = decode(&out)?;
        ensure!(value.get("error").is_none(), "native_work_error");
        Ok(value)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn strict_profiles_and_duplicate_keys() {
        let base = json!({"width":320,"height":180,"fps":25,"startMs":0,"durationMs":1000,"audio":true,"maxBlackMs":100,"maxSilenceMs":100});
        assert!(profile(&base).is_ok());
        for (k, v) in [
            ("width", json!(321)),
            ("fps", json!(true)),
            ("durationMs", json!(101)),
            ("maxBlackMs", json!(-1)),
            ("audio", json!("yes")),
        ] {
            let mut p = base.clone();
            p[k] = v;
            assert!(profile(&p).is_err());
        }
        assert!(decode(b"{\"x\":1,\"x\":2}").is_err());
    }
}
